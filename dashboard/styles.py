"""
DLP Market Analyzer — Bloomberg-grade Dark Theme con animaciones premium.
"""

BLOOMBERG_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Animaciones globales ────────────────────────────────────────────── */
@keyframes pulse-glow {
    0%, 100% { text-shadow: 0 0 20px rgba(255,184,77,0.4), 0 0 40px rgba(255,184,77,0.2); }
    50%      { text-shadow: 0 0 30px rgba(255,184,77,0.7), 0 0 60px rgba(255,184,77,0.4); }
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(20px); }
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
    from { opacity: 0; transform: translateX(20px); }
    to   { opacity: 1; transform: translateX(0); }
}

@keyframes glow-border {
    0%, 100% { box-shadow: 0 0 0 1px rgba(255,184,77,0.3), 0 0 20px rgba(255,184,77,0.1); }
    50%      { box-shadow: 0 0 0 1px rgba(255,184,77,0.6), 0 0 40px rgba(255,184,77,0.25); }
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
    50%  { transform: scale(1.03); }
    100% { transform: scale(1); }
}

/* ── Base ────────────────────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: radial-gradient(ellipse at top, #0F1218 0%, #0A0D11 60%, #06080B 100%) !important;
    color: #E4E7EC !important;
    font-family: 'Inter', sans-serif !important;
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
    background: linear-gradient(180deg, #0A0D11 0%, #0D1117 100%) !important;
    border-right: 1px solid rgba(255,184,77,0.15) !important;
    box-shadow: 4px 0 24px rgba(0,0,0,0.4);
}

[data-testid="stSidebar"] * {
    color: #C8D0D8 !important;
}

#MainMenu, footer, header, [data-testid="stDecoration"] {
    display: none !important;
}

/* ── Titulares ───────────────────────────────────────────────────────── */
h1, h2, h3 { font-family: 'Inter', sans-serif !important; }
h1 { color: #FFFFFF !important; letter-spacing: -0.5px; }
h2 { color: #E4E7EC !important; font-weight: 600 !important; }
h3 { color: #C8D0D8 !important; font-weight: 500 !important; }

/* ── HERO SECTION ───────────────────────────────────────────────────── */
.alpha-hero {
    text-align: center;
    padding: 50px 20px 40px;
    animation: fadeInUp 0.8s ease-out;
}

.alpha-hero-brand {
    font-family: 'JetBrains Mono', monospace;
    font-size: 4.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, #FFB84D 0%, #FFD740 50%, #FFA500 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 0.05em;
    animation: pulse-glow 4s ease-in-out infinite;
    margin: 0;
    line-height: 1;
}

.alpha-hero-tagline {
    font-family: 'Inter', sans-serif;
    font-size: 1rem;
    color: #7A8898;
    margin-top: 16px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    font-weight: 400;
}

.alpha-hero-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    color: #5A6878;
    margin-top: 8px;
    font-style: italic;
}

.alpha-divider {
    width: 100px;
    height: 1px;
    background: linear-gradient(90deg, transparent, #FFB84D, transparent);
    margin: 30px auto;
}

/* ── ACTION CARD: la columna CENTRAL del welcome se convierte en card ── */
/* Detectamos la columna por el placeholder único del input hero */
[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) {
    background: linear-gradient(135deg, rgba(15,20,25,0.95), rgba(20,28,38,0.95)) !important;
    border: 1px solid rgba(255,184,77,0.22) !important;
    border-radius: 16px !important;
    padding: 28px 34px !important;
    box-shadow: 0 8px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,184,77,0.05) !important;
    animation: fadeInUp 1s ease-out 0.2s both, glow-border 6s ease-in-out infinite 1s !important;
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
    animation: anim-shineAlongBorder 5.5s linear infinite;
    pointer-events: none;
    z-index: 2;
}

/* Label de la action card */
.action-label-new {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: #7A8898;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    margin-bottom: 14px;
    text-align: center;
    display: block;
}

/* Input dentro de la action card */
[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stTextInput"] input {
    background: rgba(10,13,17,0.8) !important;
    border: 1px solid rgba(255,184,77,0.3) !important;
    color: #FFFFFF !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 10px !important;
    font-size: 1.15rem !important;
    font-weight: 600 !important;
    padding: 16px 20px !important;
    letter-spacing: 0.05em !important;
    text-align: center !important;
    transition: all 0.3s cubic-bezier(0.4,0,0.2,1) !important;
}

[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stTextInput"] input:focus {
    border-color: #FFB84D !important;
    background: rgba(15,20,25,1) !important;
    box-shadow: 0 0 0 3px rgba(255,184,77,0.15), 0 0 24px rgba(255,184,77,0.12) !important;
    outline: none !important;
}

[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stTextInput"] input::placeholder {
    color: #5A6878 !important;
    font-weight: 400 !important;
    text-transform: none !important;
    letter-spacing: 0.03em !important;
}

/* Botón primario (Análisis y Escanear) dorado — padding compacto SIEMPRE
   (no en media query) para que "ESCANEAR EL MERCADO" quepa en iframe
   cuadrado de Whop sin importar viewport. */
[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #FFB84D 0%, #FFA500 100%) !important;
    border: none !important;
    color: #0A0D11 !important;
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
    transition: all 0.3s cubic-bezier(0.4,0,0.2,1) !important;
    box-shadow: 0 4px 20px rgba(255,184,77,0.3), inset 0 1px 0 rgba(255,255,255,0.2) !important;
}

[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 30px rgba(255,184,77,0.5), inset 0 1px 0 rgba(255,255,255,0.3) !important;
    background: linear-gradient(135deg, #FFD740 0%, #FFB84D 100%) !important;
    color: #0A0D11 !important;
}

/* Botón secundario (Scan) azul */
[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stButton"] > button[kind="secondary"] {
    background: linear-gradient(135deg, rgba(74,158,255,0.15) 0%, rgba(74,158,255,0.05) 100%) !important;
    border: 1px solid rgba(74,158,255,0.4) !important;
    color: #4A9EFF !important;
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
    box-shadow: 0 4px 20px rgba(74,158,255,0.15) !important;
    transition: all 0.3s cubic-bezier(0.4,0,0.2,1) !important;
}

[data-testid="stColumn"]:has(input[placeholder*="introduce un ticker"]) [data-testid="stButton"] > button[kind="secondary"]:hover {
    background: linear-gradient(135deg, rgba(74,158,255,0.25) 0%, rgba(74,158,255,0.1) 100%) !important;
    border-color: #4A9EFF !important;
    box-shadow: 0 8px 30px rgba(74,158,255,0.3) !important;
    color: #4A9EFF !important;
    transform: translateY(-2px) !important;
}

/* ── Sección genérica de header ─────────────────────────────────────── */
.section-header {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    color: #7A8898;
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
    background: linear-gradient(90deg, transparent, rgba(255,184,77,0.3));
}

.section-header::before { left: calc(50% - 180px); transform: scaleX(-1); }
.section-header::after  { right: calc(50% - 180px); }

/* ── Ticker tiles: card visual arriba + botón ▾ pegado abajo ──────── */
.ticker-tile {
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%);
    border: 1px solid rgba(255,184,77,0.12);
    border-bottom: none;
    border-radius: 12px 12px 0 0;
    padding: 14px 10px 12px 10px;
    text-align: center;
    height: 95px;
    transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    animation: fadeInUp 0.6s ease-out both;
    position: relative;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 4px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.2);
}

.tt-symbol {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: 0.06em;
    line-height: 1.15;
}

.tt-price {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.86rem;
    color: #C8D0D8;
    font-weight: 500;
    line-height: 1.15;
}

.tt-change {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    font-weight: 700;
    line-height: 1.15;
    letter-spacing: 0.02em;
}

/* Botón ▾ pequeño debajo de la card — pegado visualmente */
[data-testid="stColumn"]:has(.ticker-tile) [data-testid="stButton"] {
    margin-top: -6px !important;
}

[data-testid="stColumn"]:has(.ticker-tile) [data-testid="stButton"] > button {
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%) !important;
    border: 1px solid rgba(255,184,77,0.12) !important;
    border-top: 1px dashed rgba(255,184,77,0.22) !important;
    border-radius: 0 0 12px 12px !important;
    color: rgba(255,184,77,0.7) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    padding: 3px 0 5px 0 !important;
    height: 26px !important;
    width: 100% !important;
    line-height: 1 !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
    transition: all 0.25s cubic-bezier(0.4,0,0.2,1) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
}

