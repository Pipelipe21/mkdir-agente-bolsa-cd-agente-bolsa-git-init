"""Aplica las migraciones pendientes de migrations/.

    uv run --env-file .env python -m jobs.migrate
"""

import logging
import os
import sys

from core.db import apply_migrations, connect


def _hint(error: str) -> str:
    """Traduce errores comunes de conexión sin repetir la URL (contiene la contraseña)."""
    lowered = error.lower()
    if "password authentication failed" in lowered:
        return "contraseña incorrecta (¿reemplazaste [YOUR-PASSWORD] por tu contraseña?)"
    if "tenant or user not found" in lowered:
        return "usuario/proyecto no encontrado (copia la URI de nuevo desde Connect)"
    if any(k in lowered for k in ("network is unreachable", "translate host", "resolve host")):
        return "no se alcanza el servidor (usa la URI del 'Session pooler', no la 'Direct')"
    if "invalid" in lowered and "dsn" in lowered:
        return "la URI está mal formada (¿caracteres especiales en la contraseña?)"
    return "revisa que el secret DATABASE_URL sea la URI completa del Session pooler"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Falta DATABASE_URL", file=sys.stderr)
        return 1
    try:
        conn = connect(url.strip())
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo conectar a la base de datos ({type(exc).__name__}): "
              f"{_hint(str(exc))}", file=sys.stderr)
        return 1
    with conn:
        applied = apply_migrations(conn)
    print(f"{len(applied)} migración(es) aplicada(s): {', '.join(applied) or 'ninguna'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
