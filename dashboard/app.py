"""
DLP Market Analyzer — Bloomberg-style dashboard para el sistema de análisis de mercados.
Punto de entrada principal: streamlit run dashboard/app.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar .env ANTES de cualquier otro import — garantiza ANTHROPIC_API_KEY del .env real
from dotenv import load_dotenv
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

import json
import time
from datetime import datetime
from typing import Optional

import anthropic
import streamlit as st
import streamlit.components.v1 as components

# Tomar la key DIRECTAMENTE de la variable de entorno ya cargada
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
from agents.orchestrator import Orchestrator, StockAnalysis
from agents.screener import ScreenerAgent, ScreenerResult
from dashboard.styles import (
    BLOOMBERG_CSS, get_recommendation_badge, score_color,
    score_css_class, AGENT_ICONS,
)
from dashboard.charts import (
    build_price_chart, build_gauge, build_snowflake,
    build_score_breakdown, build_mini_gauge, build_rr_chart,
    build_sector_heatmap, build_compact_gauge, build_rsi_gauge,
    build_metric_bars, build_earnings_history_chart,
    build_sentiment_gauge, build_holders_bars,
)

# ── Config de página ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="DLP Market Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(BLOOMBERG_CSS, unsafe_allow_html=True)


# ── State inicial ─────────────────────────────────────────────────────────

def init_state():
    from config.settings import SCANNER_DEFAULTS
    # Bump esta versión cuando cambies SCANNER_DEFAULTS, así fuerza el reset
    # del session_state de usuarios con filtros viejos en caché.
    SCANNER_DEFAULTS_VERSION = "v3-2026-06-05"

    defaults = {
        "analyses":            {},     # ticker → StockAnalysis (full)
        "selected_ticker":     None,
        "quick_view_ticker":   None,   # ticker en vista rápida (sin AI)
        "analyzing":           False,
        "scan_results":        [],
        "current_scan_id":     None,   # scan_id actualmente cargado
        "scan_running":        False,
        "client":              None,
        "agent_log":           [],
        # Scanner personalizable
        "scanner_config_open": False,                # mostrar página de configuración
        "scanner_filters":     dict(SCANNER_DEFAULTS),  # selección UI actual
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Si el usuario tiene una versión vieja de filtros en session_state, la
    # forzamos a actualizar a los nuevos defaults. Sin esto, los miembros que
    # ya entraron antes siguen con `rs_strength='fuerte'` y otros viejos
    # restrictivos en caché.
    if st.session_state.get("_scanner_defaults_version") != SCANNER_DEFAULTS_VERSION:
        st.session_state.scanner_filters = dict(SCANNER_DEFAULTS)
        st.session_state._scanner_defaults_version = SCANNER_DEFAULTS_VERSION

    # Helper para validar análisis (tesis real, no fallback)
    def _is_valid_analysis(a):
        return len(getattr(a, "investment_thesis", "") or "") > 200

    # ── Limpiar análisis corruptos de la session_state (en CADA rerun) ──
    bad_tickers = [t for t, a in st.session_state.analyses.items() if not _is_valid_analysis(a)]
    for t in bad_tickers:
        del st.session_state.analyses[t]

    # ── Cargar historial desde disco local ──
    if not st.session_state.get("_history_loaded"):
        try:
            from data.persistence import load_all_analyses as disk_load
            disk_saved = disk_load()
            for ticker, analysis in disk_saved.items():
                if ticker not in st.session_state.analyses and _is_valid_analysis(analysis):
                    st.session_state.analyses[ticker] = analysis
        except Exception:
            pass
        st.session_state._history_loaded = True


init_state()


# ── Protección anti-extracción (cosmética — deterrent contra curiosos) ──
def inject_protection():
    """Inyecta JS que bloquea click derecho, atajos de DevTools, view-source y
    save-page sobre el DOM REAL de la app.

    IMPORTANTE: `st.markdown(unsafe_allow_html=True)` permite HTML pero bloquea
    la ejecución de `<script>` por seguridad. Por eso usamos
    `components.html()`, que ejecuta JS dentro de un iframe sandbox. Desde el
    iframe accedemos a `window.parent.document` (el documento real del app
    Streamlit) y registramos listeners en ÉL — no en el iframe del componente.

    Es una capa DISUASIVA contra usuarios casuales. Un usuario técnico puede
    abrir DevTools desde el menú del navegador. Para bloqueo real, usar
    verificación de Referer en el servidor al desplegar."""
    components.html("""
    <script>
    (function() {
        // Acceder al DOM real del app Streamlit, no al del componente.
        const doc = (window.parent && window.parent.document) || document;

        // Idempotente: si ya inyectamos antes en este documento, no repetir.
        if (doc.__dlp_protected) return;
        doc.__dlp_protected = true;

        // 1. Click derecho → bloqueado
        doc.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            e.stopPropagation();
            return false;
        }, true);

        // 2. Atajos: F12, Ctrl/Cmd+Shift+I/J/C, Ctrl/Cmd+U, Ctrl/Cmd+S
        doc.addEventListener('keydown', function(e) {
            const k = (e.key || '').toLowerCase();
            const blocked =
                e.key === 'F12' ||
                ((e.ctrlKey || e.metaKey) && e.shiftKey && (k === 'i' || k === 'j' || k === 'c')) ||
                (e.metaKey && e.altKey && (k === 'i' || k === 'j' || k === 'c')) ||
                ((e.ctrlKey || e.metaKey) && (k === 'u' || k === 's'));
            if (blocked) {
                e.preventDefault();
                e.stopPropagation();
                return false;
            }
        }, true);

        // 3. Drag (arrastrar elementos / links / imágenes)
        doc.addEventListener('dragstart', function(e) {
            e.preventDefault();
            return false;
        }, true);

        // 4. También sobre el window propio del componente, por si se hace
        // foco dentro del iframe (raro pero pasa con widgets nativos).
        document.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            return false;
        }, true);

        // 5. Eliminar branding de Streamlit Cloud — selectores agresivos.
        const HIDE_SELECTORS = [
            '[class*="viewerBadge"]', '[class*="ViewerBadge"]',
            '[class*="appViewerBadge"]', '[class*="stAppViewerBadge"]',
            '[data-testid*="viewerBadge"]', '[data-testid="stAppViewerBadge"]',
            '[data-testid="stToolbar"]', '[data-testid="stToolbarActions"]',
            '[data-testid="stStatusWidget"]', '[data-testid="stDecoration"]',
            '[data-testid="stHeader"]', '[data-testid="stAppDeployButton"]',
            '[data-testid="stDeployButton"]', 'header[data-testid="stHeader"]',
            'button[title="View fullscreen"]', 'button[title*="ullscreen"]',
            'button[aria-label*="ullscreen"]',
            '#MainMenu', '.stDeployButton', '.stAppDeployButton',
            'a[href*="streamlit.io"]', 'a[href*="share.streamlit.io"]',
            'footer.streamlit-footer', '.stApp > footer', '.stAppFooter',
        ];

        // Búsqueda por TEXTO — el método más robusto porque NO depende de
        // class names que Streamlit puede cambiar. Si encontramos un elemento
        // con texto "Built with Streamlit" o "Fullscreen", lo borramos junto
        // con sus 3 contenedores padres más cercanos.
        function removeByText(root) {
            try {
                var nodes = root.querySelectorAll('a, button, div, span, p, footer');
                var patterns = ['built with streamlit', 'made with streamlit', 'fullscreen'];
                for (var i = 0; i < nodes.length; i++) {
                    var el = nodes[i];
                    var txt = ((el.textContent || '') + '').trim().toLowerCase();
                    if (!txt || txt.length > 100) continue;  // skip vacío o muy largo
                    for (var p = 0; p < patterns.length; p++) {
                        if (txt === patterns[p] ||
                            (txt.length < 50 && txt.indexOf(patterns[p]) !== -1)) {
                            var target = el;
                            for (var k = 0; k < 3 && target.parentElement &&
                                 target.parentElement.tagName !== 'BODY' &&
                                 target.parentElement.tagName !== 'HTML'; k++) {
                                target = target.parentElement;
                            }
                            try { target.remove(); } catch (e) {}
                            break;
                        }
                    }
                }
            } catch (e) {}
        }

        function nukeBranding(root) {
            if (!root) return;
            // Por selectores conocidos
            try {
                HIDE_SELECTORS.forEach(function(sel) {
                    var nodes = root.querySelectorAll(sel);
                    for (var i = 0; i < nodes.length; i++) {
                        try {
                            nodes[i].style.display = 'none';
                            nodes[i].remove();
                        } catch (e) {}
                    }
                });
            } catch (e) {}
            // Por texto (catch-all)
            removeByText(root);
        }

        // Nukear en todos los documentos accesibles: el propio y window.top
        function nukeEverywhere() {
            nukeBranding(doc);
            try { if (window.top && window.top.document) nukeBranding(window.top.document); } catch (e) {}
            try { if (window.parent && window.parent.document) nukeBranding(window.parent.document); } catch (e) {}
        }

        nukeEverywhere();
        try {
            var observer = new MutationObserver(nukeEverywhere);
            observer.observe(doc.body || doc.documentElement, {
                childList: true, subtree: true, attributes: false
            });
        } catch (e) {}
        // Limpieza periódica MUY frecuente (cada 250ms) — garantiza que aunque
        // Streamlit reinyecte el badge tras un rerun, lo borramos en <500ms.
        setInterval(nukeEverywhere, 250);
    })();
    </script>
    """, height=0, width=0)


inject_protection()


# ── Anthropic Client ──────────────────────────────────────────────────────
def get_client() -> anthropic.Anthropic:
    # Recrear el cliente si la key cambió o si era inválido — no cachear clientes con keys malas
    current_key = ANTHROPIC_API_KEY
    cached_key = st.session_state.get("_cached_api_key")
    if st.session_state.client is None or cached_key != current_key:
        _debug_log(f"get_client: key prefix={current_key[:15] if current_key else 'EMPTY'}, len={len(current_key)}")
        if not current_key or len(current_key) < 50:
            st.error("⚠️ ANTHROPIC_API_KEY no configurada o inválida. Verifica el archivo .env")
            st.stop()
        st.session_state.client = anthropic.Anthropic(api_key=current_key)
        st.session_state._cached_api_key = current_key
    return st.session_state.client


# ── Header ────────────────────────────────────────────────────────────────
def render_header():
    st.markdown(f"""
    <div class="terminal-topbar">
        <span class="terminal-topbar-brand">◈ DLP MARKET ANALYZER</span>
        <span class="terminal-topbar-time">{datetime.now().strftime("%Y-%m-%d · %H:%M")}</span>
    </div>
    """, unsafe_allow_html=True)


# ── Sidebar: Brand + Watchlist ────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        # Brand
        st.markdown("""
        <div class="sidebar-brand">
            <div class="sidebar-brand-logo">◈ DLP</div>
            <div class="sidebar-brand-sub">MARKET ANALYZER</div>
        </div>
        """, unsafe_allow_html=True)

        # Reset / Home button
        if st.button("⌂  Home", use_container_width=True, key="sidebar_home"):
            st.session_state.selected_ticker = None
            st.session_state.quick_view_ticker = None
            st.session_state.scan_results = []
            st.session_state.current_scan_id = None
            st.session_state._show_scan_results = False
            st.rerun()

        # Watchlist e Historial de Scans eliminados — el usuario no los necesita.
        # Los análisis siguen guardándose en disco (data/persistence.py) por si
        # en el futuro queremos recuperarlos, pero no se muestran en el sidebar.


def render_top_nav():
    """Barra superior compacta con un botón Home centrado. Reemplaza al
    sidebar lateral en producción (Whop iframe es cuadrado — el sidebar
    apretaba demasiado el contenido). Solo se muestra en vistas NO-welcome."""
    col_a, col_home, col_c = st.columns([1, 2, 1])
    with col_home:
        if st.button("⌂  Volver al Home", use_container_width=True,
                     key="topnav_home_btn"):
            st.session_state.selected_ticker = None
            st.session_state.quick_view_ticker = None
            st.session_state.scan_results = []
            st.session_state.current_scan_id = None
            st.session_state._show_scan_results = False
            st.session_state.scanner_config_open = False
            st.rerun()


# ── Run Analysis ──────────────────────────────────────────────────────────
def _debug_log(msg: str) -> None:
    """Escribe a /tmp/dlp_debug.log con timestamp para depurar el flujo real."""
    try:
        with open("/tmp/dlp_debug.log", "a") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] {msg}\n")
    except Exception:
        pass


def run_analysis(ticker: str):
    import threading as _threading
    from data.persistence import save_analysis as disk_save

    _debug_log(f"run_analysis CALLED for ticker={ticker!r}")

    existing = st.session_state.analyses.get(ticker)
    if existing is not None:
        # Solo usar caché si la tesis es real (>300 chars) — si es fallback, re-analizar
        thesis_len = len(getattr(existing, "investment_thesis", "") or "")
        _debug_log(f"  cache hit, thesis_len={thesis_len}")
        if thesis_len > 200:
            _debug_log(f"  using cached analysis, rerunning")
            st.session_state.selected_ticker = ticker
            st.session_state.quick_view_ticker = None
            st.rerun()
            return
        else:
            del st.session_state.analyses[ticker]
            _debug_log(f"  deleted bad cache")

    # ── Caché COMPARTIDO (Upstash) — si OTRO usuario ya analizó este ticker en
    # los últimos 30 días, reutilizamos su análisis sin gastar créditos. Las
    # gráficas, precio, P/E e indicadores se refrescan en vivo al renderizar.
    # Es no-op si no hay credenciales de Upstash (vuelve al comportamiento de hoy).
    try:
        from data.cache_store import get_cached_analysis
        shared = get_cached_analysis(ticker)
    except Exception:
        shared = None
    if shared is not None:
        _debug_log(f"  shared cache HIT for {ticker}")
        st.session_state.analyses[ticker] = shared
        st.session_state.selected_ticker = ticker
        st.session_state.quick_view_ticker = None
        st.rerun()
        return

    st.session_state.analyzing = True
    st.session_state.selected_ticker = ticker

    client = get_client()
    orchestrator = Orchestrator(client)

    loading_placeholder = st.empty()
    status_container = st.empty()

    # 6 agentes × 2 eventos (Analizando + Completado) = 12 ticks + Orquestador = 13
    # (5 individuales + 1 combinado "Contexto de Mercado" que cubre macro+sent+catal)
    TOTAL_TICKS = 13
    progress_count = [0.0]
    current_agent = [""]
    synthesis_started = [False]

    def _render_frame(smooth_pct: float):
        agent_label = current_agent[0] or "Iniciando agentes…"
        loading_placeholder.markdown(
            _skeleton_analysis_full_html() + _spinner_overlay_html(
                text=f"ANÁLISIS DLP · {ticker}",
                sub=agent_label,
                progress=smooth_pct,
            ),
            unsafe_allow_html=True,
        )

    def progress_callback(agent_name: str, status: str):
        # Solo actualiza estado compartido — sin llamadas Streamlit desde hilos de fondo
        if agent_name == "Orquestador":
            synthesis_started[0] = True
            progress_count[0] = max(progress_count[0], TOTAL_TICKS - 1)
        elif "Analizando" in status:
            progress_count[0] += 0.5
        elif "Completado" in status or "Error" in status:
            progress_count[0] += 0.5
        current_agent[0] = f"{AGENT_ICONS.get(agent_name, '🔄')} {agent_name}"

    # Lanzar el análisis en un hilo de fondo
    analysis_result = [None]
    analysis_error = [None]
    analysis_done = [False]

    def _run_bg():
        _debug_log(f"  [bg thread] STARTED for {ticker}")
        try:
            analysis_result[0] = orchestrator.analyze(ticker, progress_callback=progress_callback)
            _debug_log(f"  [bg thread] orchestrator.analyze RETURNED for {ticker}")
        except Exception as e:
            import traceback as _tb
            analysis_error[0] = e
            _debug_log(f"  [bg thread] EXCEPTION: {type(e).__name__}: {e}")
            _debug_log(f"  [bg thread] TRACEBACK:\n{_tb.format_exc()}")
        finally:
            analysis_done[0] = True
            _debug_log(f"  [bg thread] DONE flag set")

    _debug_log(f"  starting bg thread")
    bg_thread = _threading.Thread(target=_run_bg, daemon=True)
    bg_thread.start()

    # Bucle principal: actualiza el UI desde el hilo principal cada 200ms
    # smooth_pct avanza continuamente (nunca retrocede) para que la barra
    # se vea siempre en movimiento — los callbacks de agentes aceleran el avance.
    smooth_pct = [0.0]
    _render_frame(0.0)

    while not analysis_done[0]:
        time.sleep(0.2)
        real_pct = min((progress_count[0] / TOTAL_TICKS) * 100, 93.0)
        if synthesis_started[0]:
            real_pct = max(real_pct, 92.0)
        # Avanza al menos 0.4% por ciclo (≈2%/s base) + salta al progreso real si está más adelante
        smooth_pct[0] = min(smooth_pct[0] + 0.4, real_pct + 3.0, 95.0)
        _render_frame(smooth_pct[0])

    if analysis_error[0]:
        _debug_log(f"  ERROR detected in main thread: {analysis_error[0]}")
        try:
            loading_placeholder.empty()
        except Exception:
            pass
        st.error(f"Error analizando {ticker}: {analysis_error[0]}")
        st.session_state.analyzing = False
        return

    _debug_log(f"  bg thread done, result type={type(analysis_result[0]).__name__}")

    # Limpiar el loading INMEDIATAMENTE — sin sleep artificial.
    # El usuario percibe la transición como instantánea en vez de los
    # ~450ms de "tiempo muerto" que tenía antes.
    try:
        loading_placeholder.empty()
        status_container.empty()
    except Exception:
        pass

    analysis = analysis_result[0]
    st.session_state.analyses[ticker] = analysis
    st.session_state.selected_ticker = ticker
    st.session_state.quick_view_ticker = None
    st.session_state.analyzing = False

    # Guardar a disco en background — no bloqueamos el rerun por IO.
    # El usuario ve el análisis listo en vez de esperar a que termine
    # el write a disco (que puede tardar 100-300ms).
    thesis_ok = len(getattr(analysis, "investment_thesis", "") or "") > 200
    if thesis_ok:
        def _save_bg():
            # Guardar a disco local (siempre)
            try:
                disk_save(analysis)
            except Exception:
                pass
            # Guardar al caché compartido Upstash (no-op si no hay credenciales).
            # Así el próximo usuario que pida este ticker en 30 días lo reutiliza.
            try:
                from data.cache_store import save_cached_analysis
                save_cached_analysis(ticker, analysis)
            except Exception:
                pass
        _threading.Thread(target=_save_bg, daemon=True).start()

    # Marcar el timestamp para activar el cooldown de 10 min de la sesión.
    # Solo se registra cuando un análisis NUEVO se completó (no en cache hits
    # ni en errores — esos no gastaron créditos).
    st.session_state._last_analysis_finished_at = time.time()

    st.rerun()


# ── Run Market Scan ───────────────────────────────────────────────────────
def run_market_scan(filters: Optional[dict] = None):
    """Ejecuta un scan del mercado.
    filters: dict de filtros técnicos del screener (resultado de
             dashboard.scanner_filters.build_screener_filters).
             Si None, usa los defaults técnicos del ScreenerAgent.
    """
    st.session_state.scan_running = True
    screener = ScreenerAgent()

    progress_placeholder = st.empty()
    progress_bar = st.progress(0)

    def scan_callback(ticker, idx, total):
        pct = idx / total if total > 0 else 0
        progress_bar.progress(pct)
        progress_placeholder.markdown(
            f'<div style="color:#FFA500;font-family:JetBrains Mono;font-size:0.85rem;">'
            f'🌐 Escaneando mercado: {ticker} ({idx}/{total})</div>',
            unsafe_allow_html=True,
        )

    with st.spinner("Escaneando el universo (NYSE + NASDAQ via TradingView)..."):
        results = screener.run_full_scan(callback=scan_callback, filters=filters)

    # Guardar diagnóstico para mostrar en la pantalla de resultados
    try:
        st.session_state._scan_diagnostics = screener.last_diagnostics
    except Exception:
        st.session_state._scan_diagnostics = {}

    progress_bar.progress(1.0)
    progress_placeholder.empty()
    progress_bar.empty()

    st.session_state.scan_results = results
    st.session_state.scan_running = False
    # Forzar mostrar la pantalla de resultados aunque la lista venga vacía
    # (así el usuario ve "0 candidatos" en vez de ser devuelto al home).
    st.session_state._show_scan_results = True

    # Persistir el scan al historial en disco (solo si hay resultados reales)
    if results:
        try:
            from data.persistence import save_scan as disk_save_scan
            scan_id = disk_save_scan(results)
            if scan_id:
                st.session_state.current_scan_id = scan_id
        except Exception:
            pass

    st.rerun()


# ── Helpers reutilizables para tabs de agentes ───────────────────────────

def _render_agent_header(report):
    """Header strip con icono, nombre del agente, score y conviction badge."""
    score = report.score
    color = score_color(score)
    icon = AGENT_ICONS.get(report.agent_name, "📊")
    conv_colors = {"HIGH": "#00FF88", "MEDIUM": "#FFB84D", "LOW": "#FF3B5C"}
    conv_color = conv_colors.get(report.conviction, "#FFB84D")
    st.markdown(f"""
    <div class="agent-header">
        <div class="agent-header-left">
            <span class="agent-icon">{icon}</span>
            <span class="agent-name">{report.agent_name}</span>
        </div>
        <div class="agent-header-right">
            <span class="agent-score" style="color:{color};">{score:.0f}<span class="agent-score-max">/100</span></span>
            <span class="conviction-badge" style="color:{conv_color};border-color:{conv_color}40;background:{conv_color}1A;">
                {report.conviction}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _render_metric_tiles(metrics):
    """Fila de KPI tiles. metrics = [{icon, label, value, color, tooltip?}]"""
    if not metrics:
        return
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            tooltip = m.get("tooltip", "")
            help_html = f'<span class="kpi-help" data-tooltip="{tooltip}">?</span>' if tooltip else ""
            st.markdown(f"""
            <div class="kpi-tile">
                <div class="kpi-tile-header">
                    <span class="kpi-tile-label">{m.get('icon', '')} {m['label']}</span>
                    {help_html}
                </div>
                <div class="kpi-tile-value" style="color:{m['color']};">{m['value']}</div>
            </div>
            """, unsafe_allow_html=True)


