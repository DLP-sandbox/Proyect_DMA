"""
DLP Market Analyzer — Bloomberg-grade Dark Theme con animaciones premium.
"""

BLOOMBERG_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ═══════════════════════════════════════════════════════════════════════
   DESIGN TOKENS — única fuente de verdad del sistema visual.
   Obsidiana + oro antiguo: neutros hacen el 90% del trabajo, un solo
   acento usado con avaricia, verde/rojo SOLO con significado financiero.
   ═══════════════════════════════════════════════════════════════════════ */
:root {
    /* Superficies (elevación por capas de fondo, no por bordes) */
    --bg:        #0A0B0D;
    --surface-0: #0D0F12;   /* sidebar / zonas hundidas */
    --surface-1: #101216;   /* cards base */
    --surface-2: #15181D;   /* elementos elevados / hover */
    --surface-3: #1B1F25;   /* nivel más alto */

    /* Líneas: hairlines de bajísimo contraste, nunca gris puro */
    --hairline:    rgba(255,255,255,0.06);
    --hairline-2:  rgba(255,255,255,0.10);
    --border-solid:#232830;

    /* Texto: rampa de 4 pasos — se acabó la sopa de grises */
    --text-hi: #F2F3F5;
    --text:    #C9CDD3;
    --text-2:  #8D949E;
    --text-3:  #5E6570;

    /* Acento único: oro antiguo (calmo, caro) */
    --accent:      #E2B25C;  --accent-rgb: 226,178,92;
    --accent-hi:   #F0C878;  --accent-hi-rgb: 240,200,120;
    --accent-deep: #C08E3B;  --accent-deep-rgb: 192,142,59;

    /* Semánticos: exclusivos para significado financiero */
    --pos:    #3DD68C;  --pos-rgb: 61,214,140;
    --neg:    #F1495F;  --neg-rgb: 241,73,95;
    --info:   #6FA3E0;  --info-rgb: 111,163,224;
    --purple: #9D8CE0;  --purple-rgb: 157,140,224;

    /* Radios con propósito: micro / control / card / hero */
    --r-xs: 4px;  --r-sm: 6px;  --r-md: 10px;  --r-lg: 14px;

    /* Sombras coherentes con UNA luz cenital + brillo interior superior */
    --shadow-1: 0 1px 2px rgba(0,0,0,0.35);
    --shadow-2: 0 4px 14px rgba(0,0,0,0.35);
    --shadow-3: 0 16px 40px rgba(0,0,0,0.5);
    --inset-hi: inset 0 1px 0 rgba(255,255,255,0.04);

    /* Movimiento: curvas con carácter, duraciones cortas */
    --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
    --ease-io:  cubic-bezier(0.77, 0, 0.175, 1);
    --dur-1: 120ms;  --dur-2: 180ms;  --dur-3: 240ms;

    /* Tipos */
    --font-ui:   'Inter', -apple-system, 'Segoe UI', system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;
}

/* ── Animaciones globales (redefinidas: sin neón, con física) ─────────── */
@keyframes pulse-glow {
    0%, 100% { opacity: 1; }
    50%      { opacity: 0.86; }
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}

@keyframes shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

@keyframes slideInRight {
    from { opacity: 0; transform: translateX(12px); }
    to   { opacity: 1; transform: translateX(0); }
}

@keyframes glow-border {
    0%, 100% { box-shadow: 0 0 0 1px rgba(var(--accent-rgb), 0.22); }
    50%      { box-shadow: 0 0 0 1px rgba(var(--accent-rgb), 0.4); }
}

@keyframes blink-cursor {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
}

@keyframes scan-line {
    0%   { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

@keyframes ticker-tick {
    0%   { transform: scale(1); }
    50%  { transform: scale(1.02); }
    100% { transform: scale(1); }
}

/* ── Base ────────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: var(--font-ui) !important;
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}

/* Un único lavado de oro casi imperceptible en la parte superior */
[data-testid="stAppViewContainer"]::before {
    content: '';
    position: fixed;
    top: -30vh; left: 50%;
    width: 120vw; height: 60vh;
    transform: translateX(-50%);
    background: radial-gradient(ellipse at center, rgba(var(--accent-rgb),0.035) 0%, transparent 65%);
    pointer-events: none;
    z-index: 0;
}

::selection { background: rgba(var(--accent-rgb), 0.28); color: var(--text-hi); }

/* Cifras que no bailan: tabular-nums en todo elemento numérico */
.kpi-tile-value, .status-pill-value, .agent-score, .tt-price, .tt-change,
.stock-price, .stock-change, .alpha-progress-value, .qv-value, .pulse-value,
[data-testid="stMetricValue"], [data-testid="stMetricDelta"], .stMarkdown code {
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
}

[data-testid="stMain"] {
    background: transparent !important;
}

[data-testid="stMainBlockContainer"] {
    padding-top: 1.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 1400px !important;
}

[data-testid="stSidebar"] {
    background: var(--surface-0) !important;
    border-right: 1px solid var(--hairline) !important;
    box-shadow: none;
}

[data-testid="stSidebar"] * {
    color: var(--text) !important;
}

#MainMenu, footer, header, [data-testid="stDecoration"] {
    display: none !important;
}

/* Accesibilidad: anillo de foco visible, discreto y del sistema */
:focus-visible {
    outline: 2px solid rgba(var(--accent-rgb), 0.55) !important;
    outline-offset: 2px !important;
}

/* ── Titulares ───────────────────────────────────────────────────────── */
h1, h2, h3 { font-family: var(--font-ui) !important; }
h1 { color: var(--text-hi) !important; letter-spacing: -0.02em; font-weight: 700 !important; }
h2 { color: var(--text) !important; font-weight: 600 !important; letter-spacing: -0.01em; }
h3 { color: var(--text) !important; font-weight: 600 !important; }

/* ── HERO SECTION ───────────────────────────────────────────────────── */
.alpha-hero {
    text-align: center;
    padding: 56px 20px 36px;
    animation: fadeInUp 0.5s var(--ease-out);
}

.alpha-hero-brand {
    font-family: var(--font-mono);
    font-size: 3.4rem;
    font-weight: 700;
    background: linear-gradient(160deg, var(--accent-hi) 0%, var(--accent) 55%, var(--accent-deep) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.01em;
    margin: 0;
    line-height: 1;
}

.alpha-hero-tagline {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-2);
    margin-top: 18px;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    font-weight: 500;
}

.alpha-hero-sub {
    font-family: var(--font-ui);
    font-size: 0.85rem;
    color: var(--text-3);
    margin-top: 10px;
}

.alpha-divider {
    width: 56px;
    height: 2px;
    border-radius: 1px;
    background: var(--accent);
    opacity: 0.6;
    margin: 28px auto;
}

/* ── ACTION CARD: la columna CENTRAL del welcome se convierte en card ── */
/* Detectamos la columna por el placeholder único del input hero */
[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) {
    background: linear-gradient(135deg, rgba(13,15,18,0.95), rgba(20,28,38,0.95)) !important;
    border: 1px solid rgba(var(--accent-rgb),0.22) !important;
    border-radius: 16px !important;
    padding: 28px 34px !important;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(var(--accent-rgb),0.05) !important;
    animation: fadeInUp var(--dur-3) var(--ease-out) both !important;
    position: relative !important;
    overflow: hidden !important;
    backdrop-filter: blur(10px);
}

/* Brillo que viaja por el perímetro del welcome card.
   Técnica nativa CSS Motion Path (offset-path): un pequeño trazo dorado
   se desplaza con velocidad uniforme siguiendo el contorno redondeado.
   border-radius de la card = 16px → mismo valor en inset() round. */
[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"])::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 70px;
    height: 2.5px;
    border-radius: 50%;
    background: linear-gradient(90deg,
        transparent 0%,
        rgba(255, 215, 64, 0.0) 15%,
        rgba(255, 215, 64, 0.85) 45%,
        rgba(255, 255, 255, 1.0) 50%,
        rgba(255, 215, 64, 0.85) 55%,
        rgba(255, 215, 64, 0.0) 85%,
        transparent 100%);
    filter: blur(0.6px) drop-shadow(0 0 6px rgba(255, 215, 64, 0.75));
    offset-path: inset(0 round 16px);
    offset-rotate: auto;
    offset-distance: 0%;
    animation: none;
    display: none;
    pointer-events: none;
    z-index: 2;
}

/* Label de la action card */
.action-label-new {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: var(--text-2);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-bottom: 14px;
    text-align: center;
    display: block;
}

/* Input dentro de la action card */
[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stTextInput"] input {
    background: rgba(10,13,17,0.8) !important;
    border: 1px solid rgba(var(--accent-rgb),0.3) !important;
    color: var(--text-hi) !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 10px !important;
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    padding: 16px 20px !important;
    letter-spacing: 0.05em !important;
    text-align: center !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
}

[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stTextInput"] input:focus {
    border-color: var(--accent) !important;
    background: rgba(13,15,18,1) !important;
    box-shadow: 0 0 0 3px rgba(var(--accent-rgb),0.12) !important;
    outline: none !important;
}

[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stTextInput"] input::placeholder {
    color: var(--text-3) !important;
    font-weight: 400 !important;
    text-transform: none !important;
    letter-spacing: 0.03em !important;
}

/* Botón primario (Análisis y Escanear) dorado — padding compacto SIEMPRE
   (no en media query) para que "ESCANEAR EL MERCADO" quepa en iframe
   cuadrado de Whop sin importar viewport. */
[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-deep) 100%) !important;
    border: none !important;
    color: var(--bg) !important;
    font-weight: 700 !important;
    font-size: 0.78rem !important;
    letter-spacing: 0.04em !important;
    text-transform: uppercase !important;
    border-radius: 10px !important;
    padding: 12px 14px !important;
    height: auto !important;
    white-space: nowrap !important;
    overflow: visible !important;
    text-overflow: clip !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
    box-shadow: 0 4px 20px rgba(var(--accent-rgb),0.3), inset 0 1px 0 rgba(255,255,255,0.2) !important;
}

[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(var(--accent-rgb),0.5), inset 0 1px 0 rgba(255,255,255,0.3) !important;
    background: linear-gradient(135deg, var(--accent-hi) 0%, var(--accent) 100%) !important;
    color: var(--bg) !important;
}

/* Botón secundario (Scan) azul */
[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stButton"] > button[kind="secondary"] {
    background: linear-gradient(135deg, rgba(var(--info-rgb),0.15) 0%, rgba(var(--info-rgb),0.05) 100%) !important;
    border: 1px solid rgba(var(--info-rgb),0.4) !important;
    color: var(--info) !important;
    font-weight: 700 !important;
    font-size: 0.88rem !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    border-radius: 10px !important;
    padding: 14px 36px !important;
    height: auto !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    box-shadow: 0 4px 20px rgba(var(--info-rgb),0.15) !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
}

[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stButton"] > button[kind="secondary"]:hover {
    background: linear-gradient(135deg, rgba(var(--info-rgb),0.25) 0%, rgba(var(--info-rgb),0.1) 100%) !important;
    border-color: var(--info) !important;
    box-shadow: 0 8px 30px rgba(var(--info-rgb),0.3) !important;
    color: var(--info) !important;
    transform: translateY(-2px) !important;
}

/* ── Sección genérica de header ─────────────────────────────────────── */
.section-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.18em;
    text-align: center;
    margin: 30px 0 16px 0;
    position: relative;
    animation: fadeIn 1s ease-out 0.4s both;
}

.section-header::before, .section-header::after {
    content: '';
    position: absolute;
    top: 50%;
    width: 60px;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(var(--accent-rgb),0.3));
}

.section-header::before { left: calc(50% - 180px); transform: scaleX(-1); }
.section-header::after  { right: calc(50% - 180px); }

/* ── Ticker tiles: card visual arriba + botón ▾ pegado abajo ──────── */
.ticker-tile {
    background: var(--surface-1);
    border: 1px solid var(--hairline);
    border-bottom: none;
    border-radius: var(--r-sm) var(--r-sm) 0 0;
    padding: 14px 10px 12px 10px;
    text-align: center;
    height: 95px;
    transition: background var(--dur-2) var(--ease-out),
                border-color var(--dur-2) var(--ease-out);
    animation: fadeInUp var(--dur-3) var(--ease-out) both;
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 4px;
    box-shadow: var(--inset-hi);
}

.tt-symbol {
    font-family: var(--font-mono);
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--text-hi);
    letter-spacing: 0.02em;
    line-height: 1.15;
}

.tt-price {
    font-family: var(--font-mono);
    font-size: 0.84rem;
    color: var(--text-2);
    font-weight: 500;
    line-height: 1.15;
    font-variant-numeric: tabular-nums;
}

.tt-change {
    font-family: var(--font-mono);
    font-size: 0.76rem;
    font-weight: 600;
    line-height: 1.15;
    letter-spacing: 0;
    font-variant-numeric: tabular-nums;
}

/* Botón ▾ pequeño debajo de la card — pegado visualmente */
[data-testid="stColumn"]:has(.ticker-tile) [data-testid="stButton"] {
    margin-top: -6px !important;
}

[data-testid="stColumn"]:has(.ticker-tile) [data-testid="stButton"] > button {
    background: var(--surface-1) !important;
    border: 1px solid var(--hairline) !important;
    border-top: 1px solid var(--hairline) !important;
    border-radius: 0 0 var(--r-sm) var(--r-sm) !important;
    color: var(--text-3) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    padding: 3px 0 5px 0 !important;
    height: 26px !important;
    width: 100% !important;
    line-height: 1 !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
    transition: background var(--dur-2) var(--ease-out),
                color var(--dur-2) var(--ease-out),
                border-color var(--dur-2) var(--ease-out) !important;
    box-shadow: none !important;
}

