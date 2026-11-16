"""Request and response schemas of the StudyMate HTTP API.

Response models mirror the dictionaries built in ``service.py`` and
``quizzes.py``; they document the API in ``/docs`` and are the source for
``frontend/src/api-schema.d.ts`` (``npm run gen:api``).
"""

from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["ru", "en", "kk"]
Format = Literal["online", "campus"]
PASSWORD_MIN, PASSWORD_MAX = 10, 128


# ---------------------------------------------------------------- requests


class DemoLogin(BaseModel):
    user_id: Literal[1, 2, 3, 99]


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class Registration(Credentials):
    name: str = Field(min_length=1, max_length=100)
    course: int = Field(default=1, ge=1, le=6)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class PasswordReset(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    code: str = Field(min_length=6, max_length=32)
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)


class WorkspaceInput(BaseModel):
    meeting_url: str | None = Field(default=None, max_length=500)
    meeting_place: str | None = Field(default=None, max_length=500)
    materials: str | None = Field(default=None, max_length=10000)
    notes: str | None = Field(default=None, max_length=20000)


class ProfileInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    course: int = Field(ge=1, le=6)
    languages: list[Language] = Field(min_length=1, max_length=3)
    interests: list[int] = Field(max_length=20)


class MentorInput(BaseModel):
    bio: str = Field(min_length=15, max_length=1000)
    price: int = Field(ge=0, le=100000)
    topic_ids: list[int] = Field(min_length=1, max_length=30)
    formats: list[Format] = Field(min_length=1, max_length=2)
    active: bool = True


class SlotInput(BaseModel):
    starts_at: int


class GroupFields(BaseModel):
    capacity: int = Field(ge=2, le=5)
    topic_id: int
    price: int = Field(ge=0, le=100000)
    format: Format = "online"
    meeting_url: str | None = Field(default=None, max_length=500)
    meeting_place: str | None = Field(default=None, max_length=500)
    min_participants: int = Field(default=1, ge=1, le=5)


class GroupSlotInput(GroupFields):
    starts_at: int


class SeriesInput(BaseModel):
    starts_at: int
    weeks: int = Field(ge=2, le=12)
    group: GroupFields | None = None


class MeetingInput(BaseModel):
    meeting_url: str | None = Field(default=None, max_length=500)
    meeting_place: str | None = Field(default=None, max_length=500)
    materials: str | None = Field(default=None, max_length=10000)


class RescheduleInput(BaseModel):
    slot_id: int


class BookingInput(BaseModel):
    slot_id: int
    topic_id: int
    deadline: int
    earliest: int = 0
    budget: int = Field(ge=0, le=100000)
    language: Language = "ru"
    format: Format = "online"
    description: str = Field(default="", max_length=1500)
    request_key: str = Field(min_length=8, max_length=80)


class ActionInput(BaseModel):
    action: Literal["confirm", "reject", "cancel", "complete", "request_completion"]
    meeting_url: str | None = Field(default=None, max_length=500)
    meeting_place: str | None = Field(default=None, max_length=500)


class ReviewInput(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=3, max_length=1000)


class WaitlistInput(BaseModel):
    topic_id: int
    budget: int = Field(ge=0, le=100000)
    deadline: int
    earliest: int
    language: Language
    format: Format


class QuizInput(BaseModel):
    topic_id: int
    stage: Literal["pre", "post", "practice"] = "practice"
    booking_id: str | None = None


class AnswersInput(BaseModel):
    answers: list[int] = Field(min_length=3, max_length=3)