[data-testid="stColumn"]:has(.ticker-tile) [data-testid="stButton"] > button:hover {
    background: linear-gradient(135deg, rgba(255,184,77,0.18) 0%, rgba(255,184,77,0.08) 100%) !important;
    border-color: rgba(255,184,77,0.45) !important;
    color: #FFD740 !important;
    transform: none !important;
    box-shadow: 0 6px 20px rgba(255,184,77,0.15) !important;
}

/* Cuando el botón ▾ es hovereado, también resaltar la card pegada arriba */
[data-testid="stColumn"]:has([data-testid="stButton"]:hover) .ticker-tile {
    border-color: rgba(255,184,77,0.45);
    background: linear-gradient(135deg, #131922 0%, #1A2030 100%);
}

/* ── Live Market Pulse Card ──────────────────────────────────────────── */
.market-pulse-card {
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%);
    border: 1px solid rgba(255,184,77,0.1);
    border-radius: 8px;
    padding: 12px 10px;
    text-align: center;
    transition: all 0.3s;
    animation: fadeInUp 0.6s ease-out both;
    /* Garantizar que el contenido no desborde la card */
    overflow: hidden;
    min-width: 0;
}

.market-pulse-card:hover {
    border-color: rgba(255,184,77,0.3);
    transform: translateY(-2px);
}

.pulse-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: #7A8898;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 4px;
}

.pulse-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem;
    font-weight: 700;
    color: #FFFFFF;
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
    padding: 16px 0 24px;
    border-bottom: 1px solid rgba(255,184,77,0.15);
    margin-bottom: 16px;
}

.sidebar-brand-logo {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, #FFB84D, #FFA500);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.sidebar-brand-sub {
    font-size: 0.6rem;
    color: #5A6878;
    letter-spacing: 0.15em;
    margin-top: 4px;
}

.sidebar-section {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #7A8898;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    padding: 16px 0 8px 0;
    margin-bottom: 4px;
}

/* Watchlist item */
[data-testid="stSidebar"] [data-testid="stButton"] > button {
    background: rgba(15,20,25,0.6) !important;
    border: 1px solid rgba(30,37,48,0.6) !important;
    color: #E4E7EC !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
    text-transform: none !important;
    letter-spacing: 0 !important;
    border-radius: 6px !important;
    padding: 8px 12px !important;
    transition: all 0.2s !important;
    text-align: left !important;
    box-shadow: none !important;
}

[data-testid="stSidebar"] [data-testid="stButton"] > button:hover {
    background: rgba(255,184,77,0.1) !important;
    border-color: rgba(255,184,77,0.4) !important;
    color: #FFB84D !important;
    box-shadow: none !important;
    transform: none !important;
}