[data-testid="stColumn"]:has(.ticker-tile) [data-testid="stButton"] > button:hover {
    background: var(--surface-2) !important;
    border-color: var(--hairline-2) !important;
    color: var(--accent) !important;
    transform: none !important;
    box-shadow: none !important;
}

/* Cuando el botón ▾ es hovereado, también resaltar la card pegada arriba */
[data-testid="stColumn"]:has([data-testid="stButton"]:hover) .ticker-tile {
    border-color: var(--hairline-2);
    background: var(--surface-2);
}

/* ── Live Market Pulse Card ──────────────────────────────────────────── */
.market-pulse-card {
    background: linear-gradient(135deg, var(--surface-1) 0%, var(--surface-2) 100%);
    border: 1px solid var(--hairline);
    border-radius: 8px;
    padding: 12px 10px;
    text-align: center;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out);
    animation: fadeInUp 0.6s ease-out both;
    /* Garantizar que el contenido no desborde la card */
    overflow: hidden;
    min-width: 0;
}

.market-pulse-card:hover {
    border-color: rgba(var(--accent-rgb),0.3);
    transform: translateY(-2px);
}

.pulse-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 4px;
}

.pulse-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--text-hi);
    margin-bottom: 2px;
    /* NUNCA romper el número — si no cabe, reduce con clamp/overflow */
    white-space: nowrap;
    overflow: hidden;
    text-overflow: clip;
}

.pulse-change {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.74rem;
    font-weight: 600;
    white-space: nowrap;
}

/* ── Sidebar styles ────────────────────────────────────────────────── */
.sidebar-brand {
    text-align: center;
    padding: 18px 0 20px;
    border-bottom: 1px solid var(--hairline);
    margin-bottom: 14px;
}

.sidebar-brand-logo {
    font-family: var(--font-mono);
    font-size: 1.15rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    background: linear-gradient(160deg, var(--accent-hi), var(--accent-deep));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.sidebar-brand-sub {
    font-family: var(--font-mono);
    font-size: 0.55rem;
    color: var(--text-3);
    letter-spacing: 0.28em;
    margin-top: 5px;
    text-transform: uppercase;
}

.sidebar-section {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.15em;
    padding: 16px 0 8px 0;
    margin-bottom: 4px;
}

/* Watchlist item: fila silenciosa, borde solo al pasar */
[data-testid="stSidebar"] [data-testid="stButton"] > button {
    background: transparent !important;
    border: 1px solid transparent !important;
    color: var(--text) !important;
    font-family: var(--font-mono) !important;
    font-weight: 500 !important;
    font-size: 0.8rem !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    border-radius: var(--r-sm) !important;
    padding: 7px 10px !important;
    transition: background var(--dur-1) var(--ease-out),
                color var(--dur-1) var(--ease-out),
                transform var(--dur-1) var(--ease-out) !important;
    text-align: left !important;
    box-shadow: none !important;
}

[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
    background: var(--surface-2) !important;
    border-color: var(--hairline) !important;
    color: var(--text-hi) !important;
    box-shadow: none !important;
    transform: none !important;
}

[data-testid="stSidebar"] [data-testid="stButton"] > button:active {
    transform: scale(0.98) !important;
}

/* ── Métricas (default Streamlit) ────────────────────────────────────── */
[data-testid="stMetricValue"] {
    color: var(--pos) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.4rem !important;
    font-weight: 700 !important;
}

[data-testid="stMetricLabel"] {
    color: var(--text-2) !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

[data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
}

/* ── Cards de análisis: superficie de LECTURA (aireada, sin adornos) ── */
.analysis-card {
    background: var(--surface-1);
    border: 1px solid var(--hairline);
    border-radius: var(--r-md);
    padding: 24px 28px;
    margin: 12px 0;
    animation: fadeIn var(--dur-3) var(--ease-out);
    box-shadow: var(--inset-hi), var(--shadow-1);
}

.analysis-text {
    font-size: 0.93rem;
    line-height: 1.8;
    color: var(--text);
    letter-spacing: 0.001em;
}

/* ── MODO DE ANÁLISIS — encabezado + selector Pro / Básico ────────────── */
.mode-switch-head {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14px;
    margin: 22px auto 12px;
    max-width: 560px;
    animation: fadeIn var(--dur-3) var(--ease-out);
}

.mode-switch-label {
    flex: 0 0 auto;
    font-family: var(--font-mono);
    font-size: 0.74rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.20em;
    color: var(--accent);
    white-space: nowrap;
}

.mode-switch-rule {
    flex: 1 1 auto;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(var(--accent-rgb),0.30));
}

.mode-switch-head .mode-switch-rule:last-child {
    background: linear-gradient(90deg, rgba(var(--accent-rgb),0.30), transparent);
}

/* ── Botones Pro / Básico ─────────────────────────────────────────────── */
/* Se anclan por .st-key-<key>, la clase que Streamlit pone en el contenedor
   de todo widget con key. Es un anclaje estable, a diferencia de los
   data-testid internos. */
.st-key-chart_mode_pro,
.st-key-chart_mode_basico {
    max-width: 190px;
    min-width: 132px;            /* nunca tan estrecho como para partir la palabra */
    margin: 0 auto 4px;          /* ← centra el botón dentro de su columna */
}

/* Nota de especificidad: todas las reglas van prefijadas con .stApp para
   ganar a `.stApp button[kind="primary"]` (el override global naranja, que
   usa !important y aparece más abajo en la hoja). Sin el prefijo tendrían la
   misma especificidad y ganaría la regla global por orden de aparición. */
.stApp .st-key-chart_mode_pro button,
.stApp .st-key-chart_mode_basico button {
    display: flex !important;
    align-items: center;
    justify-content: center;
    gap: 10px;
    background: var(--surface-1) !important;
    border: 1px solid var(--hairline) !important;
    color: var(--text-2) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.84rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.06em !important;
    padding: 10px 14px !important;
    border-radius: 10px !important;
    box-shadow: var(--shadow-1), inset 0 1px 0 rgba(255,255,255,0.03);
    /* La etiqueta va SIEMPRE en una sola línea. En un iframe estrecho (Whop)
       la columna se comprime y, sin esto, Streamlit parte "Básico" en
       "Bá / sic / o" apilado en vertical. */
    white-space: nowrap !important;
    min-width: fit-content !important;
    overflow: visible !important;
    transition: color var(--dur-1) var(--ease-out),
                background var(--dur-1) var(--ease-out),
                border-color var(--dur-1) var(--ease-out),
                transform var(--dur-1) var(--ease-out);
}

/* Streamlit envuelve la etiqueta en varios contenedores anidados; hay que
   desactivar el corte de palabra en todos ellos, no solo en el <button>. */
.stApp .st-key-chart_mode_pro button *,
.stApp .st-key-chart_mode_basico button * {
    white-space: nowrap !important;
    overflow: visible !important;
    text-overflow: clip !important;
    word-break: normal !important;
    overflow-wrap: normal !important;
    hyphens: none !important;
    max-width: none !important;
}

.stApp .st-key-chart_mode_pro button:hover,
.stApp .st-key-chart_mode_basico button:hover {
    color: var(--text-hi) !important;
    background: var(--surface-2) !important;
    border-color: rgba(var(--accent-rgb),0.22) !important;
    transform: none !important;   /* anula el translateY global de :hover */
}

.stApp .st-key-chart_mode_pro button:active,
.stApp .st-key-chart_mode_basico button:active {
    transform: scale(0.97) !important;
}

/* Modo activo — oro, con halo suave para que se lea de un vistazo.
   Se evita a propósito el relleno sólido del primary global: un botón
   macizo taparía el icono de velas / montaña, que es justo lo que hay
   que poder leer de un vistazo. */
.stApp .st-key-chart_mode_pro button[kind="primary"],
.stApp .st-key-chart_mode_basico button[kind="primary"],
.stApp .st-key-chart_mode_pro button[kind="primary"]:hover,
.stApp .st-key-chart_mode_basico button[kind="primary"]:hover {
    background: rgba(var(--accent-rgb),0.14) !important;
    color: var(--accent) !important;
    border: 1px solid rgba(var(--accent-rgb),0.42) !important;
    box-shadow: inset 0 0 0 1px rgba(var(--accent-rgb),0.16),
                0 0 18px rgba(var(--accent-rgb),0.10) !important;
    transform: none !important;
}

/* Iconos: miniaturas SVG de lo que verás al pulsar cada modo.
   Van como ::before, que dentro del botón flex es un elemento más. */
.stApp .st-key-chart_mode_pro button::before,
.stApp .st-key-chart_mode_basico button::before {
    content: "";
    flex: 0 0 auto;
    width: 28px;
    height: 19px;
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
}

/* Pro → cuatro velas japonesas en tendencia alcista, rojas y verdes */
.stApp .st-key-chart_mode_pro button::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 28 19'%3E%3Cg stroke-width='1' stroke-linecap='round'%3E%3Cline x1='4' y1='11' x2='4' y2='18' stroke='%23F1495F'/%3E%3Crect x='2.2' y='12.5' width='3.6' height='4.2' fill='%23F1495F'/%3E%3Cline x1='11' y1='7.5' x2='11' y2='15.5' stroke='%233DD68C'/%3E%3Crect x='9.2' y='9' width='3.6' height='5' fill='%233DD68C'/%3E%3Cline x1='18' y1='5' x2='18' y2='12.5' stroke='%23F1495F'/%3E%3Crect x='16.2' y='6.5' width='3.6' height='4' fill='%23F1495F'/%3E%3Cline x1='25' y1='1' x2='25' y2='9' stroke='%233DD68C'/%3E%3Crect x='23.2' y='2.5' width='3.6' height='5' fill='%233DD68C'/%3E%3C/g%3E%3C/svg%3E");
}

/* Básico → línea ascendente con degradado, solo verde (mini mountain) */
.stApp .st-key-chart_mode_basico button::before {
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 28 19'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='0' y2='1'%3E%3Cstop offset='0' stop-color='%233DD68C' stop-opacity='0.5'/%3E%3Cstop offset='1' stop-color='%233DD68C' stop-opacity='0'/%3E%3C/linearGradient%3E%3C/defs%3E%3Cpath d='M1.5 15 L7 11 L11.5 13 L16.5 7 L21 8.5 L26.5 2.5 L26.5 18 L1.5 18 Z' fill='url(%23g)'/%3E%3Cpath d='M1.5 15 L7 11 L11.5 13 L16.5 7 L21 8.5 L26.5 2.5' fill='none' stroke='%233DD68C' stroke-width='1.7' stroke-linejoin='round' stroke-linecap='round'/%3E%3C/svg%3E");
}

/* Pantallas / iframes muy estrechos: se recorta el icono y el espaciado antes
   que la palabra. El texto nunca se parte — se prefiere un botón más justo. */
@media (max-width: 640px) {
    .st-key-chart_mode_pro,
    .st-key-chart_mode_basico {
        min-width: 108px;
    }
    .stApp .st-key-chart_mode_pro button,
    .stApp .st-key-chart_mode_basico button {
        padding: 9px 10px !important;
        gap: 7px;
        font-size: 0.78rem !important;
        letter-spacing: 0.03em !important;
    }
    .stApp .st-key-chart_mode_pro button::before,
    .stApp .st-key-chart_mode_basico button::before {
        width: 22px;
        height: 15px;
    }
}

/* ── Score Badges: chips con punto de estado, sin degradados ─────────── */
.badge-strong-buy, .badge-buy, .badge-watch, .badge-pass {
    padding: 5px 12px 5px 24px;
    border-radius: 99px;
    font-weight: 700;
    font-size: 0.66rem;
    letter-spacing: 0.09em;
    display: inline-block;
    font-family: var(--font-mono);
    text-transform: uppercase;
    position: relative;
    border: 1px solid;
}

.badge-strong-buy::before, .badge-buy::before,
.badge-watch::before, .badge-pass::before {
    content: '';
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
}

.badge-strong-buy {
    color: var(--pos) !important;
    border-color: rgba(var(--pos-rgb),0.4);
    background: rgba(var(--pos-rgb),0.08);
}
.badge-buy {
    color: var(--pos) !important;
    border-color: rgba(var(--pos-rgb),0.25);
    background: rgba(var(--pos-rgb),0.05);
}
.badge-watch {
    color: var(--accent) !important;
    border-color: rgba(var(--accent-rgb),0.3);
    background: rgba(var(--accent-rgb),0.06);
}
.badge-pass {
    color: var(--neg) !important;
    border-color: rgba(var(--neg-rgb),0.3);
    background: rgba(var(--neg-rgb),0.06);
}

/* ── Tabs ────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] > div:first-child {
    border-bottom: 1px solid var(--hairline) !important;
    background: transparent !important;
    gap: 4px !important;
}

button[data-baseweb="tab"] {
    color: var(--text-2) !important;
    font-family: var(--font-ui) !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    padding: 10px 14px !important;
    border-bottom: 2px solid transparent !important;
    transition: color var(--dur-2) var(--ease-out),
                border-color var(--dur-2) var(--ease-out) !important;
    border-radius: 0 !important;
    background: transparent !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: var(--text-hi) !important;
    font-weight: 600 !important;
    border-bottom-color: var(--accent) !important;
    background: transparent !important;
}

button[data-baseweb="tab"]:hover {
    color: var(--text) !important;
    background: transparent !important;
}

/* Barra deslizante nativa de Streamlit bajo la pestaña activa */
[data-baseweb="tab-highlight"] { background-color: var(--accent) !important; }
[data-baseweb="tab-border"]    { background-color: var(--hairline) !important; }

/* ── Input genérico ────────────────────────────────────────────────── */
[data-testid="stTextInput"] input {
    background: var(--surface-0) !important;
    border: 1px solid var(--hairline-2) !important;
    color: var(--text-hi) !important;
    font-family: var(--font-mono) !important;
    border-radius: var(--r-sm) !important;
    transition: border-color var(--dur-2) var(--ease-out),
                box-shadow var(--dur-2) var(--ease-out) !important;
}

