import json
import os
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any

from app.models import (
    BenchmarkCategory,
    CandidateClaim,
    CandidateProfile,
    CreateSessionRequest,
    DimensionScore,
    FollowUpOpportunity,
    FollowUpCoachingItem,
    InterviewMemory,
    InterviewReport,
    InterviewerObservation,
    InterviewerId,
    ProgressAnalysis,
    SpeakerSelection,
    TopicState,
    TopicStatus,
    TranscriptEvidence,
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

TOPIC_COVERAGE = [
    "academics",
    "projects",
    "internships",
    "leadership",
    "career goals",
    "MBA motivation",
    "current affairs",
    "strengths",
    "weaknesses",
]

TOPIC_ALIASES = {
    "education": "academics",
    "academic": "academics",
    "academics": "academics",
    "projects": "projects",
    "project": "projects",
    "internship": "internships",
    "internships": "internships",
    "work": "internships",
    "experience": "internships",
    "career_goals": "career goals",
    "career goals": "career goals",
    "career": "career goals",
    "why mba": "MBA motivation",
    "mba motivation": "MBA motivation",
    "business school": "MBA motivation",
    "business impact": "projects",
    "measurable impact": "projects",
    "current affairs": "current affairs",
    "general awareness": "current affairs",
    "strength": "strengths",
    "strengths": "strengths",
    "weakness": "weaknesses",
    "weaknesses": "weaknesses",
    "consistency": "weaknesses",
}

TOPIC_TO_INTERVIEWER = {
    "academics": InterviewerId.academic,
    "projects": InterviewerId.academic,
    "internships": InterviewerId.academic,
    "skills": InterviewerId.academic,
    "achievements": InterviewerId.pressure,
    "career goals": InterviewerId.mba,
    "MBA motivation": InterviewerId.mba,
    "leadership": InterviewerId.mba,
    "current affairs": InterviewerId.pressure,
    "strengths": InterviewerId.pressure,
    "weaknesses": InterviewerId.pressure,
}

TOPIC_DEPTH_LADDERS = {
    "projects": [
        "problem",
        "architecture",
        "technical decisions",
        "tradeoffs",
        "business impact",
    ],
    "academics": [
        "conceptual foundation",
        "application",
        "edge cases",
        "tradeoffs",
        "business relevance",
    ],
    "internships": [
        "role scope",
        "ownership",
        "decisions",
        "stakeholder tradeoffs",
        "measured impact",
    ],
    "leadership": [
        "situation",
        "people challenge",
        "decision",
        "conflict or tradeoff",
        "learning",
    ],
    "career goals": [
        "target role",
        "reasoning",
        "skills gap",
        "market understanding",
        "long-term coherence",
    ],
    "MBA motivation": [
        "why now",
        "skills gap",
        "school fit",
        "post-MBA path",
        "alternative paths",
    ],
    "current affairs": [
        "awareness",
        "stakeholders",
        "economic reasoning",
        "tradeoffs",
        "managerial implication",
    ],
    "strengths": [
        "claim",
        "evidence",
        "replicability",
        "limits",
        "MBA relevance",
    ],
    "weaknesses": [
        "self-awareness",
        "specific incident",
        "root cause",
        "corrective action",
        "progress evidence",
    ],
}

QUALITY_RULES = [
    "New Topic",
    "Deeper Investigation",
    "Contradiction Challenge",
    "Business Impact Analysis",
    "Leadership Evaluation",
    "MBA Fit Assessment",
]

# Hard caps on unbounded InterviewMemory lists.
# These lists are serialized to JSON on every save_memory() call — without
# caps they grow by 2-3 items per turn and inflate the Supabase payload.
_MAX_OBSERVATIONS = 20   # interviewer_observations per session
_MAX_FOLLOW_UPS   = 10   # unanswered_follow_up_opportunities per session
_MAX_CLAIMS       = 30   # candidate_claims per session


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
        self._ensure_topic_states(memory)
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
            selected_topic="projects" if memory.candidate.projects else "academics",
        )

    def update_memory(self, memory: InterviewMemory, latest_answer: str) -> None:
        self._ensure_topic_states(memory)
        latest_answer = self._sanitize_candidate_text(latest_answer)
        if self.client:
            updated = self._update_memory_with_groq(memory, latest_answer)
            if updated:
                self._merge_memory_update(memory, updated)
                model_topics = [
                    self._canonical_topic(topic)
                    for topic in self._as_string_list(updated.get("topics_covered"))
                ]
                self._update_topic_evidence(
                    memory,
                    latest_answer,
                    self._dedupe(model_topics + self._topics_from_answer(latest_answer)),
                )
                return

        self._update_memory_locally(memory, latest_answer)

    def select_speaker(self, memory: InterviewMemory) -> SpeakerSelection:
        self._ensure_topic_states(memory)

        # ── Hard balance rule: force any silent panelist in by turn 3 ──
        forced = self._force_silent_panelist(memory)
        if forced:
            forced.topic = self._viable_selected_topic(memory, forced.topic)
            memory.last_speaker_reason = forced.reason
            return forced

        if self.client:
            selection = self._select_speaker_with_groq(memory)
            if selection:
                selection.topic = self._viable_selected_topic(memory, selection.topic)
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
        selected_topic: str = "",
    ) -> str:
        self._ensure_topic_states(memory)
        selected_topic = self._canonical_topic(selected_topic or self._topic_from_reason(selection_reason))
        latest_answer = self._sanitize_candidate_text(latest_answer)
        if self.client:
            question = self._generate_question_with_groq(
                memory, interviewer_id, latest_answer, selection_reason, opening_topic, selected_topic
            )
            if question:
                return self._finalize_question(memory, question, interviewer_id, selected_topic, latest_answer)

        return self._generate_question_locally(
            memory, interviewer_id, latest_answer, selection_reason, opening_topic, selected_topic
        )

    def generate_report(self, memory: InterviewMemory) -> InterviewReport:
        self._ensure_topic_states(memory)
        if self.client:
            report = self._generate_report_with_groq(memory)
            if report:
                return report

        return self._generate_report_locally(memory)

    def _viable_selected_topic(self, memory: InterviewMemory, topic: str) -> str:
        if topic:
            canonical = self._canonical_topic(topic)
            state = self._topic_state(memory, canonical)
            if state.status not in {TopicStatus.closed, TopicStatus.sufficiently_tested}:
                return canonical
        open_topics = self._open_topics(memory)
        if open_topics:
            return open_topics[0]
        return self._least_tested_reopenable_topic(memory) or "projects"

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
            if not self._is_bad_anchor(line)
            and any(
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
        topics = [self._canonical_topic(topic) for topic in self._as_string_list(data.get("topics_covered"))]
        topics = [topic for topic in topics if topic]
        memory.topics_covered = self._merge_strings(memory.topics_covered, topics)
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
        # Keep only the most recent observations to bound memory/JSON size.
        if len(memory.interviewer_observations) > _MAX_OBSERVATIONS:
            memory.interviewer_observations = memory.interviewer_observations[-_MAX_OBSERVATIONS:]

        for raw_claim in data.get("candidate_claims") or []:
            if isinstance(raw_claim, dict) and raw_claim.get("text"):
                claim_text = self._sanitize_candidate_text(str(raw_claim["text"]))
                if not claim_text or self._is_bad_anchor(claim_text):
                    continue
                claim = CandidateClaim(
                    text=claim_text[:220],
                    source="interview",
                    evidence=self._sanitize_candidate_text(str(raw_claim.get("evidence") or claim_text))[:220],
                    challenged=bool(raw_claim.get("challenged", False)),
                )
                if claim.text not in memory.claims:
                    memory.candidate_claims.append(claim)
        if len(memory.candidate_claims) > _MAX_CLAIMS:
            memory.candidate_claims = memory.candidate_claims[-_MAX_CLAIMS:]

        for raw_follow_up in data.get("unanswered_follow_up_opportunities") or []:
            if not isinstance(raw_follow_up, dict):
                continue
            topic = self._canonical_topic(str(raw_follow_up.get("topic") or "").strip())
            reason = str(raw_follow_up.get("reason") or "").strip()
            if not topic or not reason:
                continue
            interviewer = self._parse_interviewer(raw_follow_up.get("suggested_interviewer"))
            opportunity = FollowUpOpportunity(
                topic=topic[:80],
                reason=reason[:180],
                suggested_interviewer=interviewer,
                source_claim=self._sanitize_candidate_text(str(raw_follow_up.get("source_claim") or ""))[:220],
            )
            if opportunity.reason not in [item.reason for item in memory.unanswered_follow_up_opportunities]:
                memory.unanswered_follow_up_opportunities.append(opportunity)
        if len(memory.unanswered_follow_up_opportunities) > _MAX_FOLLOW_UPS:
            memory.unanswered_follow_up_opportunities = memory.unanswered_follow_up_opportunities[-_MAX_FOLLOW_UPS:]

    def _update_memory_locally(self, memory: InterviewMemory, latest_answer: str) -> None:
        lower = latest_answer.lower()
        topics = []
        topic_keywords = {
            "academics": ["college", "cgpa", "degree", "semester", "academic", "subject", "course"],
            "projects": ["project", "built", "created", "developed"],
            "internships": ["intern", "trainee", "work", "company"],
            "MBA motivation": ["mba", "management", "business school"],
            "career goals": ["career", "product", "consulting", "strategy", "goal"],
            "leadership": ["lead", "team", "organized", "managed"],
            "current affairs": ["economy", "policy", "market", "inflation", "budget", "geopolitics"],
            "strengths": ["strength", "good at", "strong"],
            "weaknesses": ["weakness", "improve", "struggle"],
        }
        for topic, keywords in topic_keywords.items():
            if any(keyword in lower for keyword in keywords):
                topics.append(topic)
        memory.topics_covered = self._merge_strings(memory.topics_covered, topics)
        if not topics:
            last_topic = self._last_interviewer_topic(memory)
            if last_topic:
                topics.append(last_topic)
        self._update_topic_evidence(memory, latest_answer, topics)

        first_sentence = latest_answer.split(".")[0].strip()
        first_sentence = self._sanitize_candidate_text(first_sentence)
        if first_sentence and not self._is_bad_anchor(first_sentence) and first_sentence not in memory.claims:
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
                    topic=topics[0] if topics else "weaknesses",
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
                    topic=topics[0] if topics else "projects",
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
                    topic="weaknesses",
                    reason="Candidate appears to have made inconsistent claims that should be challenged.",
                    suggested_interviewer=InterviewerId.pressure,
                    source_claim=contradiction,
                )
            )

        # Cap unbounded lists after local update.
        if len(memory.unanswered_follow_up_opportunities) > _MAX_FOLLOW_UPS:
            memory.unanswered_follow_up_opportunities = memory.unanswered_follow_up_opportunities[-_MAX_FOLLOW_UPS:]
        if len(memory.candidate_claims) > _MAX_CLAIMS:
            memory.candidate_claims = memory.candidate_claims[-_MAX_CLAIMS:]

    def _select_speaker_with_groq(self, memory: InterviewMemory) -> SpeakerSelection | None:
        counts = Counter(str(item.value) for item in memory.speaker_history)
        # Build a note about who is underrepresented
        silent = [p for p in ["academic", "pressure", "mba"] if counts.get(p, 0) == 0]
        balance_hint = (
            f"IMPORTANT: The following panelists have not yet spoken: {silent}. "
            "You MUST give one of them the next turn before continuing with others."
            if silent else
            "All three panelists have spoken. Continue based on memory signals."
        )
        system = (
            "You select the next speaker in an IIM admissions panel. Return only JSON. "
            "Do not use round-robin, but ensure all three panelists get meaningful turns. "
            f"{balance_hint}"
        )
        user = json.dumps(
            {
                "candidate_profile": self._profile_payload(memory.candidate),
                "memory": self._memory_payload(memory),
                "speaker_counts": counts,
                "required_shape": {
                    "speaker": "academic|pressure|mba",
                    "reason": "selection reason",
                    "topic": "topic to test next",
                },
            }
        )
        data = self._chat_json(system, user)
        if not data:
            return None
        speaker = self._parse_interviewer(data.get("speaker"))
        reason = str(data.get("reason") or "Selected from shared interview memory.").strip()
        topic = str(data.get("topic") or "").strip()
        return SpeakerSelection(speaker=speaker, reason=reason[:220], topic=topic[:80])

    def _select_speaker_locally(self, memory: InterviewMemory) -> SpeakerSelection:
        if memory.contradictions:
            return SpeakerSelection(
                speaker=InterviewerId.pressure,
                reason="Open contradiction exists and should be stress-tested before moving on.",
                topic="consistency",
            )

        if memory.unanswered_follow_up_opportunities:
            opportunity = self._next_viable_follow_up(memory)
            if opportunity:
                return SpeakerSelection(
                    speaker=opportunity.suggested_interviewer,
                    reason=f"Follow up on {opportunity.topic}: {opportunity.reason}",
                    topic=opportunity.topic,
                )

        # Rotate across panelists: pick the one with fewest turns from the open topics
        open_topics = self._open_topics(memory)
        if open_topics:
            counts = Counter(memory.speaker_history)
            # Score each open topic by (speaker_turn_count, topic_index)
            best_topic = min(
                open_topics,
                key=lambda t: (
                    counts[TOPIC_TO_INTERVIEWER.get(t, InterviewerId.mba)],
                    open_topics.index(t),
                ),
            )
            return SpeakerSelection(
                speaker=TOPIC_TO_INTERVIEWER.get(best_topic, InterviewerId.mba),
                reason=f"{best_topic} is under-tested; selecting the panelist with the fewest turns.",
                topic=best_topic,
            )

        reopenable = self._least_tested_reopenable_topic(memory)
        if reopenable:
            return SpeakerSelection(
                speaker=TOPIC_TO_INTERVIEWER.get(reopenable, InterviewerId.mba),
                reason=f"Use a different angle on {reopenable} to complete depth without repetition.",
                topic=reopenable,
            )

        counts = Counter(memory.speaker_history)
        candidates = [InterviewerId.academic, InterviewerId.pressure, InterviewerId.mba]
        speaker = min(candidates, key=lambda item: counts[item])
        return SpeakerSelection(
            speaker=speaker,
            reason="Balance the panel after resolving the available memory signals.",
            topic="panel balance",
        )

    def _force_silent_panelist(self, memory: InterviewMemory) -> SpeakerSelection | None:
        """After turn 2, force any panelist who has never spoken to take the next turn."""
        if memory.turn_count < 2:
            return None
        counts = Counter(memory.speaker_history)
        # Priority order: MBA first (most often starved), then pressure
        for candidate in [InterviewerId.mba, InterviewerId.pressure, InterviewerId.academic]:
            if counts[candidate] == 0:
                topic_map = {
                    InterviewerId.mba: "MBA motivation",
                    InterviewerId.pressure: "strengths",
                    InterviewerId.academic: "academics",
                }
                topic = topic_map[candidate]
                return SpeakerSelection(
                    speaker=candidate,
                    reason=f"{candidate.value} panelist has not spoken yet — panel balance requires their turn.",
                    topic=topic,
                )
        return None

    def _generate_question_with_groq(
        self,
        memory: InterviewMemory,
        interviewer_id: InterviewerId,
        latest_answer: str,
        selection_reason: str,
        opening_topic: str,
        selected_topic: str,
    ) -> str | None:
        # Decide whether this turn should "pick up" from the candidate's last answer
        # ~every 3rd question should feel conversationally linked.
        should_link = bool(latest_answer) and (memory.turn_count % 3 == 0)
        link_instruction = (
            "LINKING TURN: Begin your question by briefly referencing ONE specific word or phrase "
            "the candidate just used (e.g. 'You mentioned X — drilling into that...'). "
            "Then pivot naturally to your evaluation goal. Do NOT just paraphrase their whole answer."
            if should_link else
            "Do not open by repeating what the candidate said. Go directly to your question."
        )
        system = (
            f"You are the {interviewer_id.value} interviewer in PANELIQ, an IIM-style MBA "
            "admissions panel. Ask exactly one concise spoken question. "
            "Use the shared memory and resume. Continue another interviewer's thread when useful. "
            "Do not explain your reasoning. Do not ask generic chatbot questions. "
            "Never quote candidate filler or raw transcript fragments. Every question must be professional "
            "and must satisfy one of: New Topic, Deeper Investigation, Contradiction Challenge, "
            f"Business Impact Analysis, Leadership Evaluation, MBA Fit Assessment. {link_instruction}"
        )
        topic_state = self._topic_state(memory, selected_topic)
        next_depth = min(topic_state.depth_level + 1, 5)
        user = json.dumps(
            {
                "interviewer_role": self._role_for(interviewer_id),
                "candidate_profile": self._profile_payload(memory.candidate),
                "interview_memory": self._memory_payload(memory),
                "latest_candidate_response": latest_answer,
                "speaker_selection_reason": selection_reason,
                "selected_topic": selected_topic,
                "required_next_depth": next_depth,
                "depth_focus": self._depth_focus(selected_topic, next_depth),
                "asked_questions": memory.asked_questions[-12:],
                "quality_rules": QUALITY_RULES,
                "banned_patterns": [
                    "Tell me more",
                    "I don't know what to answer",
                    "what to answer",
                    "repeat the same question in different words",
                    "verbatim candidate speech",
                ],
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
        selected_topic: str,
    ) -> str:
        topic = self._canonical_topic(selected_topic or self._topic_from_reason(selection_reason))
        topic_state = self._topic_state(memory, topic)
        next_depth = min(topic_state.depth_level + 1, 5)
        depth_focus = self._depth_focus(topic, next_depth)
        claim = self._safe_question_anchor(self._last_claim(memory) or opening_topic or "your background")
        resume_anchor = self._anchor_for_topic(memory, topic, claim, opening_topic)

        # ~every 3rd question, build a natural bridge from the candidate's last answer
        should_link = bool(latest_answer) and (memory.turn_count % 3 == 0)
        link_prefix = self._extract_answer_hook(latest_answer) if should_link else ""

        if interviewer_id == InterviewerId.academic:
            memory.interviewer_observations.append(
                InterviewerObservation(
                    interviewer_id=interviewer_id,
                    note="Testing resume-grounded academic/project depth.",
                    evidence=self._clean_anchor(resume_anchor)[:220],
                )
            )
            if topic == "academics":
                body = (
                    f"On {self._safe_question_anchor(resume_anchor)}, take us to the {depth_focus} level: "
                    "which concept matters most, where is it applied, and what limitation should a manager know?"
                )
            else:
                body = (
                    f"Your resume mentions {self._safe_question_anchor(resume_anchor)}. At the {depth_focus} level, "
                    "what exactly did you build or decide, and what trade-off did that create?"
                )
            question = (link_prefix + body) if link_prefix else body
            return self._finalize_question(memory, question, interviewer_id, topic, latest_answer)

        if interviewer_id == InterviewerId.pressure:
            memory.interviewer_observations.append(
                InterviewerObservation(
                    interviewer_id=interviewer_id,
                    note="Challenging a claim for ownership, specificity, and evidence.",
                    evidence=claim[:220],
                )
            )
            if memory.contradictions:
                body = (
                    f"There is a consistency issue in your earlier answers. At the {depth_focus} level, "
                    "which version should the panel rely on, and what evidence supports it?"
                )
            elif topic == "weaknesses":
                body = (
                    "Choose one genuine weakness from a recent situation. What caused it, what corrective "
                    "action have you taken, and what evidence shows progress?"
                )
            elif topic == "current affairs":
                body = (
                    "Pick one current business or economic issue you have followed recently. What are the "
                    "stakeholder trade-offs, and what managerial judgment would you make?"
                )
            else:
                pressure_anchor = self._pressure_anchor(memory)
                if not pressure_anchor:
                    body = (
                        "Walk us through one concrete project or role where you personally drove an outcome. "
                        f"At the {depth_focus} level, what exact decision did you make, and how was success measured?"
                    )
                else:
                    anchor = self._safe_question_anchor(pressure_anchor)
                    body = (
                        f"I want to examine ownership around {anchor}. "
                        f"At the {depth_focus} level, "
                        "what exactly did you personally contribute — not the team — and what evidence shows that?"
                    )
            question = (link_prefix + body) if link_prefix else body
            return self._finalize_question(memory, question, interviewer_id, topic, latest_answer)

        # MBA interviewer
        memory.interviewer_observations.append(
            InterviewerObservation(
                interviewer_id=interviewer_id,
                note="Revisiting the thread for business impact and MBA fit.",
                evidence=claim[:220],
            )
        )
        if topic == "MBA motivation":
            body = (
                f"At the {depth_focus} level, why is an MBA necessary now rather than learning on the job, "
                "and what specific gap are you trying to close?"
            )
        elif topic == "career goals":
            body = (
                f"At the {depth_focus} level, connect your short-term role, target industry, and long-term goal. "
                "What would make that path credible to this panel?"
            )
        elif topic == "leadership":
            body = (
                f"At the {depth_focus} level, describe a leadership decision where people disagreed with you. "
                "What trade-off did you choose, and what changed afterwards?"
            )
        else:
            body = (
                f"Let us connect {claim} to management. At the {depth_focus} level, what metric or stakeholder "
                "outcome changed, and what would you do differently now?"
            )
        question = (link_prefix + body) if link_prefix else body
        return self._finalize_question(memory, question, interviewer_id, topic, latest_answer)

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
                    "verdict": "Likely Convert|Borderline|Needs Improvement",
                    "overall_score": "number from 1-10",
                    "executive_summary": "concise panel-level summary grounded in transcript evidence",
                    "strengths": ["evidence-backed strengths"],
                    "weaknesses": ["evidence-backed weaknesses"],
                    "panel_concerns": ["major concerns"],
                    "feedback_to_candidate": "short summary",
                    "transcript_evidence": [
                        {
                            "topic": "covered topic",
                            "evidence": "short transcript-backed evidence",
                            "panel_interpretation": "what the panel inferred",
                        }
                    ],
                    "recommended_improvements": ["specific improvements for next interview"],
                    "panel_comments": ["realistic panel comments"],
                    "benchmarking": [
                        {
                            "category": "Typical IIM Convert Candidate|Strong IIM ABC Candidate|Average CAT Aspirant",
                            "communication": "percentile range",
                            "leadership": "percentile range",
                            "business_awareness": "percentile range",
                            "academic_depth": "percentile range",
                            "mba_fit": "percentile range",
                            "notes": "preparedness comparison, not admission prediction",
                        }
                    ],
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
                verdict=self._normalize_verdict(str(data.get("verdict") or "")),
                overall_score=float(data.get("overall_score") or 0),
                executive_summary=str(data.get("executive_summary") or data.get("feedback_to_candidate") or ""),
                strengths=self._as_string_list(data.get("strengths")),
                weaknesses=self._as_string_list(data.get("weaknesses")),
                panel_concerns=self._as_string_list(data.get("panel_concerns")),
                dimensions=dimensions,
                transcript_evidence=self._parse_transcript_evidence(data.get("transcript_evidence")),
                recommended_improvements=self._as_string_list(data.get("recommended_improvements")),
                panel_comments=self._as_string_list(data.get("panel_comments")),
                benchmarking=self._parse_benchmarks(data.get("benchmarking")),
                mba_readiness_assessment=str(
                    data.get("mba_readiness_assessment")
                    or "MBA readiness is based only on the evidence demonstrated in this interview."
                ),
                coaching_items=self.generate_coaching_items(
                    self._as_string_list(data.get("weaknesses")),
                    self._parse_transcript_evidence(data.get("transcript_evidence")),
                ),
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
        tested_topics = set(memory.topics_covered)
        evidence_quote = self._evidence_excerpt(candidate_turns)
        transcript_evidence = self._build_transcript_evidence(memory, candidate_turns)
        has_candidate_evidence = bool(candidate_turns)
        has_specific_evidence = any(
            any(marker in turn.lower() for marker in ["i ", "my ", "because", "trade", "impact", "%"])
            or any(char.isdigit() for char in turn)
            for turn in candidate_turns
        )
        communication_score = 7.0 if has_specific_evidence else 5.5 if has_candidate_evidence else None

        dimensions = [
            self._dimension(
                "Communication clarity",
                communication_score,
                evidence_quote,
                ["Used concrete transcript evidence in answers."] if has_specific_evidence else [],
                [] if has_specific_evidence else ["Transcript lacks enough specific evidence."],
                "Use a direct answer, one example, and a quantified result.",
            ),
            self._dimension(
                "Academic depth",
                7.0 if {"academics", "projects"} & tested_topics and has_candidate_evidence else None,
                self._topic_evidence(
                    candidate_turns,
                    ["project", "built", "dashboard", "salesforce", "college", "cgpa", "degree"],
                ),
                ["Discussed academic or project material."] if {"academics", "projects"} & tested_topics else [],
                [] if {"academics", "projects"} & tested_topics else ["Academic depth was not sufficiently tested."],
                "Prepare one project and one academic subject at concept, trade-off, and impact levels.",
            ),
            self._dimension(
                "Business awareness",
                7.0 if "current affairs" in tested_topics or self._contains_any(transcript_text, ["revenue", "cost", "customer", "market", "profit"]) else None,
                self._topic_evidence(candidate_turns, ["revenue", "cost", "customer", "market", "profit"]),
                ["Connected answers to business impact."] if self._contains_any(transcript_text, ["revenue", "cost", "customer", "market", "profit"]) else [],
                [] if self._contains_any(transcript_text, ["revenue", "cost", "customer", "market", "profit"]) else ["Business impact was not demonstrated clearly."],
                "Translate projects into customer, cost, revenue, risk, and stakeholder language.",
            ),
            self._dimension(
                "Leadership potential",
                7.0 if "leadership" in tested_topics or self._contains_any(transcript_text, ["led", "team", "owned", "managed"]) else None,
                self._topic_evidence(candidate_turns, ["lead", "team", "managed", "organized"]),
                ["Mentioned leadership or team ownership."] if "leadership" in tested_topics else [],
                [] if "leadership" in tested_topics else ["Leadership evidence was not sufficiently tested."],
                "Use one incident showing conflict, decision-making, and measurable team outcome.",
            ),
            self._dimension(
                "Career clarity",
                7.0 if {"career goals", "MBA motivation"} & tested_topics or "mba" in transcript_text.lower() else None,
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
            self._dimension(
                "Answer structure",
                7.0 if has_specific_evidence and not memory.contradictions else 5.5 if has_candidate_evidence else None,
                evidence_quote,
                ["Answers contained claim, action, or impact evidence."] if has_specific_evidence else [],
                memory.contradictions[:2] or ([] if has_specific_evidence else ["Answers need clearer evidence structure."]),
                "Use claim, context, action, result, and learning for each answer.",
            ),
            self._dimension(
                "Overall admissions readiness",
                None,
                evidence_quote,
                memory.strengths[:2],
                memory.weaknesses[:2],
                "Prepare resume anchors at academic, pressure, and MBA-fit depth.",
            ),
        ]

        scored = [item.score for item in dimensions if item.score is not None]
        overall = round(sum(scored) / len(scored), 1) if scored else 0.0
        verdict = self._verdict(overall)
        weaknesses = memory.weaknesses or ["The transcript does not yet contain enough evidence for a rigorous evaluation."]
        recommended = self._recommended_improvements(memory, dimensions)
        panel_comments = self._panel_comments(memory, overall)
        executive_summary = self._executive_summary(overall, tested_topics, evidence_quote)

        return InterviewReport(
            session_id=memory.session_id,
            verdict=verdict,
            overall_score=overall,
            executive_summary=executive_summary,
            strengths=memory.strengths[:5],
            weaknesses=weaknesses[:5],
            panel_concerns=(memory.contradictions + weaknesses)[:5],
            dimensions=dimensions,
            transcript_evidence=transcript_evidence,
            recommended_improvements=recommended,
            panel_comments=panel_comments,
            benchmarking=self._benchmarking(overall, dimensions),
            mba_readiness_assessment=self._mba_readiness_assessment(overall, dimensions),
            coaching_items=self.generate_coaching_items(weaknesses[:5], transcript_evidence),
            feedback_to_candidate=(
                "This report uses only transcript evidence. Strengthen the next attempt with concrete "
                "incidents, quantified outcomes, and clearer MBA linkage."
            ),
            transcript=memory.transcript,
        )

    def generate_coaching_items(
        self, weaknesses: list[str], evidence: list[TranscriptEvidence] | None = None
    ) -> list[FollowUpCoachingItem]:
        evidence = evidence or []
        if self.client and weaknesses:
            generated = self._generate_coaching_with_groq(weaknesses, evidence)
            if generated:
                return generated
        return [self._local_coaching_item(weakness, evidence) for weakness in weaknesses[:6]]

    def analyze_progress(self, reports: list[InterviewReport]) -> ProgressAnalysis:
        if len(reports) < 2:
            latest = reports[-1] if reports else None
            return ProgressAnalysis(
                growth_summary=(
                    "Complete another interview to unlock trend analysis."
                    if latest
                    else "No completed reports are available yet."
                ),
                next_focus_areas=(latest.weaknesses[:3] if latest else []),
                recurring_weaknesses=(latest.weaknesses[:3] if latest else []),
            )
        first = reports[0]
        latest = reports[-1]
        first_scores = self._dimension_score_map(first)
        latest_scores = self._dimension_score_map(latest)
        improved = []
        declining = []
        for name, latest_score in latest_scores.items():
            previous = first_scores.get(name)
            if latest_score is None or previous is None:
                continue
            delta = latest_score - previous
            if delta >= 0.5:
                improved.append(f"{name} improved by {delta:.1f} points.")
            elif delta <= -0.5:
                declining.append(f"{name} declined by {abs(delta):.1f} points.")
        weakness_counts = Counter(
            self._normalize_for_compare(item)
            for report in reports
            for item in report.weaknesses
            if item
        )
        recurring = [
            weakness for weakness in latest.weaknesses
            if weakness_counts[self._normalize_for_compare(weakness)] >= 2
        ]
        delta = latest.overall_score - first.overall_score
        direction = "up" if delta >= 0 else "down"
        return ProgressAnalysis(
            improved_areas=improved[:6],
            declining_areas=declining[:6],
            recurring_weaknesses=recurring[:6],
            growth_summary=f"Overall score moved {direction} by {abs(delta):.1f} points across {len(reports)} completed interviews.",
            next_focus_areas=(recurring or latest.weaknesses or latest.recommended_improvements)[:5],
        )

    def compare_reports(self, left: InterviewReport, right: InterviewReport) -> dict:
        left_scores = self._dimension_score_map(left)
        right_scores = self._dimension_score_map(right)
        delta_overall = right.overall_score - left.overall_score

        changes = [f"Overall score changed by {delta_overall:+.1f} points ({left.overall_score:.1f} → {right.overall_score:.1f})."]
        improved = []
        remaining = []
        observations = []
        regressions = []

        for name, right_score in right_scores.items():
            left_score = left_scores.get(name)
            if right_score is None or left_score is None:
                continue
            delta = right_score - left_score
            if abs(delta) >= 0.3:
                changes.append(f"{name}: {left_score:.1f} → {right_score:.1f} ({delta:+.1f}).")
            if delta >= 0.5:
                improved.append(name)
            elif delta <= -0.5:
                regressions.append(f"{name} dropped by {abs(delta):.1f} points.")

        left_weak = {self._normalize_for_compare(item) for item in left.weaknesses}
        for weakness in right.weaknesses:
            if self._normalize_for_compare(weakness) in left_weak:
                remaining.append(weakness)

        observations.extend(right.panel_comments[:4])
        observations.extend(right.panel_concerns[:3])

        # ── IIM Benchmark Gap Analysis ──────────────────────────────────────────
        IIM_REFS: dict[str, dict[str, tuple[float, float]]] = {
            "Average CAT Aspirant":         {"Communication clarity": (5.0, 6.2), "Leadership potential": (4.8, 6.0), "Business awareness": (4.5, 5.8), "Academic depth": (5.2, 6.5), "Career clarity": (4.8, 6.0)},
            "Typical IIM Convert Candidate": {"Communication clarity": (6.5, 7.5), "Leadership potential": (6.2, 7.2), "Business awareness": (6.0, 7.2), "Academic depth": (6.5, 7.8), "Career clarity": (6.5, 7.5)},
            "Strong IIM ABC Candidate":      {"Communication clarity": (7.8, 9.0), "Leadership potential": (7.5, 9.0), "Business awareness": (7.5, 8.8), "Academic depth": (7.8, 9.0), "Career clarity": (7.8, 9.2)},
        }

        benchmark_gaps: list[dict] = []
        for profile_label, refs in IIM_REFS.items():
            dims = []
            for dim_name, (ref_lo, ref_hi) in refs.items():
                user_score = right_scores.get(dim_name)
                if user_score is None:
                    continue
                ref_mid = (ref_lo + ref_hi) / 2
                gap = round(user_score - ref_mid, 1)
                dims.append({
                    "dimension": dim_name,
                    "your_score": round(user_score, 1),
                    "ref_range": f"{ref_lo}–{ref_hi}",
                    "gap": gap,
                    "status": "above" if gap > 0.3 else "below" if gap < -0.3 else "within",
                })
            benchmark_gaps.append({"profile": profile_label, "dimensions": dims})

        return {
            "score_changes":       changes[:8],
            "improved_areas":      improved[:8],
            "remaining_weaknesses": remaining[:8],
            "regressions":         regressions[:6],
            "panel_observations":  self._dedupe(observations)[:8],
            "benchmark_gaps":      benchmark_gaps,
        }

    def _build_transcript_evidence(
        self, memory: InterviewMemory, candidate_turns: list[str]
    ) -> list[TranscriptEvidence]:
        items: list[TranscriptEvidence] = []
        for state in memory.topic_states:
            if not state.evidence_collected:
                continue
            evidence = state.evidence_collected[-1]
            items.append(
                TranscriptEvidence(
                    topic=state.topic_name,
                    evidence=evidence,
                    panel_interpretation=self._interpret_evidence(state.topic_name, evidence),
                )
            )
        if not items and candidate_turns:
            items.append(
                TranscriptEvidence(
                    topic="general interview evidence",
                    evidence=self._evidence_excerpt(candidate_turns),
                    panel_interpretation="The panel had limited but usable answer evidence for initial feedback.",
                )
            )
        return items[:8]

    def _interpret_evidence(self, topic: str, evidence: str) -> str:
        lower = evidence.lower()
        if any(char.isdigit() for char in evidence):
            return "Candidate used a concrete detail or number, which strengthens credibility."
        if topic in {"projects", "internships"} and self._contains_any(lower, ["trade", "decision", "because"]):
            return "Candidate showed some decision reasoning, though impact should be quantified."
        if topic in {"MBA motivation", "career goals"}:
            return "Candidate gave career or MBA-fit material that should be made more specific."
        if topic == "leadership":
            return "Candidate offered leadership material that needs clearer conflict, action, and outcome."
        return "Evidence was present but should be made sharper and more measurable."

    def _recommended_improvements(
        self, memory: InterviewMemory, dimensions: list[DimensionScore]
    ) -> list[str]:
        recommendations = [
            "Prepare one project at five depths: problem, architecture, decisions, tradeoffs, and business impact.",
            "For every major claim, add a metric, stakeholder, trade-off, and personal contribution.",
            "Practice concise answers using claim, context, action, result, and learning.",
        ]
        weak_dimensions = [item.name for item in dimensions if item.score is None or (item.score or 0) < 6.5]
        if "Business awareness" in weak_dimensions:
            recommendations.append("Read one current business issue daily and explain who gains, who loses, and why.")
        if "Leadership potential" in weak_dimensions:
            recommendations.append("Prepare a leadership story with disagreement, decision logic, and measurable outcome.")
        if memory.contradictions:
            recommendations.append("Resolve inconsistent resume or interview claims before the next mock.")
        return self._dedupe(recommendations)[:6]

    def _panel_comments(self, memory: InterviewMemory, overall: float) -> list[str]:
        comments = []
        if overall >= 7:
            comments.append("Panel sees a credible candidate, but wants sharper quantification and business framing.")
        elif overall > 0:
            comments.append("Panel needs stronger evidence before forming a positive admissions-style view.")
        else:
            comments.append("Panel could not evaluate readiness because transcript evidence was too limited.")
        for state in memory.topic_states:
            if state.status == TopicStatus.closed:
                comments.append(f"{state.topic_name}: sufficiently tested with usable evidence.")
            elif state.questions_asked and not state.evidence_collected:
                comments.append(f"{state.topic_name}: asked, but answer evidence remained thin.")
        return comments[:6]

    def _executive_summary(self, overall: float, tested_topics: set[str], evidence_quote: str) -> str:
        coverage = ", ".join(sorted(tested_topics)) if tested_topics else "limited topic coverage"
        if overall >= 7:
            assessment = "The candidate showed interview readiness in parts"
        elif overall > 0:
            assessment = "The candidate showed partial readiness but needs stronger evidence"
        else:
            assessment = "The transcript was too thin for a rigorous readiness judgment"
        return f"{assessment}. Covered areas: {coverage}. Representative evidence: {evidence_quote}"

    def _benchmarking(
        self, overall: float, dimensions: list[DimensionScore]
    ) -> list[BenchmarkCategory]:
        # Fixed reference score bands per profile — these represent interview preparedness
        # of candidates in that cohort, NOT derived from the user's score.
        # The frontend uses these alongside user dimension scores for gap analysis.
        PROFILES: dict[str, dict[str, str]] = {
            "Average CAT Aspirant": {
                "Communication clarity":  "5.0–6.2",
                "Leadership potential":   "4.8–6.0",
                "Business awareness":     "4.5–5.8",
                "Academic depth":         "5.2–6.5",
                "Career clarity":         "4.8–6.0",
                "notes": "Typical first-attempt CAT aspirant with limited structured preparation.",
            },
            "Typical IIM Convert Candidate": {
                "Communication clarity":  "6.5–7.5",
                "Leadership potential":   "6.2–7.2",
                "Business awareness":     "6.0–7.2",
                "Academic depth":         "6.5–7.8",
                "Career clarity":         "6.5–7.5",
                "notes": "A candidate who typically converts an IIM call through structured, evidence-backed answers.",
            },
            "Strong IIM ABC Candidate": {
                "Communication clarity":  "7.8–9.0",
                "Leadership potential":   "7.5–9.0",
                "Business awareness":     "7.5–8.8",
                "Academic depth":         "7.8–9.0",
                "Career clarity":         "7.8–9.2",
                "notes": "Top-tier IIM interview performance with concise evidence, structured leadership stories, and sharp business linkage.",
            },
        }

        scores = {item.name: item.score for item in dimensions}
        comm  = scores.get("Communication clarity")
        lead  = scores.get("Leadership potential")
        biz   = scores.get("Business awareness")
        acad  = scores.get("Academic depth")
        # Career clarity is the closest dimension to MBA fit; fall back to overall if absent.
        career = scores.get("Career clarity") or scores.get("Career Clarity")

        results: list[BenchmarkCategory] = []
        for label, ref in PROFILES.items():
            results.append(
                BenchmarkCategory(
                    category=label,  # type: ignore[arg-type]
                    communication=ref["Communication clarity"],
                    leadership=ref["Leadership potential"],
                    business_awareness=ref["Business awareness"],
                    academic_depth=ref["Academic depth"],
                    mba_fit=ref["Career clarity"],
                    notes=ref["notes"],
                )
            )
        return results

    def _generate_coaching_with_groq(
        self, weaknesses: list[str], evidence: list[TranscriptEvidence]
    ) -> list[FollowUpCoachingItem] | None:
        system = (
            "You are an IIM admissions mentor. Return only JSON. "
            "Generate coaching for demonstrated weaknesses without inventing candidate facts."
        )
        user = json.dumps(
            {
                "weaknesses": weaknesses[:6],
                "transcript_evidence": [item.model_dump(mode="json") for item in evidence[:8]],
                "required_shape": {
                    "coaching_items": [
                        {
                            "weakness": "specific weakness",
                            "question": "realistic follow-up interview question",
                            "why_panel_would_ask": "why an IIM panel would ask it",
                            "ideal_answer": "MBA-level answer structure, not fabricated personal facts",
                            "skills_being_evaluated": ["skills"],
                            "improvement_advice": "specific practice advice",
                        }
                    ]
                },
            }
        )
        data = self._chat_json(system, user, temperature=0.3)
        items = []
        for raw in (data or {}).get("coaching_items") or []:
            if not isinstance(raw, dict):
                continue
            weakness = str(raw.get("weakness") or "").strip()
            question = str(raw.get("question") or "").strip()
            if not weakness or not question:
                continue
            items.append(
                FollowUpCoachingItem(
                    weakness=weakness[:260],
                    question=self._sanitize_question(question),
                    why_panel_would_ask=str(raw.get("why_panel_would_ask") or "")[:500],
                    ideal_answer=str(raw.get("ideal_answer") or "")[:1400],
                    skills_being_evaluated=self._as_string_list(raw.get("skills_being_evaluated"))[:6],
                    improvement_advice=str(raw.get("improvement_advice") or "")[:700],
                )
            )
        return items[:6] or None

    def _local_coaching_item(
        self, weakness: str, evidence: list[TranscriptEvidence]
    ) -> FollowUpCoachingItem:
        weakness_lower = weakness.lower()
        related = next(
            (
                item
                for item in evidence
                if item.topic.lower() in weakness_lower or weakness_lower in item.panel_interpretation.lower()
            ),
            evidence[0] if evidence else None,
        )
        if "leadership" in weakness_lower:
            question = "Describe a leadership situation where people disagreed with you. What decision did you make, and what measurable outcome changed?"
            skills = ["Leadership judgment", "Conflict handling", "Outcome orientation"]
            answer = (
                "A strong answer would set context, name the disagreement, explain the decision criteria, "
                "show how stakeholders were aligned, quantify the result, and end with a learning relevant "
                "to an MBA classroom."
            )
        elif "business" in weakness_lower or "awareness" in weakness_lower:
            question = "Pick one recent business issue connected to your target industry. Who gains, who loses, and what managerial decision would you recommend?"
            skills = ["Business awareness", "Stakeholder thinking", "Managerial reasoning"]
            answer = (
                "A strong answer would briefly define the issue, identify stakeholders, compare trade-offs, "
                "state a recommendation, and explain the metric that would prove whether the decision worked."
            )
        elif "academic" in weakness_lower or "project" in weakness_lower:
            question = "Take one project or academic concept from your resume. What trade-off did you face, and how did you measure whether your approach worked?"
            skills = ["Academic depth", "Problem solving", "Evidence quality"]
            answer = (
                "A strong answer would explain the concept in simple language, describe the alternative options, "
                "justify the chosen approach, quantify the impact, and acknowledge one limitation."
            )
        elif "career" in weakness_lower or "mba" in weakness_lower:
            question = "Why is an MBA necessary now for your target role, and what exact skill gap are you trying to close?"
            skills = ["MBA fit", "Career clarity", "Self-awareness"]
            answer = (
                "A strong answer would connect past exposure, target role, skill gap, school resources, and a "
                "credible post-MBA path without claiming that admission itself guarantees the outcome."
            )
        else:
            question = "Give one specific incident that shows this weakness. What caused it, what did you change, and what evidence shows improvement?"
            skills = ["Self-awareness", "Communication structure", "Learning agility"]
            answer = (
                "A strong answer would use a concrete incident, accept responsibility, identify the root cause, "
                "describe corrective action, and provide evidence of changed behavior."
            )
        source = f" Panel evidence: {related.evidence}" if related else ""
        return FollowUpCoachingItem(
            weakness=weakness,
            question=question,
            why_panel_would_ask=(
                "The panel would ask this to verify whether the weakness is a one-off gap or a pattern "
                f"that affects MBA readiness.{source}"
            )[:700],
            ideal_answer=answer,
            skills_being_evaluated=skills,
            improvement_advice="Practice this answer with one real example, one metric, and one reflective learning.",
        )

    def _mba_readiness_assessment(
        self, overall: float, dimensions: list[DimensionScore]
    ) -> str:
        weak = [item.name for item in dimensions if item.score is None or (item.score or 0) < 6.5]
        if overall >= 7.4:
            base = "The candidate shows credible MBA interview readiness with evidence in several evaluated areas."
        elif overall >= 6.0:
            base = "The candidate shows partial MBA readiness but needs sharper evidence and more consistent depth."
        else:
            base = "The candidate is not yet demonstrating enough MBA interview readiness from the transcript evidence."
        if weak:
            return f"{base} Priority gaps: {', '.join(weak[:4])}."
        return base

    def _dimension_score_map(self, report: InterviewReport) -> dict[str, float | None]:
        return {item.name: item.score for item in report.dimensions}

    def _profile_payload(self, profile: CandidateProfile) -> dict[str, Any]:
        return profile.model_dump(exclude={"resume_text"}, mode="json") | {
            "resume_excerpt": profile.resume_text[:4000]
        }

    def _memory_payload(self, memory: InterviewMemory) -> dict[str, Any]:
        return {
            "topics_covered": memory.topics_covered,
            "topic_states": [state.model_dump(mode="json") for state in memory.topic_states],
            "asked_questions": memory.asked_questions[-20:],
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
        self._ensure_topic_states(memory)
        desired = []
        if memory.candidate.education:
            desired.append("academics")
        if memory.candidate.projects:
            desired.append("projects")
        if memory.candidate.internships:
            desired.append("internships")
        if memory.candidate.career_goals or memory.candidate.goals:
            desired.extend(["career goals", "MBA motivation"])
        desired.extend(["leadership", "current affairs", "strengths", "weaknesses"])
        ranked = []
        for topic in self._dedupe([self._canonical_topic(item) for item in desired]):
            state = self._topic_state(memory, topic)
            if state.status in {TopicStatus.closed, TopicStatus.sufficiently_tested}:
                continue
            if len(state.questions_asked) >= 2:
                continue
            ranked.append(topic)
        return sorted(ranked, key=lambda item: (self._topic_state(memory, item).questions_asked, self._topic_state(memory, item).depth_level))

    def _ensure_topic_states(self, memory: InterviewMemory) -> None:
        existing = {self._canonical_topic(item.topic_name): item for item in memory.topic_states}
        normalized_states = []
        for topic in TOPIC_COVERAGE:
            state = existing.get(topic)
            if state is None:
                state = TopicState(topic_name=topic)
            state.topic_name = topic
            normalized_states.append(state)
        for state in memory.topic_states:
            topic = self._canonical_topic(state.topic_name)
            if topic not in TOPIC_COVERAGE and topic:
                state.topic_name = topic
                normalized_states.append(state)
        memory.topic_states = normalized_states

    def _canonical_topic(self, topic: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", str(topic or "").lower()).strip()
        if not normalized:
            return "projects"
        return TOPIC_ALIASES.get(normalized, normalized if normalized in TOPIC_COVERAGE else "projects")

    def _topic_state(self, memory: InterviewMemory, topic: str) -> TopicState:
        canonical = self._canonical_topic(topic)
        self._ensure_topic_states(memory) if not memory.topic_states else None
        for state in memory.topic_states:
            if self._canonical_topic(state.topic_name) == canonical:
                return state
        state = TopicState(topic_name=canonical)
        memory.topic_states.append(state)
        return state

    def _next_viable_follow_up(self, memory: InterviewMemory) -> FollowUpOpportunity | None:
        while memory.unanswered_follow_up_opportunities:
            opportunity = memory.unanswered_follow_up_opportunities.pop(0)
            opportunity.topic = self._canonical_topic(opportunity.topic)
            state = self._topic_state(memory, opportunity.topic)
            if state.status in {TopicStatus.closed, TopicStatus.sufficiently_tested}:
                continue
            if len(state.questions_asked) >= 2 and not memory.contradictions:
                continue
            return opportunity
        return None

    def _least_tested_reopenable_topic(self, memory: InterviewMemory) -> str:
        candidates = []
        for topic in TOPIC_COVERAGE:
            state = self._topic_state(memory, topic)
            if state.status == TopicStatus.closed:
                continue
            if len(state.questions_asked) >= 3:
                continue
            candidates.append(topic)
        if not candidates:
            return ""
        return min(candidates, key=lambda item: (len(self._topic_state(memory, item).questions_asked), self._topic_state(memory, item).depth_level))

    def _depth_focus(self, topic: str, depth: int) -> str:
        ladder = TOPIC_DEPTH_LADDERS.get(self._canonical_topic(topic), TOPIC_DEPTH_LADDERS["projects"])
        return ladder[max(0, min(depth, len(ladder)) - 1)]

    def _last_interviewer_topic(self, memory: InterviewMemory) -> str:
        last_question = ""
        for turn in reversed(memory.transcript):
            if turn.speaker == TurnSpeaker.interviewer:
                last_question = turn.text
                break
        if not last_question:
            return ""
        for state in memory.topic_states:
            if any(self._semantically_similar(last_question, question) for question in state.questions_asked):
                return state.topic_name
        return ""

    def _topics_from_answer(self, latest_answer: str) -> list[str]:
        lower = latest_answer.lower()
        matches = []
        keyword_map = {
            "academics": ["college", "cgpa", "degree", "semester", "academic", "subject"],
            "projects": ["project", "built", "developed", "metric", "customer", "revenue", "cost", "profit"],
            "internships": ["intern", "trainee", "work", "company", "manager"],
            "leadership": ["led", "lead", "team", "organized", "managed", "conflict"],
            "career goals": ["career", "role", "industry", "consulting", "product", "strategy"],
            "MBA motivation": ["mba", "business school", "management"],
            "current affairs": ["economy", "policy", "market", "inflation", "budget", "geopolitics"],
            "strengths": ["strength", "strong", "good at"],
            "weaknesses": ["weakness", "improve", "struggle", "failed"],
        }
        for topic, keywords in keyword_map.items():
            if any(keyword in lower for keyword in keywords):
                matches.append(topic)
        return matches

    def _update_topic_evidence(
        self, memory: InterviewMemory, latest_answer: str, topics: list[str]
    ) -> None:
        evidence = self._summarize_evidence(latest_answer)
        if not evidence:
            return
        topics = topics or ([self._last_interviewer_topic(memory)] if self._last_interviewer_topic(memory) else [])
        for topic in self._dedupe([self._canonical_topic(item) for item in topics]):
            state = self._topic_state(memory, topic)
            if evidence not in state.evidence_collected:
                state.evidence_collected.append(evidence[:220])
            if topic not in memory.topics_covered:
                memory.topics_covered.append(topic)
            self._refresh_topic_status(state)

    def _summarize_evidence(self, text: str) -> str:
        clean = self._sanitize_candidate_text(text)
        if not clean or self._is_candidate_filler(clean):
            return ""
        sentences = re.split(r"(?<=[.!?])\s+", clean)
        candidate = next((item for item in sentences if len(item.split()) >= 6), clean)
        return candidate.strip()[:220]

    def _refresh_topic_status(self, state: TopicState) -> None:
        evidence_score = len(state.evidence_collected)
        if state.questions_asked:
            state.status = TopicStatus.in_progress
        if evidence_score >= 2 and state.depth_level >= 2:
            state.status = TopicStatus.closed
        elif len(state.questions_asked) >= 2 or state.depth_level >= 3:
            state.status = TopicStatus.sufficiently_tested

    def _record_accepted_question(self, memory: InterviewMemory, question: str, topic: str) -> None:
        clean_question = self._sanitize_question(question)
        state = self._topic_state(memory, topic)
        if clean_question not in state.questions_asked:
            state.questions_asked.append(clean_question)
        if clean_question not in memory.asked_questions:
            memory.asked_questions.append(clean_question)
        state.depth_level = min(max(state.depth_level + 1, 1), 5)
        state.status = TopicStatus.in_progress
        self._refresh_topic_status(state)

    def _last_claim(self, memory: InterviewMemory) -> str:
        for claim in reversed(memory.candidate_claims):
            if not self._is_bad_anchor(claim.text):
                return claim.text
        for claim in memory.candidate.notable_resume_claims:
            if not self._is_bad_anchor(claim):
                return claim
        return ""

    def _pressure_anchor(self, memory: InterviewMemory) -> str:
        """Return the best ownership anchor for the pressure interviewer.

        Priority order:
        1. Recent interview-time claims that contain an action verb (candidate's own words)
        2. Resume-seeded claims that contain an action verb
        3. Profile projects or internship items
        4. Any non-bad claim from candidate_claims
        """
        action_verbs = [
            "led", "built", "created", "designed", "developed", "managed",
            "achieved", "improved", "launched", "delivered", "owned",
            "drove", "trained", "analyzed", "solved", "reduced", "increased",
            "won", "ranked", "secured", "published", "deployed",
        ]

        def has_action(text: str) -> bool:
            lower = text.lower()
            return any(v in lower for v in action_verbs)

        # 1. Interview-time claims with action verbs (most credible)
        for claim in reversed(memory.candidate_claims):
            if claim.source == "interview" and not self._is_bad_anchor(claim.text) and has_action(claim.text):
                return claim.text

        # 2. Resume-seeded claims with action verbs
        for claim in reversed(memory.candidate_claims):
            if not self._is_bad_anchor(claim.text) and has_action(claim.text):
                return claim.text

        # 3. Profile projects / internships — concrete and always actionable
        for item in memory.candidate.projects:
            if item and not self._is_bad_anchor(item):
                return item
        for item in memory.candidate.internships:
            if item and not self._is_bad_anchor(item):
                return item

        # 4. Any acceptable claim
        for claim in reversed(memory.candidate_claims):
            if not self._is_bad_anchor(claim.text):
                return claim.text

        return ""

    def _topic_from_reason(self, reason: str) -> str:
        lower = reason.lower()
        for topic in [
            "academics",
            "education",
            "projects",
            "internships",
            "skills",
            "achievements",
            "career goals",
            "career_goals",
            "why mba",
            "mba motivation",
            "leadership",
            "current affairs",
            "strengths",
            "weaknesses",
            "consistency",
        ]:
            if topic in lower:
                return self._canonical_topic(topic)
        return "projects"

    def _anchor_for_topic(
        self,
        memory: InterviewMemory,
        topic: str,
        claim: str,
        opening_topic: str,
    ) -> str:
        profile = memory.candidate
        topic_groups = {
            "academics": profile.education,
            "projects": profile.projects,
            "internships": profile.internships,
            "skills": profile.skills,
            "achievements": profile.achievements,
            "leadership": profile.achievements + profile.notable_resume_claims,
            "career goals": profile.career_goals,
            "MBA motivation": profile.career_goals or ([profile.goals] if profile.goals else []),
            "current affairs": profile.notable_resume_claims,
            "strengths": profile.achievements + profile.notable_resume_claims,
            "weaknesses": profile.notable_resume_claims,
        }
        candidates = topic_groups.get(topic, [])
        anchor = self._first_clean_available(candidates, [opening_topic], profile.notable_resume_claims, [claim])
        return self._safe_question_anchor(anchor or "your resume and interview answers")

    def _first_clean_available(self, *groups: list[str] | tuple[str, ...] | str) -> str:
        for group in groups:
            if isinstance(group, str):
                if group.strip() and not self._is_bad_anchor(group):
                    return group.strip()
                continue
            for item in group:
                if item and item.strip() and not self._is_bad_anchor(item):
                    return item.strip()
        return ""

    def _finalize_question(
        self,
        memory: InterviewMemory,
        question: str,
        interviewer_id: InterviewerId,
        topic: str,
        latest_answer: str = "",
    ) -> str:
        topic = self._canonical_topic(topic)
        question = self._sanitize_question(question)
        if not self._question_is_acceptable(memory, question, latest_answer):
            question = self._alternative_question(memory, interviewer_id, topic, latest_answer)
        if not self._question_is_acceptable(memory, question, latest_answer):
            alternate_topic = self._first_different_open_topic(memory, topic)
            question = self._alternative_question(memory, TOPIC_TO_INTERVIEWER.get(alternate_topic, interviewer_id), alternate_topic, latest_answer)
            topic = alternate_topic
        self._record_accepted_question(memory, question, topic)
        return question

    def _question_is_acceptable(self, memory: InterviewMemory, question: str, latest_answer: str = "") -> bool:
        if not question or self._is_bad_anchor(question) or self._is_candidate_filler(question):
            return False
        lower = question.lower()
        if "tell me more" in lower or "what to answer" in lower:
            return False
        if latest_answer and self._contains_verbatim_candidate_speech(question, latest_answer):
            return False
        prior_questions = memory.asked_questions + [
            turn.text for turn in memory.transcript if turn.speaker == TurnSpeaker.interviewer
        ]
        return not any(self._semantically_similar(question, prior) for prior in prior_questions)

    def _alternative_question(
        self,
        memory: InterviewMemory,
        interviewer_id: InterviewerId,
        topic: str,
        latest_answer: str = "",
    ) -> str:
        topic = self._canonical_topic(topic)
        state = self._topic_state(memory, topic)
        next_depth = min(state.depth_level + 1, 5)
        depth_focus = self._depth_focus(topic, next_depth)
        if memory.contradictions and interviewer_id == InterviewerId.pressure:
            return (
                "Your earlier answers appear inconsistent. Which claim should the panel trust, "
                "and what concrete evidence supports that version?"
            )
        if topic == "projects":
            options = [
                f"At the {depth_focus} level of your project, which decision had the biggest trade-off, and how did you measure the result?",
                "What metric improved because of the project, and what would you change if you rebuilt it today?",
                "Why did you choose that architecture or approach over the next best alternative?",
            ]
        elif topic == "academics":
            options = [
                f"At the {depth_focus} level, explain one academic concept from your background and where it breaks down in practice.",
                "Which subject from your academics would you defend most confidently, and how does it apply to a business problem?",
                "What assumption in that concept would you challenge if the context changed?",
            ]
        elif topic == "internships":
            options = [
                f"At the {depth_focus} level of your internship, what did you personally own and how was success measured?",
                "Which stakeholder constraint shaped your internship work, and what trade-off did it force?",
                "What would your manager say was your most measurable contribution?",
            ]
        elif topic == "leadership":
            options = [
                "Describe one leadership situation where people disagreed with you. What decision did you make and what changed afterwards?",
                "How did you measure whether your leadership actually improved the team outcome?",
                "What leadership trade-off would you handle differently today?",
            ]
        elif topic == "career goals":
            options = [
                "What specific post-MBA role are you targeting, and what evidence from your past makes that path credible?",
                "Which industry problem do you want to work on, and why are you suited to it?",
                "What is your fallback path if your preferred post-MBA role does not materialize?",
            ]
        elif topic == "MBA motivation":
            options = [
                "Why is an MBA necessary now rather than learning the same skills on the job?",
                "Which exact skill gap is the MBA meant to close, and how will you test that during the program?",
                "What would make this MBA decision a poor investment for you?",
            ]
        elif topic == "current affairs":
            options = [
                "Choose one current business or economic issue. Who gains, who loses, and what managerial decision would you make?",
                "What current policy or market shift could affect your target industry, and how?",
                "Where do you disagree with the popular view on a recent business issue?",
            ]
        elif topic == "strengths":
            options = [
                "Name one strength with a specific incident, the outcome it created, and where that strength can become a liability.",
                "How would a teammate prove that this strength is real rather than self-perception?",
                "Which strength will matter most in an MBA classroom, and why?",
            ]
        else:
            options = [
                "Name one real weakness from a recent incident, its root cause, and the evidence that you are improving it.",
                "What feedback have you repeatedly received, and what have you changed because of it?",
                "Where could this weakness hurt you in an MBA classroom or placement process?",
            ]
        for option in options:
            if self._question_is_acceptable(memory, option, latest_answer):
                return option
        return options[-1]

    def _first_different_open_topic(self, memory: InterviewMemory, current_topic: str) -> str:
        current_topic = self._canonical_topic(current_topic)
        for topic in self._open_topics(memory):
            if topic != current_topic:
                return topic
        for topic in TOPIC_COVERAGE:
            if topic != current_topic and self._topic_state(memory, topic).status != TopicStatus.closed:
                return topic
        return current_topic

    def _semantically_similar(self, first: str, second: str) -> bool:
        first_norm = self._normalize_for_compare(first)
        second_norm = self._normalize_for_compare(second)
        if not first_norm or not second_norm:
            return False
        if first_norm == second_norm:
            return True
        first_tokens = set(first_norm.split())
        second_tokens = set(second_norm.split())
        overlap = len(first_tokens & second_tokens) / max(1, len(first_tokens | second_tokens))
        sequence = SequenceMatcher(None, first_norm, second_norm).ratio()
        return overlap >= 0.62 or sequence >= 0.82

    def _normalize_for_compare(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _is_bad_anchor(self, value: str) -> bool:
        lower = value.lower()
        bad_fragments = [
            "uploaded resume:",
            "resume.pdf",
            "pdf extraction is handled",
            "backend integration phase",
            "i don't know what to answer",
            "i dont know what to answer",
            "what should i answer",
            "what to answer",
            "umm",
            "uhh",
            # Skill/importance lines that make no sense as ownership anchors
            "importance of ",
            "use of python",
            "role of python",
            "introduction to ",
            "applications of ",
            "fundamentals of ",
            "coursework",
            "syllabus",
        ]
        if any(fragment in lower for fragment in bad_fragments):
            return True
        # Reject lines with no action verb — pure noun phrases from skills sections
        action_verbs = [
            "led", "built", "created", "designed", "developed", "managed",
            "achieved", "improved", "launched", "delivered", "owned",
            "drove", "trained", "analyzed", "solved", "reduced", "increased",
            "won", "ranked", "secured", "published", "deployed",
        ]
        words = lower.split()
        # Short lines (< 5 words) with no action verb are likely skill labels, not anchors
        if len(words) < 5 and not any(v in lower for v in action_verbs):
            return True
        return False

    def _sanitize_candidate_text(self, value: str) -> str:
        clean = re.sub(r"\s+", " ", str(value or "")).strip()
        filler_patterns = [
            r"(?i)\bi don'?t know what to answer\b",
            r"(?i)\bi don'?t know\b",
            r"(?i)\bwhat should i answer\b",
            r"(?i)\bwhat to answer\b",
            r"(?i)\bumm+\b",
            r"(?i)\buhh+\b",
        ]
        for pattern in filler_patterns:
            clean = re.sub(pattern, "", clean).strip()
        clean = re.sub(r"\s+", " ", clean).strip(" ,.-")
        return clean

    def _sanitize_question(self, value: str) -> str:
        clean = self._sanitize_candidate_text(value)
        clean = re.sub(r"\s+", " ", clean).strip()
        clean = clean.strip('"').strip("'").strip()
        if clean and not clean.endswith("?"):
            clean = clean.rstrip(".") + "?"
        return clean[:700]

    def _is_candidate_filler(self, value: str) -> bool:
        normalized = self._normalize_for_compare(value)
        if not normalized:
            return True
        filler = {
            "i dont know what to answer",
            "i dont know",
            "what should i answer",
            "what to answer",
            "no idea",
            "nothing",
        }
        return normalized in filler or len(normalized.split()) <= 2

    def _contains_verbatim_candidate_speech(self, question: str, latest_answer: str) -> bool:
        answer = self._sanitize_candidate_text(latest_answer)
        if len(answer.split()) < 5:
            return False
        question_norm = self._normalize_for_compare(question)
        words = self._normalize_for_compare(answer).split()
        for size in range(min(10, len(words)), 4, -1):
            for index in range(0, len(words) - size + 1):
                phrase = " ".join(words[index : index + size])
                if phrase and phrase in question_norm:
                    return True
        return False

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

    def _safe_question_anchor(self, value: str) -> str:
        clean = self._sanitize_candidate_text(value)
        if self._is_bad_anchor(clean) or self._is_candidate_filler(clean):
            return "your resume and interview answers"
        words = clean.split()
        return " ".join(words[:24]).strip().rstrip(".") or "your resume and interview answers"

    def _extract_answer_hook(self, latest_answer: str) -> str:
        """Extract a short, meaningful phrase from the candidate's last answer to use as
        a conversational bridge at the start of the next question.

        Returns a string like 'You mentioned "supply chain optimization" — ' or '' if nothing
        usable is found.
        """
        if not latest_answer or self._is_candidate_filler(latest_answer):
            return ""

        clean = self._sanitize_candidate_text(latest_answer)
        words = clean.split()
        if len(words) < 6:
            return ""

        _STOP = {
            "i", "me", "my", "we", "our", "the", "a", "an", "it", "its",
            "this", "that", "is", "was", "are", "were", "be", "been",
            "have", "had", "has", "do", "did", "and", "or", "but", "so",
            "for", "of", "in", "on", "at", "to", "from", "with", "about",
            "like", "just", "also", "very", "really", "quite", "um", "uh",
            "said", "say", "think", "feel", "would", "could", "should",
        }

        # Build a list of cleaned tokens, skip the first 2 words (usually "I did/built")
        tokens = [re.sub(r"[^a-zA-Z0-9\-]", "", w) for w in words[2:]]

        # Slide a window of 2-3 words to find the best consecutive meaningful run
        best_chunk: list[str] = []
        current_chunk: list[str] = []

        for token in tokens:
            if len(token) >= 3 and token.lower() not in _STOP:
                current_chunk.append(token)
                if len(current_chunk) >= len(best_chunk):
                    best_chunk = list(current_chunk)
                if len(current_chunk) == 3:
                    break  # 3 good words is enough
            else:
                current_chunk = []

        if len(best_chunk) < 2:
            return ""

        hook_phrase = " ".join(best_chunk)
        bridges = [
            f"You mentioned \"{hook_phrase}\" \u2014 building on that, ",
            f"Picking up on \"{hook_phrase}\" from your answer \u2014 ",
            f"You brought up \"{hook_phrase}\" \u2014 let us dig into that. ",
        ]
        bridge = bridges[hash(hook_phrase) % len(bridges)]
        return bridge

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

    def _parse_transcript_evidence(self, value: Any) -> list[TranscriptEvidence]:
        items = []
        for item in value or []:
            if not isinstance(item, dict):
                continue
            evidence = self._sanitize_candidate_text(str(item.get("evidence") or ""))
            if not evidence:
                continue
            items.append(
                TranscriptEvidence(
                    topic=self._canonical_topic(str(item.get("topic") or "projects")),
                    evidence=evidence[:240],
                    panel_interpretation=str(item.get("panel_interpretation") or "")[:240]
                    or "Panel noted this as transcript-backed evidence.",
                )
            )
        return items[:8]

    def _parse_benchmarks(self, value: Any) -> list[BenchmarkCategory]:
        items = []
        allowed = {
            "Typical IIM Convert Candidate",
            "Strong IIM ABC Candidate",
            "Average CAT Aspirant",
        }
        for item in value or []:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or "")
            if category not in allowed:
                continue
            items.append(
                BenchmarkCategory(
                    category=category,  # type: ignore[arg-type]
                    communication=str(item.get("communication") or "Insufficient evidence"),
                    leadership=str(item.get("leadership") or "Insufficient evidence"),
                    business_awareness=str(item.get("business_awareness") or "Insufficient evidence"),
                    academic_depth=str(item.get("academic_depth") or "Insufficient evidence"),
                    mba_fit=str(item.get("mba_fit") or "Insufficient evidence"),
                    notes=str(item.get("notes") or "Preparedness benchmark only."),
                )
            )
        return items[:3]

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

    def _contains_any(self, text: str, keywords: list[str]) -> bool:
        lower = text.lower()
        return any(keyword in lower for keyword in keywords)

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
        if overall >= 7.4:
            return "Likely Convert"
        if overall >= 6.0:
            return "Borderline"
        return "Needs Improvement"

    def _normalize_verdict(self, verdict: str) -> str:
        normalized = verdict.strip()
        if normalized in {"Likely Convert", "Borderline", "Needs Improvement"}:
            return normalized
        legacy = {
            "Strong Hire": "Likely Convert",
            "Lean Hire": "Borderline",
            "Lean Reject": "Needs Improvement",
            "Strong Reject": "Needs Improvement",
        }
        return legacy.get(normalized, "Needs Improvement")
