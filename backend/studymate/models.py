from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(unique=True)
    telegram_username: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str | None] = mapped_column(Text)
    campus: Mapped[str] = mapped_column(String(100), default="Astana IT University")
    course: Mapped[int] = mapped_column(default=1)
    languages: Mapped[list] = mapped_column(JSON, default=lambda: ["ru"])
    interests: Mapped[list] = mapped_column(JSON, default=list)
    registered: Mapped[bool] = mapped_column(Boolean, default=False)
    bot_started: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Topic(Base):
    __tablename__ = "topics"
    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(30), unique=True)


class Mentor(Base):
    __tablename__ = "mentors"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    bio: Mapped[str] = mapped_column(Text)
    price: Mapped[int] = mapped_column(default=2500)
    topic_ids: Mapped[list] = mapped_column(JSON, default=list)
    formats: Mapped[list] = mapped_column(JSON, default=lambda: ["online"])
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("price >= 0 AND price <= 100000"),)


class Slot(Base):
    __tablename__ = "slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("mentors.user_id"), index=True)
    starts_at: Mapped[int] = mapped_column(index=True)
    ends_at: Mapped[int] = mapped_column()
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    series_id: Mapped[str | None] = mapped_column(String(36), index=True)
    # Group lessons: several students share one slot (capacity > 1).
    capacity: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"))
    price: Mapped[int | None] = mapped_column()
    min_participants: Mapped[int] = mapped_column(default=1, server_default=text("1"))
    __table_args__ = (
        UniqueConstraint("mentor_id", "starts_at"),
        CheckConstraint("ends_at > starts_at"),
        CheckConstraint("capacity BETWEEN 1 AND 5", name="ck_slots_capacity"),
        CheckConstraint(
            "capacity = 1 OR (topic_id IS NOT NULL AND price IS NOT NULL)",
            name="ck_slots_group_fields",
        ),
        CheckConstraint("min_participants BETWEEN 1 AND capacity", name="ck_slots_min"),
    )


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("mentors.user_id"), index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    price: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String(20), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[int] = mapped_column()
    language: Mapped[str] = mapped_column(String(10), default="ru")
    format: Mapped[str] = mapped_column(String(10), default="online")
    created_at: Mapped[int] = mapped_column()
    expires_at: Mapped[int] = mapped_column()
    confirmed_at: Mapped[int | None] = mapped_column()
    completed_at: Mapped[int | None] = mapped_column()
    request_key: Mapped[str] = mapped_column(String(80))
    meeting_url: Mapped[str] = mapped_column(Text, default="")
    meeting_place: Mapped[str] = mapped_column(Text, default="")
    materials: Mapped[str] = mapped_column(Text, default="")
    mentor_completed_at: Mapped[int | None] = mapped_column()
    reschedule_count: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    __table_args__ = (
        UniqueConstraint("student_id", "request_key"),
        # Capacity itself is guarded by the slot_capacity_* triggers (migration 008).
        Index(
            "one_active_seat_per_student",
            "slot_id",
            "student_id",
            unique=True,
            sqlite_where=text("status IN ('pending', 'confirmed')"),
        ),
        CheckConstraint(
            "status IN ('pending','confirmed','completed','cancelled','rejected','expired')"
        ),
    )


class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), unique=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    mentor_id: Mapped[int] = mapped_column(ForeignKey("mentors.user_id"), index=True)
    rating: Mapped[int] = mapped_column()
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column()
    __table_args__ = (CheckConstraint("rating >= 1 AND rating <= 5"),)