[data-testid="stTextInput"] input:focus {
    border-color: rgba(var(--accent-rgb),0.6) !important;
    box-shadow: 0 0 0 3px rgba(var(--accent-rgb),0.12) !important;
}

/* ── Botones genéricos: secundario silencioso con press físico ────── */
[data-testid="stButton"] > button {
    background: var(--surface-2) !important;
    border: 1px solid var(--hairline-2) !important;
    color: var(--text) !important;
    font-family: var(--font-ui) !important;
    font-weight: 500 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0 !important;
    border-radius: var(--r-sm) !important;
    padding: 8px 16px !important;
    box-shadow: var(--inset-hi) !important;
    transition: background var(--dur-1) var(--ease-out),
                border-color var(--dur-1) var(--ease-out),
                color var(--dur-1) var(--ease-out),
                transform var(--dur-1) var(--ease-out) !important;
}

[data-testid="stButton"] > button:hover {
    background: var(--surface-3) !important;
    border-color: rgba(var(--accent-rgb),0.45) !important;
    color: var(--text-hi) !important;
}

[data-testid="stButton"] > button:active {
    transform: scale(0.97) !important;
}

/* ── Progress bar ────────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, var(--accent), var(--accent-hi)) !important;
    border-radius: 4px !important;
    box-shadow: none;
}

/* ── Divider ─────────────────────────────────────────────────────────── */
hr {
    border-color: var(--hairline) !important;
    margin: 16px 0 !important;
}

/* ── Expander ────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid var(--hairline) !important;
    background: var(--surface-1) !important;
    border-radius: 8px !important;
}

/* ── Scrollbar: fina y neutra ────────────────────────────────────────── */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-solid); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-3); }

/* ── Score colors ─────────────────────────────────────────────────── */
.score-high   { color: var(--pos) !important; font-weight: 700; }
.score-medium { color: var(--accent) !important; font-weight: 700; }
.score-low    { color: var(--neg) !important; font-weight: 700; }

/* ── Top header bar ────────────────────────────────────────────────── */
.terminal-topbar {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 0 14px 0;
    border-bottom: 1px solid var(--hairline);
    margin-bottom: 8px;
    animation: fadeIn 0.5s ease-out;
}

.terminal-topbar-brand {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--accent), var(--accent-deep));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 0.08em;
}

.terminal-topbar-sub {
    color: var(--text-3);
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.05em;
}

.terminal-topbar-time {
    margin-left: auto;
    color: var(--text-2);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    background: rgba(var(--accent-rgb),0.05);
    padding: 4px 10px;
    border-radius: 4px;
    border: 1px solid var(--hairline);
}

/* ── Stock detail header ───────────────────────────────────────────── */
.stock-header {
    display: flex;
    align-items: center;
    gap: 18px;
    padding: 14px 20px;
    background: linear-gradient(135deg, var(--surface-1) 0%, var(--surface-2) 100%);
    border: 1px solid var(--hairline);
    border-left: 3px solid var(--accent);
    border-radius: 10px;
    margin-bottom: 20px;
    animation: fadeInUp 0.5s ease-out;
}

.stock-header-ticker {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.8rem;
    font-weight: 800;
    color: var(--text-hi);
    letter-spacing: 0.05em;
}

.stock-header-name {
    font-size: 0.95rem;
    color: var(--text);
    font-weight: 500;
}

.stock-header-score {
    margin-left: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.4rem;
    font-weight: 800;
}

/* ── QUICK VIEW (dashboard compacto instantáneo) ─────────────────── */

.qv-header {
    display: flex;
    align-items: baseline;
    gap: 14px;
    padding: 16px 22px;
    background: linear-gradient(135deg, var(--surface-1) 0%, var(--surface-2) 100%);
    border: 1px solid rgba(var(--accent-rgb),0.25);
    border-left: 3px solid var(--accent);
    border-radius: 12px;
    margin: 10px 0 18px 0;
    animation: fadeInUp 0.4s ease-out;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}

.qv-ticker {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.7rem;
    font-weight: 800;
    color: var(--text-hi);
    letter-spacing: 0.04em;
}

.qv-name {
    font-size: 0.92rem;
    color: var(--text);
    font-weight: 500;
}

.qv-price {
    margin-left: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--accent);
}

.qv-change {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.95rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 6px;
    background: rgba(var(--accent-rgb),0.05);
}

.qv-section-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--hairline);
}

/* Métricas clave */
.qv-metric {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 10px;
    border-bottom: 1px solid rgba(35,40,48,0.6);
    transition: background 0.2s;
}

.qv-metric:hover {
    background: rgba(var(--accent-rgb),0.04);
}

.qv-metric-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    color: var(--text-2);
}

.qv-metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.92rem;
    font-weight: 700;
}

/* Performance tiles */
.qv-perf-tile {
    background: linear-gradient(135deg, var(--surface-1) 0%, var(--surface-2) 100%);
    border: 1px solid var(--hairline);
    border-radius: 8px;
    padding: 12px 8px;
    text-align: center;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out);
    animation: fadeInUp 0.4s ease-out both;
}

.qv-perf-tile:hover {
    border-color: rgba(var(--accent-rgb),0.3);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}

.qv-perf-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: var(--text-2);
    letter-spacing: 0.15em;
    margin-bottom: 5px;
    text-transform: uppercase;
}

.qv-perf-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.95rem;
    font-weight: 700;
}

/* News items */
.qv-news-link {
    text-decoration: none !important;
    color: inherit !important;
}

.qv-news-item {
    background: linear-gradient(135deg, var(--surface-1) 0%, var(--surface-2) 100%);
    border: 1px solid rgba(35,40,48,0.6);
    border-left: 2px solid rgba(var(--accent-rgb),0.4);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 6px;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out);
    cursor: pointer;
}

.qv-news-item:hover {
    background: linear-gradient(135deg, var(--surface-2) 0%, var(--surface-3) 100%);
    border-left-width: 3px;
    border-left-color: var(--accent);
    transform: translateX(3px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}

.qv-news-meta {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 4px;
}

.qv-news-freshness {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.64rem;
    color: var(--accent);
    font-weight: 700;
    padding: 1px 6px;
    border: 1px solid rgba(var(--accent-rgb),0.3);
    border-radius: 3px;
}

.qv-news-publisher {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

.qv-news-title {
    font-size: 0.85rem;
    color: var(--text);
    line-height: 1.45;
    font-weight: 500;
}

/* Contexto */
.qv-context-item {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 7px 10px;
    border-bottom: 1px solid rgba(35,40,48,0.6);
    gap: 12px;
}

.qv-context-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    color: var(--text-2);
    flex-shrink: 0;
}

.qv-context-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: var(--text);
    font-weight: 600;
    text-align: right;
    word-break: break-word;
}

.qv-empty {
    color: var(--text-3);
    font-style: italic;
    text-align: center;
    padding: 20px;
    font-size: 0.85rem;
}

/* Botón CTA grande de análisis profundo */
[data-testid="stButton"]:has(button[key*="qv_full_analysis"]) > button,
.element-container:has(button:contains("EJECUTAR ANÁLISIS")) > button {
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-deep) 100%) !important;
    border: none !important;
    color: var(--bg) !important;
    font-weight: 800 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.1em !important;
    padding: 18px 32px !important;
    height: auto !important;
    border-radius: 12px !important;
    box-shadow: 0 8px 32px rgba(var(--accent-rgb),0.35), inset 0 1px 0 rgba(255,255,255,0.3) !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
    animation: glow-border 4s ease-in-out infinite;
}

/* Back button */
[data-testid="stButton"] > button:has(span:contains("← Volver")) {
    background: rgba(13,15,18,0.6) !important;
    border: 1px solid rgba(var(--accent-rgb),0.2) !important;
    color: var(--text) !important;
}

/* ─────────────────────────────────────────────────────────────────────
   OVERVIEW PREMIUM: KPI tiles, tooltips, strength/risk, alpha, vetos
   ───────────────────────────────────────────────────────────────────── */

/* ── KPI Section title (mismo lenguaje overline) ────────────── */
.kpi-section-title {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--font-mono);
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin: 26px 0 12px 0;
}

.kpi-section-title::before {
    content: '';
    width: 3px;
    height: 11px;
    border-radius: 1px;
    background: var(--accent);
    flex-shrink: 0;
}

.kpi-section-title::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--hairline);
    margin-left: 4px;
}

/* ── KPI Tile: dato a la izquierda, plano, tabular ──────────── */
.kpi-tile {
    background: var(--surface-1);
    border: 1px solid var(--hairline);
    border-radius: var(--r-sm);
    padding: 12px 14px;
    margin-bottom: 8px;
    min-height: 92px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: border-color var(--dur-2) var(--ease-out),
                background var(--dur-2) var(--ease-out),
                transform var(--dur-2) var(--ease-out);
    position: relative;
    overflow: visible;
    animation: fadeInUp var(--dur-3) var(--ease-out) both;
    box-shadow: var(--inset-hi);
}

@media (hover: hover) and (pointer: fine) {
    .kpi-tile:hover {
        border-color: var(--hairline-2);
        background: var(--surface-2);
        transform: translateY(-1px);
    }
}

.kpi-tile-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 8px;
}

.kpi-tile-label {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    color: var(--text-2);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    /* Permitir 2 líneas — NUNCA truncar con elipsis. En iframe cuadrado de
       Whop los labels "Próximo Earnings" / "Sorpresa Promedio" se cortaban
       con "...". Ahora se ven completos en 2 líneas. */
    white-space: normal;
    overflow: visible;
    text-overflow: clip;
    word-break: normal;
    overflow-wrap: anywhere;
    line-height: 1.2;
    flex: 1;
    min-width: 0;
}

.kpi-tile-value {
    font-family: var(--font-mono);
    font-size: 1.3rem;
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: -0.01em;
    font-variant-numeric: tabular-nums;
    word-break: break-word;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    max-height: 3.2rem;
}

/* ── Tooltip (?) icon con popup al hover ─────────────────── */
.kpi-help {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: rgba(var(--accent-rgb),0.08);
    border: 1px solid rgba(var(--accent-rgb),0.3);
    color: var(--accent);
    font-size: 0.72rem;
    font-weight: 800;
    font-family: 'Inter', sans-serif;
    cursor: help;
    position: relative;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out);
    flex-shrink: 0;
}

.kpi-help:hover {
    background: rgba(var(--accent-rgb),0.2);
    border-color: var(--accent);
    color: var(--accent-hi);
    transform: scale(1.1);
}

.kpi-help::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: calc(100% + 10px);
    right: -8px;
    background: linear-gradient(135deg, var(--surface-2) 0%, var(--surface-3) 100%);
    color: var(--text);
    padding: 12px 14px;
    border-radius: 8px;
    border: 1px solid rgba(var(--accent-rgb),0.35);
    border-bottom: 2px solid var(--accent);
    white-space: normal;
    width: 260px;
    font-size: 0.78rem;
    font-weight: 400;
    font-family: 'Inter', sans-serif;
    line-height: 1.55;
    letter-spacing: 0;
    text-transform: none;
    text-align: left;
    z-index: 9999;
    pointer-events: none;
    box-shadow: 0 12px 32px rgba(0,0,0,0.7), 0 0 0 1px rgba(var(--accent-rgb),0.1);
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 0.2s ease-out, transform 0.2s ease-out;
}

.kpi-help::before {
    content: '';
    position: absolute;
    bottom: calc(100% + 4px);
    right: 2px;
    width: 10px;
    height: 10px;
    background: var(--surface-3);
    border-right: 1px solid rgba(var(--accent-rgb),0.35);
    border-bottom: 2px solid var(--accent);
    transform: rotate(45deg);
    z-index: 9999;
    opacity: 0;
    transition: opacity 0.2s ease-out;
}

.kpi-help:hover::after,
.kpi-help:hover::before {
    opacity: 1;
    transform: translateY(0) rotate(0);
}

.kpi-help:hover::before {
    transform: rotate(45deg);
}

/* ── Vetos Aplicados (alert box rojo) ──────────────────── */
.veto-section-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 20px 0 8px 0;
    padding: 10px 14px;
    background: linear-gradient(135deg, rgba(var(--neg-rgb),0.15) 0%, rgba(var(--neg-rgb),0.04) 100%);
    border: 1px solid rgba(var(--neg-rgb),0.35);
    border-left: 4px solid var(--neg);
    border-radius: 8px;
    animation: fadeInUp 0.4s ease-out;
}

.veto-icon { font-size: 1.15rem; }

.veto-title {
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    font-weight: 800;
    color: var(--neg);
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.veto-item {
    background: rgba(var(--neg-rgb),0.06);
    border: 1px solid rgba(var(--neg-rgb),0.18);
    border-left: 3px solid var(--neg);
    border-radius: 0 6px 6px 0;
    padding: 10px 14px;
    margin-bottom: 6px;
    font-size: 0.83rem;
    color: #E9C6CD;
    line-height: 1.55;
    animation: fadeInUp 0.4s ease-out both;
}

/* ── Fortalezas / Riesgos (cards verde/rojo) ─────────── */
.thesis-section-title {
    font-family: 'Inter', sans-serif;
    font-size: 0.92rem;
    font-weight: 700;
    margin: 18px 0 10px 0;
    padding-bottom: 8px;
    letter-spacing: 0.02em;
}

.thesis-section-title.strength {
    color: var(--pos);
    border-bottom: 1px solid var(--hairline);
}

.thesis-section-title.risk {
    color: var(--neg);
    border-bottom: 1px solid var(--hairline);
}

/* Filas con marcador colgante — sin cajitas repetidas */
.strength-item, .risk-item {
    position: relative;
    padding: 10px 4px 10px 26px;
    margin-bottom: 0;
    border-bottom: 1px solid var(--hairline);
    border-radius: 0;
    font-size: 0.86rem;
    line-height: 1.6;
    color: var(--text);
    animation: fadeInUp var(--dur-3) var(--ease-out) both;
}

.strength-item:last-child, .risk-item:last-child { border-bottom: none; }

.strength-item::before, .risk-item::before {
    position: absolute;
    left: 4px;
    top: 9px;
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: 0.9rem;
}

.strength-item::before { content: '+'; color: var(--pos); }
.risk-item::before     { content: '−'; color: var(--neg); }

/* ── Oportunidad Asimétrica: EL panel dorado (único énfasis) ── */
.alpha-opportunity-card {
    background: linear-gradient(180deg, rgba(var(--accent-rgb),0.07) 0%, rgba(var(--accent-rgb),0.02) 100%);
    border: 1px solid rgba(var(--accent-rgb),0.28);
    border-radius: var(--r-md);
    padding: 18px 22px;
    margin: 20px 0 8px 0;
    box-shadow: var(--inset-hi), var(--shadow-2);
    animation: fadeInUp var(--dur-3) var(--ease-out);
    position: relative;
    overflow: hidden;
}

.alpha-opportunity-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}