def _render_status_pills(pills):
    """Fila de pills de estado. pills = [{label, value, level}], level = good/neutral/warn/bad"""
    if not pills:
        return
    level_colors = {"good": "#00FF88", "neutral": "#4A9EFF", "warn": "#FFB84D", "bad": "#FF3B5C"}
    cols = st.columns(len(pills))
    for col, p in zip(cols, pills):
        with col:
            color = level_colors.get(p.get("level", "neutral"), "#4A9EFF")
            sub = p.get("sub", "")
            sub_html = f'<div class="status-pill-sub">{sub}</div>' if sub else ''
            st.markdown(f"""
            <div class="status-pill" style="border-color:{color}40;border-left:3px solid {color};">
                <div class="status-pill-label">{p['label']}</div>
                <div class="status-pill-value" style="color:{color};">{p['value']}</div>
                {sub_html}
            </div>
            """, unsafe_allow_html=True)


def _render_pros_cons(report, pros_title="💪 Top 3 Señales Positivas", cons_title="⚠️ Top 3 Señales Negativas"):
    # Cap a máximo 3 cada uno — garantiza el límite sin importar lo que devuelva
    # la IA (las muestra como "las 3 más importantes"). Ahorra y ordena la UI.
    col_p, col_c = st.columns(2)
    with col_p:
        if report.pros:
            st.markdown(f'<div class="thesis-section-title strength">{pros_title}</div>', unsafe_allow_html=True)
            for p in report.pros[:3]:
                st.markdown(f'<div class="strength-item">{p}</div>', unsafe_allow_html=True)
    with col_c:
        if report.cons:
            st.markdown(f'<div class="thesis-section-title risk">{cons_title}</div>', unsafe_allow_html=True)
            for c in report.cons[:3]:
                st.markdown(f'<div class="risk-item">{c}</div>', unsafe_allow_html=True)


def _render_analysis_card(report, title="Análisis Detallado"):
    if not report.analysis:
        return
    st.markdown(f'<div class="section-title-bar">📝 {title}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="analysis-card"><div class="analysis-text">{report.analysis}</div></div>',
        unsafe_allow_html=True,
    )


