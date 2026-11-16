import uuid

from sqlalchemy import select

from .models import Booking, QuizAttempt, Topic
from .service import award, fail, get, now

# Each topic has independent pre/post sets of three questions. Answers stay server-side.
BANK = {
    "sql-join": [
        (
            "Какой JOIN сохраняет все строки слева?",
            ["INNER JOIN", "LEFT JOIN", "CROSS JOIN"],
            1,
            "LEFT JOIN сохраняет строки левой таблицы, даже без совпадений справа.",
        ),
        (
            "Что будет справа при отсутствии совпадения в LEFT JOIN?",
            ["0", "NULL", "Ошибка"],
            1,
            "SQL подставляет NULL в столбцы правой таблицы.",
        ),
        (
            "Как соединить users и orders по владельцу заказа?",
            ["ON users.id = orders.user_id", "ON users.name > orders.id", "LIMIT orders.user_id"],
            0,
            "ON задаёт условие соответствия строк; здесь это ключ пользователя.",
        ),
        (
            "Какой JOIN вернёт только совпавшие строки?",
            ["LEFT JOIN", "INNER JOIN", "FULL OUTER JOIN"],
            1,
            "INNER JOIN возвращает строки, для которых условие соединения истинно.",
        ),
        (
            "У одного пользователя три заказа. Сколько его строк даст INNER JOIN с заказами?",
            ["Одну", "Три", "Всегда ноль"],
            1,
            "Каждая подходящая пара образует строку результата.",
        ),
        (
            "Как найти пользователей без заказов после LEFT JOIN?",
            ["WHERE orders.id IS NULL", "WHERE orders.id = NULL", "WHERE users.id = 0"],
            0,
            "Отсутствующее совпадение проверяют через IS NULL.",
        ),
    ],
    "sql-group": [
        (
            "Что делает GROUP BY?",
            ["Группирует строки", "Удаляет таблицу", "Соединяет базы"],
            0,
            "GROUP BY объединяет строки с одинаковыми значениями ключей группировки.",
        ),
        (
            "Что считает COUNT(*)?",
            ["Только ненулевые цены", "Все строки группы", "Число таблиц"],
            1,
            "COUNT(*) считает все строки, включая строки с NULL в отдельных столбцах.",
        ),
        (
            "Как фильтровать группы после агрегации?",
            ["HAVING", "LIMIT BY", "JOIN"],
            0,
            "HAVING фильтрует результат группировки.",
        ),
        (
            "Как получить сумму amount по каждому user_id?",
            [
                "SELECT user_id, SUM(amount) FROM orders GROUP BY user_id",
                "SELECT SUM(user_id) FROM orders",
                "SELECT amount FROM orders LIMIT 1",
            ],
            0,
            "Ключ группировки — user_id, агрегат — SUM(amount).",
        ),
        (
            "Как оставить группы с более чем двумя заказами?",
            ["WHERE COUNT(*) > 2", "HAVING COUNT(*) > 2", "ORDER COUNT(*) > 2"],
            1,
            "Условие по агрегату задаётся в HAVING.",
        ),
        (
            "Чем COUNT(column) отличается от COUNT(*)?",
            ["Не учитывает NULL в column", "Всегда больше", "Считает таблицы"],
            0,
            "COUNT(column) учитывает только ненулевые значения выбранного столбца.",
        ),
    ],
    "python-basics": [
        (
            "Чему равно len([2, 4, 6])?",
            ["2", "3", "6"],
            1,
            "len возвращает число элементов коллекции.",
        ),
        (
            "Как проверить равенство?",
            ["=", "==", ":="],
            1,
            "== сравнивает значения, = присваивает.",
        ),
        (
            "Что выдаёт list(range(3))?",
            ["[1, 2, 3]", "[0, 1, 2]", "[0, 1, 2, 3]"],
            1,
            "Правая граница range не включается.",
        ),
        (
            "Какое значение у [10, 20, 30][1]?",
            ["10", "20", "30"],
            1,
            "Индексы списков начинаются с нуля.",
        ),
        (
            "Как повторить действие для каждого элемента items?",
            ["for item in items:", "if items:", "def items:"],
            0,
            "Цикл for последовательно перебирает элементы.",
        ),
        ("Что вернёт 7 // 2?", ["3.5", "3", "1"], 1, "// выполняет деление с округлением вниз."),
    ],
    "python-functions": [
        (
            "Как объявить функцию?",
            ["def greet():", "function greet[]", "new greet()"],
            0,
            "В Python функция объявляется через def.",
        ),
        (
            "Для чего нужен return?",
            ["Вернуть результат", "Напечатать текст", "Импортировать модуль"],
            0,
            "return завершает вызов и возвращает значение.",
        ),
        (
            "Что вернёт функция без return?",
            ["0", "None", "False"],
            1,
            "Без явного return функция возвращает None.",
        ),
        (
            "def add(a, b=2): return a+b. Чему равно add(3)?",
            ["3", "5", "Ошибка"],
            1,
            "Для b используется значение по умолчанию 2.",
        ),
        (
            "Как передать именованный аргумент?",
            ["greet(name='Aya')", "greet(name:'Aya')", "greet['Aya']"],
            0,
            "Именованный аргумент записывается как имя=значение.",
        ),
        (
            "Чем return value отличается от print(value)?",
            ["return отдаёт значение вызывающему коду", "Разницы нет", "print завершает программу"],
            0,
            "print выводит текст, return передаёт результат вызывающему коду.",
        ),
    ],
    "net-ip": [
        (
            "Сколько бит в IPv4-адресе?",
            ["16", "32", "128"],
            1,
            "IPv4 состоит из четырёх октетов по 8 бит.",
        ),
        (
            "Какая маска соответствует /24?",
            ["255.255.255.0", "255.0.0.0", "255.255.0.0"],
            0,
            "/24 означает 24 бита сетевой части.",
        ),
        (
            "Для чего нужен шлюз по умолчанию?",
            ["Для выхода в другие сети", "Для хранения пароля", "Для выдачи имени файла"],
            0,
            "Через шлюз отправляют пакеты, для которых нет более точного маршрута.",
        ),
        (
            "В одной ли подсети 192.168.1.2/24 и 192.168.1.50/24?",
            ["Да", "Нет", "Только при одинаковом MAC"],
            0,
            "У обоих сетевой адрес 192.168.1.0/24.",
        ),
        (
            "Каков адрес сети для 10.0.0.77/24?",
            ["10.0.0.77", "10.0.0.0", "10.0.0.255"],
            1,
            "Последний октет относится к хосту; у адреса сети он равен нулю.",
        ),
        (
            "Какой диапазон — частный IPv4?",
            ["192.168.0.0/16", "8.8.8.0/24", "1.1.1.0/24"],
            0,
            "192.168.0.0/16 зарезервирован для частных сетей.",
        ),
    ],
    "net-protocols": [
        (
            "Что делает DNS?",
            [
                "Сопоставляет доменные имена и записи, включая IP",
                "Шифрует диск",
                "Заменяет маршрутизатор",
            ],
            0,
            "DNS позволяет получить записи для доменного имени.",
        ),
        (
            "Какой протокол обеспечивает надёжный упорядоченный поток?",
            ["UDP", "TCP", "ARP"],
            1,
            "TCP обеспечивает доставку упорядоченного потока с повторной передачей потерь.",
        ),
        (
            "Для чего используется DHCP?",
            ["Автоматически выдаёт сетевые настройки", "Хранит веб-страницы", "Переводит код"],
            0,
            "DHCP выдаёт IP-адрес и другие параметры сети.",
        ),
        (
            "Какой протокол обычно использует ping?",
            ["ICMP", "SMTP", "FTP"],
            0,
            "ping использует ICMP Echo Request и Echo Reply.",
        ),
        (
            "Что определяет ARP в локальной IPv4-сети?",
            ["MAC-адрес по IPv4-адресу", "Пароль Wi-Fi", "Домен по URL"],
            0,
            "ARP помогает найти канальный адрес соседнего устройства.",
        ),
        (
            "Чем UDP отличается от TCP?",
            [
                "Не гарантирует доставку и порядок",
                "Всегда шифрует данные",
                "Работает только без IP",
            ],
            0,
            "UDP передаёт датаграммы без гарантий доставки и порядка.",
        ),
    ],
}


