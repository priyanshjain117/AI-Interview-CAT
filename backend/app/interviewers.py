from app.models import InterviewerId, InterviewerState


INTERVIEWERS: list[InterviewerState] = [
    InterviewerState(
        id=InterviewerId.academic,
        name="Dr. Meera Rao",
        role="Academic Interviewer",
        focus="Academics, projects, technical depth, and conceptual clarity.",
    ),
    InterviewerState(
        id=InterviewerId.pressure,
        name="Prof. Arvind Menon",
        role="Pressure Interviewer",
        focus="Consistency, contradictions, vague claims, and composure under challenge.",
    ),
    InterviewerState(
        id=InterviewerId.mba,
        name="Ananya Sen",
        role="MBA Interviewer",
        focus="Leadership, business thinking, why MBA, and career goals.",
    ),
]


INTERVIEWER_BY_ID = {interviewer.id: interviewer for interviewer in INTERVIEWERS}
