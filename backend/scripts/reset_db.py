"""Drop and recreate a development database, then apply all migrations.

    uv run python scripts/reset_db.py            # resets DATABASE_URL (asks for confirmation)
    uv run python scripts/reset_db.py --yes --seed
    uv run python scripts/reset_db.py --database-url postgresql+psycopg://.../jlpt_e2e --yes

Refuses to run when APP_ENV=production.
"""

import argparse
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402


def reset(url: str) -> None:
    target = make_url(url)
    name = target.database
    if not name:
        raise SystemExit("Database URL has no database name")
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        conn.execute(text(f"CREATE DATABASE \"{name}\" ENCODING 'UTF8' TEMPLATE template0"))
    admin.dispose()

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--database-url", help="defaults to DATABASE_URL")
    parser.add_argument("--yes", action="store_true", help="do not ask for confirmation")
    parser.add_argument("--seed", action="store_true", help="load the self-authored seed dataset")
    args = parser.parse_args()

    settings = get_settings()
    if settings.app_env == "production":
        raise SystemExit("Refusing to reset a database with APP_ENV=production")
    url = args.database_url or settings.database_url
    name = make_url(url).database
    if not args.yes:
        answer = input(f"Drop and recreate database '{name}'? [y/N] ")
        if answer.strip().lower() != "y":
            raise SystemExit("Aborted")

    reset(url)
    print(f"Database '{name}' recreated and migrated to head.")
    if args.seed:
        import os

        os.environ["DATABASE_URL"] = url
        get_settings.cache_clear()
        from app.seed.__main__ import main as seed_main

        seed_main()


if __name__ == "__main__":
    main()
