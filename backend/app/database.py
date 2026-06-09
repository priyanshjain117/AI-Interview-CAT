import hashlib
import logging
import os
from datetime import datetime
from typing import Any

import httpx
from fastapi import HTTPException
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_log,
)

logger = logging.getLogger(__name__)

from app.models import (
    CandidateProfile,
    DimensionScore,
    FollowUpCoachingItem,
    InterviewHistoryItem,
    InterviewMemory,
    InterviewReport,
    InterviewStatus,
    ProgressAnalysis,
    ProgressDashboardResponse,
    ProgressPoint,
    ResumeRecord,
    TopicState,
    TranscriptEvidence,
    TranscriptTurn,
)

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover
    Client = None  # type: ignore[assignment]
    create_client = None  # type: ignore[assignment]


def _make_http_client() -> httpx.Client:
    """Return an httpx.Client with HTTP/2 disabled.

    Rationale: Render's edge negotiates HTTP/2 and sends GOAWAY / RST_STREAM
    frames when idle streams expire. httpx then tries to reuse the dead
    connection, causing RemoteProtocolError: ConnectionTerminated error_code:1.
    Forcing HTTP/1.1 eliminates the entire H2 code-path and is more than fast
    enough for PostgREST query volumes.
    """
    return httpx.Client(http2=False)


# Retry decorator for transient Supabase transport errors.
# Retries on httpx protocol/connection errors only — PostgREST application
# errors (4xx/5xx from the database) are NOT retried.
_RETRYABLE = (
    httpx.RemoteProtocolError,
    httpx.LocalProtocolError,
    httpx.ConnectError,
    httpx.ReadError,
)


def _supabase_execute(query):
    """Execute a PostgREST query builder with retry on transport errors.

    Usage::
        response = _supabase_execute(
            client.table("users").select("*").eq("id", uid).limit(1)
        )
    """
    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        before=before_log(logger, logging.WARNING),
        reraise=True,
    )
    def _run():
        return query.execute()

    return _run()


