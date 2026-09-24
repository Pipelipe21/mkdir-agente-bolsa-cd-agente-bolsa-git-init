-- Esquema inicial (fase 1). Modelo de datos descrito en CLAUDE.md.

create table assets (
    id          bigint generated always as identity primary key,
    symbol      text not null,
    type        text not null check (type in ('stock', 'crypto')),
    exchange    text not null default '',
    active      boolean not null default true,
    created_at  timestamptz not null default now(),
    unique (symbol, type, exchange)
);

create table candles (
    asset_id    bigint not null references assets (id),
    timeframe   text not null,
    ts          timestamptz not null,
    open        double precision not null,
    high        double precision not null,
    low         double precision not null,
    close       double precision not null,
    volume      double precision not null,
    primary key (asset_id, timeframe, ts)
);

create table signals (
    id          bigint generated always as identity primary key,
    asset_id    bigint not null references assets (id),
    strategy    text not null,
    direction   text not null check (direction in ('buy', 'sell')),
    strength    double precision not null check (strength between 0 and 1),
    reason      text not null,
    ts          timestamptz not null,  -- vela que generó la señal
    created_at  timestamptz not null default now(),
    -- Una misma vela no puede generar dos veces la misma señal (evita alertas repetidas).
    unique (asset_id, strategy, direction, ts)
);

create table alerts (
    id           bigint generated always as identity primary key,
    signal_id    bigint not null references signals (id),
    channel      text not null,
    sent_at      timestamptz not null default now(),
    llm_summary  text
);

-- Historial completo de operaciones (también para tributación en Chile).
create table trades (
    id          bigint generated always as identity primary key,
    signal_id   bigint references signals (id),
    mode        text not null check (mode in ('backtest', 'paper', 'live')),
    side        text not null check (side in ('buy', 'sell')),
    qty         numeric not null check (qty > 0),
    price       numeric not null check (price > 0),
    fees        numeric not null default 0,
    pnl         numeric,
    ts          timestamptz not null,
    created_at  timestamptz not null default now()
);

create index signals_ts_idx on signals (ts desc);
create index alerts_signal_idx on alerts (signal_id);
create index trades_ts_idx on trades (ts desc);

-- Supabase expone el esquema public por su API REST. Con RLS activo y sin políticas,
-- la API pública no puede leer ni escribir; la conexión directa del job (rol postgres) sí.
alter table assets  enable row level security;
alter table candles enable row level security;
alter table signals enable row level security;
alter table alerts  enable row level security;
alter table trades  enable row level security;