/* ── Métricas (default Streamlit) ────────────────────────────────────── */
[data-testid="stMetricValue"] {
    color: #00FF88 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.4rem !important;
    font-weight: 700 !important;
}

[data-testid="stMetricLabel"] {
    color: #7A8898 !important;
    font-size: 0.7rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}

[data-testid="stMetricDelta"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
}

/* ── Cards de análisis ──────────────────────────────────────────────── */
.analysis-card {
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%);
    border: 1px solid rgba(255,184,77,0.15);
    border-left: 3px solid #FFB84D;
    border-radius: 8px;
    padding: 20px 24px;
    margin: 12px 0;
    font-size: 0.9rem;
    line-height: 1.7;
    animation: fadeIn 0.4s ease-out;
    box-shadow: 0 4px 16px rgba(0,0,0,0.2);
}

.analysis-text { font-size: 0.9rem; line-height: 1.75; color: #C8D0D8; }

/* ── Score Badges ────────────────────────────────────────────────────── */
.badge-strong-buy, .badge-buy, .badge-watch, .badge-pass {
    padding: 6px 16px;
    border-radius: 6px;
    font-weight: 800;
    font-size: 0.78rem;
    letter-spacing: 0.1em;
    display: inline-block;
    font-family: 'Inter', sans-serif;
    text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}

.badge-strong-buy {
    background: linear-gradient(135deg, #00C853, #00E676);
    color: #001A06 !important;
    box-shadow: 0 4px 20px rgba(0,200,83,0.3);
}
.badge-buy {
    background: linear-gradient(135deg, #1565C0, #2196F3);
    color: #FFFFFF !important;
    box-shadow: 0 4px 20px rgba(33,150,243,0.3);
}
.badge-watch {
    background: linear-gradient(135deg, #E65100, #FF9100);
    color: #FFFFFF !important;
    box-shadow: 0 4px 20px rgba(255,145,0,0.3);
}
.badge-pass {
    background: linear-gradient(135deg, #B71C1C, #E53935);
    color: #FFFFFF !important;
    box-shadow: 0 4px 20px rgba(229,57,53,0.3);
}

/* ── Tabs ────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] > div:first-child {
    border-bottom: 1px solid rgba(255,184,77,0.15) !important;
    background: transparent !important;
    gap: 4px !important;
}

button[data-baseweb="tab"] {
    color: #7A8898 !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    padding: 10px 16px !important;
    border-bottom: 2px solid transparent !important;
    transition: all 0.25s cubic-bezier(0.4,0,0.2,1) !important;
    border-radius: 6px 6px 0 0 !important;
}

button[data-baseweb="tab"][aria-selected="true"] {
    color: #FFB84D !important;
    border-bottom-color: #FFB84D !important;
    background: rgba(255,184,77,0.05) !important;
}

button[data-baseweb="tab"]:hover {
    color: #E4E7EC !important;
    background: rgba(255,184,77,0.04) !important;
}

/* ── Input genérico ────────────────────────────────────────────────── */
[data-testid="stTextInput"] input {
    background: #0F1419 !important;
    border: 1px solid #1E2530 !important;
    color: #E4E7EC !important;
    font-family: 'JetBrains Mono', monospace !important;
    border-radius: 6px !important;
}

[data-testid="stTextInput"] input:focus {
    border-color: #FFB84D !important;
    box-shadow: 0 0 0 2px rgba(255,184,77,0.15) !important;
}

/* ── Botones genéricos (fuera de action-card) ─────────────────────── */
[data-testid="stButton"] > button {
    background: #1A1F28 !important;
    border: 1px solid #2A3545 !important;
    color: #E4E7EC !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
    letter-spacing: 0.05em !important;
    border-radius: 6px !important;
    padding: 8px 16px !important;
    transition: all 0.25s !important;
}

[data-testid="stButton"] > button:hover {
    background: rgba(255,184,77,0.1) !important;
    border-color: #FFB84D !important;
    color: #FFB84D !important;
}

/* ── Progress bar ────────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, #FFB84D, #FFD740) !important;
    border-radius: 4px !important;
    box-shadow: 0 0 10px rgba(255,184,77,0.4);
}

/* ── Divider ─────────────────────────────────────────────────────────── */
hr {
    border-color: rgba(255,184,77,0.1) !important;
    margin: 16px 0 !important;
}

/* ── Expander ────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid rgba(255,184,77,0.1) !important;
    background: #0F1419 !important;
    border-radius: 8px !important;
}

/* ── Scrollbar ───────────────────────────────────────────────────────── */
::-webkit-scrollbar       { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #0A0D11; }
::-webkit-scrollbar-thumb { background: linear-gradient(180deg, #2A3545, #1E2530); border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255,184,77,0.4); }

/* ── Score colors ─────────────────────────────────────────────────── */
.score-high   { color: #00FF88 !important; font-weight: 700; }
.score-medium { color: #FFB84D !important; font-weight: 700; }
.score-low    { color: #FF3B5C !important; font-weight: 700; }

/* ── Top header bar ────────────────────────────────────────────────── */
.terminal-topbar {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 8px 0 14px 0;
    border-bottom: 1px solid rgba(255,184,77,0.15);
    margin-bottom: 8px;
    animation: fadeIn 0.5s ease-out;
}

.terminal-topbar-brand {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.1rem;
    font-weight: 800;
    background: linear-gradient(135deg, #FFB84D, #FFA500);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: 0.08em;
}

.terminal-topbar-sub {
    color: #5A6878;
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.05em;
}

.terminal-topbar-time {
    margin-left: auto;
    color: #7A8898;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    background: rgba(255,184,77,0.05);
    padding: 4px 10px;
    border-radius: 4px;
    border: 1px solid rgba(255,184,77,0.15);
}

/* ── Stock detail header ───────────────────────────────────────────── */
.stock-header {
    display: flex;
    align-items: center;
    gap: 18px;
    padding: 14px 20px;
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%);
    border: 1px solid rgba(255,184,77,0.15);
    border-left: 3px solid #FFB84D;
    border-radius: 10px;
    margin-bottom: 20px;
    animation: fadeInUp 0.5s ease-out;
}

.stock-header-ticker {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.8rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: 0.05em;
}

.stock-header-name {
    font-size: 0.95rem;
    color: #C8D0D8;
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
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%);
    border: 1px solid rgba(255,184,77,0.25);
    border-left: 3px solid #FFB84D;
    border-radius: 12px;
    margin: 10px 0 18px 0;
    animation: fadeInUp 0.4s ease-out;
    box-shadow: 0 4px 24px rgba(0,0,0,0.4);
}

.qv-ticker {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.7rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: 0.04em;
}

.qv-name {
    font-size: 0.92rem;
    color: #C8D0D8;
    font-weight: 500;
}

.qv-price {
    margin-left: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.5rem;
    font-weight: 800;
    color: #FFB84D;
}

.qv-change {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.95rem;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 6px;
    background: rgba(255,184,77,0.05);
}

.qv-section-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: #7A8898;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid rgba(255,184,77,0.12);
}

/* Métricas clave */
.qv-metric {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 7px 10px;
    border-bottom: 1px solid rgba(30,37,48,0.6);
    transition: background 0.2s;
}

.qv-metric:hover {
    background: rgba(255,184,77,0.04);
}

.qv-metric-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    color: #7A8898;
}

.qv-metric-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.92rem;
    font-weight: 700;
}

/* Performance tiles */
.qv-perf-tile {
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%);
    border: 1px solid rgba(255,184,77,0.1);
    border-radius: 8px;
    padding: 12px 8px;
    text-align: center;
    transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
    animation: fadeInUp 0.4s ease-out both;
}

.qv-perf-tile:hover {
    border-color: rgba(255,184,77,0.3);
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.3);
}

.qv-perf-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #7A8898;
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
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%);
    border: 1px solid rgba(30,37,48,0.6);
    border-left: 2px solid rgba(255,184,77,0.4);
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 6px;
    transition: all 0.2s cubic-bezier(0.4,0,0.2,1);
    cursor: pointer;
}

.qv-news-item:hover {
    background: linear-gradient(135deg, #141A24 0%, #181F2A 100%);
    border-left-width: 3px;
    border-left-color: #FFB84D;
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
    color: #FFB84D;
    font-weight: 700;
    padding: 1px 6px;
    border: 1px solid rgba(255,184,77,0.3);
    border-radius: 3px;
}

.qv-news-publisher {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #7A8898;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}

.qv-news-title {
    font-size: 0.85rem;
    color: #E4E7EC;
    line-height: 1.45;
    font-weight: 500;
}

/* Contexto */
.qv-context-item {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 7px 10px;
    border-bottom: 1px solid rgba(30,37,48,0.6);
    gap: 12px;
}

.qv-context-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    color: #7A8898;
    flex-shrink: 0;
}

.qv-context-value {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.78rem;
    color: #E4E7EC;
    font-weight: 600;
    text-align: right;
    word-break: break-word;
}

.qv-empty {
    color: #5A6878;
    font-style: italic;
    text-align: center;
    padding: 20px;
    font-size: 0.85rem;
}

/* Botón CTA grande de análisis profundo */
[data-testid="stButton"]:has(button[key*="qv_full_analysis"]) > button,
.element-container:has(button:contains("EJECUTAR ANÁLISIS")) > button {
    background: linear-gradient(135deg, #FFB84D 0%, #FFA500 100%) !important;
    border: none !important;
    color: #0A0D11 !important;
    font-weight: 800 !important;
    font-size: 0.95rem !important;
    letter-spacing: 0.1em !important;
    padding: 18px 32px !important;
    height: auto !important;
    border-radius: 12px !important;
    box-shadow: 0 8px 32px rgba(255,184,77,0.35), inset 0 1px 0 rgba(255,255,255,0.3) !important;
    transition: all 0.3s !important;
    animation: glow-border 4s ease-in-out infinite;
}

/* Back button */
[data-testid="stButton"] > button:has(span:contains("← Volver")) {
    background: rgba(15,20,25,0.6) !important;
    border: 1px solid rgba(255,184,77,0.2) !important;
    color: #C8D0D8 !important;
}

/* ─────────────────────────────────────────────────────────────────────
   OVERVIEW PREMIUM: KPI tiles, tooltips, strength/risk, alpha, vetos
   ───────────────────────────────────────────────────────────────────── */

/* ── KPI Section title ──────────────────────────────────────── */
.kpi-section-title {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #7A8898;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    margin: 20px 0 10px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,184,77,0.18);
}

/* ── KPI Tile (cada métrica clave) ──────────────────────────── */
.kpi-tile {
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%);
    border: 1px solid rgba(255,184,77,0.12);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 8px;
    min-height: 100px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    position: relative;
    overflow: visible;
    animation: fadeInUp 0.4s ease-out both;
}

.kpi-tile:hover {
    border-color: rgba(255,184,77,0.35);
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}

.kpi-tile-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 8px;
}

.kpi-tile-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.74rem;
    color: #C8D0D8;
    font-weight: 500;
    letter-spacing: 0.02em;
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
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.35rem;
    font-weight: 800;
    line-height: 1.15;
    letter-spacing: 0.02em;
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
    background: rgba(255,184,77,0.08);
    border: 1px solid rgba(255,184,77,0.3);
    color: #FFB84D;
    font-size: 0.72rem;
    font-weight: 800;
    font-family: 'Inter', sans-serif;
    cursor: help;
    position: relative;
    transition: all 0.2s;
    flex-shrink: 0;
}

.kpi-help:hover {
    background: rgba(255,184,77,0.2);
    border-color: #FFB84D;
    color: #FFD740;
    transform: scale(1.1);
}

.kpi-help::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: calc(100% + 10px);
    right: -8px;
    background: linear-gradient(135deg, #131922 0%, #1A1F28 100%);
    color: #E4E7EC;
    padding: 12px 14px;
    border-radius: 8px;
    border: 1px solid rgba(255,184,77,0.35);
    border-bottom: 2px solid #FFB84D;
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
    box-shadow: 0 12px 32px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,184,77,0.1);
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
    background: #1A1F28;
    border-right: 1px solid rgba(255,184,77,0.35);
    border-bottom: 2px solid #FFB84D;
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
    background: linear-gradient(135deg, rgba(255,59,92,0.15) 0%, rgba(255,59,92,0.04) 100%);
    border: 1px solid rgba(255,59,92,0.35);
    border-left: 4px solid #FF3B5C;
    border-radius: 8px;
    animation: fadeInUp 0.4s ease-out;
}

.veto-icon { font-size: 1.15rem; }

.veto-title {
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    font-weight: 800;
    color: #FF3B5C;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.veto-item {
    background: rgba(255,59,92,0.06);
    border: 1px solid rgba(255,59,92,0.18);
    border-left: 3px solid #FF3B5C;
    border-radius: 0 6px 6px 0;
    padding: 10px 14px;
    margin-bottom: 6px;
    font-size: 0.83rem;
    color: #FFD0D8;
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
    color: #00FF88;
    border-bottom: 1px solid rgba(0,255,136,0.3);
}

.thesis-section-title.risk {
    color: #FF3B5C;
    border-bottom: 1px solid rgba(255,59,92,0.3);
}

.strength-item, .risk-item {
    padding: 11px 14px;
    margin-bottom: 8px;
    border-radius: 8px;
    font-size: 0.85rem;
    line-height: 1.55;
    transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
    animation: fadeInUp 0.4s ease-out both;
}

.strength-item {
    background: linear-gradient(135deg, rgba(0,255,136,0.06), rgba(0,255,136,0.02));
    border: 1px solid rgba(0,255,136,0.18);
    border-left: 3px solid #00FF88;
    color: #D4F5E2;
}

.strength-item:hover {
    background: linear-gradient(135deg, rgba(0,255,136,0.1), rgba(0,255,136,0.04));
    border-left-width: 5px;
    transform: translateX(2px);
}

.risk-item {
    background: linear-gradient(135deg, rgba(255,59,92,0.06), rgba(255,59,92,0.02));
    border: 1px solid rgba(255,59,92,0.18);
    border-left: 3px solid #FF3B5C;
    color: #F5D4DC;
}

.risk-item:hover {
    background: linear-gradient(135deg, rgba(255,59,92,0.1), rgba(255,59,92,0.04));
    border-left-width: 5px;
    transform: translateX(2px);
}

/* ── Oportunidad Asimétrica (card premium dorado) ───── */
.alpha-opportunity-card {
    background: linear-gradient(135deg, rgba(255,184,77,0.1) 0%, rgba(255,184,77,0.02) 100%);
    border: 1px solid rgba(255,184,77,0.4);
    border-left: 4px solid #FFB84D;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 20px 0 8px 0;
    box-shadow: 0 4px 24px rgba(255,184,77,0.1);
    animation: fadeInUp 0.5s ease-out;
    position: relative;
    overflow: hidden;
}

.alpha-opportunity-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 100%; height: 1px;
    background: linear-gradient(90deg, transparent, #FFB84D, transparent);
    animation: scan-line 5s linear infinite;
}

.alpha-opportunity-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,184,77,0.2);
}

