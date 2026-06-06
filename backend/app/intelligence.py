import json
import os
import re
from collections import Counter
from typing import Any

from app.models import (
    CandidateClaim,
    CandidateProfile,
    CreateSessionRequest,
    DimensionScore,
    FollowUpOpportunity,
    InterviewMemory,
    InterviewReport,
    InterviewerObservation,
    InterviewerId,
    SpeakerSelection,
    TranscriptTurn,
    TurnSpeaker,
)

try:
    from groq import Groq
except ImportError:  # pragma: no cover - dependency is present in the app venv.
    Groq = None  # type: ignore[assignment]


PROFILE_FIELDS = [
    "education",
    "projects",
    "internships",
    "achievements",
    "certifications",
    "skills",
    "career_goals",
    "notable_resume_claims",
]

TOPIC_TO_INTERVIEWER = {
    "education": InterviewerId.academic,
    "projects": InterviewerId.academic,
    "internships": InterviewerId.academic,
    "skills": InterviewerId.academic,
    "achievements": InterviewerId.pressure,
    "career_goals": InterviewerId.mba,
    "why mba": InterviewerId.mba,
    "leadership": InterviewerId.mba,
    "business impact": InterviewerId.mba,
}


class InterviewIntelligence:
    """Groq-backed interview intelligence with local development fallbacks."""

    def __init__(self) -> None:
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        api_key = os.getenv("GROQ_API_KEY")
        self.client = Groq(api_key=api_key) if Groq and api_key else None

    @property
    def is_model_enabled(self) -> bool:
        return self.client is not None

    def create_candidate_profile(self, request: CreateSessionRequest) -> CandidateProfile:
        base = CandidateProfile(
            name=request.name.strip() or "Candidate",
            goals=request.goals.strip(),
            background=request.background.strip(),
            resume_text=request.resume_text.strip(),
        )

        if self.client and request.resume_text.strip():
            parsed = self._extract_profile_with_groq(request)
            if parsed:
                return parsed

        return self._extract_profile_locally(base)

    def generate_opening_question(self, memory: InterviewMemory) -> str:
        topic = self._first_available(
            memory.candidate.projects,
            memory.candidate.internships,
            memory.candidate.education,
            memory.candidate.notable_resume_claims,
        )
        if not topic:
            topic = memory.candidate.background or memory.candidate.goals or "your background"

        return self.generate_question(
            memory=memory,
            interviewer_id=InterviewerId.academic,
            latest_answer="",
            selection_reason="Begin with resume-grounded academic and profile validation.",
            opening_topic=topic,
        )

    def update_memory(self, memory: InterviewMemory, latest_answer: str) -> None:
        if self.client:
            updated = self._update_memory_with_groq(memory, latest_answer)
            if updated:
                self._merge_memory_update(memory, updated)
                return

        self._update_memory_locally(memory, latest_answer)

    def select_speaker(self, memory: InterviewMemory) -> SpeakerSelection:
        if self.client:
            selection = self._select_speaker_with_groq(memory)
            if selection:
                memory.last_speaker_reason = selection.reason
                return selection

        selection = self._select_speaker_locally(memory)
        memory.last_speaker_reason = selection.reason
        return selection

    def generate_question(
        self,
        memory: InterviewMemory,
        interviewer_id: InterviewerId,
        latest_answer: str,
        selection_reason: str,
        opening_topic: str = "",
    ) -> str:
        if self.client:
            question = self._generate_question_with_groq(
                memory, interviewer_id, latest_answer, selection_reason, opening_topic
            )
            if question:
                return question

        return self._generate_question_locally(
            memory, interviewer_id, latest_answer, selection_reason, opening_topic
        )

    def generate_report(self, memory: InterviewMemory) -> InterviewReport:
        if self.client:
            report = self._generate_report_with_groq(memory)
            if report:
                return report

        return self._generate_report_locally(memory)

    def _chat_json(self, system: str, user: str, temperature: float = 0.25) -> dict[str, Any] | None:
        if not self.client:
            return None
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception:
            return None

    def _extract_profile_with_groq(
        self, request: CreateSessionRequest
    ) -> CandidateProfile | None:
        system = (
            "You extract MBA interview candidate profiles from resumes. "
            "Return only JSON. Do not invent facts. Empty arrays are allowed."
        )
        user = json.dumps(
            {
                "task": "Extract a PANELIQ candidate profile.",
                "required_shape": {
                    "education": ["facts about degrees, colleges, academics"],
                    "projects": ["project names and compact descriptions"],
                    "internships": ["internship or work experience facts"],
                    "achievements": ["awards, responsibilities, measurable outcomes"],
                    "certifications": ["certifications or courses"],
                    "skills": ["technical, analytical, business, and communication skills"],
                    "career_goals": ["explicit career goals only"],
                    "notable_resume_claims": ["claims worth probing in an IIM interview"],
                },
                "candidate_name": request.name,
                "declared_background": request.background,
                "declared_goals": request.goals,
                "resume_text": request.resume_text[:12000],
            }
        )
        data = self._chat_json(system, user)
        if not data:
            return None
        cleaned = {field: self._as_string_list(data.get(field)) for field in PROFILE_FIELDS}
        goals = request.goals.strip()
        if cleaned["career_goals"]:
            goals = goals or "; ".join(cleaned["career_goals"][:2])
        return CandidateProfile(
            name=request.name.strip() or "Candidate",
            resume_text=request.resume_text.strip(),
            goals=goals,
            background=request.background.strip(),
            **cleaned,
        )

    def _extract_profile_locally(self, profile: CandidateProfile) -> CandidateProfile:
        text = "\n".join([profile.background, profile.goals, profile.resume_text]).strip()
        sections = self._rough_sections(text)

        profile.education = self._section_items(sections, ["education", "academic", "qualification"])
        profile.projects = self._section_items(sections, ["project", "projects"])
        profile.internships = self._section_items(
            sections, ["experience", "internship", "internships", "work"]
        )
        profile.achievements = self._section_items(
            sections, ["achievement", "achievements", "award", "awards", "responsibility"]
        )
        profile.certifications = self._section_items(
            sections, ["certification", "certifications", "course", "courses"]
        )
        profile.skills = self._section_items(sections, ["skill", "skills", "technical skills"])
        extracted_goals = self._section_items(sections, ["career goal", "career goals", "objective"])
        profile.career_goals = self._dedupe(([profile.goals] if profile.goals else []) + extracted_goals)[:6]

        candidate_lines = [
            line
            for line in self._candidate_lines(text)
            if any(
                keyword in line.lower()
                for keyword in [
                    "led",
                    "built",
                    "created",
                    "improved",
                    "managed",
                    "achieved",
                    "project",
                    "intern",
                    "certified",
                    "winner",
                    "rank",
                    "cgpa",
                    "mba",
                    "dashboard",
                    "salesforce",
                    "product management",
                ]
            )
        ]
        profile.notable_resume_claims = self._dedupe(candidate_lines)[:10]
        return profile

    def _update_memory_with_groq(
        self, memory: InterviewMemory, latest_answer: str
    ) -> dict[str, Any] | None:
        system = (
            "You update shared memory for a multi-panel IIM interview. Return only JSON. "
            "Capture only evidence present in the candidate's latest answer and transcript. "
            "Do not invent achievements or contradictions."
        )
        user = json.dumps(
            {
                "candidate_profile": self._profile_payload(memory.candidate),
                "existing_memory": self._memory_payload(memory),
                "latest_candidate_answer": latest_answer,
                "required_shape": {
                    "topics_covered": ["topic labels tested by this answer"],
                    "candidate_claims": [
                        {
                            "text": "claim made by candidate",
                            "source": "interview",
                            "evidence": "short quote or paraphrase",
                            "challenged": False,
                        }
                    ],
                    "strengths": ["evidence-backed strengths"],
                    "weaknesses": ["evidence-backed weaknesses"],
                    "contradictions": ["explicit contradiction only"],
                    "interviewer_observations": [
                        {
                            "interviewer_id": "academic|pressure|mba",
                            "note": "panel observation to preserve",
                            "evidence": "candidate answer fragment",
                        }
                    ],
                    "unanswered_follow_up_opportunities": [
                        {
                            "topic": "topic to revisit",
                            "reason": "why follow-up is needed",
                            "suggested_interviewer": "academic|pressure|mba",
                            "source_claim": "claim or answer fragment",
                        }
                    ],
                },
            }
        )
        return self._chat_json(system, user)

    def _merge_memory_update(self, memory: InterviewMemory, data: dict[str, Any]) -> None:
        memory.topics_covered = self._merge_strings(
            memory.topics_covered, self._as_string_list(data.get("topics_covered"))
        )
        memory.strengths = self._merge_strings(memory.strengths, self._as_string_list(data.get("strengths")))
        memory.weaknesses = self._merge_strings(
            memory.weaknesses, self._as_string_list(data.get("weaknesses"))
        )
        memory.contradictions = self._merge_strings(
            memory.contradictions, self._as_string_list(data.get("contradictions"))
        )
        for raw_observation in data.get("interviewer_observations") or []:
            if not isinstance(raw_observation, dict):
                continue
            note = str(raw_observation.get("note") or "").strip()
            if not note:
                continue
            observation = InterviewerObservation(
                interviewer_id=self._parse_interviewer(raw_observation.get("interviewer_id")),
                note=note[:220],
                evidence=str(raw_observation.get("evidence") or "")[:220],
            )
            if observation.note not in [item.note for item in memory.interviewer_observations]:
                memory.interviewer_observations.append(observation)

        for raw_claim in data.get("candidate_claims") or []:
            if isinstance(raw_claim, dict) and raw_claim.get("text"):
                claim = CandidateClaim(
                    text=str(raw_claim["text"])[:220],
                    source="interview",
                    evidence=str(raw_claim.get("evidence") or raw_claim["text"])[:220],
                    challenged=bool(raw_claim.get("challenged", False)),
                )
                if claim.text not in memory.claims:
                    memory.candidate_claims.append(claim)

        for raw_follow_up in data.get("unanswered_follow_up_opportunities") or []:
            if not isinstance(raw_follow_up, dict):
                continue
            topic = str(raw_follow_up.get("topic") or "").strip()
            reason = str(raw_follow_up.get("reason") or "").strip()
            if not topic or not reason:
                continue
            interviewer = self._parse_interviewer(raw_follow_up.get("suggested_interviewer"))
            opportunity = FollowUpOpportunity(
                topic=topic[:80],
                reason=reason[:180],
                suggested_interviewer=interviewer,
                source_claim=str(raw_follow_up.get("source_claim") or "")[:220],
            )
            if opportunity.reason not in [item.reason for item in memory.unanswered_follow_up_opportunities]:
                memory.unanswered_follow_up_opportunities.append(opportunity)

    def _update_memory_locally(self, memory: InterviewMemory, latest_answer: str) -> None:
        lower = latest_answer.lower()
        topics = []
        topic_keywords = {
            "education": ["college", "cgpa", "degree", "semester", "academic"],
            "projects": ["project", "built", "created", "developed"],
            "internships": ["intern", "trainee", "work", "company"],
            "why mba": ["mba", "management", "business school"],
            "leadership": ["lead", "team", "organized", "managed"],
            "business impact": ["revenue", "cost", "customer", "market", "profit", "growth"],
        }
        for topic, keywords in topic_keywords.items():
            if any(keyword in lower for keyword in keywords):
                topics.append(topic)
        memory.topics_covered = self._merge_strings(memory.topics_covered, topics)

        first_sentence = latest_answer.split(".")[0].strip()
        if first_sentence and first_sentence not in memory.claims:
            memory.candidate_claims.append(
                CandidateClaim(text=first_sentence[:220], evidence=first_sentence[:220])
            )

        word_count = len(latest_answer.split())
        if word_count >= 55:
            memory.strengths = self._merge_strings(
                memory.strengths, ["Gave a developed answer with enough substance to probe."]
            )
        else:
            memory.weaknesses = self._merge_strings(
                memory.weaknesses, ["Answer was brief and needs stronger evidence."]
            )
            memory.unanswered_follow_up_opportunities.append(
                FollowUpOpportunity(
                    topic=topics[0] if topics else "specific evidence",
                    reason="Candidate gave a short answer that needs a concrete incident and measurable result.",
                    suggested_interviewer=InterviewerId.pressure,
                    source_claim=first_sentence[:180],
                )
            )

        if any(char.isdigit() for char in latest_answer):
            memory.strengths = self._merge_strings(
                memory.strengths, ["Used specific details or numbers in the answer."]
            )
        else:
            memory.unanswered_follow_up_opportunities.append(
                FollowUpOpportunity(
                    topic="measurable impact",
                    reason="Candidate did not provide numbers, trade-offs, or measurable impact.",
                    suggested_interviewer=InterviewerId.mba,
                    source_claim=first_sentence[:180],
                )
            )

        contradiction = self._detect_local_contradiction(memory, latest_answer)
        if contradiction:
            memory.contradictions = self._merge_strings(memory.contradictions, [contradiction])
            memory.unanswered_follow_up_opportunities.append(
                FollowUpOpportunity(
                    topic="consistency",
                    reason="Candidate appears to have made inconsistent claims that should be challenged.",
                    suggested_interviewer=InterviewerId.pressure,
                    source_claim=contradiction,
                )
            )

    def _select_speaker_with_groq(self, memory: InterviewMemory) -> SpeakerSelection | None:
        system = (
            "You select the next speaker in an IIM admissions panel. Return only JSON. "
            "Do not use round-robin. Prefer the interviewer best suited to unresolved memory."
        )
        user = json.dumps(
            {
                "candidate_profile": self._profile_payload(memory.candidate),
                "memory": self._memory_payload(memory),
                "speaker_counts": Counter(str(item.value) for item in memory.speaker_history),
                "required_shape": {"speaker": "academic|pressure|mba", "reason": "selection reason"},
            }
        )
        data = self._chat_json(system, user)
        if not data:
            return None
        speaker = self._parse_interviewer(data.get("speaker"))
        reason = str(data.get("reason") or "Selected from shared interview memory.").strip()
        return SpeakerSelection(speaker=speaker, reason=reason[:220])

    def _select_speaker_locally(self, memory: InterviewMemory) -> SpeakerSelection:
        if memory.contradictions:
            return SpeakerSelection(
                speaker=InterviewerId.pressure,
                reason="Open contradiction exists and should be stress-tested before moving on.",
            )

        if memory.unanswered_follow_up_opportunities:
            opportunity = memory.unanswered_follow_up_opportunities.pop(0)
            return SpeakerSelection(
                speaker=opportunity.suggested_interviewer,
                reason=f"Follow up on {opportunity.topic}: {opportunity.reason}",
            )

        open_topics = self._open_topics(memory)
        if open_topics:
            topic = open_topics[0]
            return SpeakerSelection(
                speaker=TOPIC_TO_INTERVIEWER.get(topic, InterviewerId.mba),
                reason=f"{topic} is under-tested for this candidate.",
            )

        counts = Counter(memory.speaker_history)
        candidates = [InterviewerId.academic, InterviewerId.pressure, InterviewerId.mba]
        speaker = min(candidates, key=lambda item: counts[item])
        return SpeakerSelection(
            speaker=speaker,
            reason="Balance the panel after resolving the available memory signals.",
        )

    def _generate_question_with_groq(
        self,
        memory: InterviewMemory,
        interviewer_id: InterviewerId,
        latest_answer: str,
        selection_reason: str,
        opening_topic: str,
    ) -> str | None:
        system = (
            f"You are the {interviewer_id.value} interviewer in PANELIQ, an IIM-style MBA "
            "admissions panel. Ask exactly one concise spoken question. "
            "Use the shared memory and resume. Continue another interviewer's thread when useful. "
            "Do not explain your reasoning. Do not ask generic chatbot questions."
        )
        user = json.dumps(
            {
                "interviewer_role": self._role_for(interviewer_id),
                "candidate_profile": self._profile_payload(memory.candidate),
                "interview_memory": self._memory_payload(memory),
                "latest_candidate_response": latest_answer,
                "speaker_selection_reason": selection_reason,
                "opening_topic": opening_topic,
                "required_shape": {
                    "question": "one interviewer question",
                    "follow_up_intent": "why this question should be asked now",
                    "evaluation_notes": "what the interviewer will watch for",
                },
            }
        )
        data = self._chat_json(system, user, temperature=0.45)
        question = str((data or {}).get("question") or "").strip()
        notes = str((data or {}).get("evaluation_notes") or "").strip()
        intent = str((data or {}).get("follow_up_intent") or "").strip()
        if notes or intent:
            memory.interviewer_observations.append(
                InterviewerObservation(
                    interviewer_id=interviewer_id,
                    note=(notes or intent)[:220],
                    evidence=latest_answer[:220],
                )
            )
        return question[:700] or None

    def _generate_question_locally(
        self,
        memory: InterviewMemory,
        interviewer_id: InterviewerId,
        latest_answer: str,
        selection_reason: str,
        opening_topic: str,
    ) -> str:
        claim = self._last_claim(memory) or opening_topic or "your resume"
        resume_anchor = self._first_available(
            memory.candidate.projects,
            memory.candidate.internships,
            memory.candidate.notable_resume_claims,
            [claim],
        )

        if interviewer_id == InterviewerId.academic:
            memory.interviewer_observations.append(
                InterviewerObservation(
                    interviewer_id=interviewer_id,
                    note="Testing resume-grounded academic/project depth.",
                    evidence=self._clean_anchor(resume_anchor)[:220],
                )
            )
            return (
                f"Your resume mentions {self._clean_anchor(resume_anchor)}. Walk me through the core idea, "
                "your exact contribution, and one technical or academic trade-off you handled."
            )
        if interviewer_id == InterviewerId.pressure:
            memory.interviewer_observations.append(
                InterviewerObservation(
                    interviewer_id=interviewer_id,
                    note="Challenging a claim for ownership, specificity, and evidence.",
                    evidence=claim[:220],
                )
            )
            return (
                f"I want to test that claim: {claim}. Give me the specific incident, "
                "what you personally did, and evidence that the outcome changed because of you."
            )
        memory.interviewer_observations.append(
            InterviewerObservation(
                interviewer_id=interviewer_id,
                note="Revisiting the thread for business impact and MBA fit.",
                evidence=claim[:220],
            )
        )
        return (
            f"Let us connect this to management. Taking {claim} as the context, "
            "what was the business impact, who was the customer or stakeholder, and why does this make an MBA necessary now?"
        )

    def _generate_report_with_groq(self, memory: InterviewMemory) -> InterviewReport | None:
        system = (
            "You are an IIM admissions evaluator. Return only JSON. "
            "Evaluate only evidence present in the transcript. Use null for insufficiently tested scores."
        )
        user = json.dumps(
            {
                "candidate_profile": self._profile_payload(memory.candidate),
                "memory": self._memory_payload(memory),
                "transcript": self._transcript_payload(memory.transcript),
                "required_shape": {
                    "verdict": "Strong Hire|Lean Hire|Lean Reject|Strong Reject",
                    "overall_score": "number from 1-10",
                    "strengths": ["evidence-backed strengths"],
                    "weaknesses": ["evidence-backed weaknesses"],
                    "panel_concerns": ["major concerns"],
                    "feedback_to_candidate": "short summary",
                    "dimensions": [
                        {
                            "name": "Communication clarity",
                            "score": "number or null",
                            "evidence": "specific transcript evidence",
                            "strengths": ["specific positive signals"],
                            "weaknesses": ["specific gaps"],
                            "advice": "actionable recommendation",
                        }
                    ],
                },
                "required_dimensions": [
                    "Communication clarity",
                    "Academic depth",
                    "Business awareness",
                    "Leadership potential",
                    "Career clarity",
                    "Composure under pressure",
                    "Answer structure",
                    "Overall admissions readiness",
                ],
            }
        )
        data = self._chat_json(system, user, temperature=0.2)
        if not data:
            return None
        try:
            dimensions = [
                DimensionScore(
                    name=str(item.get("name") or "Untitled dimension"),
                    score=item.get("score"),
                    evidence=str(item.get("evidence") or "Insufficient transcript evidence."),
                    strengths=self._as_string_list(item.get("strengths")),
                    weaknesses=self._as_string_list(item.get("weaknesses")),
                    advice=str(item.get("advice") or "Practice with transcript-backed examples."),
                )
                for item in data.get("dimensions", [])
                if isinstance(item, dict)
            ]
            if not dimensions:
                return None
            return InterviewReport(
                session_id=memory.session_id,
                verdict=data.get("verdict") or "Lean Reject",
                overall_score=float(data.get("overall_score") or 0),
                strengths=self._as_string_list(data.get("strengths")),
                weaknesses=self._as_string_list(data.get("weaknesses")),
                panel_concerns=self._as_string_list(data.get("panel_concerns")),
                dimensions=dimensions,
                feedback_to_candidate=str(data.get("feedback_to_candidate") or ""),
                transcript=memory.transcript,
            )
        except (TypeError, ValueError):
            return None

    def _generate_report_locally(self, memory: InterviewMemory) -> InterviewReport:
        candidate_turns = [
            turn.text for turn in memory.transcript if turn.speaker == TurnSpeaker.candidate
        ]
        transcript_text = " ".join(candidate_turns)
        total_words = sum(len(turn.split()) for turn in candidate_turns)
        tested_topics = set(memory.topics_covered)
        evidence_quote = self._evidence_excerpt(candidate_turns)

        dimensions = [
            self._dimension(
                "Communication clarity",
                7.0 if total_words >= 180 else 6.0 if total_words >= 70 else None,
                evidence_quote,
                ["Candidate gave developed responses."] if total_words >= 180 else [],
                ["Insufficient response depth."] if total_words < 70 else [],
                "Use a direct answer, one example, and a quantified result.",
            ),
            self._dimension(
                "Academic depth",
                7.0 if {"education", "projects"} & tested_topics else None,
                self._topic_evidence(
                    candidate_turns,
                    ["project", "built", "dashboard", "salesforce", "college", "cgpa", "degree"],
                ),
                ["Discussed academic or project material."] if {"education", "projects"} & tested_topics else [],
                [] if {"education", "projects"} & tested_topics else ["Academic depth was not sufficiently tested."],
                "Prepare one project and one academic subject at concept, trade-off, and impact levels.",
            ),
            self._dimension(
                "Business awareness",
                7.0 if "business impact" in tested_topics else None,
                self._topic_evidence(candidate_turns, ["revenue", "cost", "customer", "market", "profit"]),
                ["Connected answers to business impact."] if "business impact" in tested_topics else [],
                [] if "business impact" in tested_topics else ["Business impact was not demonstrated clearly."],
                "Translate projects into customer, cost, revenue, risk, and stakeholder language.",
            ),
            self._dimension(
                "Leadership potential",
                7.0 if "leadership" in tested_topics else None,
                self._topic_evidence(candidate_turns, ["lead", "team", "managed", "organized"]),
                ["Mentioned leadership or team ownership."] if "leadership" in tested_topics else [],
                [] if "leadership" in tested_topics else ["Leadership evidence was not sufficiently tested."],
                "Use one incident showing conflict, decision-making, and measurable team outcome.",
            ),
            self._dimension(
                "Career clarity",
                7.0 if "why mba" in tested_topics or "mba" in transcript_text.lower() else None,
                self._topic_evidence(candidate_turns, ["mba", "career", "product", "consulting", "strategy"]),
                ["Addressed MBA or career direction."] if "mba" in transcript_text.lower() else [],
                [] if "mba" in transcript_text.lower() else ["MBA motivation was not established."],
                "Clarify role, industry, skills gap, and why this is the right timing.",
            ),
            self._dimension(
                "Composure under pressure",
                6.5 if any(item == InterviewerId.pressure for item in memory.speaker_history) else None,
                evidence_quote,
                ["Handled at least one pressure follow-up."] if InterviewerId.pressure in memory.speaker_history else [],
                memory.weaknesses[:2],
                "When challenged, acknowledge the concern and answer with specific evidence.",
            ),
        ]

        scored = [item.score for item in dimensions if item.score is not None]
        overall = round(sum(scored) / len(scored), 1) if scored else 0.0
        verdict = self._verdict(overall)
        weaknesses = memory.weaknesses or ["The transcript does not yet contain enough evidence for a rigorous evaluation."]

        return InterviewReport(
            session_id=memory.session_id,
            verdict=verdict,
            overall_score=overall,
            strengths=memory.strengths[:5],
            weaknesses=weaknesses[:5],
            panel_concerns=(memory.contradictions + weaknesses)[:5],
            dimensions=dimensions,
            feedback_to_candidate=(
                "This report uses only transcript evidence. Strengthen the next attempt with concrete "
                "incidents, quantified outcomes, and clearer MBA linkage."
            ),
            transcript=memory.transcript,
        )

    def _profile_payload(self, profile: CandidateProfile) -> dict[str, Any]:
        return profile.model_dump(exclude={"resume_text"}, mode="json") | {
            "resume_excerpt": profile.resume_text[:4000]
        }

    def _memory_payload(self, memory: InterviewMemory) -> dict[str, Any]:
        return {
            "topics_covered": memory.topics_covered,
            "candidate_claims": [claim.model_dump(mode="json") for claim in memory.candidate_claims],
            "weaknesses": memory.weaknesses,
            "strengths": memory.strengths,
            "contradictions": memory.contradictions,
            "unanswered_follow_up_opportunities": [
                item.model_dump(mode="json") for item in memory.unanswered_follow_up_opportunities
            ],
            "interviewer_observations": [
                item.model_dump(mode="json") for item in memory.interviewer_observations[-12:]
            ],
            "speaker_history": [speaker.value for speaker in memory.speaker_history],
            "last_speaker_reason": memory.last_speaker_reason,
            "turn_count": memory.turn_count,
            "recent_transcript": self._transcript_payload(memory.transcript[-8:]),
        }

    def _transcript_payload(self, transcript: list[TranscriptTurn]) -> list[dict[str, Any]]:
        return [
            {
                "speaker": turn.speaker.value,
                "interviewer_id": turn.interviewer_id.value if turn.interviewer_id else None,
                "text": turn.text,
            }
            for turn in transcript
        ]

    def _rough_sections(self, text: str) -> dict[str, list[str]]:
        text = re.sub(
            r"(?i)\b(education|academics|academic|projects?|experience|internships?|work|achievements?|awards?|certifications?|courses?|skills?|technical skills|career goals?|objective)\s*:",
            lambda match: f"\n{match.group(1).lower()}:\n",
            text,
        )
        current = "general"
        sections: dict[str, list[str]] = {current: []}
        for raw_line in text.splitlines():
            line = raw_line.strip(" -\t")
            if not line:
                continue
            if len(line) < 55 and re.search(r"education|project|experience|intern|achievement|award|certification|course|skill", line, re.I):
                current = line.lower()
                sections.setdefault(current, [])
                continue
            sections.setdefault(current, []).append(line)
        return sections

    def _section_items(self, sections: dict[str, list[str]], keys: list[str]) -> list[str]:
        items: list[str] = []
        for title, lines in sections.items():
            if any(key in title for key in keys):
                items.extend(lines)
        return self._dedupe(items)[:8]

    def _candidate_lines(self, text: str) -> list[str]:
        normalized = re.sub(r"[•|]", "\n", text)
        lines = []
        for raw_line in normalized.splitlines():
            line = raw_line.strip(" -\t")
            if 12 <= len(line) <= 240:
                lines.append(line)
        return lines

    def _detect_local_contradiction(self, memory: InterviewMemory, latest_answer: str) -> str:
        lower = latest_answer.lower()
        prior = " ".join(memory.claims).lower()
        if "no internship" in lower and "intern" in prior:
            return "Candidate now says there was no internship, but prior claims mention internship experience."
        if "not interested in mba" in lower and ("mba" in prior or memory.candidate.goals):
            return "Candidate's current MBA motivation conflicts with earlier stated goals."
        return ""

    def _open_topics(self, memory: InterviewMemory) -> list[str]:
        desired = []
        if memory.candidate.education:
            desired.append("education")
        if memory.candidate.projects:
            desired.append("projects")
        if memory.candidate.internships:
            desired.append("internships")
        if memory.candidate.skills:
            desired.append("skills")
        if memory.candidate.career_goals or memory.candidate.goals:
            desired.append("why mba")
        desired.extend(["leadership", "business impact"])
        return [topic for topic in self._dedupe(desired) if topic not in memory.topics_covered]

    def _last_claim(self, memory: InterviewMemory) -> str:
        if memory.candidate_claims:
            return memory.candidate_claims[-1].text
        if memory.candidate.notable_resume_claims:
            return memory.candidate.notable_resume_claims[0]
        return ""

    def _first_available(self, *groups: list[str] | tuple[str, ...] | str) -> str:
        for group in groups:
            if isinstance(group, str):
                if group.strip():
                    return group.strip()
                continue
            for item in group:
                if item and item.strip():
                    return item.strip()
        return ""

    def _clean_anchor(self, value: str) -> str:
        return value.strip().rstrip(".")

    def _role_for(self, interviewer_id: InterviewerId) -> str:
        if interviewer_id == InterviewerId.academic:
            return "Academic Interviewer: academics, projects, internships, conceptual depth."
        if interviewer_id == InterviewerId.pressure:
            return "Pressure Interviewer: contradictions, vague claims, weak evidence, composure."
        return "MBA Interviewer: why MBA, leadership, business impact, career goals."

    def _parse_interviewer(self, value: Any) -> InterviewerId:
        try:
            return InterviewerId(str(value).lower())
        except ValueError:
            return InterviewerId.pressure

    def _as_string_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []

    def _merge_strings(self, existing: list[str], new_items: list[str]) -> list[str]:
        return self._dedupe([*existing, *new_items])[:20]

    def _dedupe(self, items: list[str]) -> list[str]:
        seen = set()
        result = []
        for item in items:
            compact = re.sub(r"\s+", " ", item).strip()
            key = compact.lower()
            if compact and key not in seen:
                seen.add(key)
                result.append(compact)
        return result

    def _evidence_excerpt(self, turns: list[str]) -> str:
        for turn in reversed(turns):
            if turn.strip():
                return turn.strip()[:240]
        return "Insufficient transcript evidence."

    def _topic_evidence(self, turns: list[str], keywords: list[str]) -> str:
        for turn in reversed(turns):
            if any(keyword in turn.lower() for keyword in keywords):
                return turn.strip()[:240]
        return "Insufficient transcript evidence."

    def _dimension(
        self,
        name: str,
        score: float | None,
        evidence: str,
        strengths: list[str],
        weaknesses: list[str],
        advice: str,
    ) -> DimensionScore:
        return DimensionScore(
            name=name,
            score=score,
            evidence=evidence,
            strengths=strengths,
            weaknesses=weaknesses,
            advice=advice,
        )

    def _verdict(self, overall: float) -> str:
        if overall >= 8.2:
            return "Strong Hire"
        if overall >= 6.8:
            return "Lean Hire"
        if overall >= 4.5:
            return "Lean Reject"
        return "Strong Reject"