class SupabaseRepository:
    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        self.client: Client | None = None
        if create_client and self.url and self.service_key:
            # http2=False: prevents Render GOAWAY/RST_STREAM connection-reuse crashes.
            self.client = create_client(
                self.url,
                self.service_key,
                options={"httpclient": _make_http_client()},
            )

    @property
    def is_configured(self) -> bool:
        return self.client is not None

    def require(self) -> Client:
        if not self.client:
            raise HTTPException(
                status_code=503,
                detail="Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.",
            )
        return self.client

    def verify_access_token(self, token: str) -> dict[str, Any]:
        if not self.url or not self.anon_key or not create_client:
            raise HTTPException(status_code=503, detail="Supabase Auth is not configured.")
        # http2=False: same transport fix for the ephemeral auth client.
        auth_client = create_client(
            self.url,
            self.anon_key,
            options={"httpclient": _make_http_client()},
        )
        try:
            user = auth_client.auth.get_user(token).user
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid Supabase session.") from exc
        if not user:
            raise HTTPException(status_code=401, detail="Invalid Supabase session.")
        metadata = user.user_metadata or {}
        return {
            "id": user.id,
            "email": user.email,
            "full_name": metadata.get("full_name") or metadata.get("name") or "Candidate",
            "avatar_url": metadata.get("avatar_url"),
            "provider": (user.app_metadata or {}).get("provider") or "email",
        }

    def get_configured_demo_user(self) -> dict[str, Any]:
        demo_user_id = os.getenv("DEMO_USER_ID")
        demo_email = os.getenv("DEMO_USER_EMAIL")
        if not demo_user_id and not demo_email:
            raise HTTPException(
                status_code=503,
                detail="Demo account is not configured. Set DEMO_USER_ID or DEMO_USER_EMAIL.",
            )

        query = self.require().table("users").select("id,email,full_name,avatar_url,provider")
        if demo_user_id:
            query = query.eq("id", demo_user_id)
        else:
            query = query.eq("email", demo_email)
        rows = _supabase_execute(query.limit(1)).data or []
        if not rows:
            raise HTTPException(status_code=404, detail="Configured demo user was not found in Supabase.")
        row = rows[0]
        return {
            "id": row["id"],
            "email": row.get("email"),
            "full_name": row.get("full_name") or "Candidate",
            "avatar_url": row.get("avatar_url"),
            "provider": row.get("provider") or "email",
        }

    def ensure_user(self, user: dict[str, Any]) -> None:
        client = self.require()
        now = datetime.utcnow().isoformat()
        payload = {
            "id": user["id"],
            "email": user.get("email"),
            "full_name": user.get("full_name") or "Candidate",
            "avatar_url": user.get("avatar_url"),
            "provider": user.get("provider") or "email",
            "updated_at": now,
        }
        _supabase_execute(client.table("users").upsert(payload, on_conflict="id"))
        _supabase_execute(
            client.table("user_profiles").upsert(
                {
                    "user_id": user["id"],
                    "display_name": payload["full_name"],
                    "updated_at": now,
                },
                on_conflict="user_id",
            )
        )

    def update_user_profile(
        self, user_id: str, display_name: str, background: str, goals: str
    ) -> None:
        _supabase_execute(
            self.require().table("user_profiles").upsert(
                {
                    "user_id": user_id,
                    "display_name": display_name or "Candidate",
                    "background": background,
                    "goals": goals,
                    "onboarding_completed": True,
                    "updated_at": datetime.utcnow().isoformat(),
                },
                on_conflict="user_id",
            )
        )

    def get_active_resume(self, user_id: str) -> ResumeRecord | None:
        client = self.require()
        response = _supabase_execute(
            client.table("resumes")
            .select("*")
            .eq("user_id", user_id)
            .eq("is_active", True)
            .is_("deleted_at", "null")
            .order("version", desc=True)
            .order("parsed_at", desc=True)
            .limit(1)
        )
        rows = response.data or []
        return self._resume_record(rows[0]) if rows else None

    def create_resume(
        self,
        user_id: str,
        filename: str,
        content_type: str | None,
        extracted_text: str,
        profile: CandidateProfile,
    ) -> ResumeRecord:
        client = self.require()
        active = self.get_active_resume(user_id)
        text_hash = hashlib.sha256(extracted_text.encode("utf-8")).hexdigest()
        if active:
            _supabase_execute(client.table("resumes").update({"is_active": False}).eq("id", active.id))
        response = _supabase_execute(
            client.table("resumes")
            .insert(
                {
                    "user_id": user_id,
                    "filename": filename,
                    "content_type": content_type,
                    "extracted_text": extracted_text,
                    "text_hash": text_hash,
                    "version": (active.version + 1) if active else 1,
                    "is_active": True,
                }
            )
        )
        resume = self._resume_record(response.data[0])
        self.save_candidate_profile(user_id, resume.id, profile)
        return resume

    def delete_active_resume(self, user_id: str) -> bool:
        client = self.require()
        _supabase_execute(
            client.table("resumes").update(
                {"is_active": False, "deleted_at": datetime.utcnow().isoformat()}
            ).eq("user_id", user_id).eq("is_active", True)
        )
        return True

    def save_candidate_profile(
        self, user_id: str, resume_id: str | None, profile: CandidateProfile
    ) -> str:
        client = self.require()
        payload = {
            "user_id": user_id,
            "resume_id": resume_id,
            "profile": profile.model_dump(mode="json"),
            "updated_at": datetime.utcnow().isoformat(),
        }
        query = client.table("candidate_profiles").select("id").eq("user_id", user_id)
        if resume_id:
            query = query.eq("resume_id", resume_id)
        else:
            query = query.is_("resume_id", "null")
        existing = _supabase_execute(query.order("updated_at", desc=True).limit(1)).data or []
        if existing:
            response = _supabase_execute(
                client.table("candidate_profiles")
                .update(payload)
                .eq("id", existing[0]["id"])
                .eq("user_id", user_id)
            )
            return (response.data or existing)[0]["id"]
        else:
            response = _supabase_execute(client.table("candidate_profiles").insert(payload))
        return response.data[0]["id"]

    def latest_candidate_profile(self, user_id: str) -> tuple[str | None, CandidateProfile | None]:
        client = self.require()
        response = _supabase_execute(
            client.table("candidate_profiles")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .limit(1)
        )
        rows = response.data or []
        if not rows:
            return None, None
        return rows[0]["id"], CandidateProfile.model_validate(rows[0]["profile"])

    def candidate_profile_for_resume(
        self, user_id: str, resume_id: str
    ) -> tuple[str | None, CandidateProfile | None]:
        response = _supabase_execute(
            self.require()
            .table("candidate_profiles")
            .select("*")
            .eq("user_id", user_id)
            .eq("resume_id", resume_id)
            .order("updated_at", desc=True)
            .limit(1)
        )
        rows = response.data or []
        if not rows:
            return None, None
        return rows[0]["id"], CandidateProfile.model_validate(rows[0]["profile"])

    def create_session(
        self,
        user_id: str,
        memory: InterviewMemory,
        resume_id: str | None,
        candidate_profile_id: str | None,
        interview_type: str,
    ) -> None:
        client = self.require()
        _supabase_execute(
            client.table("interview_sessions").insert(
                {
                    "id": memory.session_id,
                    "user_id": user_id,
                    "resume_id": resume_id,
                    "candidate_profile_id": candidate_profile_id,
                    "status": memory.status.value,
                    "interview_type": interview_type,
                    "mode": "real",
                    "active_interviewer_id": memory.active_interviewer_id.value if memory.active_interviewer_id else None,
                    "last_speaker_reason": memory.last_speaker_reason,
                    "turn_count": memory.turn_count,
                    "started_at": memory.started_at.isoformat(),
                }
            )
        )
        self.save_memory(user_id, memory)

    def load_memory(self, user_id: str, session_id: str) -> InterviewMemory:
        client = self.require()
        response = _supabase_execute(
            client.table("interview_memory")
            .select("memory")
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .limit(1)
        )
        rows = response.data or []
        if not rows:
            raise KeyError(session_id)
        return InterviewMemory.model_validate(rows[0]["memory"])

    def save_memory(self, user_id: str, memory: InterviewMemory) -> None:
        client = self.require()
        payload = memory.model_dump(mode="json")
        _supabase_execute(
            client.table("interview_memory").upsert(
                {
                    "session_id": memory.session_id,
                    "user_id": user_id,
                    "memory": payload,
                    "strengths": memory.strengths,
                    "weaknesses": memory.weaknesses,
                    "contradictions": memory.contradictions,
                    "speaker_history": [speaker.value for speaker in memory.speaker_history],
                    "topic_coverage": [state.model_dump(mode="json") for state in memory.topic_states],
                    "updated_at": datetime.utcnow().isoformat(),
                },
                on_conflict="session_id",
            )
        )
        duration_seconds = 0
        if memory.completed_at:
            duration_seconds = max(0, int((memory.completed_at - memory.started_at).total_seconds()))
        _supabase_execute(
            client.table("interview_sessions").update(
                {
                    "status": memory.status.value,
                    "active_interviewer_id": memory.active_interviewer_id.value if memory.active_interviewer_id else None,
                    "last_speaker_reason": memory.last_speaker_reason,
                    "turn_count": memory.turn_count,
                    "completed_at": memory.completed_at.isoformat() if memory.completed_at else None,
                    "duration_seconds": duration_seconds,
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ).eq("id", memory.session_id).eq("user_id", user_id)
        )
        self._replace_turns(user_id, memory)
        self._replace_topic_tracking(user_id, memory.session_id, memory.topic_states)

    def record_speaker_decision(
        self, user_id: str, session_id: str, interviewer_id: str, reason: str, topic: str
    ) -> None:
        _supabase_execute(
            self.require().table("speaker_decisions").insert(
                {
                    "user_id": user_id,
                    "session_id": session_id,
                    "interviewer_id": interviewer_id,
                    "reason": reason,
                    "topic": topic,
                }
            )
        )

    def save_report(
        self, user_id: str, report: InterviewReport, progress: ProgressAnalysis | None
    ) -> InterviewReport:
        client = self.require()
        if progress:
            report.progress = progress
        report_payload = report.model_dump(mode="json")
        response = _supabase_execute(
            client.table("reports").upsert(
                {
                    "session_id": report.session_id,
                    "user_id": user_id,
                    "overall_score": report.overall_score,
                    "verdict": report.verdict,
                    "executive_summary": report.executive_summary,
                    "strengths": report.strengths,
                    "weaknesses": report.weaknesses,
                    "panel_concerns": report.panel_concerns,
                    "mba_readiness_assessment": report.mba_readiness_assessment,
                    "benchmark": [item.model_dump(mode="json") for item in report.benchmarking],
                    "report": report_payload,
                },
                on_conflict="session_id",
            )
        )
        report_id = response.data[0]["id"]
        self._replace_report_children(user_id, report_id, report)
        if progress:
            self._save_progress_snapshot(user_id, report_id, report, progress)
        return report

    def get_report(self, user_id: str, session_id: str) -> InterviewReport | None:
        response = _supabase_execute(
            self.require()
            .table("reports")
            .select("report")
            .eq("user_id", user_id)
            .eq("session_id", session_id)
            .limit(1)
        )
        rows = response.data or []
        return InterviewReport.model_validate(rows[0]["report"]) if rows else None

    def list_reports(self, user_id: str) -> list[InterviewReport]:
        response = _supabase_execute(
            self.require()
            .table("reports")
            .select("report")
            .eq("user_id", user_id)
            .order("created_at")
        )
        return [InterviewReport.model_validate(row["report"]) for row in response.data or []]

    def history(self, user_id: str) -> list[InterviewHistoryItem]:
        response = _supabase_execute(
            self.require()
            .table("interview_sessions")
            .select("id,started_at,duration_seconds,interview_type,status,reports(overall_score,verdict)")
            .eq("user_id", user_id)
            .order("started_at", desc=True)
        )
        items = []
        for row in response.data or []:
            report = (row.get("reports") or [{}])[0] if isinstance(row.get("reports"), list) else row.get("reports") or {}
            items.append(
                InterviewHistoryItem(
                    session_id=row["id"],
                    interview_date=self._parse_dt(row["started_at"]),
                    overall_score=report.get("overall_score"),
                    verdict=report.get("verdict"),
                    duration_seconds=row.get("duration_seconds") or 0,
                    interview_type=row.get("interview_type") or "IIM MBA Panel",
                    status=InterviewStatus(row.get("status") or "ready"),
                )
            )
        return items

    def delete_incomplete_session(self, user_id: str, session_id: str) -> bool:
        """Delete a session only if it is NOT completed (i.e., abandoned / stuck in created/in_progress)."""
        client = self.require()
        # Safety check: only allow deletion of non-completed sessions.
        check = _supabase_execute(
            client.table("interview_sessions")
            .select("id,status")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .neq("status", "completed")
        )
        if not check.data:
            return False
        _supabase_execute(
            client.table("interview_sessions").delete().eq("id", session_id).eq("user_id", user_id)
        )
        return True

    def progress_dashboard(self, user_id: str) -> ProgressDashboardResponse:
        response = _supabase_execute(
            self.require()
            .table("progress_snapshots")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at")
        )
        points = [
            ProgressPoint(
                report_id=row.get("report_id"),
                created_at=self._parse_dt(row["created_at"]),
                communication=row.get("communication"),
                leadership=row.get("leadership"),
                business_awareness=row.get("business_awareness"),
                mba_fit=row.get("mba_fit"),
                career_clarity=row.get("career_clarity"),
                academic_depth=row.get("academic_depth"),
            )
            for row in response.data or []
        ]
        latest_row = (response.data or [])[-1] if response.data else {}
        latest = ProgressAnalysis(
            improved_areas=latest_row.get("improved_areas") or [],
            declining_areas=latest_row.get("declining_areas") or [],
            recurring_weaknesses=latest_row.get("recurring_weaknesses") or [],
            growth_summary=latest_row.get("growth_summary") or "",
            next_focus_areas=latest_row.get("next_focus_areas") or [],
        )
        return ProgressDashboardResponse(points=points, latest=latest)

    def mark_practiced(self, user_id: str, practice_id: str) -> tuple[int, str]:
        client = self.require()
        response = _supabase_execute(
            client.table("followup_questions")
            .select("practiced_count,question")
            .eq("user_id", user_id)
            .eq("id", practice_id)
            .limit(1)
        )
        rows = response.data or []
        if not rows:
            raise KeyError(practice_id)
        count = int(rows[0].get("practiced_count") or 0) + 1
        _supabase_execute(
            client.table("followup_questions").update(
                {"practiced_count": count, "last_practiced_at": datetime.utcnow().isoformat()}
            ).eq("id", practice_id).eq("user_id", user_id)
        )
        return count, rows[0]["question"]

    def _replace_turns(self, user_id: str, memory: InterviewMemory) -> None:
        client = self.require()
        _supabase_execute(
            client.table("interview_turns").delete().eq("session_id", memory.session_id).eq("user_id", user_id)
        )
        rows = [
            {
                "id": turn.id,
                "session_id": memory.session_id,
                "user_id": user_id,
                "turn_index": index,
                "speaker": turn.speaker.value,
                "interviewer_id": turn.interviewer_id.value if turn.interviewer_id else None,
                "text": turn.text,
                "created_at": turn.created_at.isoformat(),
            }
            for index, turn in enumerate(memory.transcript)
        ]
        if rows:
            _supabase_execute(client.table("interview_turns").insert(rows))

    def _replace_topic_tracking(
        self, user_id: str, session_id: str, topics: list[TopicState]
    ) -> None:
        client = self.require()
        _supabase_execute(
            client.table("topic_tracking").delete().eq("session_id", session_id).eq("user_id", user_id)
        )
        rows = [
            {
                "session_id": session_id,
                "user_id": user_id,
                "topic_name": topic.topic_name,
                "depth_level": topic.depth_level,
                "questions_asked": topic.questions_asked,
                "evidence_collected": topic.evidence_collected,
                "status": topic.status.value,
            }
            for topic in topics
        ]
        if rows:
            _supabase_execute(client.table("topic_tracking").insert(rows))

    def _replace_report_children(
        self, user_id: str, report_id: str, report: InterviewReport
    ) -> None:
        client = self.require()
        for table in ["report_scores", "report_evidence", "coaching_plans"]:
            _supabase_execute(client.table(table).delete().eq("report_id", report_id).eq("user_id", user_id))
        followups = (
            _supabase_execute(
                client.table("followup_questions")
                .select("id")
                .eq("report_id", report_id)
                .eq("user_id", user_id)
            ).data
            or []
        )
        followup_ids = [row["id"] for row in followups]
        if followup_ids:
            _supabase_execute(
                client.table("ideal_answers").delete().eq("user_id", user_id).in_(
                    "followup_question_id", followup_ids
                )
            )
            _supabase_execute(
                client.table("followup_questions").delete().eq("report_id", report_id).eq("user_id", user_id)
            )
        scores = [
            {
                "report_id": report_id,
                "user_id": user_id,
                "dimension": item.name,
                "score": item.score,
                "evidence": item.evidence,
                "advice": item.advice,
                "strengths": item.strengths,
                "weaknesses": item.weaknesses,
            }
            for item in report.dimensions
        ]
        if scores:
            _supabase_execute(client.table("report_scores").insert(scores))
        evidence_rows = [
            {
                "report_id": report_id,
                "user_id": user_id,
                "topic": item.topic,
                "evidence": item.evidence,
                "panel_interpretation": item.panel_interpretation,
            }
            for item in report.transcript_evidence
        ]
        if evidence_rows:
            _supabase_execute(client.table("report_evidence").insert(evidence_rows))
        followup_rows = [
            {
                "report_id": report_id,
                "user_id": user_id,
                "weakness": item.weakness,
                "question": item.question,
                "why_panel_would_ask": item.why_panel_would_ask,
                "skills_evaluated": item.skills_being_evaluated,
                "improvement_advice": item.improvement_advice,
            }
            for item in report.coaching_items
        ]
        inserted = _supabase_execute(client.table("followup_questions").insert(followup_rows)) if followup_rows else None
        if inserted:
            ideal_rows = []
            for row, item in zip(inserted.data or [], report.coaching_items):
                item.practice_id = row["id"]
                ideal_rows.append(
                    {
                        "followup_question_id": row["id"],
                        "user_id": user_id,
                        "answer": item.ideal_answer,
                    }
                )
            if ideal_rows:
                _supabase_execute(client.table("ideal_answers").insert(ideal_rows))
        _supabase_execute(
            client.table("coaching_plans").insert(
                {
                    "report_id": report_id,
                    "user_id": user_id,
                    "plan": {"items": [item.model_dump(mode="json") for item in report.coaching_items]},
                }
            )
        )

    def _save_progress_snapshot(
        self, user_id: str, report_id: str, report: InterviewReport, progress: ProgressAnalysis
    ) -> None:
        # Normalise all dimension names to lowercase for robust key matching.
        scores = {item.name.lower().strip(): item.score for item in report.dimensions}

        def _score(*candidates: str) -> float | None:
            """Return the first matching dimension score from multiple candidate keys."""
            for key in candidates:
                value = scores.get(key)
                if value is not None:
                    return value
            return None

        _supabase_execute(
            self.require().table("progress_snapshots").insert(
                {
                    "user_id": user_id,
                    "report_id": report_id,
                    "communication": _score("communication clarity", "communication"),
                    "leadership": _score("leadership potential", "leadership"),
                    "business_awareness": _score("business awareness"),
                    "mba_fit": _score("mba fit", "mba readiness"),
                    "career_clarity": _score("career clarity"),
                    "academic_depth": _score("academic depth"),
                    "improved_areas": progress.improved_areas,
                    "declining_areas": progress.declining_areas,
                    "recurring_weaknesses": progress.recurring_weaknesses,
                    "growth_summary": progress.growth_summary,
                    "next_focus_areas": progress.next_focus_areas,
                }
            )
        )

    def _resume_record(self, row: dict[str, Any]) -> ResumeRecord:
        return ResumeRecord(
            id=row["id"],
            filename=row["filename"],
            extracted_text=row["extracted_text"],
            version=row["version"],
            is_active=row["is_active"],
            parsed_at=self._parse_dt(row["parsed_at"]),
            created_at=self._parse_dt(row["created_at"]),
        )

    def _parse_dt(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