.alpha-opportunity-icon { font-size: 1.3rem; }

.alpha-opportunity-title {
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
    font-weight: 800;
    color: #FFB84D;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

.alpha-opportunity-body {
    color: #E4E7EC;
    font-size: 0.88rem;
    line-height: 1.65;
    font-weight: 400;
}

/* ─────────────────────────────────────────────────────────────────────
   AGENT TAB DASHBOARDS: header, status pills, insight cards, section bar
   ───────────────────────────────────────────────────────────────────── */

/* ── Agent header (icon + name + score + conviction) ──────── */
.agent-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%);
    border: 1px solid rgba(255,184,77,0.15);
    border-left: 4px solid #FFB84D;
    border-radius: 10px;
    margin: 4px 0 18px 0;
    animation: fadeInUp 0.4s ease-out;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
}

.agent-header-left {
    display: flex;
    align-items: center;
    gap: 12px;
}

.agent-icon { font-size: 1.5rem; }

.agent-name {
    font-family: 'Inter', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    color: #FFFFFF;
    letter-spacing: 0.03em;
}

.agent-header-right {
    display: flex;
    align-items: center;
    gap: 14px;
}

.agent-score {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.7rem;
    font-weight: 800;
    line-height: 1;
}

.agent-score-max {
    font-size: 0.7rem;
    color: #5A6878;
    font-weight: 400;
    margin-left: 2px;
}