.alpha-opportunity-icon { display: none; }

.alpha-opportunity-title {
    font-family: var(--font-mono);
    font-size: 0.66rem;
    font-weight: 700;
    color: var(--accent);
    letter-spacing: 0.14em;
    text-transform: uppercase;
}

.alpha-opportunity-body {
    color: var(--text);
    font-size: 0.88rem;
    line-height: 1.65;
    font-weight: 400;
}

/* ─────────────────────────────────────────────────────────────────────
   AGENT TAB DASHBOARDS: header, status pills, insight cards, section bar
   ───────────────────────────────────────────────────────────────────── */

/* ── Agent header: monograma + nombre + score tabular ──────── */
.agent-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    background: var(--surface-1);
    border: 1px solid var(--hairline);
    border-radius: var(--r-md);
    margin: 4px 0 20px 0;
    animation: fadeInUp var(--dur-3) var(--ease-out);
    box-shadow: var(--inset-hi), var(--shadow-1);
}

.agent-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

/* Monograma tipográfico en vez de emoji: identidad sobria */
.agent-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
    border-radius: var(--r-sm);
    background: rgba(var(--accent-rgb), 0.08);
    border: 1px solid rgba(var(--accent-rgb), 0.25);
    color: var(--accent);
    font-family: var(--font-mono);
    font-size: 0.66rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    flex-shrink: 0;
}

.agent-name {
    font-family: var(--font-ui);
    font-size: 0.98rem;
    font-weight: 600;
    color: var(--text-hi);
    letter-spacing: -0.01em;
}

.agent-header-right {
    display: flex;
    align-items: baseline;
    gap: 14px;
}

.agent-score {
    font-family: var(--font-mono);
    font-size: 1.55rem;
    font-weight: 700;
    line-height: 1;
    letter-spacing: -0.02em;
}

.agent-score-max {
    font-size: 0.68rem;
    color: var(--text-3);
    font-weight: 500;
    margin-left: 2px;
}

.conviction-badge {
    font-family: var(--font-mono);
    font-size: 0.62rem;
    font-weight: 700;
    padding: 4px 10px;
    border: 1px solid;
    border-radius: 99px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    align-self: center;
}

/* ── Section title bar: overline con tique de acento + regla ─ */
.section-title-bar {
    display: flex;
    align-items: center;
    gap: 10px;
    font-family: var(--font-mono);
    font-size: 0.68rem;
    font-weight: 600;
    color: var(--text-2);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin: 26px 0 12px 0;
    animation: fadeIn var(--dur-3) var(--ease-out);
}

.section-title-bar::before {
    content: '';
    width: 3px;
    height: 11px;
    border-radius: 1px;
    background: var(--accent);
    flex-shrink: 0;
}

.section-title-bar::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--hairline);
    margin-left: 4px;
}

/* ── Status pill: superficie plana + punto indicador ──────── */
.status-pill {
    background: var(--surface-1);
    border: 1px solid var(--hairline);
    border-radius: var(--r-sm);
    padding: 12px 14px;
    text-align: left;
    transition: border-color var(--dur-2) var(--ease-out),
                background var(--dur-2) var(--ease-out);
    animation: fadeInUp var(--dur-3) var(--ease-out) both;
    min-height: 100px;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 6px;
    box-shadow: var(--inset-hi);
}

@media (hover: hover) and (pointer: fine) {
    .status-pill:hover {
        border-color: var(--hairline-2);
        background: var(--surface-2);
    }
}

/* Punto de estado: el color vive aquí, no en el borde de la card */
.status-pill-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    margin-right: 7px;
    vertical-align: 2px;
}

.status-pill-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.6rem;
    color: var(--text-2);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    /* Permitir 2 líneas siempre — NUNCA truncar (los labels "MOMENTUM",
       "TEMA NARRATIVO", "SEÑAL CONTRARIA", "RIESGO REPUTACIONAL" se cortaban
       en iframe cuadrado de Whop). */
    white-space: normal;
    overflow: visible;
    text-overflow: clip;
    word-break: normal;
    overflow-wrap: anywhere;
    line-height: 1.2;
    margin-bottom: 6px;
}

.status-pill-value {
    font-family: var(--font-mono);
    font-size: 0.98rem;
    font-weight: 700;
    line-height: 1.25;
    letter-spacing: -0.01em;
    font-variant-numeric: tabular-nums;
    color: var(--text-hi);
    word-break: break-word;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    max-height: 2.7rem;
}

.status-pill-sub {
    font-family: var(--font-ui);
    font-size: 0.68rem;
    color: var(--text-3);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* ── Insight card: panel sereno con barra fina de acento ── */
.insight-card {
    background: var(--surface-1);
    border: 1px solid var(--hairline);
    border-left: 2px solid var(--accent);
    border-radius: var(--r-sm);
    padding: 16px 20px;
    margin: 14px 0 8px 0;
    animation: fadeInUp var(--dur-3) var(--ease-out);
    transition: border-color var(--dur-2) var(--ease-out);
    box-shadow: var(--inset-hi);
}

.insight-card-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}

.insight-card-icon { display: none; }

.insight-card-title {
    font-family: var(--font-mono);
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

.insight-card-body {
    color: var(--text);
    font-size: 0.89rem;
    line-height: 1.7;
}

/* ─────────────────────────────────────────────────────────────────────
   SKELETON LOADERS — pantallas de carga con shimmer + spinner pequeño
   ───────────────────────────────────────────────────────────────────── */

@keyframes skeleton-shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

@keyframes fade-soft {
    0%, 100% { opacity: 0.7; }
    50%      { opacity: 1; }
}

.skeleton-block {
    background: linear-gradient(90deg,
        rgba(19,25,34,0.6) 25%,
        rgba(35,42,54,0.6) 50%,
        rgba(19,25,34,0.6) 75%);
    background-size: 200% 100%;
    animation: skeleton-shimmer 1.6s ease-in-out infinite;
    border-radius: 10px;
    border: 1px solid rgba(var(--accent-rgb),0.06);
}

.skeleton-line {
    background: linear-gradient(90deg,
        rgba(19,25,34,0.6) 25%,
        rgba(35,42,54,0.6) 50%,
        rgba(19,25,34,0.6) 75%);
    background-size: 200% 100%;
    animation: skeleton-shimmer 1.6s ease-in-out infinite;
    border-radius: 4px;
    height: 14px;
    margin-bottom: 8px;
}

.skeleton-grid {
    display: grid;
    gap: 14px;
    margin-top: 16px;
}

.skeleton-row-2 {
    grid-template-columns: 2fr 1fr;
}

.skeleton-row-4 {
    grid-template-columns: 1fr 1fr 1fr 1fr;
}

.skeleton-row-6 {
    grid-template-columns: repeat(6, 1fr);
}

/* Spinner pequeño centrado */
.alpha-spinner-overlay {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    z-index: 10000;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
    background: rgba(11, 14, 17, 0.88);
    backdrop-filter: blur(8px);
    padding: 26px 32px;
    border-radius: 14px;
    border: 1px solid rgba(255, 184, 77, 0.25);
    box-shadow: 0 12px 48px rgba(0, 0, 0, 0.6),
                0 0 0 1px rgba(255, 184, 77, 0.08);
    animation: fade-soft 2s ease-in-out infinite;
    pointer-events: none;
}

.alpha-spinner {
    width: 36px;
    height: 36px;
    border: 3px solid rgba(255, 184, 77, 0.18);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.85s linear infinite;
}

/* ── Progress Ring (circular con SVG, % real con transición suave) ── */
.alpha-progress-ring-wrap {
    position: relative;
    width: 92px;
    height: 92px;
    display: flex;
    align-items: center;
    justify-content: center;
    filter: drop-shadow(0 0 16px rgba(var(--accent-rgb),0.25));
}

.alpha-progress-svg {
    transform: rotate(-90deg);
    width: 92px;
    height: 92px;
}

.alpha-progress-bg {
    fill: none;
    stroke: rgba(255, 184, 77, 0.12);
    stroke-width: 6;
}

.alpha-progress-fg {
    fill: none;
    stroke: var(--accent);
    stroke-width: 6;
    stroke-linecap: round;
    /* circumference = 2 * π * 38 ≈ 238.76 */
    stroke-dasharray: 238.76;
    transition: stroke-dashoffset 0.55s cubic-bezier(0.4, 0, 0.2, 1);
    filter: drop-shadow(0 0 4px rgba(255, 184, 77, 0.5));
}

.alpha-progress-value {
    position: absolute;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.15rem;
    font-weight: 800;
    color: var(--accent);
    letter-spacing: 0.02em;
    transition: color 0.3s;
}

/* Rotación sutil del trazo dorado para "vida" mientras avanza */
@keyframes ring-rotate {
    to { transform: rotate(270deg); }
}

.alpha-progress-ring-wrap.indeterminate .alpha-progress-svg {
    animation: ring-rotate 1.2s linear infinite;
    transform-origin: center;
}

/* Estado completado (100%) — pulso verde */
.alpha-progress-ring-wrap.complete .alpha-progress-fg {
    stroke: var(--pos);
    filter: drop-shadow(0 0 8px rgba(0, 255, 136, 0.6));
}

.alpha-progress-ring-wrap.complete .alpha-progress-value {
    color: var(--pos);
}

.alpha-spinner-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: var(--accent);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    text-align: center;
    font-weight: 600;
}

.alpha-spinner-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.7rem;
    color: var(--text-2);
    text-align: center;
}

/* Skeleton específicos */
.skeleton-header { height: 70px; }
.skeleton-chart  { height: 360px; }
.skeleton-tile   { height: 95px; }
.skeleton-list-item {
    height: 60px;
    margin-bottom: 8px;
}

/* ─────────────────────────────────────────────────────────────────────
   ASYMMETRY DIAGNOSTIC CARDS + COMPOUND MACHINE BADGE (rebalanceo 2026)
   ───────────────────────────────────────────────────────────────────── */

/* Badge "🏆 BEST-IN-CLASS" / "💎 COMPOUNDER" en el stock header */
.compound-machine-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    background: linear-gradient(135deg, var(--accent-hi) 0%, var(--accent) 50%, var(--accent-deep) 100%);
    color: var(--bg) !important;
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    border-radius: 6px;
    box-shadow: 0 4px 16px rgba(var(--accent-rgb),0.35), inset 0 1px 0 rgba(255,255,255,0.3);
    animation: fade-soft 3s ease-in-out infinite;
}

/* Card "Diagnóstico de Asimetría" — 3 variantes */
.asymmetry-card {
    background: linear-gradient(135deg, rgba(13,15,18,0.95), rgba(20,28,38,0.95));
    border: 1px solid;
    border-left: 4px solid;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 18px 0 8px 0;
    animation: fadeInUp 0.5s ease-out;
    position: relative;
    overflow: hidden;
}

.asymmetry-card.alcista {
    border-color: rgba(var(--pos-rgb),0.35);
    border-left-color: var(--pos);
    background: linear-gradient(135deg, rgba(var(--pos-rgb),0.07), rgba(var(--pos-rgb),0.02));
    box-shadow: 0 4px 24px rgba(var(--pos-rgb),0.1);
}

.asymmetry-card.bajista {
    border-color: rgba(var(--neg-rgb),0.35);
    border-left-color: var(--neg);
    background: linear-gradient(135deg, rgba(var(--neg-rgb),0.07), rgba(var(--neg-rgb),0.02));
    box-shadow: 0 4px 24px rgba(var(--neg-rgb),0.1);
}

.asymmetry-card.equilibrado {
    border-color: rgba(var(--info-rgb),0.35);
    border-left-color: var(--info);
    background: linear-gradient(135deg, rgba(var(--info-rgb),0.07), rgba(var(--info-rgb),0.02));
    box-shadow: 0 4px 24px rgba(var(--info-rgb),0.1);
}

.asymmetry-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
}

.asymmetry-icon { font-size: 1.3rem; }

