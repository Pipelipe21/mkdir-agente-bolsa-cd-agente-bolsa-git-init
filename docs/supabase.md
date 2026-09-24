# Configurar Supabase

El radar guarda cada señal y cada alerta enviada. Esto sirve para:
- **No repetir alertas**: si el job corre dos veces sobre la misma vela, la segunda no envía nada.
- **Medir la fase 1**: revisar las alertas de las últimas 2 semanas y ver si fueron confiables.
- **Historial de operaciones** (fases siguientes), también para tributación.

## 1. Crear el proyecto

1. Entra a https://supabase.com → **New project**.
2. Elige un nombre, una **contraseña de base de datos** (guárdala en tu gestor de contraseñas) y una región cercana (p. ej. `South America (São Paulo)`).

## 2. Obtener la URI de conexión

1. En el proyecto, botón **Connect** (arriba).
2. Pestaña **Connection string** → tipo **URI** → modo **Session pooler** (funciona en redes solo IPv4, como Cloud Run).
3. Copia la URI y reemplaza `[YOUR-PASSWORD]` por tu contraseña:

```
postgresql://postgres.abcdefgh:TU_CONTRASEÑA@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
```

> Si la contraseña tiene caracteres especiales (`@`, `:`, `/`, `#`…), cámbiala por una solo con letras y números, o codifícala (p. ej. `@` → `%40`).

## 3. Pegarla en `.env`

```
DATABASE_URL=postgresql://postgres.abcdefgh:TU_CONTRASEÑA@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
```

## 4. Crear las tablas

```bash
uv run --env-file .env python -m jobs.migrate
```

Debe responder `1 migración(es) aplicada(s): 001_init.sql`. Correrlo de nuevo no hace nada.

En Supabase → **Table Editor** vas a ver `assets`, `candles`, `signals`, `alerts` y `trades`.

## Seguridad

- Todas las tablas tienen **RLS activo sin políticas**: la API pública de Supabase (con la llave `anon`) no puede leer ni escribir. El job entra por conexión directa con el usuario `postgres`, que no pasa por RLS.
- No uses ni publiques la llave `service_role`; este proyecto no la necesita.

## Consultas útiles (SQL Editor)

Alertas de las últimas 2 semanas:

```sql
select a.sent_at, s.symbol, sg.strategy, sg.direction, sg.strength, sg.reason
from alerts a
join signals sg on sg.id = a.signal_id
join assets s on s.id = sg.asset_id
where a.sent_at > now() - interval '14 days'
order by a.sent_at desc;
```

## Tests contra Postgres

Los tests de `tests/test_db.py` se omiten salvo que definas `TEST_DATABASE_URL`.
**Usa una base de pruebas: el test borra el esquema `public`.** Nunca apuntes a Supabase.

```bash
TEST_DATABASE_URL=postgresql://postgres@localhost:5432/agente_test uv run pytest
```
