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


def describe_url(url: str) -> str:
    """Describe el tipo de dirección sin revelar contraseña ni identificador del proyecto."""
    from urllib.parse import urlsplit

    if "YOUR-PASSWORD" in url or "[" in url:
        return "todavía contiene [YOUR-PASSWORD]: reemplázalo (con corchetes) por tu contraseña"
    try:
        parts = urlsplit(url.strip())
        host, port = parts.hostname or "", parts.port
    except ValueError:
        return "no se pudo leer la dirección (¿caracteres especiales en la contraseña?)"
    notes = []
    if parts.scheme not in ("postgresql", "postgres"):
        notes.append("no empieza con postgresql://")
    if host.endswith("pooler.supabase.com"):
        kind = "Session pooler" if port == 5432 else f"Transaction pooler (puerto {port})"
    elif host.startswith("db.") and host.endswith(".supabase.co"):
        kind = "Direct connection (no funciona desde GitHub: usa Session pooler)"
    else:
        kind = "no parece una dirección de Supabase"
    notes.append(f"tipo: {kind}")
    return "; ".join(notes)


def password_problem(url: str) -> str | None:
    """Detecta caracteres que rompen la dirección, sin mostrar la contraseña."""
    rest = url.strip().split("://", 1)[-1]
    if rest.count("@") > 1:
        return ("La contraseña contiene '@', que rompe la dirección. Cambia la contraseña en "
                "Supabase por una solo con letras y números y actualiza el secret DATABASE_URL.")
    userinfo = rest.rsplit("@", 1)[0] if "@" in rest else ""
    password = userinfo.split(":", 1)[1] if ":" in userinfo else ""
    bad = sorted({c for c in password if c in "/?#[]% "})
    if bad:
        return ("La contraseña contiene caracteres especiales que rompen la dirección. Usa una "
                "contraseña solo con letras y números y actualiza el secret DATABASE_URL.")
    return None


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Falta DATABASE_URL", file=sys.stderr)
        return 1
    problem = password_problem(url)
    if problem:
        print(problem, file=sys.stderr)
        return 1
    try:
        conn = connect(url.strip())
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo conectar a la base de datos ({type(exc).__name__}): "
              f"{_hint(str(exc))}", file=sys.stderr)
        print(f"Dirección recibida → {describe_url(url)}", file=sys.stderr)
        return 1
    with conn:
        applied = apply_migrations(conn)
    print(f"{len(applied)} migración(es) aplicada(s): {', '.join(applied) or 'ninguna'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