.asymmetry-title {
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
    font-weight: 800;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

.asymmetry-card.alcista    .asymmetry-title { color: var(--pos); }
.asymmetry-card.bajista  .asymmetry-title { color: var(--neg); }
.asymmetry-card.equilibrado  .asymmetry-title { color: var(--info); }

.asymmetry-strength {
    margin-left: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: var(--text-2);
    padding: 3px 8px;
    border-radius: 4px;
    background: rgba(0,0,0,0.3);
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

.asymmetry-body {
    color: var(--text);
    font-size: 0.88rem;
    line-height: 1.6;
}

.asymmetry-body .em {
    font-weight: 700;
}

.asymmetry-card.alcista   .asymmetry-body .em { color: var(--pos); }
.asymmetry-card.bajista .asymmetry-body .em { color: var(--neg); }
.asymmetry-card.equilibrado .asymmetry-body .em { color: var(--info); }


/* ── Markdown ────────────────────────────────────────────────────── */
.stMarkdown p { color: var(--text) !important; font-size: 0.88rem; line-height: 1.7; }
.stMarkdown strong { color: var(--text-hi) !important; }
.stMarkdown li { color: var(--text) !important; font-size: 0.88rem; }


/* ══════════════════════════════════════════════════════════════════════
   GLOBAL BUTTON COLOR OVERRIDE — primary brand = orange (no rojo Streamlit)
   ══════════════════════════════════════════════════════════════════════ */

.stApp button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent) 100%) !important;
    color: var(--bg) !important;
    border: 1px solid rgba(var(--accent-rgb),0.30) !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 12px rgba(var(--accent-rgb),0.18), inset 0 1px 0 rgba(255,255,255,0.18) !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
}
.stApp button[kind="primary"]:hover {
    background: linear-gradient(135deg, var(--accent-hi) 0%, var(--accent) 100%) !important;
    box-shadow: 0 4px 20px rgba(var(--accent-rgb),0.35), inset 0 1px 0 rgba(255,255,255,0.25) !important;
    transform: translateY(-1px);
}
.stApp button[kind="primary"]:focus:not(:active) {
    border-color: rgba(var(--accent-rgb),0.55) !important;
    box-shadow: 0 0 0 3px rgba(var(--accent-rgb),0.22), 0 4px 20px rgba(var(--accent-rgb),0.30) !important;
}


/* ══════════════════════════════════════════════════════════════════════
   SCANNER CONFIG PAGE — diseño premium con accent colors por categoría
   ══════════════════════════════════════════════════════════════════════ */

/* Hero del scanner */
.scanner-hero {
    text-align: center;
    padding: 28px 20px 8px;
    animation: fadeInUp 0.6s ease-out;
    position: relative;
}

.scanner-hero-eyebrow {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: var(--accent);
    letter-spacing: 0.18em;
    text-transform: uppercase;
    padding: 4px 12px;
    border: 1px solid rgba(var(--accent-rgb),0.35);
    border-radius: 20px;
    background: rgba(var(--accent-rgb),0.08);
    margin-bottom: 14px;
}

.scanner-hero-title {
    font-family: 'Inter', sans-serif;
    font-size: 2.05rem;
    font-weight: 800;
    color: var(--text-hi);
    letter-spacing: -0.8px;
    margin-bottom: 12px;
    background: linear-gradient(135deg, var(--text-hi) 0%, #EFD9AE 70%, var(--accent) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.scanner-hero-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.93rem;
    color: var(--text-2);
    max-width: 600px;
    margin: 0 auto;
    line-height: 1.7;
}

.scanner-section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, rgba(var(--accent-rgb),0.20) 30%, rgba(var(--accent-rgb),0.20) 70%, transparent 100%);
    margin: 24px 0 18px;
}

/* ── Encabezado de bloque de criterios (1 · 2 · 3) ───────────────────── */
.scanner-group-head {
    display: flex;
    align-items: center;
    gap: 12px;
    margin: 30px 0 14px;
    animation: fadeIn var(--dur-3) var(--ease-out);
}

.scanner-group-head:first-of-type { margin-top: 4px; }

.scanner-group-step {
    flex: 0 0 auto;
    width: 26px;
    height: 26px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: 1px solid rgba(var(--accent-rgb),0.35);
    background: rgba(var(--accent-rgb),0.09);
    color: var(--accent);
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    line-height: 1;
}

.scanner-group-titles {
    flex: 0 1 auto;
    min-width: 0;
}

.scanner-group-title {
    font-size: 0.86rem;
    font-weight: 700;
    color: var(--text-hi);
    letter-spacing: 0.02em;
    line-height: 1.25;
}

.scanner-group-subtitle {
    font-size: 0.72rem;
    color: var(--text-3);
    line-height: 1.35;
    margin-top: 2px;
}

.scanner-group-rule {
    flex: 1 1 auto;
    height: 1px;
    min-width: 16px;
    background: linear-gradient(90deg, rgba(var(--accent-rgb),0.22) 0%, transparent 100%);
}

/* Card de filtro premium */
.scanner-card {
    background: linear-gradient(135deg, rgba(28,34,44,0.55) 0%, rgba(15,18,24,0.85) 100%);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 20px 22px 20px;
    margin-bottom: 18px;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    animation: fadeInUp 0.55s ease-out backwards;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out);
    position: relative;
    /* overflow: visible para que el tooltip del "?" pueda escapar hacia arriba
       y verse por encima de las cards adyacentes. El glow radial del ::after
       queda contenido por su propio mask-image (ver regla más abajo). */
    overflow: visible;
}

/* Accent strip vertical a la izquierda (cada card tiene su color) */
.scanner-card::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 3px;
    height: 100%;
    background: var(--accent, var(--accent));
    opacity: 0.75;
}

/* Glow sutil de fondo del accent al hacer hover.
   Ahora que la card es overflow:visible, posicionamos el glow DENTRO del
   rectángulo (anchored top-right) y reducimos su tamaño para que no se
   escape de los bordes. */
.scanner-card::after {
    content: "";
    position: absolute;
    top: 0;
    right: 0;
    width: 160px;
    height: 160px;
    background: radial-gradient(circle at top right,
        var(--accent, var(--accent)) 0%,
        transparent 65%);
    border-top-right-radius: 14px;
    opacity: 0;
    transition: opacity 0.4s ease;
    pointer-events: none;
}

.scanner-card:hover {
    border-color: rgba(255,255,255,0.12);
    transform: translateY(-2px);
    box-shadow: 0 12px 36px rgba(0,0,0,0.45);
}

.scanner-card:hover::after {
    opacity: 0.06;
}

/* Header de la card: ícono en caja + título + subtítulo */
.scanner-card-head {
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 18px;
    position: relative;
    z-index: 1;
}

.scanner-card-icon-box {
    flex-shrink: 0;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 30%, transparent) 0%, color-mix(in srgb, var(--accent) 8%, transparent) 100%);
    border: 1px solid color-mix(in srgb, var(--accent) 35%, transparent);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--accent) 15%, transparent), inset 0 1px 0 rgba(255,255,255,0.08);
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out);
}

.scanner-card:hover .scanner-card-icon-box {
    transform: scale(1.06) rotate(-3deg);
    box-shadow: 0 6px 20px color-mix(in srgb, var(--accent) 25%, transparent), inset 0 1px 0 rgba(255,255,255,0.15);
}

.scanner-card-icon-emoji {
    font-size: 1.45rem;
    line-height: 1;
}

.scanner-card-titles {
    flex: 1;
    min-width: 0;
}

.scanner-card-title {
    font-family: 'Inter', sans-serif;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--text-hi);
    letter-spacing: -0.3px;
    line-height: 1.3;
    margin-bottom: 3px;
}

.scanner-card-subtitle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: var(--accent, var(--accent));
    opacity: 0.7;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    font-weight: 500;
}

/* Body de la card: contiene los pills */
.scanner-card-body {
    position: relative;
    z-index: 1;
}

/* ── PILL BUTTONS DEL SCANNER — uniformes en alto y estilo ─────────────
   Selector específico via key prefix: todos los st.button del scanner.
   Streamlit no permite agregar clases, pero podemos targetear todos los
   botones que están dentro del flujo y forzar dimensiones consistentes.
   La clave: aplicar a TODO botón dentro de columnas dentro del scanner. */

/* Descendant selector (sin `>`) para ser robusto frente a cambios DOM de Streamlit.
   box-sizing: border-box garantiza que el padding NO crezca la altura. */
.scanner-card-body div[data-testid="stButton"] button,
.scanner-card-body div[data-testid="stColumn"] div[data-testid="stButton"] button {
    height: 44px !important;
    min-height: 44px !important;
    max-height: 44px !important;
    box-sizing: border-box !important;
    padding: 0 10px !important;
    font-size: 0.72rem !important;
    line-height: 1 !important;
    border-radius: 11px !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    word-break: keep-all !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
}

/* Selector UNIVERSAL para garantizar nowrap en TODOS los descendientes
   del botón (Streamlit puede usar p, div o span según versión). */
.scanner-card-body div[data-testid="stButton"] button *,
[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) div[data-testid="stButton"] button * {
    white-space: nowrap !important;
    word-break: keep-all !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    max-width: 100% !important;
    text-align: center !important;
    margin: 0 !important;
    line-height: 1 !important;
    flex-shrink: 0 !important;
}

/* ── SECTORES DE INTERÉS — Tarjetón "Filtro Principal" ─────────────
   Usamos st.container(border=True) + un anchor invisible, y vía :has()
   estilamos el wrapper completo. Streamlit normalmente solo permite
   wrappers HTML alrededor de markdown — pero los componentes nativos
   (botones, columns) salen del flujo. Con container+anchor+:has() sí
   logramos que TODO el contenido (header + toggles + pills) viva dentro
   de la misma caja visual. */
[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) {
    background: linear-gradient(135deg, rgba(214,92,126,0.10) 0%, rgba(var(--accent-rgb),0.05) 100%) !important;
    border: 1.5px solid rgba(214,92,126,0.38) !important;
    border-left: 4px solid #D65C7E !important;
    border-radius: 14px !important;
    padding: 28px 28px 22px 28px !important;
    margin: 14px 0 28px 0 !important;
    box-shadow: 0 6px 24px rgba(214,92,126,0.14), inset 0 1px 0 rgba(255,255,255,0.04) !important;
    position: relative !important;
    overflow: visible !important;
}

/* Badge flotante "FILTRO PRINCIPAL" arriba a la izquierda */
[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor)::before {
    content: "FILTRO PRINCIPAL";
    position: absolute;
    top: -11px;
    left: 22px;
    background: linear-gradient(135deg, #D65C7E 0%, var(--accent) 100%);
    color: var(--bg);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    padding: 4px 12px;
    border-radius: 6px;
    box-shadow: 0 3px 10px rgba(214,92,126,0.40);
    z-index: 2;
}

/* Anchor invisible (solo sirve para :has()) */
.scanner-pri-anchor {
    display: none;
}

/* Header del tarjetón */
.scanner-pri-header {
    display: flex;
    align-items: center;
    gap: 14px;
    margin: -4px 0 18px 0;
    padding-bottom: 14px;
    border-bottom: 1px solid rgba(214,92,126,0.20);
}

.scanner-pri-icon {
    font-size: 2.2rem;
    line-height: 1;
    flex-shrink: 0;
}

.scanner-pri-titles { flex: 1; }

.scanner-pri-title {
    font-family: 'Inter', sans-serif;
    font-size: 1.4rem;
    font-weight: 800;
    color: var(--text-hi);
    line-height: 1.1;
    margin-bottom: 4px;
}

.scanner-pri-subtitle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #D65C7E;
    text-transform: uppercase;
    letter-spacing: 0.10em;
    font-weight: 600;
}

/* Pills del tarjetón principal — más grandes, con icono al lado del texto */
[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) div[data-testid="stButton"] button {
    height: 56px !important;
    min-height: 56px !important;
    max-height: 56px !important;
    padding: 0 14px !important;
    font-size: 0.84rem !important;
    line-height: 1 !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    white-space: nowrap !important;
    word-break: keep-all !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) div[data-testid="stButton"] button[kind="secondary"] {
    background: rgba(20,25,32,0.75) !important;
    color: var(--text) !important;
    border: 1.5px solid rgba(255,255,255,0.10) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.18) !important;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) div[data-testid="stButton"] button[kind="secondary"]:hover {
    background: rgba(35,42,54,0.95) !important;
    border-color: rgba(214,92,126,0.55) !important;
    color: var(--text-hi) !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(214,92,126,0.22) !important;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) div[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #D65C7E 0%, #E0854E 100%) !important;
    color: var(--text-hi) !important;
    border: 1.5px solid rgba(255,255,255,0.18) !important;
    box-shadow: 0 6px 20px rgba(214,92,126,0.40), inset 0 1px 0 rgba(255,255,255,0.20) !important;
    font-weight: 700 !important;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) div[data-testid="stButton"] button[kind="primary"]:hover {
    background: linear-gradient(135deg, var(--neg) 0%, #E0854E 100%) !important;
    box-shadow: 0 8px 26px rgba(214,92,126,0.55), inset 0 1px 0 rgba(255,255,255,0.26) !important;
    transform: translateY(-2px);
}

/* Pills inactivos (kind=secondary) */
.scanner-card-body div[data-testid="stButton"] > button[kind="secondary"] {
    background: rgba(20,25,32,0.6) !important;
    color: var(--text) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    box-shadow: none !important;
}

.scanner-card-body div[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: rgba(35,40,48,0.85) !important;
    border-color: rgba(var(--accent-rgb),0.30) !important;
    color: var(--text-hi) !important;
    transform: translateY(-1px);
}

/* Pills activos (kind=primary) — naranja brand */
.scanner-card-body div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent) 100%) !important;
    color: var(--bg) !important;
    border: 1px solid rgba(var(--accent-rgb),0.55) !important;
    box-shadow: 0 4px 14px rgba(var(--accent-rgb),0.28), inset 0 1px 0 rgba(255,255,255,0.22) !important;
    font-weight: 700 !important;
}

.scanner-card-body div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: linear-gradient(135deg, var(--accent-hi) 0%, var(--accent) 100%) !important;
    box-shadow: 0 6px 22px rgba(var(--accent-rgb),0.40), inset 0 1px 0 rgba(255,255,255,0.30) !important;
    transform: translateY(-1px);
}

/* Tooltip "?" del scanner */
.scanner-help {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: rgba(var(--accent-rgb),0.10);
    border: 1px solid rgba(var(--accent-rgb),0.30);
    color: var(--accent);
    font-size: 0.70rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    cursor: help;
    margin-left: auto;
    flex-shrink: 0;
    position: relative;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out);
}

