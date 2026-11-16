import argparse
import fcntl
from pathlib import Path

import uvicorn

from .config import Settings
from .db import Database
from .seed import seed


def main():
    parser = argparse.ArgumentParser(description="StudyMate local launcher")
    parser.add_argument(
        "command",
        choices=["serve", "init", "reset-demo", "admin", "reset-password", "openapi", "reindex"],
        nargs="?",
        default="serve",
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--email", help="Existing website account (admin, reset-password)")
    args = parser.parse_args()
    if args.command == "openapi":
        import json

        from .api import create_app
        from .config import ROOT

        target = ROOT / "docs" / "openapi.json"
        schema = create_app(Settings(worker_enabled=False)).openapi()
        target.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n")
        print(f"OpenAPI-схема сохранена: {target.relative_to(ROOT)}")
        return
    settings = Settings.load()
    Path(settings.database).parent.mkdir(parents=True, exist_ok=True)
    # Held for the whole process lifetime, so no context manager.
    lock = open(settings.database + ".lock", "a")  # noqa: SIM115
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("StudyMate уже использует эту базу. Остановите запущенное приложение")
    if args.command == "admin":
        from sqlalchemy import select

        from .models import User

        if not args.email:
            parser.error("Укажите --email существующего аккаунта")
        database = Database(settings)
        database.migrate()
        with database.transaction() as session:
            user = session.scalar(select(User).where(User.email == args.email.strip().lower()))
            if not user:
                parser.error("Сначала зарегистрируйте этот аккаунт на сайте")
            user.is_admin = True
        database.engine.dispose()
        print("Аккаунту предоставлен доступ к разделу команды.")
        lock.close()
        return
    if args.command == "reset-password":
        from sqlalchemy import select

        from .auth import RESET_CODE_SECONDS, issue_reset_code
        from .models import User

        if not args.email:
            parser.error("Укажите --email существующего аккаунта")
        database = Database(settings)
        database.migrate()
        with database.transaction() as session:
            user = session.scalar(select(User).where(User.email == args.email.strip().lower()))
            if not user:
                parser.error("Аккаунт с таким email не найден")
            code = issue_reset_code(session, user.id)
        database.engine.dispose()
        print(f"Одноразовый код для {args.email.strip().lower()}: {code}")
        print(
            f"Действует {RESET_CODE_SECONDS // 60} минут. Передайте его владельцу аккаунта лично."
        )
        print("Ввести код: страница входа → «Забыли пароль?».")
        lock.close()
        return
    if args.command == "reindex":
        from .search import reindex_all

        database = Database(settings)
        database.migrate()
        with database.transaction() as session:
            count = reindex_all(session)
        database.engine.dispose()
        print(f"Поисковый индекс обновлён: {count} анкет.")
        lock.close()
        return
    if args.command == "reset-demo":
        if settings.mode != "demo" or "demo" not in Path(settings.database).name.lower():
            parser.error("Reset is allowed only for a demo database")
        for suffix in ("", "-wal", "-shm"):
            Path(settings.database + suffix).unlink(missing_ok=True)
        print("Демобаза сброшена. Все созданные здесь данные — демонстрационные.")
    if args.command in ("init", "reset-demo"):
        database = Database(settings)
        database.migrate()
        seed(database)
        database.engine.dispose()
        print(f"StudyMate: база подготовлена, режим {settings.mode}.")
    else:
        from .api import create_app

        uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, access_log=False)
    lock.close()


if __name__ == "__main__":
    main()
