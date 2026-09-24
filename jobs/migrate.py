"""Aplica las migraciones pendientes de migrations/.

    uv run --env-file .env python -m jobs.migrate
"""

import logging
import os
import sys

from core.db import apply_migrations, connect


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Falta DATABASE_URL", file=sys.stderr)
        return 1
    with connect(url) as conn:
        applied = apply_migrations(conn)
    print(f"{len(applied)} migración(es) aplicada(s): {', '.join(applied) or 'ninguna'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