.scanner-help:hover {
    background: rgba(var(--accent-rgb),0.25);
    border-color: rgba(var(--accent-rgb),0.55);
    transform: scale(1.08);
}

.scanner-help::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: calc(100% + 10px);
    right: 0;
    width: 280px;
    background: var(--bg);
    color: var(--text);
    border: 1px solid rgba(var(--accent-rgb),0.45);
    border-radius: 8px;
    padding: 12px 14px;
    font-family: 'Inter', sans-serif;
    font-size: 0.76rem;
    font-weight: 400;
    line-height: 1.5;
    letter-spacing: 0;
    text-transform: none;
    text-align: left;
    box-shadow: 0 14px 40px rgba(0,0,0,0.85),
                0 0 0 1px rgba(var(--accent-rgb),0.20);
    opacity: 0;
    pointer-events: none;
    transform: translateY(4px);
    transition: opacity 0.2s ease, transform 0.2s ease;
    /* z-index muy alto para garantizar que aparezca por encima de TODA la página */
    z-index: 9999;
    white-space: normal;
}

/* Cuando se hace hover sobre el "?", elevar el stacking de toda la card
   para que el tooltip no quede tapado por cards adyacentes que vienen
   después en el DOM (Streamlit las renderiza con stacking propio por
   backdrop-filter). */
.scanner-card:has(.scanner-help:hover) {
    z-index: 9998;
    position: relative;
}

.scanner-help:hover::after {
    opacity: 1;
    transform: translateY(0);
}

/* ── Barra de acción inferior ── */
.scanner-actions-strip {
    background: linear-gradient(135deg, rgba(28,34,44,0.7) 0%, rgba(15,18,24,0.9) 100%);
    border: 1px solid var(--hairline);
    border-radius: 14px;
    padding: 18px 22px;
    margin-top: 8px;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    display: flex;
    align-items: center;
    gap: 12px;
}

.scanner-actions-hint {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    color: var(--text-2);
    flex: 1;
}

.scanner-actions-hint strong {
    color: var(--accent);
    font-weight: 600;
}

/* Botones de la action bar — el primario más grande y prominente */
.scanner-actions-strip div[data-testid="stButton"] > button {
    height: 46px !important;
    font-size: 0.88rem !important;
    border-radius: 11px !important;
    font-weight: 600 !important;
}

/* ════════════════════════════════════════════════════════════════════════
   ✨ SISTEMA DE ANIMACIONES PREMIUM — calidad alta, performance segura
   Todas las animaciones usan SOLO transform + opacity (GPU-accelerated).
   Curvas cubic-bezier para sensación "spring" y "smooth". Stagger automático
   con animation-delay para cascadas en hijos.
   ════════════════════════════════════════════════════════════════════════ */

:root {
    --anim-fast:   180ms;
    --anim-normal: 280ms;
    --anim-slow:   480ms;
    --ease-out:    cubic-bezier(0.16, 1, 0.3, 1);
    --ease-soft:   cubic-bezier(0.4, 0, 0.2, 1);
    --ease-spring: cubic-bezier(0.34, 1.4, 0.64, 1);
}

/* ── Keyframes base ── */
@keyframes anim-fadeInUp {
    from { opacity: 0; transform: translate3d(0, 12px, 0); }
    to   { opacity: 1; transform: translate3d(0, 0, 0); }
}
@keyframes anim-fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}
@keyframes anim-scaleIn {
    from { opacity: 0; transform: scale(0.96); }
    to   { opacity: 1; transform: scale(1); }
}
@keyframes anim-popIn {
    0%   { opacity: 0; transform: scale(0.85); }
    60%  { opacity: 1; transform: scale(1.04); }
    100% { opacity: 1; transform: scale(1); }
}
@keyframes anim-slideInLeft {
    from { opacity: 0; transform: translate3d(-14px, 0, 0); }
    to   { opacity: 1; transform: translate3d(0, 0, 0); }
}
@keyframes anim-glowPulse {
    0%, 100% { box-shadow: 0 3px 10px rgba(214,92,126,0.32); }
    50%      { box-shadow: 0 4px 18px rgba(214,92,126,0.55); }
}
@keyframes anim-subtleFloat {
    0%, 100% { transform: translate3d(0, 0, 0); }
    50%      { transform: translate3d(0, -2px, 0); }
}
@keyframes anim-shimmer {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes anim-shineAlongBorder {
    from { offset-distance: 0%; }
    to   { offset-distance: 100%; }
}

/* ── 1. HERO WELCOME — entrada en cascada ───────────────────────────── */
.alpha-hero-brand   { animation: anim-fadeInUp 700ms var(--ease-out) both; }
.alpha-hero-tagline { animation: anim-fadeInUp 700ms 80ms  var(--ease-out) both; }
.alpha-divider      { animation: anim-fadeIn   600ms 160ms var(--ease-out) both; }
.action-label-new   { animation: anim-fadeInUp 600ms 200ms var(--ease-out) both; }

/* Quick-access ticker tiles con stagger por delay calculado en JSX (animation-delay) */
.ticker-tile {
    animation: anim-fadeInUp 520ms var(--ease-out) both;
    transition: transform var(--anim-normal) var(--ease-out),
                box-shadow var(--anim-normal) var(--ease-out),
                border-color var(--anim-normal) var(--ease-out);
}
.ticker-tile:hover {
    transform: translate3d(0, -3px, 0);
}

/* ── 2. BOTONES GLOBALES — feedback al press y al hover ─────────────── */
[data-testid="stButton"] > button {
    transition: transform var(--anim-fast) var(--ease-out),
                box-shadow var(--anim-normal) var(--ease-out),
                background var(--anim-normal) var(--ease-soft),
                border-color var(--anim-normal) var(--ease-soft),
                color var(--anim-normal) var(--ease-soft) !important;
}
[data-testid="stButton"] > button:active {
    transform: scale(0.97) !important;
    transition-duration: 80ms !important;
}

/* ── 3. KPI TILES — entrada con stagger + hover lift ───────────────── */
.kpi-tile {
    animation: anim-fadeInUp 520ms var(--ease-out) both;
    transition: transform var(--anim-normal) var(--ease-out),
                box-shadow var(--anim-normal) var(--ease-out),
                border-color var(--anim-normal) var(--ease-out);
}
.kpi-tile:hover {
    transform: translate3d(0, -2px, 0);
}
/* Stagger por posición de hermano (hasta 12 hijos) */
.kpi-tile:nth-child(1) { animation-delay: 0ms; }
.kpi-tile:nth-child(2) { animation-delay: 60ms; }
.kpi-tile:nth-child(3) { animation-delay: 120ms; }
.kpi-tile:nth-child(4) { animation-delay: 180ms; }
.kpi-tile:nth-child(5) { animation-delay: 240ms; }
.kpi-tile:nth-child(6) { animation-delay: 300ms; }

/* ── 4. STATUS PILLS — fade-in suave ───────────────────────────────── */
.status-pill {
    animation: anim-fadeInUp 460ms var(--ease-out) both;
    transition: transform var(--anim-normal) var(--ease-out),
                box-shadow var(--anim-normal) var(--ease-out);
}
.status-pill:hover { transform: translate3d(0, -1px, 0); }

/* ── 5. CARDS Y SECCIONES — entrada elegante ───────────────────────── */
.analysis-card,
.insight-card,
.asymmetry-card,
.alpha-opportunity-card {
    animation: anim-fadeInUp 540ms var(--ease-out) both;
}

.scanner-card {
    animation: anim-fadeInUp 500ms var(--ease-out) both;
    transition: transform var(--anim-normal) var(--ease-out),
                box-shadow var(--anim-normal) var(--ease-out),
                border-color var(--anim-normal) var(--ease-out);
}
.scanner-card:hover {
    transform: translate3d(0, -2px, 0);
}

/* ── 6. TARJETÓN PRINCIPAL (Sectores) — entrada destacada + badge ──── */
[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) {
    animation: anim-scaleIn 580ms var(--ease-out) both;
}
[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor)::before {
    animation: anim-glowPulse 2.8s ease-in-out infinite;
}

/* Pills del tarjetón principal — activación tipo spring */
[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor)
    div[data-testid="stButton"] > button[kind="primary"] {
    animation: anim-popIn 380ms var(--ease-spring) both;
}

/* ── 7. PLOTLY CHARTS — fade-in al renderizar ──────────────────────── */
.js-plotly-plot,
[data-testid="stPlotlyChart"] {
    animation: anim-fadeIn var(--anim-slow) var(--ease-out) both;
}

/* ── 8. SIDEBAR WATCHLIST — slide-in por elemento ──────────────────── */
[data-testid="stSidebar"] [data-testid="stButton"] {
    animation: anim-slideInLeft 420ms var(--ease-out) both;
}
[data-testid="stSidebar"] [data-testid="stButton"]:nth-child(2)  { animation-delay: 40ms; }
[data-testid="stSidebar"] [data-testid="stButton"]:nth-child(3)  { animation-delay: 80ms; }
[data-testid="stSidebar"] [data-testid="stButton"]:nth-child(4)  { animation-delay: 120ms; }
[data-testid="stSidebar"] [data-testid="stButton"]:nth-child(5)  { animation-delay: 160ms; }
[data-testid="stSidebar"] [data-testid="stButton"]:nth-child(6)  { animation-delay: 200ms; }
[data-testid="stSidebar"] [data-testid="stButton"]:nth-child(7)  { animation-delay: 240ms; }
[data-testid="stSidebar"] [data-testid="stButton"]:nth-child(8)  { animation-delay: 280ms; }

[data-testid="stSidebar"] [data-testid="stButton"] > button {
    transition: transform var(--anim-fast) var(--ease-out),
                background var(--anim-normal) var(--ease-soft),
                color var(--anim-normal) var(--ease-soft) !important;
}
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
    transform: translate3d(2px, 0, 0) !important;
}

/* ── 9. THESIS / STRENGTH / RISK ITEMS — fade-in con stagger ──────── */
.strength-item, .risk-item, .veto-item {
    animation: anim-fadeInUp 440ms var(--ease-out) both;
}
.strength-item:nth-child(1), .risk-item:nth-child(1) { animation-delay: 0ms; }
.strength-item:nth-child(2), .risk-item:nth-child(2) { animation-delay: 70ms; }
.strength-item:nth-child(3), .risk-item:nth-child(3) { animation-delay: 140ms; }
.strength-item:nth-child(4), .risk-item:nth-child(4) { animation-delay: 210ms; }

/* ── 10. RECOMMENDATION BADGE — entrada con pop ───────────────────── */
.badge-strong-buy, .badge-buy, .badge-watch, .badge-pass {
    animation: anim-popIn 460ms var(--ease-spring) both;
}
.badge-strong-buy {
    /* Glow continuo sutil solo para la mejor recomendación */
    box-shadow: 0 0 20px rgba(var(--pos-rgb),0.25);
}

/* ── 11. SKELETON shimmer durante carga ───────────────────────────── */
.skeleton-block {
    background: linear-gradient(90deg,
        rgba(35,40,48,0.6) 0%,
        rgba(50,60,75,0.85) 50%,
        rgba(35,40,48,0.6) 100%) !important;
    background-size: 200% 100% !important;
    animation: anim-shimmer 1.6s ease-in-out infinite !important;
}

/* ── 12. PROGRESS RING durante análisis — pulse glow ──────────────── */
.alpha-progress-ring-wrap:not(.complete) .alpha-progress-fg {
    filter: drop-shadow(0 0 6px rgba(var(--accent-rgb),0.55));
}

/* ── 13. SCANNER ACTIONS — botón "Ejecutar búsqueda" con pulse ────── */
.scanner-actions-strip div[data-testid="stButton"]:last-child > button[kind="primary"] {
    animation: anim-fadeInUp 520ms 200ms var(--ease-out) both;
}

/* ── 14. TICKER TILES stagger por fila ────────────────────────────── */
[data-testid="stColumn"]:has(.ticker-tile) .ticker-tile {
    animation: anim-fadeInUp 480ms var(--ease-out) both;
}

/* ── 15. BRILLO DE BORDE — botón "Ejecutar búsqueda" (ÚNICO) ──────
   Selector ESTRICTO: el botón es el element-container que sigue
   INMEDIATAMENTE al element-container que contiene el anchor.
   `+` (adjacent sibling) garantiza que NINGÚN otro botón de la página
   recibe el efecto, ni siquiera por herencia o cascada de :has(). */

[data-testid="element-container"]:has(.ejecutar-glow-anchor)
    + [data-testid="element-container"]
    [data-testid="stButton"] > button {
    position: relative !important;
    isolation: isolate;
    height: 56px !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.04em !important;
    border-radius: 12px !important;
    overflow: visible !important;
}

[data-testid="element-container"]:has(.ejecutar-glow-anchor)
    + [data-testid="element-container"]
    [data-testid="stButton"] > button::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    width: 60px;
    height: 2px;
    border-radius: 50%;
    background: linear-gradient(90deg,
        transparent 0%,
        rgba(255, 215, 64, 0.0) 15%,
        rgba(255, 215, 64, 0.85) 45%,
        rgba(255, 255, 255, 1.0) 50%,
        rgba(255, 215, 64, 0.85) 55%,
        rgba(255, 215, 64, 0.0) 85%,
        transparent 100%);
    filter: blur(0.5px) drop-shadow(0 0 5px rgba(255, 215, 64, 0.80));
    offset-path: inset(0 round 12px);
    offset-rotate: auto;
    offset-distance: 0%;
    animation: anim-shineAlongBorder 4s linear infinite;
    pointer-events: none;
    z-index: 2;
}

/* Anchor invisible — solo sirve como marcador para el selector hermano. */
.ejecutar-glow-anchor { display: none; }