def attempt_json(session, attempt):
    topic = get(session, Topic, attempt.topic_id)
    bank = BANK[topic.code]
    result = {
        "id": attempt.id,
        "topic": topic.name,
        "stage": attempt.stage,
        "score": attempt.score,
        "submitted": attempt.submitted_at is not None,
        "questions": [
            {"id": i, "text": bank[i][0], "options": bank[i][1]} for i in attempt.question_ids
        ],
    }
    if attempt.submitted_at is not None:
        result["answers"] = attempt.answers
        result["feedback"] = [
            {
                "correct": bank[i][2],
                "explanation": bank[i][3],
                "is_correct": attempt.answers[j] == bank[i][2],
            }
            for j, i in enumerate(attempt.question_ids)
        ]
    return result


def start_attempt(session, user, topic_id, stage, booking_id):
    topic = get(session, Topic, topic_id)
    if topic.code not in BANK:
        fail(422, "Для этой темы вопросы ещё не подготовлены")
    if stage not in ("pre", "post", "practice"):
        fail(422, "Неизвестный этап теста")
    if stage != "practice":
        booking = get(session, Booking, booking_id)
        if booking.student_id != user.id or booking.topic_id != topic_id:
            fail(403, "Тест недоступен для этого занятия")
        existing = session.scalar(
            select(QuizAttempt).where(
                QuizAttempt.booking_id == booking.id, QuizAttempt.stage == stage
            )
        )
        if existing:
            return attempt_json(session, existing)
        if stage == "post" and booking.status != "completed":
            fail(409, "Тест после занятия доступен после завершения")
        if stage == "pre" and booking.status not in ("pending", "confirmed"):
            fail(409, "Тест до занятия доступен для активной записи")
    else:
        booking_id = None
        pending = session.scalar(
            select(QuizAttempt).where(
                QuizAttempt.user_id == user.id,
                QuizAttempt.topic_id == topic_id,
                QuizAttempt.stage == "practice",
                QuizAttempt.submitted_at.is_(None),
            )
        )
        if pending:
            return attempt_json(session, pending)
    attempt = QuizAttempt(
        id=str(uuid.uuid4()),
        user_id=user.id,
        topic_id=topic_id,
        booking_id=booking_id,
        stage=stage,
        question_ids=[3, 4, 5] if stage == "post" else [0, 1, 2],
        created_at=now(),
    )
    session.add(attempt)
    session.flush()
    return attempt_json(session, attempt)