def _render_insight_card(title, content, color="#FFB84D", icon="💡"):
    """Card con borde lateral coloreado para insights especiales."""
    if not content or not isinstance(content, str) or len(content) < 5:
        return
    st.markdown(f"""
    <div class="insight-card" style="border-left-color:{color};background:linear-gradient(135deg,{color}0D,{color}03);">
        <div class="insight-card-header">
            <span class="insight-card-icon">{icon}</span>
            <span class="insight-card-title" style="color:{color};">{title}</span>
        </div>
        <div class="insight-card-body">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def _safe_num(value, default=None):
    """Convierte a float si es posible, retorna default si no."""
    try:
        if value is None or value == "" or value == "N/A":
            return default
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
            return float(cleaned)
        return float(value)
    except Exception:
        return default


# ── Traducciones EN → ES para valores devueltos por los agentes ──────────
import re as _re

SPANISH_TRANSLATIONS = {
    "VERY BULLISH": "MUY ALCISTA",
    "VERY BEARISH": "MUY BAJISTA",
    "BULLISH": "ALCISTA",
    "BEARISH": "BAJISTA",
    "NEUTRAL": "NEUTRAL",
    "ACCUMULATING": "ACUMULANDO",
    "DISTRIBUTING": "DISTRIBUYENDO",
    "WIDE": "AMPLIO",
    "NARROW": "ESTRECHO",
    "NONE": "NINGUNO",
    "LOW": "BAJO",
    "MEDIUM": "MEDIO",
    "HIGH": "ALTO",
    "CRITICAL": "CRÍTICO",
    "EXCELLENT": "EXCELENTE",
    "GOOD": "BUENO",
    "AVERAGE": "PROMEDIO",
    "POOR": "POBRE",
    "EXPANDING RAPIDLY": "EXPANSIÓN RÁPIDA",
    "EXPANDING": "EN EXPANSIÓN",
    "STABLE": "ESTABLE",
    "CONTRACTING": "CONTRAYENDO",
    "STRONG": "FUERTE",
    "WEAK": "DÉBIL",
    "NORMAL": "NORMAL",
    "FLAT": "PLANA",
    "INVERTED": "INVERTIDA",
    "IMPROVING": "MEJORANDO",
    "DETERIORATING": "DETERIORANDO",
    "BUY THE FEAR": "COMPRAR EL MIEDO",
    "SELL THE HYPE": "VENDER EL HYPE",
    "NO SIGNAL": "SIN SEÑAL",
    "STRONG_BUY": "FUERTE COMPRA",
    "STRONG_SELL": "FUERTE VENTA",
    "STRONG BUY": "FUERTE COMPRA",
    "STRONG SELL": "FUERTE VENTA",
    "HOLD": "MANTENER",
    "PRICING POWER": "PRICING POWER",
    "NETWORK EFFECTS": "EFECTOS DE RED",
    "SWITCHING COSTS": "COSTOS DE CAMBIO",
    "COST ADVANTAGE": "VENTAJA EN COSTO",
    "INTANGIBLES": "INTANGIBLES",
    "MARKETPLACE": "MARKETPLACE",
    "PLATFORM": "PLATAFORMA",
    "TRADITIONAL": "TRADICIONAL",
    "COMMODITY": "COMMODITY",
    "OTHER": "OTRO",
    "RISK-ON": "RISK-ON",
    "RISK-OFF": "RISK-OFF",
    "HIGH POSITIVE": "ALTA POSITIVA",
    "HIGH NEGATIVE": "ALTA NEGATIVA",
    "FAVORABLE": "FAVORABLE",
    "UNFAVORABLE": "DESFAVORABLE",
}


def _translate_status(text):
    """Reemplaza términos en inglés por su equivalente en español (preserva mayúsculas/minúsculas del original)."""
    if not text or not isinstance(text, str):
        return text
    upper = text.upper().strip()
    if upper in SPANISH_TRANSLATIONS:
        # Mantén el case: si el original estaba en MAYÚS, devuelve MAYÚS
        if text.isupper():
            return SPANISH_TRANSLATIONS[upper]
        return SPANISH_TRANSLATIONS[upper].capitalize()
    # Reemplaza término por término (longest first)
    result = text
    for en, es in sorted(SPANISH_TRANSLATIONS.items(), key=lambda x: -len(x[0])):
        if text.isupper():
            replacement = es
        else:
            replacement = es.capitalize() if en[0].isupper() else es.lower()
        result = _re.sub(rf'\b{_re.escape(en)}\b', replacement, result, flags=_re.IGNORECASE)
    return result


def _clean_tile_value(value, max_len=22):
    """Limpia valor para tile: quita paréntesis, descripciones largas, traduce y trunca."""
    if value is None or value == "":
        return "—"
    s = str(value).strip()
    if not s or s.upper() in ("N/A", "—", "NONE", "NULL"):
        return "—"
    # Quita contenido en paréntesis (descripciones largas)
    s = _re.sub(r'\s*\([^)]*\)\s*', ' ', s).strip()
    # Quita descripciones largas tras " - " o " — " si tienen > 15 chars
    s = _re.sub(r'\s+[-—]\s+.{15,}$', '', s).strip()
    # Si empieza con "N/A", lo limpiamos
    if s.upper().startswith("N/A"):
        return "—"
    # Traduce términos comunes
    s = _translate_status(s)
    # Trunca con ellipsis
    if len(s) > max_len:
        s = s[:max_len].rstrip() + "…"
    return s


def _extract_rr_ratio(value):
    """Extrae 'X.X:1' de un string como '1.82:1 ❌ INSUFICIENTE' (1 decimal)."""
    if value is None or value == "":
        return "—"
    s = str(value)
    m = _re.search(r'(\d+\.?\d*)\s*:\s*(\d+\.?\d*)', s)
    if m:
        try:
            num = float(m.group(1))
            den = float(m.group(2))
            return f"{num:.1f}:{int(den) if den == int(den) else den:.1f}"
        except Exception:
            return f"{m.group(1)}:{m.group(2)}"
    n = _safe_num(value)
    if n is not None:
        return f"{n:.1f}:1"
    return s[:10] if s else "—"


# ── Loading skeletons + spinner pequeño centrado ─────────────────────────

def _spinner_overlay_html(text: str = "CARGANDO", sub: str = "",
                          progress: float = None) -> str:
    """HTML del overlay de carga centrado.
    - progress=None  → spinner indeterminate (Quick View, scans, etc.)
    - progress=0-100 → ring circular SVG con % real animado suavemente

    NOTA: el HTML se construye SIN indentación interna porque Streamlit
    interpreta texto con 4+ espacios al inicio de línea como bloque de
    código (<pre>), mostrando el HTML crudo como texto.
    """
    sub_html = f'<div class="alpha-spinner-sub">{sub}</div>' if sub else ""

    if progress is None:
        indicator_html = '<div class="alpha-spinner"></div>'
    else:
        pct = max(0, min(100, float(progress)))
        circumference = 238.76  # 2π × 38 (radio del círculo en el SVG)
        offset = circumference * (1 - pct / 100)
        state_class = "complete" if pct >= 99.5 else ""
        indicator_html = (
            f'<div class="alpha-progress-ring-wrap {state_class}">'
            f'<svg class="alpha-progress-svg" viewBox="0 0 92 92">'
            f'<circle class="alpha-progress-bg" cx="46" cy="46" r="38"></circle>'
            f'<circle class="alpha-progress-fg" cx="46" cy="46" r="38" '
            f'style="stroke-dashoffset: {offset:.2f};"></circle>'
            f'</svg>'
            f'<div class="alpha-progress-value">{pct:.0f}%</div>'
            f'</div>'
        )

    return (
        f'<div class="alpha-spinner-overlay">'
        f'{indicator_html}'
        f'<div class="alpha-spinner-text">{text}</div>'
        f'{sub_html}'
        f'</div>'
    )


def _skeleton_quick_view_html() -> str:
    """Skeleton para la vista rápida — header + chart + métricas + noticias.
    HTML sin indentación interna (ver nota en _spinner_overlay_html)."""
    return (
        '<div class="skeleton-block skeleton-header" style="margin-bottom:18px;"></div>'
        '<div class="skeleton-grid skeleton-row-2">'
        '<div class="skeleton-block skeleton-chart"></div>'
        '<div>'
        '<div class="skeleton-block skeleton-tile" style="margin-bottom:8px;"></div>'
        '<div class="skeleton-block skeleton-tile" style="margin-bottom:8px;"></div>'
        '<div class="skeleton-block skeleton-tile" style="margin-bottom:8px;"></div>'
        '<div class="skeleton-block skeleton-tile"></div>'
        '</div>'
        '</div>'
        '<div style="margin-top:18px;"></div>'
        '<div class="skeleton-grid skeleton-row-6">'
        '<div class="skeleton-block skeleton-tile"></div>'
        '<div class="skeleton-block skeleton-tile"></div>'
        '<div class="skeleton-block skeleton-tile"></div>'
        '<div class="skeleton-block skeleton-tile"></div>'
        '<div class="skeleton-block skeleton-tile"></div>'
        '<div class="skeleton-block skeleton-tile"></div>'
        '</div>'
        '<div style="margin-top:18px;"></div>'
        '<div class="skeleton-grid skeleton-row-2">'
        '<div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '</div>'
        '<div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '</div>'
        '</div>'
    )


def _skeleton_analysis_full_html() -> str:
    """Skeleton para el análisis DLP completo — overview con gauge + snowflake + breakdown + niveles.
    HTML sin indentación interna (ver nota en _spinner_overlay_html)."""
    return (
        '<div class="skeleton-grid" style="grid-template-columns: 1.2fr 1fr 1.5fr;">'
        '<div class="skeleton-block" style="height:280px;"></div>'
        '<div class="skeleton-block" style="height:280px;"></div>'
        '<div class="skeleton-block" style="height:280px;"></div>'
        '</div>'
        '<div style="margin-top:24px;"></div>'
        '<div class="skeleton-grid skeleton-row-2">'
        '<div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '<div class="skeleton-block skeleton-tile"></div>'
        '<div class="skeleton-block skeleton-tile"></div>'
        '<div class="skeleton-block skeleton-tile"></div>'
        '<div class="skeleton-block skeleton-tile"></div>'
        '</div>'
        '<div>'
        '<div class="skeleton-block" style="height:160px;"></div>'
        '<div style="margin-top:14px;"></div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '<div class="skeleton-block skeleton-list-item"></div>'
        '</div>'
        '</div>'
    )


def _extract_percent(value):
    """Extrae el primer % de un string. Ej: '~31.2% (entre top 8...)' → '~31.2%'."""
    if value is None or value == "":
        return "—"
    s = str(value)
    m = _re.search(r'([~<>]?\s*-?\d+\.?\d*\s*%)', s)
    if m:
        return m.group(1).replace(" ", "")
    return _clean_tile_value(value)


# ── Overview Tab ──────────────────────────────────────────────────────────
def render_overview(analysis: StockAnalysis):
    # Fila 1: Gauge + Snowflake (en pantalla ancha — 50/50 cada uno).
    # Esto da MUCHO más espacio horizontal al snowflake → los labels
    # ("Crecimiento", "Momentum", "💰 Valor") caben sin cortarse.
    col_gauge, col_snow = st.columns([1, 1])

    with col_gauge:
        fig = build_gauge(analysis.composite_score, analysis.recommendation)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key=f"chart_overview_gauge_{analysis.ticker}")

        # Badge de recomendación
        badge_html = get_recommendation_badge(analysis.recommendation)
        st.markdown(
            f'<div style="text-align:center;margin-top:-10px;">{badge_html}</div>',
            unsafe_allow_html=True,
        )

        # Conviction
        conviction_color = {"HIGH": "#00FF88", "MEDIUM": "#FFA500", "LOW": "#FF3B5C"}.get(
            analysis.conviction_level, "#FFA500"
        )
        st.markdown(
            f'<div style="text-align:center;font-family:JetBrains Mono;font-size:0.75rem;color:{conviction_color};margin-top:4px;">'
            f'Conviction: {analysis.conviction_level}</div>',
            unsafe_allow_html=True,
        )

    with col_snow:
        fig = build_snowflake(analysis.snowflake)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key=f"chart_overview_snowflake_{analysis.ticker}")

    # Fila 2: Score breakdown full-width (debajo, con todo el ancho disponible)
    fig = build_score_breakdown(analysis.score_breakdown)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                    key=f"chart_overview_breakdown_{analysis.ticker}")

    st.markdown("---")

    # Fila 2: Info básica + Tesis + Niveles
    col_info, col_thesis = st.columns([1, 2])

    with col_info:
        st.markdown("#### Información")
        info_data = {
            "Empresa":   analysis.company_name,
            "Ticker":    analysis.ticker,
            "Sector":    analysis.sector,
            "Horizonte": analysis.time_horizon,
        }
        for k, v in info_data.items():
            # Layout grid (NO flex) — evita que key y value se solapen
            # cuando el value es largo (típicamente el Horizonte). El value
            # se limita a 2 líneas con line-clamp; resto se trunca con "...".
            st.markdown(
                f'<div class="overview-info-row">'
                f'<span class="overview-info-key">{k}</span>'
                f'<span class="overview-info-value">{v}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── Métricas Clave (4 KPIs premium con tooltips) ─────────
        if any([analysis.entry_price, analysis.target_price, analysis.risk_reward, analysis.position_size_pct]):
            st.markdown('<div class="kpi-section-title">📊 Métricas Clave</div>', unsafe_allow_html=True)

            entry_str  = f"${analysis.entry_price:.2f}"  if analysis.entry_price else "—"
            target_str = f"${analysis.target_price:.2f}" if analysis.target_price else "—"
            rr_str     = _extract_rr_ratio(analysis.risk_reward)
            rr_num     = _safe_num(str(analysis.risk_reward or "").split(":")[0]) if analysis.risk_reward else None
            sizing_str = _extract_percent(analysis.position_size_pct) if analysis.position_size_pct else "—"
            sizing_num = _safe_num(sizing_str)

            metrics = [
                {
                    "icon": "📍", "label": "Precio Actual", "value": entry_str, "color": "#FFB84D",
                    "tooltip": "Precio actual del activo al momento del análisis. Se usa como línea de referencia para calcular el upside hasta el precio objetivo y el downside hasta el nivel de protección.",
                },
                {
                    "icon": "🏁", "label": "Precio Objetivo", "value": target_str, "color": "#00FF88",
                    "tooltip": "Precio donde tomar ganancias totales o parciales. Combina la resistencia técnica cercana (52W high, niveles psicológicos) con el valor intrínseco fundamental estimado.",
                },
                {
                    "icon": "⚖️", "label": "R/R Ratio", "value": rr_str,
                    "color": ("#00FF88" if (rr_num or 0) >= 3 else
                              "#FFB84D" if (rr_num or 0) >= 2 else "#FF3B5C"),
                    "tooltip": "Risk/Reward Ratio — relación entre la ganancia potencial al target y la pérdida máxima al stop. Un 3:1 significa que arriesgas 1 para ganar 3. Mínimo aceptable para operar: 2:1. El color del valor indica si supera el umbral (verde ≥3, amarillo ≥2, rojo <2).",
                },
                {
                    "icon": "📐", "label": "Sizing", "value": sizing_str,
                    "color": ("#FF3B5C" if (sizing_num or 0) == 0 else
                              "#9B59FF"),
                    "tooltip": "Position Sizing — porcentaje del portafolio sugerido. Calculado vía Kelly Criterion modificado. 0% indica que el sistema recomienda NO operar (R/R insuficiente).",
                },
            ]

            # Tile NUEVO: Calidad de Largo Plazo (solo si está disponible — backward compat)
            lt_quality = getattr(analysis, "long_term_quality_score", None)
            if lt_quality is not None:
                quality_verdict = getattr(analysis, "quality_verdict", "") or ""
                verdict_es = {
                    "best-in-class": "Best-in-Class",
                    "high":          "Alta Calidad",
                    "average":       "Calidad Media",
                    "low":           "Calidad Baja",
                }.get(quality_verdict, quality_verdict.title())
                metrics.append({
                    "icon": "🏛️", "label": "Calidad LP", "value": f"{lt_quality:.0f}/100",
                    "color": ("#00FF88" if lt_quality >= 85 else
                              "#4A9EFF" if lt_quality >= 70 else
                              "#FFB84D" if lt_quality >= 55 else "#FF3B5C"),
                    "tooltip": f"Calidad estructural de largo plazo (3-7 años). Promedio de Fundamentales + Future Viability. Veredicto: {verdict_es}. Empresas con score ≥85 son COMPOUNDERS (best-in-class) que merecen hold de muy largo plazo.",
                })

            for m in metrics:
                st.markdown(f"""
                <div class="kpi-tile">
                    <div class="kpi-tile-header">
                        <span class="kpi-tile-label">{m['icon']} {m['label']}</span>
                        <span class="kpi-help" data-tooltip="{m['tooltip']}">?</span>
                    </div>
                    <div class="kpi-tile-value" style="color:{m['color']};">{m['value']}</div>
                </div>
                """, unsafe_allow_html=True)

        # ── Vetos aplicados: ya NO se muestran en el Overview (el dato
        # analysis.vetos_applied sigue existiendo internamente para el scoring,
        # solo se quitó su visualización). ─────────────────────────

    with col_thesis:
        st.markdown("#### 👔 Tesis de Inversión — Orquestador")
        st.markdown(
            f'<div class="analysis-card"><div class="analysis-text">{analysis.investment_thesis}</div></div>',
            unsafe_allow_html=True,
        )

        # ── Fortalezas / Riesgos en cards ────────────────────────
        col_s, col_r = st.columns(2)
        with col_s:
            if analysis.key_strengths:
                st.markdown('<div class="thesis-section-title strength">💪 Fortalezas Clave</div>',
                            unsafe_allow_html=True)
                for s in analysis.key_strengths:
                    st.markdown(f'<div class="strength-item">{s}</div>', unsafe_allow_html=True)

        with col_r:
            if analysis.key_risks:
                st.markdown('<div class="thesis-section-title risk">⚠️ Riesgos Clave</div>',
                            unsafe_allow_html=True)
                for r in analysis.key_risks:
                    st.markdown(f'<div class="risk-item">{r}</div>', unsafe_allow_html=True)

        # ── Card NUEVA: Diagnóstico de Asimetría (upside / downside / balanced) ─
        asym_dir = getattr(analysis, "asymmetry_direction", None)
        asym_str = getattr(analysis, "asymmetry_strength", None)
        if asym_dir in ("upside", "downside", "balanced"):
            asym_config = {
                "upside": {
                    "icon": "📈", "title": "Asimetría al Alza",
                    "body": "El <span class='em'>upside potencial supera materialmente al downside</span>. La situación actual favorece tomar posición — la recompensa esperada justifica el riesgo asumido.",
                },
                "downside": {
                    "icon": "📉", "title": "Asimetría a la Baja",
                    "body": "El <span class='em'>downside potencial supera al upside</span>. La recompensa actual NO compensa el riesgo. Esperar mejor punto de entrada o evitar la posición.",
                },
                "balanced": {
                    "icon": "⚖️", "title": "Riesgo Balanceado",
                    "body": "El <span class='em'>upside y downside son similares</span>. No hay edge claro de asimetría — la decisión debe basarse en la calidad estructural del negocio y el horizonte temporal.",
                },
            }[asym_dir]
            strength_label = ""
            if asym_str:
                strength_es = {"strong": "FUERTE", "moderate": "MODERADA", "weak": "DÉBIL"}.get(asym_str, asym_str.upper())
                strength_label = f'<span class="asymmetry-strength">{strength_es}</span>'
            st.markdown(f"""
            <div class="asymmetry-card {asym_dir}">
                <div class="asymmetry-header">
                    <span class="asymmetry-icon">{asym_config['icon']}</span>
                    <span class="asymmetry-title">{asym_config['title']}</span>
                    {strength_label}
                </div>
                <div class="asymmetry-body">{asym_config['body']}</div>
            </div>
            """, unsafe_allow_html=True)

        # ── Oportunidad Asimétrica (card premium — se mantiene intacta) ──
        if analysis.alpha_opportunity and analysis.alpha_opportunity != "No identificada":
            st.markdown(f"""
            <div class="alpha-opportunity-card">
                <div class="alpha-opportunity-header">
                    <span class="alpha-opportunity-icon">⚡</span>
                    <span class="alpha-opportunity-title">Oportunidad Asimétrica</span>
                </div>
                <div class="alpha-opportunity-body">{analysis.alpha_opportunity}</div>
            </div>
            """, unsafe_allow_html=True)

    # Risk/Reward visual — usando PRECIO ACTUAL de yfinance como referencia
    if analysis.stop_loss and analysis.target_price:
        from data.market_data import get_company_info
        info_live = get_company_info(analysis.ticker) or {}
        current_price = info_live.get("current_price") or analysis.entry_price
        if current_price:
            st.markdown("---")
            fig = build_rr_chart(current_price, analysis.stop_loss,
                                 analysis.target_price, analysis.ticker)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                            key=f"chart_overview_rr_{analysis.ticker}")


# ── Technical Tab ─────────────────────────────────────────────────────────
def render_technical(analysis: StockAnalysis):
    tech_report = analysis.reports.get("technical")
    if tech_report is None:
        st.info("Análisis técnico no disponible.")
        return

    # Header con score + conviction
    _render_agent_header(tech_report)

    # ── Gráfica principal (candlestick + MAs + RSI + MACD + Volumen) ──
    from data.market_data import get_price_history, compute_technical_indicators
    df = get_price_history(analysis.ticker, period="2y")
    indicators = compute_technical_indicators(df) if not df.empty else {}

    st.markdown('<div class="section-title-bar">📈 Chart Multi-Indicador</div>', unsafe_allow_html=True)
    fig = build_price_chart(df, indicators, analysis.ticker)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True},
                    key=f"chart_technical_price_{analysis.ticker}")

    # ── Status pills clave (Stage, RSI, MACD, Distancia 52W high) ──
    st.markdown('<div class="section-title-bar">🎯 Indicadores Clave</div>', unsafe_allow_html=True)

    stage = indicators.get("stage", 0) or 0
    stage_level = "good" if stage == 2 else "neutral" if stage == 1 else "warn" if stage == 3 else "bad"
    stage_sub = {2: "Tendencia alcista", 1: "Acumulación", 3: "Distribución", 4: "Bajista"}.get(stage, "Sin definir")

    rsi = indicators.get("rsi_14", 50) or 50
    rsi_level = "bad" if rsi > 70 or rsi < 30 else "good" if 40 <= rsi <= 60 else "neutral"

    macd_hist = indicators.get("macd_hist", 0) or 0
    macd_level = "good" if macd_hist > 0 else "bad"
    macd_val = "Alcista" if macd_hist > 0 else "Bajista"

    pct_high = indicators.get("pct_from_52w_high", 0) or 0
    high_level = "good" if pct_high > -5 else "neutral" if pct_high > -15 else "bad"

    _render_status_pills([
        {"label": "Stage Minervini", "value": f"Stage {stage}", "level": stage_level, "sub": stage_sub},
        {"label": "RSI 14", "value": f"{rsi:.1f}", "level": rsi_level,
         "sub": "Sobrecomprado" if rsi > 70 else "Sobrevendido" if rsi < 30 else "Neutral"},
        {"label": "MACD Hist", "value": macd_val, "level": macd_level,
         "sub": f"{macd_hist:+.3f}"},
        {"label": "Dist. 52W High", "value": f"{pct_high:.1f}%", "level": high_level,
         "sub": "Cerca del máximo" if pct_high > -5 else "Lejos del máximo"},
    ])

    # ── Performance vs MAs y vs SPY ──
    st.markdown('<div class="section-title-bar">📊 Performance Relativa</div>', unsafe_allow_html=True)

    rs = tech_report.raw_data.get("rs", {}) or {}
    col_mas, col_rs = st.columns(2)

    with col_mas:
        ma_items = []
        for n, color in [(20, "#4A9EFF"), (50, "#FFD740"), (150, "#FF6B35"), (200, "#FF3B5C")]:
            pct = indicators.get(f"price_vs_sma{n}_pct")
            if pct is not None:
                bar_color = "#00FF88" if pct > 0 else "#FF3B5C"
                ma_items.append((f"vs SMA {n}", pct, bar_color))
        if ma_items:
            fig_ma = build_metric_bars(ma_items, height=220, title="DISTANCIA A MOVING AVERAGES")
            st.plotly_chart(fig_ma, use_container_width=True, config={"displayModeBar": False},
                            key=f"chart_technical_mas_{analysis.ticker}")

    with col_rs:
        rs_items = []
        for period, label in [("rs_1m", "RS 1M"), ("rs_3m", "RS 3M"), ("rs_6m", "RS 6M")]:
            v = rs.get(period)
            if v is not None:
                bar_color = "#00FF88" if v > 0 else "#FF3B5C"
                rs_items.append((label, v, bar_color))
        if rs_items:
            fig_rs = build_metric_bars(rs_items, height=220, title="RELATIVE STRENGTH vs S&P 500")
            st.plotly_chart(fig_rs, use_container_width=True, config={"displayModeBar": False},
                            key=f"chart_technical_rs_{analysis.ticker}")

    # ── Señales alcistas / bajistas (cards) ──
    _render_pros_cons(tech_report,
                      pros_title="📈 Top 3 Señales Alcistas",
                      cons_title="📉 Top 3 Señales Bajistas")

    # ── Análisis textual ──
    _render_analysis_card(tech_report, title="Análisis Técnico Completo")


# ── Generic Agent Tab ─────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────
# CUSTOM TABS: Fundamentales, Futuro, Smart Money, Catalizadores,
#              Sentimiento, Riesgo. Cada uno es un mini-dashboard visual.
# ──────────────────────────────────────────────────────────────────────

def render_fundamentals(analysis: StockAnalysis):
    report = analysis.reports.get("fundamentals")
    if report is None:
        st.info("Análisis fundamental no disponible.")
        return

    _render_agent_header(report)
    km = report.key_metrics or {}
    sub = report.sub_scores or {}
    rd  = report.raw_data or {}

    # SIEMPRE fetcheamos datos frescos de yfinance — no dependemos del JSON guardado
    from data.market_data import get_company_info, get_financials, compute_quality_ratios
    info = get_company_info(analysis.ticker) or {}
    financials = get_financials(analysis.ticker) or {}
    ratios_fresh = compute_quality_ratios(info, financials) or {}

    # Fallback chain: yfinance fresco → raw_data del agente → key_metrics del agente
    ratios = {**(rd.get("ratios") or {}), **ratios_fresh}

    # ── KPI tiles: Crecimiento + Rentabilidad ─────────────────────
    st.markdown('<div class="section-title-bar">💰 Crecimiento y Rentabilidad</div>',
                unsafe_allow_html=True)

    rev_growth = ratios.get("revenue_growth_yoy")
    if rev_growth is None: rev_growth = _safe_num(km.get("revenue_growth"))

    roic = ratios.get("roic")
    if roic is None: roic = _safe_num(km.get("roic"))

    fcf_yield = ratios.get("fcf_yield")
    if fcf_yield is None: fcf_yield = _safe_num(km.get("fcf_yield"))

    gross_marg = ratios.get("gross_margin")
    if gross_marg is None: gross_marg = _safe_num(km.get("gross_margin"))

    _render_metric_tiles([
        {"icon": "📈", "label": "Revenue Growth YoY",
         "value": f"{rev_growth:+.1f}%" if rev_growth is not None else "—",
         "color": "#00FF88" if (rev_growth or 0) > 0 else "#FF3B5C",
         "tooltip": "Crecimiento de ingresos año contra año. >15% es excelente."},
        {"icon": "🎯", "label": "ROIC",
         "value": f"{roic:.1f}%" if roic is not None else "—",
         "color": "#00FF88" if (roic or 0) > 15 else "#FFB84D" if (roic or 0) > 8 else "#FF3B5C",
         "tooltip": "Return on Invested Capital. >15% indica negocio de alta calidad."},
        {"icon": "💵", "label": "FCF Yield",
         "value": f"{fcf_yield:.2f}%" if fcf_yield is not None else "—",
         "color": "#00FF88" if (fcf_yield or 0) > 5 else "#FFB84D" if (fcf_yield or 0) > 2 else "#FF3B5C",
         "tooltip": "Free Cash Flow Yield. FCF / Market Cap. >5% es atractivo."},
        {"icon": "📊", "label": "Gross Margin",
         "value": f"{gross_marg:.1f}%" if gross_marg is not None else "—",
         "color": "#00FF88" if (gross_marg or 0) > 50 else "#FFB84D" if (gross_marg or 0) > 30 else "#FF3B5C",
         "tooltip": "Margen bruto: indica pricing power. >50% es excepcional."},
    ])

    # ── Valoración tiles ─────────────────────────────────────────
    st.markdown('<div class="section-title-bar">🧮 Múltiplos de Valoración</div>',
                unsafe_allow_html=True)

    # Todos los múltiplos vienen DIRECTOS de yfinance (siempre frescos)
    pe       = _safe_num(info.get("pe_ratio"))      or _safe_num(km.get("pe_ratio"))
    fwd_pe   = _safe_num(info.get("forward_pe"))
    ps       = _safe_num(info.get("ps_ratio"))
    ev_ebit  = _safe_num(info.get("ev_ebitda"))     or _safe_num(km.get("ev_ebitda"))
    de       = ratios.get("debt_to_equity")          or _safe_num(km.get("debt_equity"))
    op_marg  = ratios.get("operating_margin")

    _render_metric_tiles([
        {"icon": "💎", "label": "P/E Trailing",
         "value": f"{pe:.1f}" if pe else "—", "color": "#4A9EFF",
         "tooltip": "Price/Earnings (trailing). Múltiplo precio/utilidad de los últimos 12 meses. Compara contra el sector y la historia de la empresa."},
        {"icon": "🔮", "label": "P/E Forward",
         "value": f"{fwd_pe:.1f}" if fwd_pe else "—", "color": "#4A9EFF",
         "tooltip": "Price/Earnings forward. Basado en el EPS estimado del próximo año. Si está bastante por debajo del trailing, indica crecimiento esperado."},
        {"icon": "🏛️", "label": "EV/EBITDA",
         "value": f"{ev_ebit:.1f}" if ev_ebit else "—", "color": "#9B59FF",
         "tooltip": "Enterprise Value / EBITDA. <12 suele ser atractivo, >20 ya es caro. Es más fiable que P/E para comparar empresas con diferente estructura de capital."},
        {"icon": "🏦", "label": "Debt/Equity",
         "value": f"{de:.2f}" if de is not None else "—",
         "color": "#00FF88" if (de or 0) < 0.5 else "#FFB84D" if (de or 0) < 1.5 else "#FF3B5C",
         "tooltip": "Apalancamiento financiero (deuda/equity). <0.5 = sano, >1.5 = riesgoso. Negocios con cash flow estable toleran más deuda."},
    ])

    # Tiles secundarios (Margen operativo + P/S + adicionales)
    extra_tiles = []
    if op_marg is not None:
        extra_tiles.append({
            "icon": "⚙️", "label": "Operating Margin",
            "value": f"{op_marg:.1f}%",
            "color": "#00FF88" if op_marg > 20 else "#FFB84D" if op_marg > 10 else "#FF3B5C",
            "tooltip": "Margen operativo: % de cada dólar de ingresos que queda tras costos operativos. >20% indica negocio escalable y eficiente.",
        })
    if ps is not None:
        extra_tiles.append({
            "icon": "📏", "label": "P/S Ratio",
            "value": f"{ps:.2f}",
            "color": "#9B59FF",
            "tooltip": "Price/Sales. Útil para empresas no rentables aún (SaaS, biotech). <3 suele ser razonable, >10 implica altas expectativas de crecimiento.",
        })
    roe_val = ratios.get("roe")
    if roe_val is not None:
        extra_tiles.append({
            "icon": "💼", "label": "ROE",
            "value": f"{roe_val:.1f}%",
            "color": "#00FF88" if roe_val > 15 else "#FFB84D" if roe_val > 8 else "#FF3B5C",
            "tooltip": "Return on Equity: rentabilidad sobre patrimonio. >15% es excelente, indica gestión eficiente del capital de accionistas.",
        })
    cr = ratios.get("current_ratio")
    if cr is not None:
        extra_tiles.append({
            "icon": "💧", "label": "Current Ratio",
            "value": f"{cr:.2f}",
            "color": "#00FF88" if cr > 1.5 else "#FFB84D" if cr > 1 else "#FF3B5C",
            "tooltip": "Liquidez de corto plazo: activos corrientes / pasivos corrientes. >1.5 = sólido, <1 = posible estrés de caja.",
        })

    if extra_tiles:
        _render_metric_tiles(extra_tiles[:4])

    # ── Datos directos de Yahoo Finance ──────────────────────────
    st.markdown('<div class="section-title-bar">📡 Datos Yahoo Finance</div>',
                unsafe_allow_html=True)

    # Market Cap
    mktcap_raw = info.get("market_cap", 0) or 0
    if mktcap_raw >= 1e12:
        mktcap_str = f"${mktcap_raw/1e12:.2f}T"
    elif mktcap_raw >= 1e9:
        mktcap_str = f"${mktcap_raw/1e9:.1f}B"
    elif mktcap_raw > 0:
        mktcap_str = f"${mktcap_raw/1e6:.0f}M"
    else:
        mktcap_str = "—"

    # Profit Margin (directo de YF — decimal)
    pm_raw = info.get("profit_margin")
    pm_str = f"{pm_raw*100:.2f}%" if pm_raw is not None else "—"
    pm_color = ("#00FF88" if (pm_raw or 0)*100 > 20
                else "#FFB84D" if (pm_raw or 0)*100 > 10
                else "#FF3B5C")

    # Revenue TTM (directo de YF)
    rev_ttm = info.get("revenue_ttm", 0) or 0
    if rev_ttm >= 1e12:
        rev_ttm_str = f"${rev_ttm/1e12:.2f}T"
    elif rev_ttm >= 1e9:
        rev_ttm_str = f"${rev_ttm/1e9:.1f}B"
    elif rev_ttm > 0:
        rev_ttm_str = f"${rev_ttm/1e6:.0f}M"
    else:
        rev_ttm_str = "—"

    # Beta (directo de YF)
    beta_raw = info.get("beta")
    beta_str = f"{beta_raw:.2f}" if isinstance(beta_raw, (int, float)) else "—"
    beta_color = ("#00FF88" if isinstance(beta_raw, (int, float)) and beta_raw < 1
                  else "#FFB84D" if isinstance(beta_raw, (int, float)) and beta_raw <= 1.5
                  else "#FF3B5C")

    _render_metric_tiles([
        {"icon": "💎", "label": "Market Cap",
         "value": mktcap_str, "color": "#FFB84D",
         "tooltip": "Capitalización de mercado total (precio × acciones en circulación). Fuente: Yahoo Finance."},
        {"icon": "📊", "label": "Profit Margin",
         "value": pm_str, "color": pm_color,
         "tooltip": "Margen neto (Profit Margin) directo de Yahoo Finance. % de cada dólar de ingresos que queda como ganancia neta."},
        {"icon": "💰", "label": "Revenue TTM",
         "value": rev_ttm_str, "color": "#4A9EFF",
         "tooltip": "Ingresos totales de los últimos 12 meses (Trailing Twelve Months). Fuente: Yahoo Finance."},
        {"icon": "📈", "label": "Beta",
         "value": beta_str, "color": beta_color,
         "tooltip": "Beta vs S&P 500. <1 = menos volátil que el índice, >1 = más volátil, 1 = correlación perfecta."},
    ])

    # ── Desglose de sub-scores ───────────────────────────────────
    st.markdown('<div class="section-title-bar">⚖️ Pilares Fundamentales</div>',
                unsafe_allow_html=True)

    sub_items = []
    pillars = [
        ("Calidad",          sub.get("quality"),           "#FFB84D"),
        ("Crecimiento",      sub.get("growth"),            "#00FF88"),
        ("Valoración",       sub.get("valuation"),         "#4A9EFF"),
        ("Solidez Financiera", sub.get("financial_health"), "#9B59FF"),
    ]
    for label, val, color in pillars:
        if val is not None:
            sub_items.append((label, float(val) * 4, color))  # escalar /25 → /100

    if sub_items:
        fig = build_metric_bars(sub_items, height=240,
                                title="SUB-SCORES (0-100)", x_format="num",
                                x_zero_line=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key=f"chart_fund_pillars_{analysis.ticker}")

    # ── Pros / Cons ──
    _render_pros_cons(report)

    # ── Insights: DCF Thesis + Earnings Quality ──
    if isinstance(rd.get("dcf_thesis"), str) or report.analysis:
        # raw_data normalmente no tiene dcf_thesis (eso lo guarda el report al nivel superior)
        pass
    # El agente fundamentals retorna estos campos en el JSON; los buscamos en report.raw_data
    # o si no, en key_metrics extras
    _render_insight_card("Tesis DCF", rd.get("dcf_thesis", ""),
                         color="#00FF88", icon="💎")
    _render_insight_card("Calidad de Earnings", rd.get("earnings_quality", ""),
                         color="#4A9EFF", icon="✓")

    # ── Análisis completo ──
    _render_analysis_card(report, title="Análisis Fundamental Completo")


def render_future(analysis: StockAnalysis):
    report = analysis.reports.get("future")
    if report is None:
        st.info("Análisis de viabilidad futura no disponible.")
        return

    _render_agent_header(report)
    km = report.key_metrics or {}
    sub = report.sub_scores or {}
    rd  = report.raw_data or {}

    # ── Status pills: 4 dimensiones críticas del futuro ──
    st.markdown('<div class="section-title-bar">🔭 Diagnóstico del Negocio Futuro</div>',
                unsafe_allow_html=True)

    moat_str = (km.get("moat_strength") or "").lower()
    moat_level = "good" if "wide" in moat_str else "warn" if "narrow" in moat_str else "bad"

    disr = (km.get("disruption_risk") or "").lower()
    disr_level = "good" if "low" in disr else "warn" if "medium" in disr else "bad"

    tam = (km.get("tam_growth") or "").lower()
    tam_level = "good" if "rapidly" in tam or "expanding rapidly" in tam else "neutral" if "expanding" in tam else "warn"

    mgmt = (km.get("management_quality") or "").lower()
    mgmt_level = "good" if "excellent" in mgmt else "neutral" if "good" in mgmt else "warn"

    _render_status_pills([
        {"label": "Moat Defensivo",
         "value": _clean_tile_value(km.get("moat_strength"), max_len=14),
         "level": moat_level,
         "sub": _clean_tile_value(km.get("moat_type"), max_len=20)},
        {"label": "Riesgo Disrupción",
         "value": _clean_tile_value(km.get("disruption_risk"), max_len=14),
         "level": disr_level, "sub": "IA / tecnología"},
        {"label": "Crecimiento TAM",
         "value": _clean_tile_value(km.get("tam_growth"), max_len=18),
         "level": tam_level, "sub": "Mercado direccionable"},
        {"label": "Calidad Gerencia",
         "value": _clean_tile_value(km.get("management_quality"), max_len=14),
         "level": mgmt_level, "sub": "Asignación de capital"},
    ])

    # ── Bar chart: 4 pilares del futuro ──
    st.markdown('<div class="section-title-bar">⚡ Pilares de Viabilidad Futura</div>',
                unsafe_allow_html=True)

    sub_items = []
    pillars = [
        ("Calidad del Moat",     sub.get("moat_quality"),                 "#FFB84D"),
        ("Runway de Crecimiento", sub.get("growth_runway"),               "#00FF88"),
        ("Resistencia Disrupción", sub.get("disruption_resilience"),      "#4A9EFF"),
        ("Capital Allocation",   sub.get("management_capital_allocation"), "#9B59FF"),
    ]
    for label, val, color in pillars:
        if val is not None:
            sub_items.append((label, float(val) * 4, color))

    if sub_items:
        fig = build_metric_bars(sub_items, height=240,
                                title="SUB-SCORES (0-100)", x_format="num",
                                x_zero_line=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key=f"chart_future_pillars_{analysis.ticker}")

    # ── Pros / Cons ──
    _render_pros_cons(report,
                      pros_title="🚀 Top 3 Ventajas Futuras",
                      cons_title="⚠️ Top 3 Riesgos Estructurales")

    # ── Insight: Future Thesis ──
    _render_insight_card("Tesis a 5 años", rd.get("future_thesis", ""),
                         color="#FFB84D", icon="🔭")

    # Key risks específicos (lista)
    key_risks = rd.get("key_risks") or []
    if key_risks and isinstance(key_risks, list):
        st.markdown('<div class="section-title-bar">⚠️ Riesgos Críticos Identificados</div>',
                    unsafe_allow_html=True)
        for r in key_risks:
            st.markdown(f'<div class="risk-item">{r}</div>', unsafe_allow_html=True)

    _render_analysis_card(report, title="Análisis de Viabilidad Futura")


def render_institutional(analysis: StockAnalysis):
    report = analysis.reports.get("institutional")
    if report is None:
        st.info("Análisis de flujo institucional no disponible.")
        return

    _render_agent_header(report)
    km = report.key_metrics or {}
    rd = report.raw_data or {}
    holders_raw = rd.get("holders_raw", {}) or {}

    # ── KPI tiles del Smart Money ──
    st.markdown('<div class="section-title-bar">🏦 Indicadores Smart Money</div>',
                unsafe_allow_html=True)

    inst_raw = km.get("institutional_ownership") or ""
    short_raw = km.get("short_interest") or ""
    insider_raw = km.get("insider_buying_signal") or "neutral"
    squeeze_raw = km.get("squeeze_potential") or "low"

    insider_level = "good" if "bullish" in insider_raw.lower() else "bad" if "bearish" in insider_raw.lower() else "neutral"
    squeeze_level = "good" if "high" in squeeze_raw.lower() else "neutral" if "medium" in squeeze_raw.lower() else "warn"

    _render_status_pills([
        {"label": "Propiedad Institucional",
         "value": _extract_percent(inst_raw),
         "level": "good", "sub": "% del outstanding"},
        {"label": "Señal de Insiders",
         "value": _clean_tile_value(insider_raw, max_len=12),
         "level": insider_level, "sub": "Compras vs ventas"},
        {"label": "Short Interest",
         "value": _extract_percent(short_raw),
         "level": "neutral", "sub": "% del float"},
        {"label": "Potencial Squeeze",
         "value": _clean_tile_value(squeeze_raw, max_len=12),
         "level": squeeze_level, "sub": "Short squeeze"},
    ])

    # ── Top holders bar chart ──
    top_inst = holders_raw.get("top_institutions") or []
    if top_inst:
        fig = build_holders_bars(top_inst)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key=f"chart_inst_holders_{analysis.ticker}")

    # ── Smart Money Signal pill grande ──
    smart_raw = km.get("smart_money_signal") or "neutral"
    smart_display = _translate_status(smart_raw).upper()
    signal_color = "#00FF88" if "accumul" in smart_raw.lower() else "#FF3B5C" if "distribut" in smart_raw.lower() else "#4A9EFF"
    st.markdown(f"""
    <div class="insight-card" style="border-left-color:{signal_color};background:linear-gradient(135deg,{signal_color}11,{signal_color}03);">
        <div class="insight-card-header">
            <span class="insight-card-icon">📡</span>
            <span class="insight-card-title" style="color:{signal_color};">Señal Agregada del Smart Money</span>
        </div>
        <div class="insight-card-body" style="font-size:1.15rem;font-weight:700;color:{signal_color};font-family:'JetBrains Mono',monospace;">{smart_display}</div>
    </div>
    """, unsafe_allow_html=True)

    # ── Pros / Cons ──
    _render_pros_cons(report)

    # ── Key Insight ──
    _render_insight_card("Insight Clave del Flujo", rd.get("key_insight", ""),
                         color="#9B59FF", icon="🎯")

    _render_analysis_card(report, title="Análisis Completo de Flujo")


def render_catalysts(analysis: StockAnalysis):
    report = analysis.reports.get("catalysts")
    if report is None:
        st.info("Análisis de catalizadores no disponible.")
        return

    _render_agent_header(report)
    km = report.key_metrics or {}
    rd = report.raw_data or {}

    # ── Re-fetch earnings data fresco para tener days_to_next_earnings ──
    from data.market_data import get_earnings_data
    earnings = get_earnings_data(analysis.ticker) or {}

    # ── KPI tiles ──
    st.markdown('<div class="section-title-bar">⚡ Catalizadores en el Horizonte</div>',
                unsafe_allow_html=True)

    next_earn = earnings.get("next_earnings", "") or km.get("next_earnings", "")
    days_to = earnings.get("days_to_next_earnings")
    if days_to is not None:
        days_str = f"{days_to}d"
        next_tooltip = (f"Próximo reporte: {next_earn}. "
                        f"Earnings inminentes (<7d) son catalizador de alta volatilidad.")
        next_color = "#FF3B5C" if days_to < 7 else "#FFB84D" if days_to < 30 else "#4A9EFF"
    else:
        days_str = "N/D"
        next_tooltip = ("Fecha del próximo reporte de resultados no disponible en este momento "
                        "(la fuente de datos puede estar temporalmente fuera de servicio). "
                        "Intenta reanalizar en unos minutos.")
        next_color = "#5A6878"

    def _looks_empty(v):
        """Detecta si un valor de tile está efectivamente vacío después de limpieza."""
        if v is None:
            return True
        s = str(v).strip()
        return s in ("", "—", "N/A", "N/D", "None", "null")

    beat_count = earnings.get("beat_count")
    eh = earnings.get("earnings_history", []) or []
    if eh and beat_count is not None:
        beat_rate_str = f"{beat_count}/{len(eh)}"
        beat_tooltip = "Trimestres en los que la empresa superó el consenso de EPS en los últimos 8 trimestres."
        beat_color = "#00FF88"
    else:
        raw = km.get("earnings_beat_rate", "")
        cleaned = _clean_tile_value(raw, max_len=10) if raw else None
        if _looks_empty(cleaned):
            beat_rate_str = "N/D"
            beat_tooltip = ("Historial de beats no disponible — requiere datos detallados de earnings "
                            "que la fuente puede no exponer para todos los tickers.")
            beat_color = "#5A6878"
        else:
            beat_rate_str = cleaned
            beat_tooltip = "Beat rate estimado por el agente de catalizadores."
            beat_color = "#FFB84D"

    avg_surp = earnings.get("avg_surprise")
    if isinstance(avg_surp, (int, float)):
        avg_surp_str = f"{avg_surp:+.1f}%"
        avg_surp_tooltip = ("Promedio de % sorpresa en EPS sobre el consenso. "
                            "Positivo y sostenido indica momentum fundamental.")
        avg_surp_color = ("#00FF88" if avg_surp > 5
                          else "#FFB84D" if avg_surp > 0
                          else "#FF3B5C")
    else:
        raw = km.get("avg_earnings_surprise", "")
        extracted = _extract_percent(raw) if raw else None
        if _looks_empty(extracted):
            avg_surp_str = "N/D"
            avg_surp_tooltip = ("Sorpresa promedio no disponible — requiere historial detallado "
                                "de earnings que la fuente puede no exponer.")
            avg_surp_color = "#5A6878"
        else:
            avg_surp_str = extracted
            avg_surp_tooltip = "Sorpresa promedio estimada por el agente de catalizadores."
            avg_surp_color = "#FFB84D"

    sentiment_raw = km.get("analyst_sentiment_trend") or "stable"
    sentiment_display = _clean_tile_value(sentiment_raw, max_len=12)
    sent_level_str = sentiment_raw.lower()
    sent_color = ("#00FF88" if "improv" in sent_level_str else
                  "#FF3B5C" if "deterior" in sent_level_str else "#FFB84D")

    _render_metric_tiles([
        {"icon": "📅", "label": "Próximo Earnings",
         "value": days_str, "color": next_color, "tooltip": next_tooltip},
        {"icon": "🎯", "label": "Beat Rate",
         "value": beat_rate_str, "color": beat_color, "tooltip": beat_tooltip},
        {"icon": "🚀", "label": "Sorpresa Promedio",
         "value": avg_surp_str, "color": avg_surp_color, "tooltip": avg_surp_tooltip},
        {"icon": "📊", "label": "Tendencia Analistas",
         "value": sentiment_display, "color": sent_color,
         "tooltip": "Dirección de las revisiones de estimaciones y ratings del consenso (factor de momentum potente)."},
    ])

    # ── Historial de Earnings Surprises (bar chart) ──
    if eh and len(eh) >= 2:
        st.markdown('<div class="section-title-bar">📈 Track Record de Earnings</div>',
                    unsafe_allow_html=True)
        fig = build_earnings_history_chart(eh)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key=f"chart_catalysts_earn_{analysis.ticker}")

    # ── Top Catalyst destacado ──
    top_cat = rd.get("top_catalyst", "")
    if top_cat:
        st.markdown(f"""
        <div class="alpha-opportunity-card">
            <div class="alpha-opportunity-header">
                <span class="alpha-opportunity-icon">⚡</span>
                <span class="alpha-opportunity-title">Catalizador #1 — Potencial Mayor</span>
            </div>
            <div class="alpha-opportunity-body">{top_cat}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Próximo evento clave ──
    key_event = km.get("key_upcoming_event", "")
    if key_event and key_event not in ("—", ""):
        _render_insight_card("Próximo Evento Crítico", str(key_event),
                             color="#4A9EFF", icon="🔔")

    # ── Pros / Cons ──
    _render_pros_cons(report,
                      pros_title="✅ Top 3 Catalizadores Alcistas",
                      cons_title="⚠️ Top 3 Riesgos de Evento")

    _render_analysis_card(report, title="Análisis de Catalizadores")


def render_macro(analysis: StockAnalysis):
    report = analysis.reports.get("macro")
    if report is None:
        st.info("Análisis macro no disponible.")
        return

    _render_agent_header(report)
    km = report.key_metrics or {}
    rd = report.raw_data or {}

    # ── Status pills del entorno macro ──
    st.markdown('<div class="section-title-bar">🌍 Diagnóstico Macro</div>',
                unsafe_allow_html=True)

    env_raw = km.get("market_environment") or "neutral"
    env_level = "good" if "risk-on" in env_raw.lower() else "bad" if "risk-off" in env_raw.lower() else "neutral"

    sec_raw = km.get("sector_momentum") or "neutral"
    sec_level = "good" if "strong" in sec_raw.lower() else "bad" if "weak" in sec_raw.lower() else "neutral"

    yc_raw = km.get("yield_curve") or "normal"
    yc_level = "good" if "normal" in yc_raw.lower() else "warn" if "flat" in yc_raw.lower() else "bad"

    vix_raw = km.get("vix_level") or "low <20"
    vix_level = "good" if "<20" in vix_raw else "warn" if "20-30" in vix_raw else "bad"

    _render_status_pills([
        {"label": "Entorno Mercado",
         "value": _clean_tile_value(env_raw, max_len=12),
         "level": env_level, "sub": "Risk On / Off"},
        {"label": "Momentum Sector",
         "value": _clean_tile_value(sec_raw, max_len=12),
         "level": sec_level, "sub": f"Sector: {rd.get('sector', '—')}"},
        {"label": "Curva Yield",
         "value": _clean_tile_value(yc_raw, max_len=12),
         "level": yc_level, "sub": "10Y-2Y spread"},
        {"label": "Nivel VIX",
         "value": _clean_tile_value(vix_raw, max_len=12),
         "level": vix_level, "sub": "Volatilidad esperada"},
    ])

    # ── Sector heatmap ──
    from data.market_data import get_macro_data
    macro = get_macro_data() or {}
    sector_perf = macro.get("sector_performance", {})

    if sector_perf:
        st.markdown('<div class="section-title-bar">📊 Rotación Sectorial (1Y)</div>',
                    unsafe_allow_html=True)
        fig = build_sector_heatmap(sector_perf)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key=f"chart_macro_sector_heatmap_{analysis.ticker}")

    # ── Snapshot de indicadores macro ──
    st.markdown('<div class="section-title-bar">📡 Snapshot Macro</div>',
                unsafe_allow_html=True)
    indicators_macro = [
        ("S&P 500",  macro.get("sp500", {}),  "index"),
        ("NASDAQ",   macro.get("nasdaq", {}), "index"),
        ("VIX",      macro.get("vix", {}),    "vol"),
        ("DXY",      macro.get("dxy", {}),    "dollar"),
        ("10Y YIELD", macro.get("tnx", {}),    "yield"),
        ("GOLD",     macro.get("gold", {}),   "price"),
    ]
    cols = st.columns(6, gap="small")
    for i, (label, data, fmt) in enumerate(indicators_macro):
        if not isinstance(data, dict):
            data = {}
        curr = data.get("current")
        chg = data.get("1m_change", 0) or 0
        if isinstance(curr, (int, float)):
            if fmt == "yield":
                val_str = f"{curr:.2f}%"
            elif fmt == "price":
                val_str = f"${curr:,.2f}"
            elif fmt == "index":
                val_str = f"{curr:,.0f}"
            else:
                val_str = f"{curr:.2f}"
        else:
            val_str = "—"
        color = "#00FF88" if chg >= 0 else "#FF3B5C"
        arrow = "▲" if chg >= 0 else "▼"
        chg_str = f"{arrow} {abs(chg):.2f}% (1M)" if isinstance(curr, (int, float)) else "—"
        with cols[i]:
            st.markdown(f"""
            <div class="market-pulse-card">
                <div class="pulse-label">{label}</div>
                <div class="pulse-value">{val_str}</div>
                <div class="pulse-change" style="color:{color};">{chg_str}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Pros / Cons ──
    _render_pros_cons(report,
                      pros_title="🌤️ Top 3 Vientos de Cola",
                      cons_title="🌪️ Top 3 Vientos en Contra")

    # ── Macro verdict ──
    _render_insight_card("Veredicto Macro", rd.get("macro_verdict", ""),
                         color="#FFB84D", icon="🎯")

    _render_analysis_card(report, title="Análisis Macro Completo")


def render_sentiment(analysis: StockAnalysis):
    report = analysis.reports.get("sentiment")
    if report is None:
        st.info("Análisis de sentimiento no disponible.")
        return

    _render_agent_header(report)
    km = report.key_metrics or {}
    rd = report.raw_data or {}

    # ── Gauge grande de sentimiento + 2 status pills ──
    col_gauge, col_pills = st.columns([1, 2])

    with col_gauge:
        fig = build_sentiment_gauge(report.score, height=260)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key=f"chart_sent_gauge_{analysis.ticker}")

    with col_pills:
        st.markdown('<div class="section-title-bar" style="margin-top:0;">📰 Estado de la Narrativa</div>',
                    unsafe_allow_html=True)

        mom_raw = km.get("sentiment_momentum") or "stable"
        mom_level = ("good" if "improv" in mom_raw.lower() else
                     "bad" if "deterior" in mom_raw.lower() else "neutral")

        cont_raw = km.get("contrarian_signal") or "no signal"
        cont_level = ("good" if "buy the fear" in cont_raw.lower() else
                      "bad" if "sell the hype" in cont_raw.lower() else "neutral")

        narr_raw = km.get("narrative_theme") or "—"

        rep_raw = km.get("reputational_risk") or "low"
        rep_level = ("good" if "low" in rep_raw.lower() else
                     "bad" if "high" in rep_raw.lower() else "warn")

        _render_status_pills([
            {"label": "Momentum Sentimiento",
             "value": _clean_tile_value(mom_raw, max_len=14),
             "level": mom_level, "sub": "Mejorando o deteriorando"},
            {"label": "Tema Narrativo",
             "value": _clean_tile_value(narr_raw, max_len=14),
             "level": "neutral",
             "sub": f"{rd.get('news_count', 0)} noticias"},
            {"label": "Señal Contraria",
             "value": _clean_tile_value(cont_raw, max_len=14),
             "level": cont_level, "sub": "Buy fear / Sell hype"},
            {"label": "Riesgo Reputacional",
             "value": _clean_tile_value(rep_raw, max_len=10),
             "level": rep_level, "sub": "ESG / regulatorio"},
        ])

    # ── Pros / Cons ──
    _render_pros_cons(report,
                      pros_title="📈 Top 3 Señales Positivas",
                      cons_title="📉 Top 3 Riesgos de Narrativa")

    # ── Narrativa dominante ──
    _render_insight_card("Narrativa Dominante", rd.get("dominant_narrative", ""),
                         color="#4A9EFF", icon="📖")

    # ── Oportunidad detectada (si hay divergencia) ──
    opportunity = rd.get("opportunity", "")
    if opportunity and "No hay divergencia" not in opportunity:
        st.markdown(f"""
        <div class="alpha-opportunity-card">
            <div class="alpha-opportunity-header">
                <span class="alpha-opportunity-icon">⚡</span>
                <span class="alpha-opportunity-title">Divergencia Sentimiento-Fundamentales</span>
            </div>
            <div class="alpha-opportunity-body">{opportunity}</div>
        </div>
        """, unsafe_allow_html=True)

    _render_analysis_card(report, title="Análisis de Sentimiento")


def render_risk(analysis: StockAnalysis):
    report = analysis.reports.get("risk")
    if report is None:
        st.info("Análisis de riesgo no disponible.")
        return

    _render_agent_header(report)
    km = report.key_metrics or {}
    rd = report.raw_data or {}

    # ── KPI tiles de Riesgo ──
    st.markdown('<div class="section-title-bar">⚖️ Métricas de Riesgo</div>',
                unsafe_allow_html=True)

    vol      = _safe_num(km.get("volatility_atr_pct"))
    rr_raw   = km.get("risk_reward", "")

    # Get computed values as fallback
    computed = rd.get("computed_risk", {}) or {}
    if vol is None: vol = computed.get("atr_pct")

    # Recalcular Pérdida Máxima y Ganancia Potencial usando el PRECIO ACTUAL en vivo
    # (más útil que el entry hipotético del agente)
    from data.market_data import get_company_info
    info_live = get_company_info(analysis.ticker) or {}
    current_price = info_live.get("current_price") or analysis.entry_price

    downside = None
    upside = None
    rr_num = None
    if current_price and analysis.stop_loss:
        downside = (current_price - analysis.stop_loss) / current_price * 100
    if current_price and analysis.target_price:
        upside = (analysis.target_price - current_price) / current_price * 100
    if downside and downside > 0 and upside is not None:
        rr_num = upside / downside

    rr_clean = f"{rr_num:.1f}:1" if rr_num is not None else _extract_rr_ratio(rr_raw)

    _render_metric_tiles([
        {"icon": "💔", "label": "Pérdida Máxima",
         "value": f"-{downside:.1f}%" if downside is not None else "—",
         "color": "#FF3B5C",
         "tooltip": "Pérdida porcentual si el precio cae al nivel de protección desde el PRECIO ACTUAL del mercado."},
        {"icon": "🚀", "label": "Ganancia Potencial",
         "value": f"+{upside:.1f}%" if upside is not None else "—",
         "color": "#00FF88",
         "tooltip": "Ganancia porcentual si el precio alcanza el target desde el PRECIO ACTUAL del mercado."},
        {"icon": "⚖️", "label": "R/R Ratio",
         "value": rr_clean,
         "color": ("#00FF88" if (rr_num or 0) >= 3 else
                   "#FFB84D" if (rr_num or 0) >= 2 else "#FF3B5C"),
         "tooltip": "Risk/Reward Ratio calculado desde el precio actual. Mínimo aceptable 2:1, ideal 3:1 o superior."},
        {"icon": "📊", "label": "Volatilidad ATR",
         "value": f"{vol:.1f}%" if vol is not None else "—",
         "color": "#4A9EFF" if (vol or 0) < 3 else "#FFB84D" if (vol or 0) < 5 else "#FF3B5C",
         "tooltip": "Average True Range como % del precio. >5% indica activo muy volátil con drawdowns frecuentes."},
    ])

    # ── R/R Chart visual — usando PRECIO ACTUAL como referencia ──
    if analysis.stop_loss and analysis.target_price:
        from data.market_data import get_company_info
        info_live = get_company_info(analysis.ticker) or {}
        current_price = info_live.get("current_price") or analysis.entry_price
        if current_price:
            st.markdown('<div class="section-title-bar">🎯 Upside / Downside vs Precio Actual</div>',
                        unsafe_allow_html=True)
            fig = build_rr_chart(current_price, analysis.stop_loss,
                                 analysis.target_price, analysis.ticker)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                            key=f"chart_risk_tab_rr_{analysis.ticker}")

    # ── Pros / Cons ──
    _render_pros_cons(report,
                      pros_title="✅ Top 3 Aspectos Favorables",
                      cons_title="⚠️ Top 3 Riesgos Identificados")

    _render_analysis_card(report, title="Análisis Completo de Riesgo")


# ──────────────────────────────────────────────────────────────────────
def render_agent_tab(analysis: StockAnalysis, agent_key: str):
    report = analysis.reports.get(agent_key)
    if not report:
        st.info("Análisis no disponible para este agente.")
        return

    icon = AGENT_ICONS.get(report.agent_name, "📊")

    col_score, col_conv = st.columns([1, 3])
    with col_score:
        score = report.score
        color = score_color(score)
        css_class = score_css_class(score)
        st.markdown(
            f'<div style="text-align:center;padding:16px;background:#0F1419;border:1px solid #1E2530;border-radius:8px;border-top:3px solid {color};">'
            f'<div style="font-family:JetBrains Mono;font-size:3rem;font-weight:700;color:{color};">{score:.0f}</div>'
            f'<div style="font-size:0.7rem;color:#7A8898;text-transform:uppercase;letter-spacing:0.1em;">Score / 100</div>'
            f'<div style="font-size:0.75rem;color:{color};margin-top:4px;">{report.conviction}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Sub-scores
        if report.sub_scores:
            st.markdown("**Sub-scores**")
            for k, v in report.sub_scores.items():
                if not k.endswith("_snowflake") and isinstance(v, (int, float)):
                    bar_width = min(v / 34 * 100, 100)
                    st.markdown(
                        f'<div style="margin:4px 0;">'
                        f'<div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#7A8898;">'
                        f'<span>{k.replace("_", " ").title()}</span><span>{v:.0f}</span></div>'
                        f'<div style="background:#1A2030;border-radius:2px;height:4px;margin-top:2px;">'
                        f'<div style="background:{color};width:{bar_width}%;height:100%;border-radius:2px;"></div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

    with col_conv:
        st.markdown(f"#### {icon} {report.agent_name}")
        st.markdown(
            f'<div class="analysis-card"><div class="analysis-text">{report.analysis}</div></div>',
            unsafe_allow_html=True,
        )

        col_p, col_c = st.columns(2)
        with col_p:
            if report.pros:
                st.markdown("**Positivos**")
                for p in report.pros[:3]:
                    st.markdown(f'<div style="color:#00FF88;font-size:0.82rem;padding:2px 0;">✓ {p}</div>', unsafe_allow_html=True)
        with col_c:
            if report.cons:
                st.markdown("**Riesgos / Negativos**")
                for c in report.cons[:3]:
                    st.markdown(f'<div style="color:#FF3B5C;font-size:0.82rem;padding:2px 0;">⚠ {c}</div>', unsafe_allow_html=True)

        # Key metrics
        if report.key_metrics:
            st.markdown("---")
            st.markdown("**Métricas Clave**")
            cols = st.columns(3)
            for i, (k, v) in enumerate(report.key_metrics.items()):
                with cols[i % 3]:
                    st.metric(label=k.replace("_", " ").title(), value=str(v) if v else "N/A")

    # Raw data extra (insights específicos de cada agente)
    extra_keys = {
        "fundamentals":  ["dcf_thesis", "earnings_quality"],
        "future":        ["future_thesis", "key_risks"],
        "catalysts":     ["top_catalyst"],
        "institutional": ["key_insight"],
        "macro":         ["macro_verdict"],
        "sentiment":     ["dominant_narrative", "opportunity"],
        "risk":          ["risk_verdict", "stop_rationale"],
    }

    extra = extra_keys.get(agent_key, [])
    for key in extra:
        val = report.raw_data.get(key)
        if val and isinstance(val, str) and len(val) > 5:
            label = key.replace("_", " ").title()
            st.markdown(
                f'<div style="background:#141920;border:1px solid #2A3545;border-radius:4px;padding:10px;margin-top:8px;">'
                f'<div style="font-size:0.7rem;color:#7A8898;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">{label}</div>'
                f'<div style="font-size:0.85rem;color:#C8D0D8;line-height:1.6;">{val}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ── Scan Results Tab ──────────────────────────────────────────────────────
def render_scan_results():
    # ── Top action bar: volver a filtros + volver al home ──
    col_filters, col_home, _spacer = st.columns([2, 2, 6])
    with col_filters:
        if st.button("🔧 Ajustar filtros", key="scan_back_to_filters",
                     use_container_width=True,
                     help="Volver al screener para modificar los filtros"):
            st.session_state.scanner_config_open = True
            st.session_state._show_scan_results = False
            st.rerun()
    with col_home:
        if st.button("⌂ Volver al Home", key="scan_back_home",
                     use_container_width=True):
            st.session_state.scan_results = []
            st.session_state.current_scan_id = None
            st.session_state._show_scan_results = False
            st.rerun()

    st.markdown("## 🌐 Resultados del Scan de Mercado")
    n = len(st.session_state.scan_results)
    st.markdown(f"*{n} candidatos pasaron los filtros del screener*")

    # ── Diagnóstico del último scan (visible cuando hay pocos resultados) ──
    diag = st.session_state.get("_scan_diagnostics", {}) or {}
    universe = diag.get("universe_count", 0)
    passing = diag.get("passing_count", 0)
    err = diag.get("error")
    if universe or err:
        # Mostrar SIEMPRE el diagnóstico para entender qué pasó
        if err:
            color = "#FF3B5C"
            msg = f"❌ Error de TradingView: {err}"
        elif universe < 100:
            color = "#FFB84D"
            msg = (f"⚠️ TradingView devolvió solo <strong>{universe} acciones</strong> "
                   f"al universo crudo (esperábamos 1000+). De ellas, <strong>{passing}</strong> "
                   f"pasaron los filtros. Puede ser rate-limit transitorio — reintenta en 1-2 min.")
        else:
            color = "#4A9EFF"
            msg = (f"✓ TradingView devolvió <strong>{universe} acciones</strong> al universo crudo. "
                   f"De ellas, <strong>{passing}</strong> pasaron los filtros del usuario.")
        st.markdown(
            f'<div style="background:#141920;border-left:3px solid {color};'
            f'padding:10px 14px;margin:8px 0 16px 0;border-radius:4px;'
            f'font-size:0.82rem;color:#C8D0D8;">{msg}</div>',
            unsafe_allow_html=True,
        )

    if not st.session_state.scan_results:
        # Si el flag indica que JUSTO terminó un scan pero quedó vacío,
        # explicamos por qué (no es un "no hay scan reciente").
        if st.session_state.get("_show_scan_results"):
            st.warning(
                "El scan se ejecutó pero **0 acciones pasaron los filtros**.\n\n"
                "Causas posibles:\n"
                "- Los filtros son demasiado estrictos (prueba con menos restricciones).\n"
                "- Yahoo Finance está rate-limitando temporalmente. Espera 1-2 minutos y vuelve a intentar.\n\n"
                "Puedes ajustar los filtros desde 'Escanear el Mercado' o lanzar un análisis individual de una acción específica."
            )
        else:
            st.info("No hay resultados de scan. Usa el botón '🌐 Escanear el Mercado' en el home.")
        return


    # Header tabla
    headers = ["Ticker", "Empresa", "Sector", "Precio", "Market Cap", "Stage", "RS Score", "Mom 6M", "Mom 3M", "Score", "Acción"]
    col_widths = [1, 2, 2, 1, 1.2, 0.8, 1, 1, 1, 1, 1.2]

    header_html = '<div style="display:grid;grid-template-columns:' + " ".join([f"{w}fr" for w in col_widths]) + ';gap:8px;padding:6px 8px;background:#141920;border-radius:4px;margin-bottom:4px;">'
    for h in headers:
        header_html += f'<div style="font-size:0.65rem;color:#7A8898;text-transform:uppercase;letter-spacing:0.08em;font-weight:600;">{h}</div>'
    header_html += "</div>"
    st.markdown(header_html, unsafe_allow_html=True)

    for result in st.session_state.scan_results:
        color = score_color(result.screener_score)
        stage_color = {"2": "#00FF88", "1": "#FFA500", "0": "#7A8898"}.get(str(result.stage), "#FF3B5C")
        mom_color = "#00FF88" if result.momentum_6m > 0 else "#FF3B5C"
        mom3_color = "#00FF88" if result.momentum_3m > 0 else "#FF3B5C"

        mktcap = f"${result.market_cap / 1e9:.1f}B" if result.market_cap > 0 else "N/A"

        row_html = f"""<div style="display:grid;grid-template-columns:{" ".join([f'{w}fr' for w in col_widths])};gap:8px;padding:8px 8px;border-bottom:1px solid #1A2030;align-items:center;">
            <div style="font-family:JetBrains Mono;font-size:0.85rem;font-weight:700;color:#E0E0E0;">{result.ticker}</div>
            <div style="font-size:0.78rem;color:#C8D0D8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{result.name[:25]}</div>
            <div style="font-size:0.75rem;color:#7A8898;">{result.sector[:18]}</div>
            <div style="font-family:JetBrains Mono;font-size:0.85rem;color:#E0E0E0;">${result.price:.2f}</div>
            <div style="font-size:0.8rem;color:#7A8898;">{mktcap}</div>
            <div style="font-family:JetBrains Mono;font-size:0.85rem;font-weight:700;color:{stage_color};">S{result.stage}</div>
            <div style="font-family:JetBrains Mono;font-size:0.85rem;color:#9B59FF;">{result.rs_score:.0f}</div>
            <div style="font-family:JetBrains Mono;font-size:0.85rem;color:{mom_color};">{'+' if result.momentum_6m > 0 else ''}{result.momentum_6m:.1f}%</div>
            <div style="font-family:JetBrains Mono;font-size:0.85rem;color:{mom3_color};">{'+' if result.momentum_3m > 0 else ''}{result.momentum_3m:.1f}%</div>
            <div style="font-family:JetBrains Mono;font-size:0.9rem;font-weight:700;color:{color};">{result.screener_score:.0f}</div>
        </div>"""
        st.markdown(row_html, unsafe_allow_html=True)

        # Botón "Ver más" → abre el Quick View (preview rápido SIN IA, GRATIS):
        # gráfica, métricas clave, noticias y performance. Reemplaza al análisis
        # completo directo desde el scan para no gastar créditos en cada acción.
        # Si el ticker ya tiene un análisis completo en sesión, lo muestra directo.
        if st.button(f"🔍 Ver más — {result.ticker}",
                     key=f"scan_quickview_{result.ticker}",
                     use_container_width=True):
            if result.ticker in st.session_state.analyses:
                st.session_state.selected_ticker = result.ticker
                st.session_state.quick_view_ticker = None
            else:
                st.session_state.quick_view_ticker = result.ticker
                st.session_state.selected_ticker = None
                # Marca que viene del scan → el Quick View ocultará el botón
                # de lanzar análisis completo.
                st.session_state.quick_view_from_scan = True
            st.rerun()


# ── Scanner Config Page ──────────────────────────────────────────────────

# Accent colors por categoría — cohesivos con la paleta del dashboard
SCANNER_ACCENTS = {
    "size":      "#FFB84D",   # naranja — tamaño / valor
    "stage":     "#00FF88",   # verde — tendencia
    "rs":        "#9B59FF",   # morado — fortaleza
    "momentum":  "#4A9EFF",   # azul — momentum
    "proximity": "#00D4FF",   # cyan — máximo anual
    "sector":    "#E94B7B",   # rosa — sectores
    "liquidity": "#7BA8FF",   # azul claro — liquidez
    "results":   "#FFD740",   # amarillo — cantidad
}


def _scanner_pill(label: str, key: str, active: bool, sub: str = "") -> bool:
    """Renderiza un pill button uniforme. type='primary' si activo (naranja brand)."""
    btn_type = "primary" if active else "secondary"
    return st.button(label, key=key, type=btn_type, use_container_width=True,
                     help=sub if sub else None)


def _scanner_card_open(icon: str, title: str, subtitle: str, accent: str, tooltip: str = ""):
    """Abre una card de scanner con accent color, icon container y header.
    Devuelve un placeholder en el que el caller pondrá los pills."""
    help_html = f'<span class="scanner-help" data-tooltip="{tooltip}">?</span>' if tooltip else ''
    st.markdown(f"""
    <div class="scanner-card" style="--accent: {accent};">
        <div class="scanner-card-head">
            <div class="scanner-card-icon-box">
                <span class="scanner-card-icon-emoji">{icon}</span>
            </div>
            <div class="scanner-card-titles">
                <div class="scanner-card-title">{title}</div>
                <div class="scanner-card-subtitle">{subtitle}</div>
            </div>
            {help_html}
        </div>
        <div class="scanner-card-body">
    """, unsafe_allow_html=True)


def _scanner_card_close():
    st.markdown('</div></div>', unsafe_allow_html=True)


def render_scanner_config():
    """Página de configuración del scanner — filtros amigables que se mapean
    a parámetros técnicos del ScreenerAgent."""
    from config.settings import SCANNER_DEFAULTS
    from dashboard.scanner_filters import (
        SIZE_OPTIONS, STAGE_OPTIONS, RS_OPTIONS, MOMENTUM_OPTIONS,
        PROXIMITY_OPTIONS, SECTOR_OPTIONS, LIQUIDITY_OPTIONS, MAX_RESULTS_OPTIONS,
        build_screener_filters,
    )

    # Asegurar que el state tenga estructura completa
    if not isinstance(st.session_state.get("scanner_filters"), dict):
        st.session_state.scanner_filters = dict(SCANNER_DEFAULTS)
    for k, v in SCANNER_DEFAULTS.items():
        if k not in st.session_state.scanner_filters:
            st.session_state.scanner_filters[k] = v

    sf = st.session_state.scanner_filters

    # ── Hero ──
    st.markdown("""
    <div class="scanner-hero">
        <div class="scanner-hero-eyebrow">◇ Búsqueda personalizada</div>
        <div class="scanner-hero-title">Encuentra las mejores acciones</div>
        <div class="scanner-hero-sub">
            Configura los criterios que coinciden con tu estilo. Cada filtro está pensado
            para que sea fácil de entender — el término técnico está abajo del título por si
            quieres profundizar.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Top bar: Volver (izq) ─ espacio ─ Restablecer (der), simétricos ──
    col_back, _spacer_top, col_reset = st.columns([2, 7, 2])
    with col_back:
        if st.button("← Volver al inicio", key="scanner_back_top", use_container_width=True):
            st.session_state.scanner_config_open = False
            st.rerun()
    with col_reset:
        if st.button("🔄 Restablecer", key="scanner_reset_top",
                     use_container_width=True,
                     help="Volver a los filtros por defecto"):
            st.session_state.scanner_filters = dict(SCANNER_DEFAULTS)
            st.rerun()

    st.markdown('<div class="scanner-section-divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # FILTRO PRINCIPAL: Sectores de interés (tarjetón full-width)
    # st.container(border=True) crea un wrapper que envuelve TODO el contenido
    # (header + toggles + pills) como una sola tarjeta visual. El anchor invisible
    # nos permite estilarla vía CSS :has() sin afectar otros containers.
    # ════════════════════════════════════════════════════════════════════
    with st.container(border=True):
        st.markdown('<div class="scanner-pri-anchor"></div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="scanner-pri-header">
            <span class="scanner-pri-icon">🏭</span>
            <div class="scanner-pri-titles">
                <div class="scanner-pri-title">Sectores de interés</div>
                <div class="scanner-pri-subtitle">Elige uno o varios — sin selección = todos los sectores</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Toggles "Todos / Ninguno"
        tog_a, tog_b, _spacer = st.columns([1, 1, 6])
        with tog_a:
            if st.button("✓ Todos", key="sec_all_top", use_container_width=True):
                sf["sectors"] = [opt["key"] for opt in SECTOR_OPTIONS]
                st.rerun()
        with tog_b:
            if st.button("✕ Ninguno", key="sec_none_top", use_container_width=True):
                sf["sectors"] = []
                st.rerun()

        # Grid de sectores con iconos — 4 columnas (full-width tiene espacio sobrado)
        sec_per_row_top = 4
        for row_start in range(0, len(SECTOR_OPTIONS), sec_per_row_top):
            row_opts = SECTOR_OPTIONS[row_start:row_start + sec_per_row_top]
            row_cols = st.columns(sec_per_row_top)
            for i, opt in enumerate(row_opts):
                with row_cols[i]:
                    active = opt["key"] in (sf.get("sectors") or [])
                    btn_type = "primary" if active else "secondary"
                    icon = opt.get("icon", "")
                    label = f"{icon}  {opt['label']}" if icon else opt["label"]
                    if st.button(label, key=f"sec_top_{opt['key']}", type=btn_type,
                                 use_container_width=True):
                        current = list(sf.get("sectors") or [])
                        if active:
                            current = [x for x in current if x != opt["key"]]
                        else:
                            current.append(opt["key"])
                        sf["sectors"] = current
                        st.rerun()

    # ── GRID de filtros secundarios (2 columnas) ──
    col_l, col_r = st.columns(2, gap="medium")

    # 1. Tamaño de la empresa (multi-select) — IZQ
    with col_l:
        _scanner_card_open(
            "🏢", "Tamaño de la empresa", "Capitalización de mercado",
            SCANNER_ACCENTS["size"],
            tooltip="Filtra por el tamaño total de la empresa según su valor en bolsa. Las megacaps son las más estables; las micro caps tienen más volatilidad pero más potencial."
        )
        size_cols = st.columns(len(SIZE_OPTIONS))
        for i, opt in enumerate(SIZE_OPTIONS):
            with size_cols[i]:
                active = opt["key"] in (sf.get("size_buckets") or [])
                if _scanner_pill(opt["label"], f"size_{opt['key']}", active, sub=opt["sub"]):
                    current = list(sf.get("size_buckets") or [])
                    if active:
                        current = [x for x in current if x != opt["key"]]
                    else:
                        current.append(opt["key"])
                    sf["size_buckets"] = current
                    st.rerun()
        _scanner_card_close()

    # 2. Tendencia técnica (multi-select) — DER
    with col_r:
        _scanner_card_open(
            "📈", "Tendencia técnica", "Stage Analysis (Minervini)",
            SCANNER_ACCENTS["stage"],
            tooltip="Identifica en qué fase del ciclo está la acción. Stage 2 es la fase alcista ideal; Stage 1 es base de acumulación; Stage 3 y 4 son distribución y caída."
        )
        stage_cols = st.columns(len(STAGE_OPTIONS))
        for i, opt in enumerate(STAGE_OPTIONS):
            with stage_cols[i]:
                active = opt["key"] in (sf.get("stages") or [])
                if _scanner_pill(opt["label"], f"stage_{opt['key']}", active, sub=opt["sub"]):
                    current = list(sf.get("stages") or [])
                    if active:
                        current = [x for x in current if x != opt["key"]]
                    else:
                        current.append(opt["key"])
                    sf["stages"] = current
                    st.rerun()
        _scanner_card_close()

    # 3. Fortaleza vs el mercado (single) — IZQ
    with col_l:
        _scanner_card_open(
            "💪", "Fortaleza vs el mercado", "Relative Strength vs S&P 500",
            SCANNER_ACCENTS["rs"],
            tooltip="Mide qué tan mejor o peor se ha comportado la acción comparada con el S&P 500. RS alto = la acción está liderando el mercado."
        )
        rs_cols = st.columns(len(RS_OPTIONS))
        for i, opt in enumerate(RS_OPTIONS):
            with rs_cols[i]:
                active = sf.get("rs_strength") == opt["key"]
                if _scanner_pill(opt["label"], f"rs_{opt['key']}", active, sub=opt["sub"]):
                    sf["rs_strength"] = opt["key"]
                    st.rerun()
        _scanner_card_close()

    # 4. Momentum reciente (single) — DER
    with col_r:
        _scanner_card_open(
            "🚀", "Momentum reciente", "Retorno últimos 6 meses",
            SCANNER_ACCENTS["momentum"],
            tooltip="Cómo se ha movido la acción en los últimos 6 meses. Aceleración indica un movimiento alcista fuerte y sostenido."
        )
        mom_cols = st.columns(len(MOMENTUM_OPTIONS))
        for i, opt in enumerate(MOMENTUM_OPTIONS):
            with mom_cols[i]:
                active = sf.get("momentum_6m") == opt["key"]
                if _scanner_pill(opt["label"], f"mom_{opt['key']}", active, sub=opt["sub"]):
                    sf["momentum_6m"] = opt["key"]
                    st.rerun()
        _scanner_card_close()

    # 5. Cercanía al máximo anual (single) — IZQ
    with col_l:
        _scanner_card_open(
            "🏔️", "Cercanía al máximo anual", "Distancia al 52W High",
            SCANNER_ACCENTS["proximity"],
            tooltip="Qué tan cerca está la acción de su precio más alto de los últimos 12 meses. Cerca del máximo suele indicar fortaleza; lejos puede ser oportunidad o caída."
        )
        prox_cols = st.columns(len(PROXIMITY_OPTIONS))
        for i, opt in enumerate(PROXIMITY_OPTIONS):
            with prox_cols[i]:
                active = sf.get("proximity_high") == opt["key"]
                if _scanner_pill(opt["label"], f"prox_{opt['key']}", active, sub=opt["sub"]):
                    sf["proximity_high"] = opt["key"]
                    st.rerun()
        _scanner_card_close()

    # NOTE: Sectores movido al filtro principal arriba (full-width destacado).

    # 7. Liquidez mínima (single) — IZQ
    with col_l:
        _scanner_card_open(
            "💧", "Liquidez mínima", "Volumen promedio diario",
            SCANNER_ACCENTS["liquidity"],
            tooltip="Cuántas acciones se negocian al día en promedio. Alta liquidez = más fácil entrar y salir sin afectar el precio."
        )
        liq_cols = st.columns(len(LIQUIDITY_OPTIONS))
        for i, opt in enumerate(LIQUIDITY_OPTIONS):
            with liq_cols[i]:
                active = sf.get("liquidity") == opt["key"]
                if _scanner_pill(opt["label"], f"liq_{opt['key']}", active, sub=opt["sub"]):
                    sf["liquidity"] = opt["key"]
                    st.rerun()
        _scanner_card_close()

    # 8. Cantidad de resultados (single) — DER
    with col_r:
        _scanner_card_open(
            "📋", "Cantidad de resultados", "Top N por puntaje del screener",
            SCANNER_ACCENTS["results"],
            tooltip="Cuántas acciones ver al final. Más resultados = más opciones pero más ruido. 20 es suficiente para revisar a fondo."
        )
        mr_cols = st.columns(len(MAX_RESULTS_OPTIONS))
        for i, opt in enumerate(MAX_RESULTS_OPTIONS):
            with mr_cols[i]:
                active = sf.get("max_results") == opt["key"]
                if _scanner_pill(opt["label"], f"mr_{opt['key']}", active, sub=opt["sub"]):
                    sf["max_results"] = opt["key"]
                    st.rerun()
        _scanner_card_close()

    # ── Barra de acción inferior — Ejecutar centrado con halo dorado + Volver ──
    st.markdown('<div class="scanner-section-divider"></div>', unsafe_allow_html=True)

    # 1) Botón principal "Ejecutar búsqueda" centrado con halo dorado giratorio.
    #    Usamos st.container() + anchor invisible para envolverlo y aplicarle
    #    el efecto vía CSS :has(). El anchor es invisible (display:none).
    _spacer_l1, run_col, _spacer_r1 = st.columns([1, 2, 1])
    with run_col:
        with st.container():
            st.markdown('<div class="ejecutar-glow-anchor"></div>',
                        unsafe_allow_html=True)
            if st.button("🚀 Ejecutar búsqueda", key="scanner_run",
                         use_container_width=True, type="primary"):
                tech_filters = build_screener_filters(sf)
                st.session_state.scanner_config_open = False
                run_market_scan(filters=tech_filters)

    # 2) Botón secundario "Volver" centrado debajo, más estrecho, simétrico.
    _spacer_l2, back_col, _spacer_r2 = st.columns([1.5, 1, 1.5])
    with back_col:
        if st.button("← Volver", key="scanner_back_bottom",
                     use_container_width=True):
            st.session_state.scanner_config_open = False
            st.rerun()


# ── Quick View (compact instant dashboard, sin AI processing) ───────────

def render_quick_view(ticker: str):
    """Dashboard compacto e instantáneo de una acción con datos en vivo de yfinance.
    Sin AI processing — todo se carga en 1-3 segundos."""
    from data.market_data import get_company_info, get_price_history, get_news

    # Loading: skeleton + spinner centrado mientras cargan los datos
    loading_placeholder = st.empty()
    loading_placeholder.markdown(
        _skeleton_quick_view_html() + _spinner_overlay_html(
            text=f"CARGANDO {ticker}",
            sub="Obteniendo precio, noticias y métricas en vivo…"
        ),
        unsafe_allow_html=True,
    )

    info = get_company_info(ticker)
    df = get_price_history(ticker, period="1y")
    news = get_news(ticker, max_items=6)

    loading_placeholder.empty()

    name = info.get("name", ticker)
    current_price = info.get("current_price") or 0

    # ── Calcular performance multi-timeframe ─────────────────────────
    day_change = week_change = month_change = year_change = 0
    high_52w = info.get("52w_high", 0) or 0
    low_52w = info.get("52w_low", 0) or 0

    if not df.empty:
        latest = float(df["Close"].iloc[-1])
        if not current_price:
            current_price = latest
        prev = float(df["Close"].iloc[-2]) if len(df) > 1 else latest
        day_change = (latest - prev) / prev * 100 if prev else 0
        if len(df) >= 6:
            week_change = (latest - float(df["Close"].iloc[-6])) / float(df["Close"].iloc[-6]) * 100
        if len(df) >= 22:
            month_change = (latest - float(df["Close"].iloc[-22])) / float(df["Close"].iloc[-22]) * 100
        year_start = float(df["Close"].iloc[0])
        year_change = (latest - year_start) / year_start * 100 if year_start else 0

    # ── Header con precio + cambio día ───────────────────────────────
    day_color = "#00FF88" if day_change >= 0 else "#FF3B5C"
    arrow = "▲" if day_change >= 0 else "▼"

    col_back, col_spacer = st.columns([1, 5])
    with col_back:
        if st.button("← Volver al Hub", use_container_width=True, key="qv_back"):
            st.session_state.quick_view_ticker = None
            st.rerun()

    st.markdown(f"""
    <div class="qv-header">
        <span class="qv-ticker">{ticker}</span>
        <span class="qv-name">{name}</span>
        <span class="qv-price">${current_price:.2f}</span>
        <span class="qv-change" style="color:{day_color};">{arrow} {abs(day_change):.2f}% día</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Row 1: Chart + Métricas clave ────────────────────────────────
    col_chart, col_metrics = st.columns([2, 1], gap="medium")

    with col_chart:
        st.markdown('<div class="qv-section-title">📈 PRECIO 6 MESES</div>', unsafe_allow_html=True)
        from dashboard.charts import build_quick_chart
        fig = build_quick_chart(df, ticker)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key=f"chart_quickview_price_{ticker}")

    with col_metrics:
        st.markdown('<div class="qv-section-title">📊 MÉTRICAS CLAVE</div>', unsafe_allow_html=True)

        mcap = info.get("market_cap", 0) or 0
        if mcap >= 1e12:
            mcap_str = f"${mcap/1e12:.2f}T"
        elif mcap >= 1e9:
            mcap_str = f"${mcap/1e9:.1f}B"
        else:
            mcap_str = f"${mcap/1e6:.0f}M" if mcap > 0 else "—"

        pe = info.get("pe_ratio")
        pe_str = f"{pe:.1f}" if isinstance(pe, (int, float)) and pe > 0 else "—"

        fwd_pe = info.get("forward_pe")
        fwd_pe_str = f"{fwd_pe:.1f}" if isinstance(fwd_pe, (int, float)) and fwd_pe > 0 else "—"

        ps = info.get("ps_ratio")
        ps_str = f"{ps:.1f}" if isinstance(ps, (int, float)) and ps > 0 else "—"

        avg_vol = info.get("avg_volume", 0) or 0
        vol_str = f"{avg_vol/1e6:.1f}M" if avg_vol >= 1e6 else f"{avg_vol/1e3:.0f}K" if avg_vol > 0 else "—"

        beta = info.get("beta")
        beta_str = f"{beta:.2f}" if isinstance(beta, (int, float)) else "—"

        div_yield = (info.get("dividend_yield") or 0) * 100
        div_str = f"{div_yield:.2f}%" if div_yield > 0 else "—"

        metrics = [
            ("Market Cap",   mcap_str,   "#FFB84D"),
            ("P/E Trailing", pe_str,     "#4A9EFF"),
            ("P/E Forward",  fwd_pe_str, "#4A9EFF"),
            ("P/S",          ps_str,     "#9B59FF"),
            ("Vol Promedio", vol_str,    "#FFB84D"),
            ("Beta",         beta_str,   "#9B59FF"),
            ("Div Yield",    div_str,    "#00FF88"),
        ]
        for label, val, color in metrics:
            st.markdown(f"""
            <div class="qv-metric">
                <span class="qv-metric-label">{label}</span>
                <span class="qv-metric-value" style="color:{color};">{val}</span>
            </div>
            """, unsafe_allow_html=True)

    # ── Row 2: Performance multi-timeframe ───────────────────────────
    st.markdown('<div class="qv-section-title" style="margin-top:8px;">⚡ PERFORMANCE</div>', unsafe_allow_html=True)
    perf_cols = st.columns(6, gap="small")
    range_pct = ((current_price - low_52w) / (high_52w - low_52w) * 100) if (high_52w - low_52w) > 0 else 50

    perf_data = [
        ("1D",  day_change,    "%"),
        ("1W",  week_change,   "%"),
        ("1M",  month_change,  "%"),
        ("1Y", year_change,    "%"),
        ("52W Range", range_pct, " pct"),
        ("52W H/L", None,      ""),
    ]

    for i, (label, val, suffix) in enumerate(perf_data):
        with perf_cols[i]:
            if label == "52W Range":
                color = "#FFB84D" if 20 < val < 80 else ("#00FF88" if val >= 80 else "#FF3B5C")
                val_str = f"{val:.0f}%"
            elif label == "52W H/L":
                color = "#C8D0D8"
                val_str = f"${low_52w:.0f} / ${high_52w:.0f}"
            elif val is None:
                color = "#C8D0D8"
                val_str = "—"
            else:
                color = "#00FF88" if val >= 0 else "#FF3B5C"
                ar = "▲" if val >= 0 else "▼"
                val_str = f"{ar} {abs(val):.1f}%"

            st.markdown(f"""
            <div class="qv-perf-tile">
                <div class="qv-perf-label">{label}</div>
                <div class="qv-perf-value" style="color:{color};">{val_str}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Row 3: Noticias + Contexto ───────────────────────────────────
    col_news, col_ctx = st.columns([2, 1], gap="medium")

    with col_news:
        st.markdown('<div class="qv-section-title" style="margin-top:14px;">📰 NOTICIAS RECIENTES</div>', unsafe_allow_html=True)
        if news:
            for item in news[:5]:
                publisher = item.get("publisher", "—")
                title = item.get("title", "")
                age = item.get("age_hours", 0) or 0
                age_label = f"{age:.0f}h" if age < 48 else f"{age/24:.0f}d"
                freshness_emoji = "🔥" if age < 24 else "⚡" if age < 168 else "📅"
                link = item.get("link", "#")

                st.markdown(f"""
                <a href="{link}" target="_blank" class="qv-news-link">
                <div class="qv-news-item">
                    <div class="qv-news-meta">
                        <span class="qv-news-freshness">{freshness_emoji} {age_label}</span>
                        <span class="qv-news-publisher">{publisher}</span>
                    </div>
                    <div class="qv-news-title">{title}</div>
                </div>
                </a>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="qv-empty">Sin noticias recientes disponibles</div>', unsafe_allow_html=True)

    with col_ctx:
        st.markdown('<div class="qv-section-title" style="margin-top:14px;">🏭 CONTEXTO</div>', unsafe_allow_html=True)

        sector = info.get("sector", "—") or "—"
        industry = info.get("industry", "—") or "—"
        country = info.get("country", "—") or "—"
        employees = info.get("employees", 0) or 0
        emp_str = f"{employees:,}" if employees else "—"

        analyst_target = info.get("target_price")
        target_str = "—"
        if isinstance(analyst_target, (int, float)) and analyst_target > 0 and current_price > 0:
            upside = (analyst_target - current_price) / current_price * 100
            arrow_t = "▲" if upside >= 0 else "▼"
            target_str = f"${analyst_target:.2f} ({arrow_t} {abs(upside):.1f}%)"

        rating = (info.get("analyst_rating") or "—").upper()

        ctx_items = [
            ("Sector",   sector),
            ("Industria", industry[:30] + "..." if len(industry) > 30 else industry),
            ("País",     country),
            ("Empleados", emp_str),
            ("Target Analistas", target_str),
            ("Rating",   rating),
        ]
        for label, val in ctx_items:
            st.markdown(f"""
            <div class="qv-context-item">
                <span class="qv-context-label">{label}</span>
                <span class="qv-context-value">{val}</span>
            </div>
            """, unsafe_allow_html=True)

    # ── CTA: Lanzar análisis profundo ────────────────────────────────
    # Solo se muestra si el Quick View NO viene del scan. Desde el scan no se
    # muestra nada (para analizar, el usuario vuelve al inicio y lo escribe).
    if not st.session_state.get("quick_view_from_scan"):
        st.markdown('<div style="margin-top:24px;"></div>', unsafe_allow_html=True)
        _, cta_col, _ = st.columns([1, 2, 1])
        with cta_col:
            if st.button(
                f"🔍  EJECUTAR ANÁLISIS DLP DE {ticker}",
                use_container_width=True,
                key="qv_full_analysis",
                type="primary",
            ):
                st.session_state.quick_view_ticker = None
                run_analysis(ticker)


# ── Welcome / Central Hub ─────────────────────────────────────────────────
POPULAR_TICKERS = ["NVDA", "AAPL", "MSFT", "TSLA", "GOOGL", "META", "AMZN", "AMD", "AVGO", "NFLX", "COIN", "PLTR"]


def render_welcome():
    # Hero
    st.markdown("""
    <div class="alpha-hero">
        <div class="alpha-hero-brand">◈ DLP MARKET ANALYZER</div>
        <div class="alpha-hero-tagline">Analiza en profundidad cualquier acción del NYSE & NASDAQ</div>
        <div class="alpha-divider"></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Action Card central — usa casi todo el ancho del viewport.
    # En iframe cuadrado de Whop antes se cortaba "ESCANEAR EL MERCAD" — ahora
    # con un centro de 96% + botones con padding compacto, "ESCANEAR EL MERCADO"
    # cabe completo siempre.
    _, center_col, _ = st.columns([1, 50, 1])

    with center_col:
        st.markdown('<div class="action-label-new">◇  ANALIZA UNA ACCIÓN O ESCANEA EL MERCADO COMPLETO</div>', unsafe_allow_html=True)

        ticker_input = st.text_input(
            label="Ticker",
            label_visibility="collapsed",
            placeholder="NVDA · AAPL · MSFT · TSLA  →  introduce un ticker y haz clic en Analizar",
            key="hero_ticker_input",
        ).upper().strip()

        # Asimetría 1:1.3 — el botón derecho (Escanear el Mercado) tiene un
        # 30% más de ancho porque su texto es más largo. Garantiza que quepa.
        btn_col1, btn_col2 = st.columns([1, 1.3], gap="small")
        with btn_col1:
            analyze_btn = st.button("🔍  Análisis DLP", use_container_width=True, key="hero_analyze", type="primary")
        with btn_col2:
            scan_btn = st.button("🌐  Escanear el Mercado", use_container_width=True, key="hero_scan", type="primary")

        if analyze_btn and ticker_input:
            # Validar el ticker ANTES de gastar créditos de Anthropic.
            # validate_ticker() es gratis (~200ms via TradingView, sin Claude).
            # Si el usuario escribió "NVDA " con espacio → lo limpia a "NVDA".
            # Si escribió "NVD@" → muestra error claro, no lanza análisis.
            # Si escribió "FAKE123" → muestra "no encontrado en NYSE/NASDAQ".
            from data.market_data import validate_ticker
            is_valid, clean_ticker, error_msg = validate_ticker(ticker_input)
            if not is_valid:
                st.error(error_msg)
            else:
                # Cooldown de 60 min entre análisis — vive SOLO en st.session_state
                # (RAM volátil de la sesión actual). Recargar la pestaña lo resetea
                # por diseño. Es un freno suave para no saturar el servidor.
                ANALYSIS_COOLDOWN_SEC = 3600  # 60 minutos
                last_finished = st.session_state.get("_last_analysis_finished_at", 0)
                elapsed = time.time() - last_finished
                if elapsed < ANALYSIS_COOLDOWN_SEC:
                    remaining_min = max(1, int(round((ANALYSIS_COOLDOWN_SEC - elapsed) / 60)))
                    st.warning(
                        f"⏳ Tienes un cooldown de ~**{remaining_min} min** activo "
                        f"para no saturar el servidor."
                    )
                else:
                    run_analysis(clean_ticker)
        if scan_btn:
            # Abre la página de configuración del scanner (no corre scan directo)
            st.session_state.scanner_config_open = True
            st.rerun()

    # ── Quick Access Tickers ──────────────────────────────────────────
    st.markdown('<div class="section-header">⊕  Acceso Rápido — Tickers Populares</div>', unsafe_allow_html=True)

    # Spinner visible mientras cargan los precios en vivo (~1-3s)
    tickers_loader = st.empty()
    tickers_loader.markdown("""
    <div class="section-spinner-wrap">
        <div class="section-spinner"></div>
        <div class="section-spinner-text">Cargando precios en vivo…</div>
    </div>
    """, unsafe_allow_html=True)

    from data.market_data import get_live_snapshot
    snapshot = {}
    try:
        snapshot = get_live_snapshot(POPULAR_TICKERS)
    except Exception:
        pass

    # Quitar el spinner — vamos a renderizar las cards reales abajo
    tickers_loader.empty()

    # Grid 6 cols x 2 rows — layout multi-línea + botón invisible overlay
    rows = [POPULAR_TICKERS[:6], POPULAR_TICKERS[6:12]]
    for row_idx, row in enumerate(rows):
        cols = st.columns(6, gap="small")
        for i, ticker in enumerate(row):
            with cols[i]:
                data = snapshot.get(ticker, {})
                price = data.get("price")
                change = data.get("change_pct", 0) or 0

                change_color = "#00FF88" if change >= 0 else "#FF3B5C"
                arrow = "▲" if change >= 0 else "▼"
                price_str = f"${price:.2f}" if price else "—"
                change_str = f"{arrow} {abs(change):.2f}%" if price else "—"
                anim_delay = (row_idx * 6 + i) * 0.06

                # Card visual con layout multi-línea (TICKER / $price / ▲ X%)
                st.markdown(f"""
                <div class="ticker-tile" style="animation-delay:{anim_delay}s;">
                    <div class="tt-symbol">{ticker}</div>
                    <div class="tt-price">{price_str}</div>
                    <div class="tt-change" style="color:{change_color};">{change_str}</div>
                </div>
                """, unsafe_allow_html=True)

                # Botón pequeño con flecha ▾ debajo de la card — abre Quick View
                if st.button("▾", key=f"quick_{ticker}", use_container_width=True,
                             help=f"Ver dashboard rápido de {ticker}"):
                    if ticker in st.session_state.analyses:
                        st.session_state.selected_ticker = ticker
                        st.session_state.quick_view_ticker = None
                    else:
                        st.session_state.quick_view_ticker = ticker
                        st.session_state.selected_ticker = None
                        # Desde el home SÍ se permite lanzar análisis desde el
                        # Quick View → marcamos que NO viene del scan.
                        st.session_state.quick_view_from_scan = False
                    st.rerun()

    # ── Live Market Pulse ─────────────────────────────────────────────
    st.markdown('<div class="section-header">📡  Live Market Pulse</div>', unsafe_allow_html=True)

    # Spinner mientras cargan los datos macro (~2-5s — el más lento)
    macro_loader = st.empty()
    macro_loader.markdown("""
    <div class="section-spinner-wrap">
        <div class="section-spinner"></div>
        <div class="section-spinner-text">Cargando índices y sectores…</div>
    </div>
    """, unsafe_allow_html=True)

    from data.market_data import get_macro_data
    try:
        macro = get_macro_data()
    except Exception:
        macro = {}

    # Quitar el spinner — vamos a renderizar los datos reales abajo
    macro_loader.empty()

    # (label, key del macro, formato del valor)
    pulse_items = [
        ("S&P 500",   "sp500",  "index"),     # puntos del índice ^GSPC
        ("NASDAQ",    "nasdaq", "index"),     # puntos del índice ^IXIC
        ("VIX",       "vix",    "vol"),       # nivel del VIX
        ("DXY",       "dxy",    "dollar"),    # US Dollar Index
        ("10Y YIELD", "tnx",    "yield"),     # rendimiento Treasury en %
        ("GOLD",      "gold",   "price"),     # precio en USD por onza
    ]

    def _format_pulse(curr, fmt):
        """Formato COMPACTO para que NUNCA se rompa el número en cards
        angostas del iframe cuadrado. Ej: 7383.74 → '7,384' (sin decimales
        si >= 1000) o 25709 → '25.7K'."""
        if not isinstance(curr, (int, float)):
            return "—"
        if fmt == "yield":
            return f"{curr:.2f}%"
        if fmt == "price":
            # Gold: $4,353 (sin decimales si >= 1000)
            if curr >= 1000:
                return f"${curr:,.0f}"
            return f"${curr:,.2f}"
        if fmt == "index":
            # S&P 500, NASDAQ: 7,384 / 25,709 (sin decimales — cabe mejor)
            return f"{curr:,.0f}"
        # vol, dollar y default: 2 decimales (cabe siempre)
        return f"{curr:.2f}"

    cols = st.columns(6, gap="small")
    for i, (label, key, fmt) in enumerate(pulse_items):
        data = macro.get(key, {})
        if not isinstance(data, dict):
            data = {}
        curr = data.get("current")
        chg = data.get("1m_change", 0) or 0
        change_color = "#00FF88" if chg >= 0 else "#FF3B5C"
        change_symbol = "▲" if chg >= 0 else "▼"

        val_str = _format_pulse(curr, fmt)
        chg_str = f"{change_symbol} {abs(chg):.2f}% (1M)" if isinstance(curr, (int, float)) else "—"

        anim_delay = i * 0.05

        with cols[i]:
            st.markdown(f"""
            <div class="market-pulse-card" style="animation-delay:{anim_delay}s;">
                <div class="pulse-label">{label}</div>
                <div class="pulse-value">{val_str}</div>
                <div class="pulse-change" style="color:{change_color};">{chg_str}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Sector Performance ─────────────────────────────────────────────
    sector_perf = macro.get("sector_performance", {}) if macro else {}
    if sector_perf:
        st.markdown('<div class="section-header">🌍  Rotación Sectorial (1Y)</div>', unsafe_allow_html=True)

        # Spinner independiente mientras se construye el heatmap de Plotly
        # (~200-500ms) — feedback visual consistente con las otras 2 secciones.
        sector_loader = st.empty()
        sector_loader.markdown("""
        <div class="section-spinner-wrap">
            <div class="section-spinner"></div>
            <div class="section-spinner-text">Cargando rotación sectorial…</div>
        </div>
        """, unsafe_allow_html=True)

        from dashboard.charts import build_sector_heatmap
        fig = build_sector_heatmap(sector_perf)

        # Quitar el spinner — vamos a renderizar el heatmap abajo
        sector_loader.empty()

        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False},
                        key="chart_welcome_sector_heatmap")


# ── Main App ──────────────────────────────────────────────────────────────
def main():
    render_header()

    # En lugar del sidebar lateral, mostramos un botón "Volver al Home"
    # centrado arriba SOLO cuando el usuario no está en la welcome screen.
    # En welcome ya hay un hero claro — no se necesita botón redundante.
    in_welcome = (
        not st.session_state.get("selected_ticker") and
        not st.session_state.get("quick_view_ticker") and
        not st.session_state.scan_results and
        not st.session_state.get("scanner_config_open") and
        not st.session_state.get("_show_scan_results")
    )
    if not in_welcome:
        render_top_nav()

    selected = st.session_state.selected_ticker
    qv = st.session_state.get("quick_view_ticker")

    # Prioridad: Quick View > Full Analysis > Scanner Config > Scan Results > Welcome
    if qv and qv not in st.session_state.analyses:
        render_quick_view(qv)
        return

    if not selected or selected not in st.session_state.analyses:
        # Si el scanner config está abierto, mostrarlo (tiene prioridad sobre scan_results y welcome)
        if st.session_state.get("scanner_config_open"):
            render_scanner_config()
            return
        if st.session_state.scan_results or st.session_state.get("_show_scan_results"):
            render_scan_results()
        else:
            render_welcome()
        return

    analysis = st.session_state.analyses[selected]

    # Botón "← Volver al Scan" — visible cuando hay resultados de scan activos
    if st.session_state.scan_results:
        scan_count = len(st.session_state.scan_results)
        col_back, col_spacer = st.columns([1, 5])
        with col_back:
            if st.button(f"← Volver al Scan ({scan_count})", key="back_to_scan",
                         use_container_width=True,
                         help="Volver a los resultados del último scan de mercado"):
                st.session_state.selected_ticker = None
                st.session_state.quick_view_ticker = None
                st.rerun()

    # Header del ticker (premium)
    rec_badge = get_recommendation_badge(analysis.recommendation)
    score = analysis.composite_score
    color = score_color(score)
    compound_badge = ('<span class="compound-machine-badge">💎 COMPOUNDER</span>'
                      if getattr(analysis, "is_compound_machine", False) else "")

    st.markdown(
        f'<div class="stock-header">'
        f'<span class="stock-header-ticker">{analysis.ticker}</span>'
        f'<span class="stock-header-name">{analysis.company_name}</span>'
        f'<span>{rec_badge}</span>'
        f'{compound_badge}'
        f'<span class="stock-header-score" style="color:{color};">{score:.1f}<span style="font-size:0.75rem;color:#7A8898;font-weight:400;">/100</span></span>'
        f'<span style="color:#5A6878;font-family:JetBrains Mono;font-size:0.7rem;">{analysis.timestamp[:10]}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Tabs principales
    tabs = st.tabs([
        "📊 Overview",
        "📈 Técnico",
        "💰 Fundamentales",
        "🔭 Futuro",
        "🏦 Smart Money",
        "🌐 Contexto del Mercado",
        "⚖️ Riesgo",
    ])

    with tabs[0]:
        render_overview(analysis)
    with tabs[1]:
        render_technical(analysis)
    with tabs[2]:
        render_fundamentals(analysis)
    with tabs[3]:
        render_future(analysis)
    with tabs[4]:
        render_institutional(analysis)
    with tabs[5]:
        # Contexto del Mercado = Catalizadores + Macro + Sentimiento.
        # Cada uno mantiene sus gráficas/tarjetas/gauge intactos — solo
        # se renderizan dentro del mismo tab con separadores claros.
        render_catalysts(analysis)
        st.markdown('<div style="margin:28px 0;border-top:1px solid #1E2530;"></div>',
                    unsafe_allow_html=True)
        render_macro(analysis)
        st.markdown('<div style="margin:28px 0;border-top:1px solid #1E2530;"></div>',
                    unsafe_allow_html=True)
        render_sentiment(analysis)
    with tabs[6]:
        render_risk(analysis)


if __name__ == "__main__":
    main()