/* ── 16. REDUCE MOTION — respeto al usuario que lo desactiva ──────── */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* ── 17. PROTECCIÓN ANTI-EXTRACCIÓN ────────────────────────────────
   Bloquea selección de texto en botones, navegación y chrome del UI.
   Texto narrativo (análisis, tesis, pros/cons) MANTIENE selección
   para que el usuario sí pueda copiar contenido legítimo. Capa
   cosmética / disuasiva — no es seguridad real. */
[data-testid="stButton"],
[data-testid="stButton"] *,
[data-testid="stSidebar"],
[data-testid="stSidebar"] *,
.scanner-card-head,
.scanner-card-head *,
.scanner-pri-header,
.scanner-pri-header *,
.alpha-hero,
.alpha-hero *,
.action-label-new,
.ticker-tile,
.ticker-tile *,
.kpi-tile-label,
.scanner-pri-anchor,
.ejecutar-glow-anchor {
    -webkit-user-select: none !important;
    -moz-user-select: none !important;
    -ms-user-select: none !important;
    user-select: none !important;
    -webkit-user-drag: none !important;
}

/* Bloquear arrastrar imágenes y links nativamente */
img, a {
    -webkit-user-drag: none !important;
    user-drag: none !important;
    -webkit-touch-callout: none !important;
}

/* ── 18. OCULTAR BRANDING Y CONTROLES DE STREAMLIT CLOUD ──────────────
   Quitar "Built with Streamlit", botón "Fullscreen", menú hamburguesa,
   header, footer y cualquier control que la plataforma agregue alrededor
   de la app. Necesario para que dentro del iframe de Whop se vea como
   producto propio sin escape al exterior. */
[class*="viewerBadge"],
[class*="ViewerBadge"],
[data-testid="stToolbar"],
[data-testid="stToolbarActions"],
[data-testid="stStatusWidget"],
[data-testid="stDecoration"],
[data-testid="stHeader"],
[data-testid="stAppDeployButton"],
[data-testid="stDeployButton"],
[data-testid="stActionButtonIcon"],
header[data-testid="stHeader"],
.stApp > header,
.stApp > footer,
footer.streamlit-footer,
#MainMenu,
.stDeployButton,
.stAppDeployButton,
button[title="View fullscreen"],
button[kind="header"],
button[kind="headerNoPadding"],
a[href*="streamlit.io"],
a[href*="streamlit.app/login"],
iframe[title="streamlit_extras_padding"] + div,
.element-container:has(> [class*="viewerBadge"]),
.element-container:has(> button[title*="ullscreen"]) {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    width: 0 !important;
    max-height: 0 !important;
    max-width: 0 !important;
    overflow: hidden !important;
    opacity: 0 !important;
    pointer-events: none !important;
    position: absolute !important;
    left: -9999px !important;
}

/* Forzar que el contenido de la app llene el espacio (sin gap inferior
   del badge eliminado) */
.stApp {
    padding-bottom: 0 !important;
    margin-bottom: 0 !important;
}

/* ── 19. SIDEBAR LATERAL CON HISTORIAL ────────────────────────────────
   Antes ocultábamos el sidebar (iframe Whop cuadrado). Ahora lo
   mostramos porque el historial de análisis y escaneos va aquí.
   El botón "Volver al Home" del top-nav se mantiene como redundancia
   amistosa cuando el sidebar está colapsado. */
[data-testid="stSidebar"],
section[data-testid="stSidebar"] {
    display: flex !important;
    visibility: visible !important;
    transform: none !important;
    width: 260px !important;
    min-width: 260px !important;
    max-width: 260px !important;
}

/* Permitir que el botón de colapso del sidebar siga funcionando */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    transform: none !important;
}

/* Layout principal: dejamos el padding lateral mínimo del contenido pero
   permitimos que el sidebar reciba su ancho normal sin pelear con él */
[data-testid="stAppViewContainer"] > section.main,
[data-testid="stMain"],
.main .block-container {
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
}

/* Botón "Volver al Home" del top nav — sutil pero claro, tema dark */
.st-key-topnav_home_btn button,
[data-testid="stButton"] button[key*="topnav_home"] {
    background: linear-gradient(135deg, rgba(28,34,44,0.85), rgba(15,18,24,0.95)) !important;
    border: 1px solid rgba(var(--accent-rgb),0.30) !important;
    color: var(--accent) !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    font-size: 0.82rem !important;
    text-transform: uppercase !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    margin-bottom: 14px !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
}

.st-key-topnav_home_btn button:hover {
    background: linear-gradient(135deg, rgba(40,48,60,0.95), rgba(20,25,32,1)) !important;
    border-color: rgba(var(--accent-rgb),0.55) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(var(--accent-rgb),0.15) !important;
}

/* ── 20. RESPONSIVE: iframe CUADRADO (Whop, mobile, tablets) ──────────
   La app fue diseñada para pantallas wide (16:9). En el iframe de Whop
   el ratio es casi 1:1 y los componentes que asumen "mucho ancho"
   (header del análisis, tabs, KPI tiles, status pills, gauges) se
   apretaban. Estas media queries comprimen tamaños y permiten reflow
   sin romper el layout original de PC. */

@media (max-width: 900px) {
    /* Header del análisis — permitir wrap, reducir tamaños, gap menor */
    .stock-header {
        flex-wrap: wrap !important;
        gap: 10px !important;
        padding: 14px 16px !important;
    }
    .stock-header-ticker { font-size: 1.6rem !important; }
    .stock-header-name   { font-size: 0.85rem !important; }
    .stock-header-score  { font-size: 1.6rem !important; margin-left: auto !important; }
    .compound-machine-badge { font-size: 0.62rem !important; padding: 4px 8px !important; }

    /* Tabs del análisis — scroll horizontal smooth en vez de cortarse */
    [data-testid="stTabs"] > div:first-child {
        overflow-x: auto !important;
        overflow-y: hidden !important;
        flex-wrap: nowrap !important;
        scrollbar-width: thin !important;
        -webkit-overflow-scrolling: touch !important;
    }
    [data-testid="stTabs"] button[data-baseweb="tab"] {
        padding: 8px 12px !important;
        font-size: 0.74rem !important;
        flex-shrink: 0 !important;
        white-space: nowrap !important;
    }

    /* KPI tiles — labels en 2 líneas si hace falta, NO truncar con "..." */
    .kpi-tile {
        padding: 10px 8px !important;
        min-height: 76px !important;
    }
    .kpi-tile-label {
        font-size: 0.62rem !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        line-height: 1.15 !important;
    }
    .kpi-tile-value { font-size: 1.0rem !important; }

    /* Status pills del sentimiento — mismo tratamiento que KPI tiles */
    .status-pill {
        padding: 10px 8px !important;
        min-height: 76px !important;
    }
    .status-pill-label {
        font-size: 0.62rem !important;
        white-space: normal !important;
        overflow: visible !important;
        line-height: 1.15 !important;
    }
    .status-pill-value { font-size: 0.85rem !important; }
    .status-pill-sub   { font-size: 0.62rem !important; }

    /* Live Market Pulse cards — números compactos sin saltos de línea */
    .market-pulse-card { padding: 8px 6px !important; }
    .pulse-label  { font-size: 0.55rem !important; letter-spacing: 0.08em !important; }
    .pulse-value  { font-size: 0.85rem !important; }
    .pulse-change { font-size: 0.62rem !important; }

    /* Botones de la action card del home — padding más compacto y font un
       poquito más chico para que "🌐 ESCANEAR EL MERCADO" quepa completo en
       el iframe cuadrado de Whop sin cortarse. */
    [data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"])
        [data-testid="stButton"] > button[kind="primary"],
    [data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"])
        [data-testid="stButton"] > button[kind="secondary"] {
        padding: 10px 8px !important;
        font-size: 0.72rem !important;
        letter-spacing: 0.03em !important;
        white-space: nowrap !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }
}

/* Iframe ANGOSTO (Whop con sidebar): forzar que TODO el texto del botón
   quepa, incluso a costa de tamaño aún más chico. */
@media (max-width: 700px) {
    [data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"])
        [data-testid="stButton"] > button[kind="primary"],
    [data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"])
        [data-testid="stButton"] > button[kind="secondary"] {
        padding: 10px 6px !important;
        font-size: 0.66rem !important;
        letter-spacing: 0.02em !important;
    }
}

/* ── 21. INFO ROWS DEL OVERVIEW (Empresa, Ticker, Sector, Horizonte) ──
   Layout GRID en vez de flex para que el value (especialmente "Horizonte"
   que puede ser un texto largo del LLM) NO se solape con el key. Máximo
   2 líneas con line-clamp + ellipsis. */
.overview-info-row {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 14px;
    padding: 5px 0;
    border-bottom: 1px solid var(--border-solid);
    align-items: start;
}
.overview-info-key {
    color: var(--text-2);
    font-size: 0.8rem;
    white-space: nowrap;
}
.overview-info-value {
    color: var(--text);
    font-size: 0.8rem;
    font-weight: 500;
    text-align: right;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    line-height: 1.3;
    word-break: break-word;
    min-width: 0;
}

/* ── 22. SECTION SPINNERS — para Tickers Populares y Live Market Pulse ──
   Cuando esas secciones están cargando datos de red, mostramos un círculo
   girando + texto debajo, así el usuario sabe que hay algo cargando ahí
   abajo en vez de pensar que la app está rota. */
.section-spinner-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 28px 0 24px;
    gap: 12px;
    animation: fadeIn 0.4s ease-out;
}
.section-spinner {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    border: 3px solid rgba(255, 184, 77, 0.12);
    border-top-color: var(--accent);
    animation: spin 0.9s linear infinite;
}
.section-spinner-text {
    color: var(--text-2);
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.10em;
    text-transform: uppercase;
    animation: fade-soft 1.6s ease-in-out infinite;
}
@keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}

@media (max-width: 600px) {
    /* En iframes verdaderamente angostos, font-sizes aún más chicos */
    .stock-header-ticker { font-size: 1.3rem !important; }
    .stock-header-name   { font-size: 0.75rem !important; }
    .stock-header-score  { font-size: 1.4rem !important; }
    .kpi-tile-label  { font-size: 0.58rem !important; }
    .kpi-tile-value  { font-size: 0.9rem  !important; }
    .status-pill-value { font-size: 0.78rem !important; }

    /* Live Market Pulse — extra compacto */
    .market-pulse-card { padding: 6px 4px !important; }
    .pulse-label  { font-size: 0.50rem !important; }
    .pulse-value  { font-size: 0.78rem !important; }
    .pulse-change { font-size: 0.58rem !important; }
}

/* ── PASSWORD GATE — pantalla de login en cloud ─────────────────────── */
.auth-gate-wrap {
    text-align: center;
    padding: 80px 20px 30px;
    animation: fadeInUp 0.6s ease-out;
}
.auth-gate-brand {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2.6rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-hi) 50%, var(--accent-deep) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 0.05em;
    line-height: 1;
}
.auth-gate-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    color: var(--text-2);
    margin-top: 14px;
    letter-spacing: 0.30em;
    text-transform: uppercase;
    font-weight: 600;
}
.auth-gate-divider {
    width: 60px;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    margin: 28px auto 22px auto;
}
.auth-gate-hint {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    color: var(--text-3);
    margin-bottom: 24px;
    font-style: italic;
}

/* Compactar el formulario del gate y darle borde dorado sutil */
[data-testid="stForm"]:has(input[placeholder="Contraseña…"]) {
    background: linear-gradient(135deg, rgba(13,15,18,0.95), rgba(20,28,38,0.95)) !important;
    border: 1px solid rgba(var(--accent-rgb),0.25) !important;
    border-radius: 12px !important;
    padding: 22px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.5) !important;
}

/* ── 21. HISTORIAL EN SIDEBAR (Análisis + Escaneos) ────────────────────
   Estética coherente con el resto del terminal: paleta naranja sutil,
   monoespaciada para tickers, separadores con gradiente, badge de
   calificación remarcado a la derecha. */

/* Sección título dentro del sidebar */
.sb-section-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.18em;
    padding: 18px 6px 8px 6px;
    margin-top: 6px;
    border-bottom: 1px solid var(--hairline);
    margin-bottom: 10px;
}

.sb-empty {
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    color: var(--text-3);
    padding: 8px 10px;
    font-style: italic;
    text-align: center;
}

/* Separador estético entre secciones del sidebar */
.sb-section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(var(--accent-rgb),0.30), transparent);
    margin: 14px 4px;
}

/* Wrap del badge a la derecha de un item: alinearlo a la izquierda de su
   columna y permitirle ocupar todo el ancho disponible compactamente */
.sb-badge-wrap {
    display: flex;
    align-items: center;
    justify-content: flex-start;
    height: 100%;
    padding-top: 2px;
}

/* Versión compacta de los recommendation badges (cabe en sidebar 260px) */
.sb-badge-wrap .badge-strong-buy,
.sb-badge-wrap .badge-buy,
.sb-badge-wrap .badge-watch,
.sb-badge-wrap .badge-pass {
    /* padding-left amplio: deja sitio al punto de estado (::before) para que
       no se solape con la primera letra de la recomendación. */
    padding: 4px 9px 4px 19px !important;
    font-size: 0.58rem !important;
    letter-spacing: 0.06em !important;
    border-radius: 4px !important;
    white-space: nowrap;
    line-height: 1.2;
    /* Glow más sutil aquí — no queremos que el sidebar grite */
    box-shadow: 0 2px 8px rgba(0,0,0,0.35) !important;
    /* Apagamos la animación de entrada para que no parpadee cada rerun */
    animation: none !important;
}

/* El punto de estado, recolocado para la versión compacta del sidebar:
   queda holgado a la izquierda del texto, sin pisarlo. */
