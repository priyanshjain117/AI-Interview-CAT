from datetime import datetime, timedelta

from app.models import (
    BenchmarkCategory,
    CandidateProfile,
    DimensionScore,
    FollowUpCoachingItem,
    InterviewHistoryItem,
    InterviewReport,
    InterviewStatus,
    ProgressAnalysis,
    ProgressDashboardResponse,
    ProgressPoint,
    ResumeRecord,
    TranscriptEvidence,
    TranscriptTurn,
    TurnSpeaker,
)

DEMO_USER_ID = "c8122263-2008-4d34-a30c-4176b850e45c"
DEMO_RESUME_ID = "c8122263-2008-4d34-a30c-4176b850e101"

DEMO_PROFILE = CandidateProfile(
    name="Demo Candidate",
    goals="Product management after an MBA, with a focus on consumer technology.",
    background="Final-year engineering student with projects, internships, and leadership exposure.",
    resume_text=(
        "Demo Candidate\nEngineering undergraduate\nProjects: analytics dashboard, pricing model\n"
        "Internship: product operations trainee\nLeadership: organized placement preparation group"
    ),
    education=["Engineering undergraduate with analytics coursework"],
    projects=["Built an analytics dashboard for student placement preparation"],
    internships=["Product operations trainee at a consumer technology startup"],
    achievements=["Led a peer preparation group for mock interviews"],
    skills=["Analytics", "Product thinking", "Communication"],
    career_goals=["Product management", "Consumer technology"],
    notable_resume_claims=[
        "Built an analytics dashboard for student placement preparation",
        "Led a peer preparation group for mock interviews",
    ],
)

DEMO_RESUME = ResumeRecord(
    id=DEMO_RESUME_ID,
    filename="demo-candidate-resume.txt",
    extracted_text=DEMO_PROFILE.resume_text,
    version=1,
    is_active=True,
    parsed_at=datetime.utcnow() - timedelta(days=21),
    created_at=datetime.utcnow() - timedelta(days=21),
)