class MessageInput(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    client_id: str = Field(min_length=8, max_length=64)


class ReadInput(BaseModel):
    last_read_id: int = Field(ge=0)


class VerifyInput(BaseModel):
    verified: bool
    active: bool


class SubjectInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    active: bool


# --------------------------------------------------------------- responses


class Ok(BaseModel):
    ok: bool = True
    message: str | None = None


class MentorProfileOut(BaseModel):
    bio: str
    price: int
    topic_ids: list[int]
    formats: list[str]
    verified: bool
    active: bool
    suspended: bool


class UserOut(BaseModel):
    id: int
    name: str
    email: str | None
    campus: str
    course: int
    languages: list[str]
    interests: list[int]
    registered: bool
    is_admin: bool
    mentor: MentorProfileOut | None


class AuthOut(BaseModel):
    token: str
    user: UserOut


class TopicOut(BaseModel):
    id: int
    name: str
    code: str


class SubjectOut(BaseModel):
    id: int
    slug: str
    name: str
    active: bool
    topics: list[TopicOut]


class SlotOut(BaseModel):
    id: int
    mentor_id: int
    starts_at: int
    ends_at: int
    enabled: bool
    series_id: str | None = None
    capacity: int = 1
    taken: int | None = None
    price: int | None = None
    topic_id: int | None = None
    min_participants: int | None = None
    format: str | None = None


class SkippedOut(BaseModel):
    starts_at: int
    reason: str


class SeriesOut(BaseModel):
    series_id: str
    created: list[SlotOut]
    skipped: list[SkippedOut]


class SeriesClosedOut(BaseModel):
    closed: int
    kept_with_bookings: int


class RescheduleOut(BaseModel):
    id: int
    proposed_slot: SlotOut
    requested_by: int
    expires_at: int


class MySlotOut(SlotOut):
    state: str
    booking_id: str | None
    student: str | None
    students: list[str] = []


class MentorTopicOut(BaseModel):
    id: int
    name: str
    subject_id: int


class PublicReviewOut(BaseModel):
    rating: int
    comment: str
    student: str
    created_at: int


class MentorCardOut(MentorProfileOut):
    id: int
    name: str
    course: int
    campus: str
    languages: list[str]
    topics: list[MentorTopicOut]
    rating: float | None
    review_count: int
    rating_score: float | None = None
    is_favorite: bool = False
    slots: list[SlotOut]
    reasons: list[str]
    reviews: list[PublicReviewOut] | None = None


class GroupOut(BaseModel):
    capacity: int
    taken: int
    participants: list[str]


class ReceiptOut(BaseModel):
    id: str
    amount: int
    commission: int
    mentor_amount: int


class PaymentOut(ReceiptOut):
    charged: int
    simulation: bool


class ReviewOut(BaseModel):
    rating: int
    comment: str


class QuizSummaryOut(BaseModel):
    id: str
    score: int | None
    total: int


class BookingOut(BaseModel):
    id: str
    student_id: int
    student_name: str
    mentor_id: int
    mentor_name: str
    topic_id: int
    topic: str
    subject_id: int
    slot: SlotOut
    price: int
    status: str
    status_label: str
    description: str
    deadline: int
    format: str
    language: str
    created_at: int
    expires_at: int
    meeting_url: str
    meeting_place: str
    materials: str
    mentor_completed_at: int | None
    reschedule: RescheduleOut | None = None
    group: GroupOut | None = None
    payment: str
    unread_messages: int = 0
    receipt: ReceiptOut | None
    review: ReviewOut | None
    quizzes: dict[str, QuizSummaryOut]


class LessonOut(BookingOut):
    notes: str


class PlantOut(BaseModel):
    subject_id: int
    name: str
    slug: str
    points: int
    level: int
    next_level: int | None


class AchievementOut(BaseModel):
    name: str
    description: str
    earned: bool


class ProgressOut(BaseModel):
    plants: list[PlantOut]
    completed_sessions: int
    successful_tests: int
    points: int
    achievements: list[AchievementOut]


class NotificationOut(BaseModel):
    id: int
    body: str
    kind: str
    booking_id: str | None
    status: str
    read: bool
    due_at: int
    link: str | None = None


class WaitlistOut(BaseModel):
    id: int
    topic: str
    deadline: int
    budget: int


class QuizQuestionOut(BaseModel):
    id: int
    text: str
    options: list[str]


class QuizFeedbackOut(BaseModel):
    correct: int
    explanation: str
    is_correct: bool


class QuizOut(BaseModel):
    id: str
    topic: str
    stage: str
    score: int | None
    submitted: bool
    questions: list[QuizQuestionOut]
    answers: list[int] | None = None
    feedback: list[QuizFeedbackOut] | None = None


class DemoAccountOut(BaseModel):
    id: int
    name: str
    role: str


class ConfigOut(BaseModel):
    mode: Literal["demo", "site"]
    timezone: str
    payment: str
    demo_accounts: list[DemoAccountOut]


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    mode: str
    notification_worker: str


class TopicCountOut(BaseModel):
    topic: str
    count: int


class StatsOut(BaseModel):
    total: int
    completed: int
    completion_rate: float | None
    cancelled: int
    median_confirmation_seconds: float | None
    repeat_students: int
    unique_students: int
    repeat_rate: float | None
    topics: list[TopicCountOut]
    definitions: dict[str, str]


class AdminWaitlistOut(BaseModel):
    student: str
    topic: str
    deadline: int
    budget: int


class DeliveryIssueOut(BaseModel):
    id: int
    status: str
    kind: str


class AdminOut(BaseModel):
    stats: StatsOut
    mentors: list[MentorCardOut]
    bookings: list[BookingOut]
    catalog: list[SubjectOut]
    waitlist: list[AdminWaitlistOut]
    delivery_issues: list[DeliveryIssueOut]


class MessageOut(BaseModel):
    id: int
    sender_id: int
    sender_name: str
    body: str
    created_at: int
    client_id: str


class ThreadOut(BaseModel):
    thread: str
    can_write: bool
    messages: list[MessageOut]
    my_last_read_id: int
    others_last_read_id: int


class TicketOut(BaseModel):
    ticket: str


class ExportMessageOut(BaseModel):
    thread: str
    body: str
    created_at: int


class ExportNoteOut(BaseModel):
    booking_id: str
    body: str
    updated_at: int


class ExportAttemptOut(BaseModel):
    id: str
    topic_id: int
    booking_id: str | None
    stage: str
    score: int | None
    created_at: int
    submitted_at: int | None


class ExportOut(BaseModel):
    exported_at: int
    profile: UserOut
    bookings: list[BookingOut]
    notes: list[ExportNoteOut]
    quiz_attempts: list[ExportAttemptOut]
    progress: ProgressOut
    waitlist: list[WaitlistOut]
    messages: list[ExportMessageOut]
