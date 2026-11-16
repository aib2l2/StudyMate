import math

from sqlalchemy import select

from .models import Booking, Mentor, Review, Slot, Subject, Topic, User
from .service import award, notify, now

CATALOG = [
    (
        1,
        "sql",
        "Базы данных",
        [(1, "SQL JOIN", "sql-join"), (2, "Группировка и агрегаты", "sql-group")],
    ),
    (
        2,
        "python",
        "Python",
        [(3, "Основы Python", "python-basics"), (4, "Функции и аргументы", "python-functions")],
    ),
    (
        3,
        "networks",
        "Компьютерные сети",
        [(5, "IPv4 и подсети", "net-ip"), (6, "Сетевые протоколы", "net-protocols")],
    ),
]


def seed(db):
    with db.transaction() as session:
        if not session.scalar(select(Subject.id)):
            for sid, slug, name, topics in CATALOG:
                session.add(Subject(id=sid, slug=slug, name=name))
                session.flush()
                for tid, title, code in topics:
                    session.add(Topic(id=tid, subject_id=sid, name=title, code=code))
            session.flush()
        if db.settings.mode != "demo":
            return
        if session.get(User, 1):
            seed_v22(session)  # existing demo databases get the 2.2 examples too
            return
        session.add_all(
            [
                User(
                    id=1,
                    name="Аликхан",
                    course=2,
                    languages=["ru", "en"],
                    interests=[1, 2],
                    registered=True,
                ),
                User(
                    id=3,
                    name="Ерлан",
                    course=2,
                    languages=["ru"],
                    interests=[1, 3],
                    registered=True,
                ),
                User(
                    id=99,
                    name="Команда StudyMate",
                    course=4,
                    languages=["ru", "en"],
                    interests=[1, 2, 3],
                    registered=True,
                    is_admin=True,
                ),
            ]
        )
        mentors = [
            (
                2,
                "Аяулым",
                4,
                [1, 2],
                2500,
                "Прошла курс баз данных в AITU. Разбираем JOIN на понятных таблицах и пишем запросы вместе.",
            ),
            (
                10,
                "Данияр",
                3,
                [3, 4],
                2000,
                "Помогаю освоить Python: от первого цикла до функций. Объясняю небольшими шагами.",
            ),
            (
                11,
                "Мадина",
                4,
                [5, 6],
                2800,
                "Разбираю подсети, маршрутизацию и протоколы на схемах и примерах Packet Tracer.",
            ),
            (
                12,
                "Тимур",
                3,
                [1, 3],
                2200,
                "Люблю задачи с данными. Помогу понять запросы и перенести логику в Python.",
            ),
            (
                13,
                "Аружан",
                4,
                [2, 4],
                3000,
                "Спокойная подготовка к лабораторным. После объяснения решаем похожую задачу самостоятельно.",
            ),
            (
                14,
                "Ерасыл",
                3,
                [5, 6],
                2000,
                "Разберём IPv4 и маски без зубрёжки. Есть опыт взаимопомощи в учебной группе.",
            ),
            (
                15,
                "Амина",
                4,
                [1, 2],
                2700,
                "Показываю, как читать условие задачи и проверять SQL-запрос на маленьком наборе данных.",
            ),
            (
                16,
                "Санжар",
                3,
                [3, 4],
                1800,
                "Функции, списки, циклы. Сначала обсуждаем твою попытку, затем вместе ищем ошибку.",
            ),
            (
                17,
                "Диана",
                4,
                [5, 6],
                2500,
                "Помогаю связать теорию сетей с тем, что происходит при открытии сайта и отправке пакетов.",
            ),
        ]
        base = math.ceil(now() / 1800) * 1800
        for i, (uid, name, course, topics, price, bio) in enumerate(mentors):
            session.add(
                User(
                    id=uid,
                    name=name,
                    course=course,
                    languages=["ru", "en"] if i % 3 != 2 else ["ru", "kk"],
                    interests=list(set((t + 1) // 2 for t in topics)),
                    registered=True,
                )
            )
            session.flush()
            session.add(
                Mentor(
                    user_id=uid,
                    bio=bio,
                    price=price,
                    topic_ids=topics,
                    formats=["online", "campus"] if i % 2 == 0 else ["online"],
                    verified=i < 5,
                    active=True,
                )
            )
            session.flush()
            for day in range(4):
                for step in range(3):
                    start = base + (i % 3 + 1) * 3600 + day * 86400 + step * 1800
                    session.add(Slot(mentor_id=uid, starts_at=start, ends_at=start + 1800))
            # Historical records are explicitly synthetic, as is this whole database.
            old_slot = Slot(
                mentor_id=uid,
                starts_at=base - (i + 2) * 86400,
                ends_at=base - (i + 2) * 86400 + 1800,
            )
            session.add(old_slot)
            session.flush()
            student_id = 1 if uid == 10 else 3
            booking = Booking(
                id=f"demo-history-{uid}",
                student_id=student_id,
                mentor_id=uid,
                slot_id=old_slot.id,
                topic_id=topics[0],
                price=price,
                status="completed",
                description="Пример проведённого занятия. Демо-данные.",
                deadline=old_slot.ends_at + 86400,
                language="ru",
                format="online",
                created_at=old_slot.starts_at - 7200,
                confirmed_at=old_slot.starts_at - 6600,
                completed_at=old_slot.ends_at,
                expires_at=old_slot.starts_at - 6300,
                request_key=f"seed-{uid}",
            )
            session.add(booking)
            session.flush()
            if uid != 10:
                session.add(
                    Review(
                        booking_id=booking.id,
                        student_id=student_id,
                        mentor_id=uid,
                        rating=5 if i % 3 else 4,
                        comment="Демонстрационный отзыв: объяснение на примерах помогло разобраться.",
                        created_at=old_slot.ends_at + 600,
                    )
                )
            award(session, student_id, (topics[0] + 1) // 2, f"session:{booking.id}", 30)
        session.flush()
        slot = session.scalar(
            select(Slot)
            .where(Slot.mentor_id == 2, Slot.starts_at > now())
            .order_by(Slot.starts_at.desc())
        )
        booking = Booking(
            id="demo-incoming",
            student_id=3,
            mentor_id=2,
            slot_id=slot.id,
            topic_id=1,
            price=2500,
            status="pending",
            description="Путаю INNER и LEFT JOIN. Хочу разобрать на примере заказов.",
            deadline=slot.ends_at + 3600,
            language="ru",
            format="online",
            created_at=now(),
            expires_at=now() + 900,
            request_key="seed-incoming",
        )
        session.add(booking)
        session.flush()
        notify(
            session,
            2,
            booking.id,
            "new_booking",
            "Новая демозаявка от Ерлана: SQL JOIN",
            "demo-incoming:new",
        )
        session.flush()
        from .search import reindex_all

        reindex_all(session)
        seed_v22(session)


DEMO_GROUP_URL = "https://meet.example.org/studymate-group-demo"
DEMO_SERIES = "demo-series-ayaulym"


def _free(session, mentor_id, start):
    return not session.scalar(
        select(Slot.id).where(
            Slot.mentor_id == mentor_id, Slot.starts_at < start + 1800, Slot.ends_at > start
        )
    )


def seed_v22(session):
    """2.2 demo examples. Idempotent: every block checks a stable marker first."""
    from .models import ChatMessage, Favorite, SlotMeeting, Waitlist

    base = math.ceil(now() / 1800) * 1800
    # A weekly series for Ayaulym (4 weeks).
    if not session.scalar(
        select(Slot.id).where(Slot.series_id == DEMO_SERIES, Slot.starts_at > now())
    ):
        first = base + 6 * 86400 + 13 * 3600
        for week in range(4):
            start = first + week * 7 * 86400
            if _free(session, 2, start):
                session.add(
                    Slot(mentor_id=2, starts_at=start, ends_at=start + 1800, series_id=DEMO_SERIES)
                )
        session.flush()
    # A group lesson "SQL JOIN, 4 seats" where Erlan already holds a seat.
    upcoming_group = session.scalar(
        select(Slot)
        .join(SlotMeeting, SlotMeeting.slot_id == Slot.id)
        .where(
            Slot.mentor_id == 2, Slot.starts_at > now(), SlotMeeting.meeting_url == DEMO_GROUP_URL
        )
    )
    if upcoming_group is None:
        start = base + 2 * 86400 + 5 * 3600
        while not _free(session, 2, start):
            start += 1800
        slot = Slot(
            mentor_id=2,
            starts_at=start,
            ends_at=start + 1800,
            capacity=4,
            topic_id=1,
            price=1200,
            min_participants=2,
        )
        session.add(slot)
        session.flush()
        session.add(SlotMeeting(slot_id=slot.id, format="online", meeting_url=DEMO_GROUP_URL))
        session.add(
            Booking(
                id=f"demo-group-{slot.id}",
                student_id=3,
                mentor_id=2,
                slot_id=slot.id,
                topic_id=1,
                price=1200,
                status="confirmed",
                description="Хочу разобрать JOIN вместе с другими. Демо-данные.",
                deadline=slot.ends_at + 86400,
                language="ru",
                format="online",
                created_at=now(),
                confirmed_at=now(),
                expires_at=slot.starts_at,
                request_key=f"seed-group-{slot.id}",
            )
        )
        session.flush()
    # Alikhan: one favorite mentor and a waitlist request that a new slot will match.
    if session.get(Favorite, (1, 15)) is None:
        session.add(Favorite(user_id=1, mentor_id=15, created_at=now()))
    if not session.scalar(
        select(Waitlist.id).where(Waitlist.student_id == 1, Waitlist.deadline > now())
    ):
        window = base + 9 * 86400 + 12 * 3600
        session.add(
            Waitlist(
                student_id=1,
                topic_id=1,
                budget=3000,
                earliest=window,
                deadline=window + 2 * 3600,
                language="ru",
                format="online",
                created_at=now(),
            )
        )
    # A short chat in the incoming demo request.
    if session.get(Booking, "demo-incoming") and not session.scalar(
        select(ChatMessage.id).where(ChatMessage.client_id == "seed-chat-1")
    ):
        for i, (sender, body) in enumerate(
            [
                (3, "Здравствуйте! Пришлю пример запроса, где путаюсь с LEFT JOIN."),
                (2, "Отлично, присылай. Начнём с того, какие строки должны остаться."),
            ],
            start=1,
        ):
            session.add(
                ChatMessage(
                    thread_key="booking:demo-incoming",
                    sender_id=sender,
                    body=body,
                    created_at=now() - 600 + i * 60,
                    client_id=f"seed-chat-{i}",
                )
            )
    session.flush()