.conviction-badge {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    font-weight: 800;
    padding: 5px 12px;
    border: 1px solid;
    border-radius: 6px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

/* ── Section title bar ────────────────────────────────────── */
.section-title-bar {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #7A8898;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    margin: 20px 0 10px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,184,77,0.18);
    animation: fadeIn 0.4s ease-out;
}

/* ── Status pill (visualización rápida de un indicador) ──── */
.status-pill {
    background: linear-gradient(135deg, #0F1419 0%, #131922 100%);
    border: 1px solid rgba(255,184,77,0.12);
    border-radius: 8px;
    padding: 14px 12px;
    text-align: center;
    transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    animation: fadeInUp 0.4s ease-out both;
    min-height: 110px;
    height: 100%;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 6px;
}

.status-pill:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,0.35);
}

.status-pill-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: #7A8898;
    text-transform: uppercase;
    letter-spacing: 0.10em;
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
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.0rem;
    font-weight: 800;
    line-height: 1.2;
    word-break: break-word;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    max-height: 2.6rem;
}

.status-pill-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.68rem;
    color: #7A8898;
    font-style: italic;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* ── Insight card (DCF thesis, key insight, etc.) ───────── */
.insight-card {
    background: linear-gradient(135deg, rgba(255,184,77,0.06), rgba(255,184,77,0.02));
    border: 1px solid rgba(255,184,77,0.18);
    border-left: 4px solid #FFB84D;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 14px 0 8px 0;
    animation: fadeInUp 0.4s ease-out;
    transition: all 0.25s;
}

