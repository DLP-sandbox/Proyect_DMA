-- DLP Market Analyzer — Supabase Schema
-- Ejecutar en: Supabase Dashboard → SQL Editor → New Query → Run

-- ── Tabla: análisis guardados por usuario ─────────────────────────────────
CREATE TABLE IF NOT EXISTS user_analyses (
    uid         TEXT        NOT NULL,
    ticker      TEXT        NOT NULL,
    data        JSONB       NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (uid, ticker)
);

-- ── Tabla: historial de scans por usuario ─────────────────────────────────
CREATE TABLE IF NOT EXISTS user_scans (
    uid         TEXT        NOT NULL,
    scan_id     TEXT        NOT NULL,
    label       TEXT        NOT NULL DEFAULT '',
    count       INTEGER     NOT NULL DEFAULT 0,
    data        JSONB       NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (uid, scan_id)
);

-- ── Tabla: contador de uso mensual por usuario ────────────────────────────
CREATE TABLE IF NOT EXISTS user_usage (
    uid             TEXT        NOT NULL,
    month_key       TEXT        NOT NULL,   -- formato 'YYYY-MM'
    analyses_used   INTEGER     NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (uid, month_key)
);

-- ── Índices para queries frecuentes ───────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_user_analyses_uid     ON user_analyses(uid);
CREATE INDEX IF NOT EXISTS idx_user_scans_uid        ON user_scans(uid);
CREATE INDEX IF NOT EXISTS idx_user_scans_created    ON user_scans(uid, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_usage_uid        ON user_usage(uid);

-- ── Row Level Security (recomendado para producción) ──────────────────────
-- La app usa la anon key y accede con uid hasheado — habilitar RLS
-- cuando implementes autenticación real con JWT.
-- Por ahora, desactivado para simplicidad con anon key:
ALTER TABLE user_analyses DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_scans    DISABLE ROW LEVEL SECURITY;
ALTER TABLE user_usage    DISABLE ROW LEVEL SECURITY;