def demo_report(session_id: str = "c8122263-2008-4d34-a30c-4176b850e203") -> InterviewReport:
    attempts = {
        "c8122263-2008-4d34-a30c-4176b850e201": {
            "score": 6.8,
            "verdict": "Waitlist",
            "summary": "Attempt 1 showed credible foundations, but answers needed sharper metrics, leadership depth, and MBA linkage.",
            "evidence": "I built a placement dashboard, but my first answer did not quantify adoption clearly.",
        },
        "c8122263-2008-4d34-a30c-4176b850e202": {
            "score": 7.6,
            "verdict": "Borderline Admit",
            "summary": "Attempt 2 improved by adding metrics, clearer stakeholder language, and more structured career motivation.",
            "evidence": "I added baseline adoption, weekly active users, and explained how students used the dashboard.",
        },
        "c8122263-2008-4d34-a30c-4176b850e203": {
            "score": 8.7,
            "verdict": "Strong Admit",
            "summary": "Attempt 3 showed strong readiness: quantified project impact, credible leadership ownership, and clear MBA fit.",
            "evidence": "I linked the MBA to product strategy, stakeholder leadership, and quantified user impact from the dashboard.",
        },
    }
    attempt = attempts.get(session_id, attempts["c8122263-2008-4d34-a30c-4176b850e203"])
    transcript = [
        TranscriptTurn(
            speaker=TurnSpeaker.interviewer,
            text="Walk us through the dashboard project and the decision trade-off you owned.",
        ),
        TranscriptTurn(
            speaker=TurnSpeaker.candidate,
            text=attempt["evidence"],
        ),
    ]
    dimensions = [
        DimensionScore(
            name="Communication clarity",
            score=min(9.0, float(attempt["score"]) + 0.1),
            evidence="Candidate used clearer structure and stronger evidence as attempts progressed.",
            strengths=["Clear project anchor."],
            weaknesses=[] if float(attempt["score"]) >= 8 else ["Impact framing needed more precision."],
            advice="Keep answers metric-led and concise.",
        ),
        DimensionScore(
            name="Leadership potential",
            score=max(6.2, float(attempt["score"]) - 0.2),
            evidence="Leadership ownership became more concrete across attempts.",
            strengths=["Has peer-group leadership exposure."],
            weaknesses=[] if float(attempt["score"]) >= 8 else ["Needs a stronger disagreement example."],
            advice="Prepare one leadership story with disagreement, decision, and outcome.",
        ),
        DimensionScore(
            name="Business awareness",
            score=float(attempt["score"]),
            evidence="Business framing improved from activity description to user impact.",
            strengths=["Connected project work to users and adoption."],
            weaknesses=[] if float(attempt["score"]) >= 8 else ["Business impact needs sharper framing."],
            advice="Translate project work into user, cost, risk, or revenue language.",
        ),
        DimensionScore(
            name="Academic depth",
            score=min(9.0, float(attempt["score"]) + 0.2),
            evidence="Explained analytics project choices with reasonable clarity.",
            strengths=["Comfortable with project fundamentals."],
            weaknesses=[],
            advice="Add trade-offs and limitations to academic answers.",
        ),
        DimensionScore(
            name="Career clarity",
            score=min(9.0, float(attempt["score"]) + 0.3),
            evidence="Product management goal became more specific and MBA-linked.",
            strengths=["MBA goal is directionally coherent."],
            weaknesses=[] if float(attempt["score"]) >= 8 else ["Target role needs more specificity."],
            advice="Name target function, industry, skills gap, and why now.",
        ),
    ]
    evidence = [
        TranscriptEvidence(
            topic="projects",
            evidence=attempt["evidence"],
            panel_interpretation="Project ownership and MBA fit improved across the seeded attempts.",
        )
    ]
    coaching = [
        FollowUpCoachingItem(
            weakness="Impact was not quantified.",
            question="What metric improved because of the dashboard, and how did you validate that improvement?",
            why_panel_would_ask="The panel would test whether the project had measurable value or was only an activity.",
            ideal_answer="A strong answer would define the baseline, explain the intervention, show adoption or outcome metrics, and state one limitation.",
            skills_being_evaluated=["Business impact", "Analytical depth", "Ownership"],
            improvement_advice="Prepare the dashboard answer with baseline, metric, stakeholder, and result.",
            practice_id="demo-practice-1",
        )
    ]
    return InterviewReport(
        session_id=session_id,
        verdict=attempt["verdict"],
        overall_score=attempt["score"],
        executive_summary=attempt["summary"],
        strengths=["Clear project anchor.", "Directionally coherent MBA goal."],
        weaknesses=["Can still sharpen current-affairs examples."] if float(attempt["score"]) >= 8 else ["Impact was not quantified.", "Leadership conflict handling was not demonstrated."],
        panel_concerns=["Minimal concerns for this preparation stage."] if float(attempt["score"]) >= 8 else ["Business impact needs sharper framing."],
        dimensions=dimensions,
        transcript_evidence=evidence,
        recommended_improvements=[
            "Quantify one project outcome.",
            "Prepare one leadership story involving disagreement.",
            "Connect MBA goals to a specific skill gap.",
        ],
        panel_comments=["Panel sees potential, but evidence needs more depth before a stronger verdict."],
        benchmarking=[
            BenchmarkCategory(
                category="Average CAT Aspirant",
                communication="58-72 percentile",
                leadership="52-66 percentile",
                business_awareness="55-69 percentile",
                academic_depth="62-76 percentile",
                mba_fit="58-72 percentile",
                notes="Preparedness comparison only.",
            ),
            BenchmarkCategory(
                category="Typical IIM Convert Candidate",
                communication="48-62 percentile",
                leadership="42-56 percentile",
                business_awareness="45-59 percentile",
                academic_depth="52-66 percentile",
                mba_fit="48-62 percentile",
                notes="Preparedness comparison only.",
            ),
            BenchmarkCategory(
                category="Strong IIM ABC Candidate",
                communication="38-52 percentile",
                leadership="32-46 percentile",
                business_awareness="35-49 percentile",
                academic_depth="42-56 percentile",
                mba_fit="38-52 percentile",
                notes="A stricter preparation benchmark, not an admission prediction.",
            ),
        ],
        mba_readiness_assessment="Ready for a strong interview performance." if float(attempt["score"]) >= 8 else "The candidate is partially ready but needs stronger quantified impact and leadership evidence.",
        coaching_items=coaching,
        progress=ProgressAnalysis(
            improved_areas=["Communication clarity", "Leadership", "Business awareness", "MBA fit", "Career clarity", "Academic depth"] if float(attempt["score"]) >= 8 else ["Communication clarity improved."],
            declining_areas=[],
            recurring_weaknesses=["Impact was not quantified."],
            growth_summary="Overall score improved from 6.8 to 8.7 across three seeded attempts.",
            next_focus_areas=["Quantified impact", "Leadership conflict story", "Career specificity"],
        ),
        feedback_to_candidate="Use evidence, metrics, and management framing in the next attempt.",
        transcript=transcript,
    )


def demo_history() -> list[InterviewHistoryItem]:
    now = datetime.utcnow()
    return [
        InterviewHistoryItem(
            session_id="c8122263-2008-4d34-a30c-4176b850e201",
            interview_date=now - timedelta(days=28),
            overall_score=6.8,
            verdict="Waitlist",
            duration_seconds=840,
            interview_type="IIM MBA Panel",
            status=InterviewStatus.completed,
        ),
        InterviewHistoryItem(
            session_id="c8122263-2008-4d34-a30c-4176b850e202",
            interview_date=now - timedelta(days=14),
            overall_score=7.6,
            verdict="Borderline Admit",
            duration_seconds=910,
            interview_type="IIM MBA Panel",
            status=InterviewStatus.completed,
        ),
        InterviewHistoryItem(
            session_id="c8122263-2008-4d34-a30c-4176b850e203",
            interview_date=now - timedelta(days=3),
            overall_score=8.7,
            verdict="Strong Admit",
            duration_seconds=960,
            interview_type="IIM MBA Panel",
            status=InterviewStatus.completed,
        ),
    ]


def demo_progress() -> ProgressDashboardResponse:
    now = datetime.utcnow()
    return ProgressDashboardResponse(
        points=[
            ProgressPoint(created_at=now - timedelta(days=28), communication=6.7, leadership=6.2, business_awareness=6.4, mba_fit=6.9, career_clarity=6.9, academic_depth=7.1),
            ProgressPoint(created_at=now - timedelta(days=14), communication=7.6, leadership=7.0, business_awareness=7.4, mba_fit=7.8, career_clarity=7.8, academic_depth=8.0),
            ProgressPoint(created_at=now - timedelta(days=3), communication=8.8, leadership=8.5, business_awareness=8.6, mba_fit=9.0, career_clarity=9.0, academic_depth=8.6),
        ],
        latest=demo_report().progress or ProgressAnalysis(),
    )