class Waitlist(Base):
    __tablename__ = "waitlist"
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    budget: Mapped[int] = mapped_column()
    deadline: Mapped[int] = mapped_column()
    earliest: Mapped[int] = mapped_column()
    language: Mapped[str] = mapped_column(String(10))
    format: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[int] = mapped_column()
    __table_args__ = (UniqueConstraint("student_id", "topic_id", "deadline"),)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"))
    booking_id: Mapped[str | None] = mapped_column(ForeignKey("bookings.id"))
    stage: Mapped[str] = mapped_column(String(15))
    question_ids: Mapped[list] = mapped_column(JSON)
    answers: Mapped[list | None] = mapped_column(JSON)
    score: Mapped[int | None] = mapped_column()
    created_at: Mapped[int] = mapped_column()
    submitted_at: Mapped[int | None] = mapped_column()
    __table_args__ = (UniqueConstraint("booking_id", "stage"),)


class ProgressEvent(Base):
    __tablename__ = "progress_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    source: Mapped[str] = mapped_column(String(100))
    points: Mapped[int] = mapped_column()
    created_at: Mapped[int] = mapped_column()
    __table_args__ = (UniqueConstraint("user_id", "source"),)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    booking_id: Mapped[str | None] = mapped_column(ForeignKey("bookings.id"))
    kind: Mapped[str] = mapped_column(String(30))
    body: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(120), unique=True)
    due_at: Mapped[int] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(default=0)
    sent_at: Mapped[int | None] = mapped_column()
    error: Mapped[str | None] = mapped_column(String(100))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    link: Mapped[str | None] = mapped_column(String(200))
    slot_id: Mapped[int | None] = mapped_column()


class SessionToken(Base):
    __tablename__ = "session_tokens"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[int] = mapped_column()


class PaymentSimulation(Base):
    __tablename__ = "payment_simulations"
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), primary_key=True)
    receipt_id: Mapped[str] = mapped_column(String(40), unique=True)
    amount: Mapped[int] = mapped_column()
    commission: Mapped[int] = mapped_column()
    created_at: Mapped[int] = mapped_column()


class LessonNote(Base):
    __tablename__ = "lesson_notes"
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    body: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[int] = mapped_column()


class PasswordResetCode(Base):
    """One-time code issued locally by the Mac owner (``studymate reset-password``)."""

    __tablename__ = "password_reset_codes"
    code_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[int] = mapped_column()
    used_at: Mapped[int | None] = mapped_column()


class ChatMessage(Base):
    """A message in a lesson thread: ``booking:{id}`` (1:1) or ``slot:{id}`` (group)."""

    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    thread_key: Mapped[str] = mapped_column(String(60))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column()
    client_id: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint("sender_id", "client_id"),
        Index("ix_chat_messages_thread", "thread_key", "id"),
        CheckConstraint("length(body) BETWEEN 1 AND 2000"),
    )


class ChatRead(Base):
    __tablename__ = "chat_reads"
    thread_key: Mapped[str] = mapped_column(String(60), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    last_read_id: Mapped[int] = mapped_column(default=0)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("mentors.user_id"), primary_key=True)
    created_at: Mapped[int] = mapped_column()


class RescheduleRequest(Base):
    """A proposal to move a 1:1 lesson to another free slot of the same mentor."""

    __tablename__ = "reschedule_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), index=True)
    proposed_slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"))
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(12), default="pending")
    created_at: Mapped[int] = mapped_column()
    expires_at: Mapped[int] = mapped_column()
    __table_args__ = (
        CheckConstraint("status IN ('pending','accepted','declined','cancelled','expired')"),
        Index(
            "one_pending_reschedule_per_booking",
            "booking_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
        ),
    )


class SlotMeeting(Base):
    """Shared data of a group lesson; 1:1 lessons keep these fields on bookings."""

    __tablename__ = "slot_meetings"
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), primary_key=True)
    format: Mapped[str] = mapped_column(String(10), default="online")
    meeting_url: Mapped[str] = mapped_column(Text, default="")
    meeting_place: Mapped[str] = mapped_column(Text, default="")
    materials: Mapped[str] = mapped_column(Text, default="")
    mentor_completed_at: Mapped[int | None] = mapped_column()
    cancelled_at: Mapped[int | None] = mapped_column()