.sb-badge-wrap .badge-strong-buy::before,
.sb-badge-wrap .badge-buy::before,
.sb-badge-wrap .badge-watch::before,
.sb-badge-wrap .badge-pass::before {
    left: 7px;
    width: 5px;
    height: 5px;
}

/* Badge numérico para escaneos (cuántos candidatos pasaron) */
.sb-count-badge {
    display: inline-block;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    font-size: 0.68rem;
    color: var(--accent);
    background: rgba(var(--accent-rgb),0.10);
    border: 1px solid rgba(var(--accent-rgb),0.30);
    border-radius: 4px;
    padding: 3px 8px;
    letter-spacing: 0.04em;
    text-align: center;
    min-width: 38px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.25);
}

.sb-count-sub {
    display: block;
    font-size: 0.50rem;
    color: var(--text-2);
    letter-spacing: 0.10em;
    text-transform: uppercase;
    margin-top: 1px;
    font-family: 'JetBrains Mono', monospace;
    font-weight: 500;
}

/* Botones de items del historial — sobrescriben el estilo genérico del
   sidebar para que se vean como cards densas, no como botones largos */
[data-testid="stSidebar"] [class*="st-key-sb_a_"] button,
[data-testid="stSidebar"] [class*="st-key-sb_s_"] button {
    background: linear-gradient(135deg, rgba(20,25,35,0.85), rgba(12,16,22,0.95)) !important;
    border: 1px solid rgba(35,40,48,0.7) !important;
    border-left: 3px solid rgba(var(--accent-rgb),0.45) !important;
    color: var(--text) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 700 !important;
    font-size: 0.78rem !important;
    text-transform: none !important;
    letter-spacing: 0.02em !important;
    border-radius: 6px !important;
    padding: 8px 10px !important;
    text-align: left !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
    box-shadow: none !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

[data-testid="stSidebar"] [class*="st-key-sb_a_"] button:hover,
[data-testid="stSidebar"] [class*="st-key-sb_s_"] button:hover {
    background: linear-gradient(135deg, rgba(35,42,55,0.95), rgba(20,25,32,1)) !important;
    border-color: rgba(var(--accent-rgb),0.4) !important;
    border-left-color: var(--accent) !important;
    color: var(--accent) !important;
    transform: translateX(2px) !important;
    box-shadow: 0 3px 12px rgba(var(--accent-rgb),0.12) !important;
}

/* Accent del borde izquierdo por recomendación — usamos un sufijo en la
   key del botón para colorear el item según su rating */
[data-testid="stSidebar"] [class*="__rec_strong_buy"] button { border-left-color: var(--pos) !important; }
[data-testid="stSidebar"] [class*="__rec_buy"] button        { border-left-color: var(--info) !important; }
[data-testid="stSidebar"] [class*="__rec_watch"] button      { border-left-color: var(--accent-deep) !important; }
[data-testid="stSidebar"] [class*="__rec_pass"] button       { border-left-color: var(--neg) !important; }

/* Hover preserva el color del rating pero más intenso */
[data-testid="stSidebar"] [class*="__rec_strong_buy"] button:hover { border-left-color: var(--pos) !important; box-shadow: 0 3px 12px rgba(var(--pos-rgb),0.18) !important; }
[data-testid="stSidebar"] [class*="__rec_buy"] button:hover        { border-left-color: var(--info) !important; box-shadow: 0 3px 12px rgba(var(--info-rgb),0.18) !important; }
[data-testid="stSidebar"] [class*="__rec_watch"] button:hover      { border-left-color: var(--accent) !important; box-shadow: 0 3px 12px rgba(var(--accent-deep-rgb),0.18) !important; }
[data-testid="stSidebar"] [class*="__rec_pass"] button:hover       { border-left-color: var(--neg) !important; box-shadow: 0 3px 12px rgba(var(--neg-rgb),0.18) !important; }

/* Botón Home del sidebar — más prominente, full-width */
[data-testid="stSidebar"] [class*="st-key-sidebar_home"] button {
    background: linear-gradient(135deg, rgba(var(--accent-rgb),0.15), rgba(var(--accent-deep-rgb),0.10)) !important;
    border: 1px solid rgba(var(--accent-rgb),0.40) !important;
    color: var(--accent) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.80rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.10em !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
    text-align: center !important;
    box-shadow: 0 2px 10px rgba(var(--accent-rgb),0.08) !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
}

[data-testid="stSidebar"] [class*="st-key-sidebar_home"] button:hover {
    background: linear-gradient(135deg, rgba(var(--accent-rgb),0.28), rgba(var(--accent-deep-rgb),0.18)) !important;
    border-color: rgba(var(--accent-rgb),0.70) !important;
    color: var(--text-hi) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 18px rgba(var(--accent-rgb),0.25) !important;
}

/* Compactar columnas dentro del sidebar para que el ticker/label + badge
   quepan en 260px sin recortes */
[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
    gap: 6px !important;
}

[data-testid="stSidebar"] [data-testid="stColumn"] {
    padding: 0 !important;
}

/* Reducimos el padding general del sidebar para más densidad */
[data-testid="stSidebarUserContent"] {
    padding: 1rem 0.75rem 2rem 0.75rem !important;
}

/* Estética del scroll del sidebar — barra fina y dorada */
[data-testid="stSidebar"] ::-webkit-scrollbar {
    width: 6px;
}
[data-testid="stSidebar"] ::-webkit-scrollbar-track {
    background: rgba(13,15,18,0.5);
}
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {
    background: rgba(var(--accent-rgb),0.25);
    border-radius: 3px;
}
[data-testid="stSidebar"] ::-webkit-scrollbar-thumb:hover {
    background: rgba(var(--accent-rgb),0.50);
}

/* ── 22. COLAPSAR / EXPANDIR SIDEBAR (mismo estilo que "Volver al Home") ── */

/* Botón minimizar («) — superpuesto sobre la MISMA línea del logo "◈ DLP",
   arriba a la derecha. Se posiciona en absoluto para no alterar el brand
   (que conserva su centrado y su subrayado a todo el ancho). */
[data-testid="stSidebarUserContent"] {
    position: relative !important;
}
[data-testid="stSidebar"] [class*="st-key-sidebar_collapse_btn"] {
    position: absolute !important;
    top: 14px !important;
    right: 4px !important;
    z-index: 20 !important;
    width: auto !important;
    margin: 0 !important;
}
[data-testid="stSidebar"] [class*="st-key-sidebar_collapse_btn"] button {
    background: linear-gradient(135deg, rgba(var(--accent-rgb),0.15), rgba(var(--accent-deep-rgb),0.10)) !important;
    border: 1px solid rgba(var(--accent-rgb),0.40) !important;
    color: var(--accent) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1.25rem !important;
    line-height: 1 !important;
    letter-spacing: 0.05em !important;
    border-radius: 8px !important;
    padding: 6px 12px !important;
    min-height: 0 !important;
    width: auto !important;
    box-shadow: 0 2px 10px rgba(var(--accent-rgb),0.08) !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
}
[data-testid="stSidebar"] [class*="st-key-sidebar_collapse_btn"] button:hover {
    background: linear-gradient(135deg, rgba(var(--accent-rgb),0.28), rgba(var(--accent-deep-rgb),0.18)) !important;
    border-color: rgba(var(--accent-rgb),0.70) !important;
    color: var(--text-hi) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 18px rgba(var(--accent-rgb),0.25) !important;
}

/* Botón expandir (») — fijo arriba a la izquierda cuando el sidebar está oculto.
   Ponemos position:fixed en el CONTENEDOR para que no deje hueco en el flujo. */
[class*="st-key-sidebar_expand_btn"] {
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    z-index: 999990 !important;
    width: auto !important;
    margin: 0 !important;
}
[class*="st-key-sidebar_expand_btn"] button {
    background: linear-gradient(135deg, rgba(var(--accent-rgb),0.15), rgba(var(--accent-deep-rgb),0.10)) !important;
    border: 1px solid rgba(var(--accent-rgb),0.40) !important;
    color: var(--accent) !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    line-height: 1 !important;
    letter-spacing: 0.05em !important;
    border-radius: 8px !important;
    padding: 7px 12px !important;
    min-height: 0 !important;
    width: auto !important;
    box-shadow: 0 2px 12px rgba(var(--accent-rgb),0.15) !important;
    transition: background var(--dur-2) var(--ease-out), border-color var(--dur-2) var(--ease-out), color var(--dur-2) var(--ease-out), transform var(--dur-2) var(--ease-out), box-shadow var(--dur-2) var(--ease-out), opacity var(--dur-2) var(--ease-out) !important;
}
[class*="st-key-sidebar_expand_btn"] button:hover {
    background: linear-gradient(135deg, rgba(var(--accent-rgb),0.28), rgba(var(--accent-deep-rgb),0.18)) !important;
    border-color: rgba(var(--accent-rgb),0.70) !important;
    color: var(--text-hi) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(var(--accent-rgb),0.30) !important;
}

/* Ocultar el "resize handle" del borde del sidebar: parecía arrastrable pero
   el ancho está fijado, así que confundía. (Refuerzo por JS en inject_protection
   que oculta cualquier elemento con cursor de redimensionar.) */
[data-testid="stSidebar"] [class*="e6f82ta3"] {
    display: none !important;
}

/* ═══════════════════════════════════════════════════════════════════════
   CAPA DE MOVIMIENTO Y LECTURA — cierre del sistema
   ═══════════════════════════════════════════════════════════════════════ */

/* Iconos-emoji de cards especiales: fuera (identidad tipográfica) */
.asymmetry-icon, .veto-icon { display: none; }

/* ── Signal card: agrupa pros o contras en UNA tarjeta ─────────────────
   Fondo un paso por encima del resto + sombra útil + filo semántico arriba. */
.signal-card {
    background: var(--surface-2);
    border: 1px solid var(--hairline);
    border-radius: var(--r-md);
    padding: 14px 18px 8px 18px;
    margin: 8px 0 4px 0;
    box-shadow: var(--inset-hi), var(--shadow-2);
    animation: fadeInUp var(--dur-3) var(--ease-out) both;
    height: 100%;
}

.signal-card--pos { border-top: 2px solid rgba(var(--pos-rgb), 0.55); }
.signal-card--neg { border-top: 2px solid rgba(var(--neg-rgb), 0.55); }

.signal-card .thesis-section-title {
    margin-top: 0;
    border-bottom: 1px solid var(--hairline);
}

/* Dentro de la tarjeta, las filas usan su propio separador */
.signal-card .strength-item, .signal-card .risk-item {
    border-bottom: 1px solid var(--hairline);
}
.signal-card .strength-item:last-child, .signal-card .risk-item:last-child {
    border-bottom: none;
}

/* ── Meter: termómetro rojo→ámbar→verde con dot posicionado ────────────
   Lectura instantánea de qué tan bueno es el dato de la tarjeta. */
.meter {
    position: relative;
    height: 12px;
    display: flex;
    align-items: center;
    margin-top: 10px;
}

.meter::before {
    content: '';
    width: 100%;
    height: 4px;
    border-radius: 99px;
    background: linear-gradient(90deg, var(--neg) 0%, #E5C05C 50%, var(--pos) 100%);
    opacity: 0.55;
}

.meter-dot {
    position: absolute;
    top: 50%;
    width: 11px;
    height: 11px;
    border-radius: 50%;
    transform: translate(-50%, -50%);
    border: 2px solid var(--surface-1);
    transition: left var(--dur-3) var(--ease-out);
}

/* Prosa de análisis: medida legible y aire entre párrafos */
.stMarkdown p { line-height: 1.7; }

/* Los emojis semánticos que llegan como DATO (🔥 INMINENTE) se atenúan */
.kpi-tile-value, .status-pill-value { font-feature-settings: "tnum"; }

/* Streamlit spinner + toast en el idioma del sistema */
[data-testid="stSpinner"] p { color: var(--text-2) !important; font-family: var(--font-mono) !important; font-size: 0.78rem !important; }

/* Tablas HTML inline (insiders, etc.) */
.stMarkdown table { border-collapse: collapse; }
.stMarkdown td, .stMarkdown th { font-variant-numeric: tabular-nums; }

/* Hover solo donde hay puntero real (evita falsos hover en táctil) */
@media (hover: none) {
    .kpi-tile:hover, .status-pill:hover, .ticker-tile:hover { transform: none; }
}

/* Movimiento reducido: se conservan fundidos, se eliminan desplazamientos */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
    }
}

</style>
"""


def get_recommendation_badge(recommendation: str) -> str:
    css_class = {
        # Nombres nuevos en español
        "MUY ATRACTIVO":   "badge-strong-buy",
        "ATRACTIVO":       "badge-buy",
        "EN OBSERVACIÓN":  "badge-watch",
        "EVITAR":          "badge-pass",
        # Backward compat para análisis viejos
        "STRONG BUY":      "badge-strong-buy",
        "BUY":             "badge-buy",
        "WATCH":           "badge-watch",
        "PASS":            "badge-pass",
    }.get(recommendation, "badge-watch")
    return f'<span class="{css_class}">{recommendation}</span>'


def score_color(score: float) -> str:
    if score >= 70:
        return "#3DD68C"
    if score >= 50:
        return "#E2B25C"
    return "#F1495F"


def score_css_class(score: float) -> str:
    if score >= 70:
        return "score-high"
    if score >= 50:
        return "score-medium"
    return "score-low"


# Monogramas tipográficos (renderizados como chip .agent-icon).
# Sustituyen a los emojis: identidad sobria estilo terminal.
AGENT_ICONS = {
    "Fundamentales":     "FN",
    "Técnico":           "TC",
    "Viabilidad Futura": "FU",
    "Smart Money":       "SM",
    "Catalizadores":     "CT",
    "Macro & Sector":    "MC",
    "Sentimiento":       "SN",
    "Contexto de Mercado": "CM",
    "Riesgo & Sizing":   "RS",
    "Orquestador":       "OR",
}