.insight-card:hover {
    border-left-width: 5px;
    box-shadow: 0 6px 24px rgba(0,0,0,0.3);
}

.insight-card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid rgba(255,184,77,0.15);
}

.insight-card-icon { font-size: 1.2rem; }

.insight-card-title {
    font-family: 'Inter', sans-serif;
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.insight-card-body {
    color: #E4E7EC;
    font-size: 0.87rem;
    line-height: 1.65;
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
    border: 1px solid rgba(255,184,77,0.06);
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
    border-top-color: #FFB84D;
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
    filter: drop-shadow(0 0 16px rgba(255,184,77,0.25));
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
    stroke: #FFB84D;
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
    color: #FFB84D;
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
    stroke: #00FF88;
    filter: drop-shadow(0 0 8px rgba(0, 255, 136, 0.6));
}

.alpha-progress-ring-wrap.complete .alpha-progress-value {
    color: #00FF88;
}

.alpha-spinner-text {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #FFB84D;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    text-align: center;
    font-weight: 600;
}

.alpha-spinner-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.7rem;
    color: #7A8898;
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
    background: linear-gradient(135deg, #FFD740 0%, #FFB84D 50%, #FFA500 100%);
    color: #0A0D11 !important;
    font-family: 'Inter', sans-serif;
    font-size: 0.72rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    border-radius: 6px;
    box-shadow: 0 4px 16px rgba(255,184,77,0.35), inset 0 1px 0 rgba(255,255,255,0.3);
    animation: fade-soft 3s ease-in-out infinite;
}

/* Card "Diagnóstico de Asimetría" — 3 variantes */
.asymmetry-card {
    background: linear-gradient(135deg, rgba(15,20,25,0.95), rgba(20,28,38,0.95));
    border: 1px solid;
    border-left: 4px solid;
    border-radius: 10px;
    padding: 14px 18px;
    margin: 18px 0 8px 0;
    animation: fadeInUp 0.5s ease-out;
    position: relative;
    overflow: hidden;
}

.asymmetry-card.upside {
    border-color: rgba(0,255,136,0.35);
    border-left-color: #00FF88;
    background: linear-gradient(135deg, rgba(0,255,136,0.07), rgba(0,255,136,0.02));
    box-shadow: 0 4px 24px rgba(0,255,136,0.1);
}

.asymmetry-card.downside {
    border-color: rgba(255,59,92,0.35);
    border-left-color: #FF3B5C;
    background: linear-gradient(135deg, rgba(255,59,92,0.07), rgba(255,59,92,0.02));
    box-shadow: 0 4px 24px rgba(255,59,92,0.1);
}

.asymmetry-card.balanced {
    border-color: rgba(74,158,255,0.35);
    border-left-color: #4A9EFF;
    background: linear-gradient(135deg, rgba(74,158,255,0.07), rgba(74,158,255,0.02));
    box-shadow: 0 4px 24px rgba(74,158,255,0.1);
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

.asymmetry-card.upside    .asymmetry-title { color: #00FF88; }
.asymmetry-card.downside  .asymmetry-title { color: #FF3B5C; }
.asymmetry-card.balanced  .asymmetry-title { color: #4A9EFF; }

.asymmetry-strength {
    margin-left: auto;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.68rem;
    color: #7A8898;
    padding: 3px 8px;
    border-radius: 4px;
    background: rgba(0,0,0,0.3);
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

.asymmetry-body {
    color: #E4E7EC;
    font-size: 0.88rem;
    line-height: 1.6;
}

.asymmetry-body .em {
    font-weight: 700;
}

.asymmetry-card.upside   .asymmetry-body .em { color: #00FF88; }
.asymmetry-card.downside .asymmetry-body .em { color: #FF3B5C; }
.asymmetry-card.balanced .asymmetry-body .em { color: #4A9EFF; }


/* ── Markdown ────────────────────────────────────────────────────── */
.stMarkdown p { color: #C8D0D8 !important; font-size: 0.88rem; line-height: 1.7; }
.stMarkdown strong { color: #FFFFFF !important; }
.stMarkdown li { color: #C8D0D8 !important; font-size: 0.88rem; }


/* ══════════════════════════════════════════════════════════════════════
   GLOBAL BUTTON COLOR OVERRIDE — primary brand = orange (no rojo Streamlit)
   ══════════════════════════════════════════════════════════════════════ */

.stApp button[kind="primary"] {
    background: linear-gradient(135deg, #FFB84D 0%, #FF9D2E 100%) !important;
    color: #0A0D11 !important;
    border: 1px solid rgba(255,184,77,0.30) !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 12px rgba(255,184,77,0.18), inset 0 1px 0 rgba(255,255,255,0.18) !important;
    transition: all 0.18s ease !important;
}
.stApp button[kind="primary"]:hover {
    background: linear-gradient(135deg, #FFC865 0%, #FFAA40 100%) !important;
    box-shadow: 0 4px 20px rgba(255,184,77,0.35), inset 0 1px 0 rgba(255,255,255,0.25) !important;
    transform: translateY(-1px);
}
.stApp button[kind="primary"]:focus:not(:active) {
    border-color: rgba(255,184,77,0.55) !important;
    box-shadow: 0 0 0 3px rgba(255,184,77,0.22), 0 4px 20px rgba(255,184,77,0.30) !important;
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
    color: #FFB84D;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    padding: 4px 12px;
    border: 1px solid rgba(255,184,77,0.35);
    border-radius: 20px;
    background: rgba(255,184,77,0.08);
    margin-bottom: 14px;
}

.scanner-hero-title {
    font-family: 'Inter', sans-serif;
    font-size: 2.05rem;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: -0.8px;
    margin-bottom: 12px;
    background: linear-gradient(135deg, #FFFFFF 0%, #FFE3B0 70%, #FFB84D 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.scanner-hero-sub {
    font-family: 'Inter', sans-serif;
    font-size: 0.93rem;
    color: #8A95A4;
    max-width: 600px;
    margin: 0 auto;
    line-height: 1.7;
}

.scanner-section-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent 0%, rgba(255,184,77,0.20) 30%, rgba(255,184,77,0.20) 70%, transparent 100%);
    margin: 24px 0 18px;
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
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
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
    background: var(--accent, #FFB84D);
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
        var(--accent, #FFB84D) 0%,
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
    transition: all 0.25s ease;
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
    color: #FFFFFF;
    letter-spacing: -0.3px;
    line-height: 1.3;
    margin-bottom: 3px;
}

.scanner-card-subtitle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    color: var(--accent, #FFB84D);
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
    transition: all 0.18s ease !important;
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
    background: linear-gradient(135deg, rgba(233,75,123,0.10) 0%, rgba(255,184,77,0.05) 100%) !important;
    border: 1.5px solid rgba(233,75,123,0.38) !important;
    border-left: 4px solid #E94B7B !important;
    border-radius: 14px !important;
    padding: 28px 28px 22px 28px !important;
    margin: 14px 0 28px 0 !important;
    box-shadow: 0 6px 24px rgba(233,75,123,0.14), inset 0 1px 0 rgba(255,255,255,0.04) !important;
    position: relative !important;
    overflow: visible !important;
}

/* Badge flotante "FILTRO PRINCIPAL" arriba a la izquierda */
[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor)::before {
    content: "FILTRO PRINCIPAL";
    position: absolute;
    top: -11px;
    left: 22px;
    background: linear-gradient(135deg, #E94B7B 0%, #FFB84D 100%);
    color: #0A0D11;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.62rem;
    font-weight: 800;
    letter-spacing: 0.14em;
    padding: 4px 12px;
    border-radius: 6px;
    box-shadow: 0 3px 10px rgba(233,75,123,0.40);
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
    border-bottom: 1px solid rgba(233,75,123,0.20);
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
    color: #FFFFFF;
    line-height: 1.1;
    margin-bottom: 4px;
}

.scanner-pri-subtitle {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: #E94B7B;
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
    transition: all 0.20s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) div[data-testid="stButton"] button[kind="secondary"] {
    background: rgba(20,25,32,0.75) !important;
    color: #E4E7EC !important;
    border: 1.5px solid rgba(255,255,255,0.10) !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.18) !important;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) div[data-testid="stButton"] button[kind="secondary"]:hover {
    background: rgba(35,42,54,0.95) !important;
    border-color: rgba(233,75,123,0.55) !important;
    color: #FFFFFF !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(233,75,123,0.22) !important;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) div[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, #E94B7B 0%, #FF7A4C 100%) !important;
    color: #FFFFFF !important;
    border: 1.5px solid rgba(255,255,255,0.18) !important;
    box-shadow: 0 6px 20px rgba(233,75,123,0.40), inset 0 1px 0 rgba(255,255,255,0.20) !important;
    font-weight: 700 !important;
}

[data-testid="stVerticalBlockBorderWrapper"]:has(.scanner-pri-anchor) div[data-testid="stButton"] button[kind="primary"]:hover {
    background: linear-gradient(135deg, #FF5A8A 0%, #FF8A5C 100%) !important;
    box-shadow: 0 8px 26px rgba(233,75,123,0.55), inset 0 1px 0 rgba(255,255,255,0.26) !important;
    transform: translateY(-2px);
}

/* Pills inactivos (kind=secondary) */
.scanner-card-body div[data-testid="stButton"] > button[kind="secondary"] {
    background: rgba(20,25,32,0.6) !important;
    color: #C8D0D8 !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    box-shadow: none !important;
}

.scanner-card-body div[data-testid="stButton"] > button[kind="secondary"]:hover {
    background: rgba(30,37,48,0.85) !important;
    border-color: rgba(255,184,77,0.30) !important;
    color: #FFFFFF !important;
    transform: translateY(-1px);
}

/* Pills activos (kind=primary) — naranja brand */
.scanner-card-body div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #FFB84D 0%, #FF9D2E 100%) !important;
    color: #0A0D11 !important;
    border: 1px solid rgba(255,184,77,0.55) !important;
    box-shadow: 0 4px 14px rgba(255,184,77,0.28), inset 0 1px 0 rgba(255,255,255,0.22) !important;
    font-weight: 700 !important;
}

.scanner-card-body div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #FFC865 0%, #FFAA40 100%) !important;
    box-shadow: 0 6px 22px rgba(255,184,77,0.40), inset 0 1px 0 rgba(255,255,255,0.30) !important;
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
    background: rgba(255,184,77,0.10);
    border: 1px solid rgba(255,184,77,0.30);
    color: #FFB84D;
    font-size: 0.70rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    cursor: help;
    margin-left: auto;
    flex-shrink: 0;
    position: relative;
    transition: all 0.2s ease;
}

.scanner-help:hover {
    background: rgba(255,184,77,0.25);
    border-color: rgba(255,184,77,0.55);
    transform: scale(1.08);
}

.scanner-help::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: calc(100% + 10px);
    right: 0;
    width: 280px;
    background: #0A0D11;
    color: #E4E7EC;
    border: 1px solid rgba(255,184,77,0.45);
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
                0 0 0 1px rgba(255,184,77,0.20);
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
    border: 1px solid rgba(255,184,77,0.18);
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
    color: #8A95A4;
    flex: 1;
}

.scanner-actions-hint strong {
    color: #FFB84D;
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
    0%, 100% { box-shadow: 0 3px 10px rgba(233,75,123,0.32); }
    50%      { box-shadow: 0 4px 18px rgba(233,75,123,0.55); }
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
    box-shadow: 0 0 20px rgba(0,255,136,0.25);
}

/* ── 11. SKELETON shimmer durante carga ───────────────────────────── */
.skeleton-block {
    background: linear-gradient(90deg,
        rgba(30,37,48,0.6) 0%,
        rgba(50,60,75,0.85) 50%,
        rgba(30,37,48,0.6) 100%) !important;
    background-size: 200% 100% !important;
    animation: anim-shimmer 1.6s ease-in-out infinite !important;
}

/* ── 12. PROGRESS RING durante análisis — pulse glow ──────────────── */
.alpha-progress-ring-wrap:not(.complete) .alpha-progress-fg {
    filter: drop-shadow(0 0 6px rgba(255,184,77,0.55));
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

/* ── 19. OCULTAR SIDEBAR Y SU TOGGLE ──────────────────────────────────
   El sidebar lateral apretaba demasiado el contenido en el iframe de
   Whop (que es cuadrado). Lo escondemos completamente y movemos la
   navegación al cuerpo principal (botón "Volver al Home" centrado). */
[data-testid="stSidebar"],
section[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"],
[data-testid="stSidebarUserContent"],
[data-testid="stSidebarHeader"],
button[kind="header"][aria-label*="ide"],
button[kind="header"][aria-label*="iew"] {
    display: none !important;
    width: 0 !important;
    min-width: 0 !important;
    max-width: 0 !important;
    visibility: hidden !important;
    transform: translateX(-9999px) !important;
}

/* Sin gap del sidebar, el main content usa 100% del ancho */
[data-testid="stAppViewContainer"] > section.main,
[data-testid="stMain"],
.main .block-container {
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
    margin-left: 0 !important;
}

/* Botón "Volver al Home" del top nav — sutil pero claro, tema dark */
.st-key-topnav_home_btn button,
[data-testid="stButton"] button[key*="topnav_home"] {
    background: linear-gradient(135deg, rgba(28,34,44,0.85), rgba(15,18,24,0.95)) !important;
    border: 1px solid rgba(255,184,77,0.30) !important;
    color: #FFB84D !important;
    font-weight: 600 !important;
    letter-spacing: 0.08em !important;
    font-size: 0.82rem !important;
    text-transform: uppercase !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    margin-bottom: 14px !important;
    transition: all 0.2s ease !important;
}

.st-key-topnav_home_btn button:hover {
    background: linear-gradient(135deg, rgba(40,48,60,0.95), rgba(20,25,32,1)) !important;
    border-color: rgba(255,184,77,0.55) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px rgba(255,184,77,0.15) !important;
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
    border-bottom: 1px solid #1E2530;
    align-items: start;
}
.overview-info-key {
    color: #7A8898;
    font-size: 0.8rem;
    white-space: nowrap;
}
.overview-info-value {
    color: #E0E0E0;
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
    border-top-color: #FFB84D;
    animation: spin 0.9s linear infinite;
}
.section-spinner-text {
    color: #7A8898;
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
        return "#00FF88"
    if score >= 50:
        return "#FFB84D"
    return "#FF3B5C"


def score_css_class(score: float) -> str:
    if score >= 70:
        return "score-high"
    if score >= 50:
        return "score-medium"
    return "score-low"


AGENT_ICONS = {
    "Fundamentales":     "📊",
    "Técnico":           "📈",
    "Viabilidad Futura": "🔭",
    "Smart Money":       "🏦",
    "Catalizadores":     "⚡",
    "Macro & Sector":    "🌍",
    "Sentimiento":       "📰",
    "Riesgo & Sizing":   "⚖️",
    "Orquestador":       "👔",
}