def submit_attempt(session, user, attempt_id, answers):
    attempt = get(session, QuizAttempt, attempt_id)
    if attempt.user_id != user.id:
        fail(403, "Это попытка другого пользователя")
    if attempt.submitted_at is not None:
        return attempt_json(session, attempt)
    if attempt.booking_id:
        booking = get(session, Booking, attempt.booking_id)
        if attempt.stage == "pre" and booking.status not in ("pending", "confirmed"):
            fail(409, "Время теста до занятия прошло")
        if attempt.stage == "post" and booking.status != "completed":
            fail(409, "Занятие ещё не завершено")
    topic = get(session, Topic, attempt.topic_id)
    bank = BANK[topic.code]
    if len(answers) != len(attempt.question_ids) or any(
        type(a) is not int or a < 0 or a >= len(bank[i][1])
        for a, i in zip(answers, attempt.question_ids, strict=True)
    ):
        fail(422, "Ответьте на каждый вопрос")
    attempt.answers = answers
    attempt.score = sum(a == bank[i][2] for a, i in zip(answers, attempt.question_ids, strict=True))
    attempt.submitted_at = now()
    if attempt.score >= 2:
        award(session, user.id, topic.subject_id, f"quiz:{topic.id}:{attempt.stage}", 20)
    session.flush()
    return attempt_json(session, attempt)
