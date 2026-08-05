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
    BLOOMBERG_CSS, get_recommendation_badge, rec_display_label, score_color,
    score_css_class, AGENT_ICONS, AGENT_ICON_SLUG,
)
from dashboard.charts import (
    build_price_chart, build_gauge, build_snowflake,
    build_score_breakdown, build_mini_gauge, build_rr_chart,
    build_sector_heatmap, build_sector_rotation, build_compact_gauge, build_rsi_gauge,
    build_metric_bars, build_earnings_history_chart,
    build_sentiment_gauge, build_holders_bars, build_mountain_chart,
    STATIC_CHART_CONFIG,
)

# ── Config de página ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="DLP Market Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(BLOOMBERG_CSS, unsafe_allow_html=True)


# ── Render de gráficas: SIEMPRE bloqueadas ────────────────────────────────

def _chart(fig, **kwargs):
    """Dibuja una gráfica de Plotly BLOQUEADA: no se puede hacer zoom, ni
    arrastrar, ni reencuadrar con doble clic, ni tocar los ejes.

    Punto ÚNICO por el que pasan TODAS las gráficas de la app (tacómetros,
    barras, velas, radar, heatmap…), así ninguna se queda suelta aunque su
    builder monte el layout por su cuenta.

    `dragmode=False` es lo que desactiva el zoom por arrastre; el resto lo cubre
    STATIC_CHART_CONFIG. A propósito NO se usa `staticPlot`, que bloquearía
    también el hover y perderíamos los tooltips con los datos. Ante cualquier
    error se dibuja la figura igualmente: nunca rompe el render."""
    try:
        fig.update_layout(dragmode=False)
    except Exception:
        pass
    kwargs.setdefault("use_container_width", True)
    kwargs["config"] = STATIC_CHART_CONFIG
    # Tarjeta envolvente (misma estética que .analysis-card). El ancla oculta
    # `.chart-card-anchor` es lo que el CSS busca con :has(), igual que ya se
    # hace con `.scanner-pri-anchor`: sin ella, un :has([stPlotlyChart]) genérico
    # también pintaría cualquier contenedor ANCESTRO que tuviera una gráfica
    # dentro. El padding vive en el WRAPPER, nunca en [stPlotlyChart], para no
    # alterar la medición de ancho de Plotly (use_container_width).
    with st.container(border=True):
        st.markdown('<div class="chart-card-anchor"></div>', unsafe_allow_html=True)
        st.plotly_chart(fig, **kwargs)


# ── State inicial ─────────────────────────────────────────────────────────

# Máximo de análisis en memoria (RAM) a la vez. Coincide con
# MAX_ANALYSES_ON_DISK (persistence) para que la barra lateral, el disco y la
# nube muestren lo mismo: los 10 más recientes.
MAX_HISTORY_IN_MEMORY = 10


def _sb_mark_used(ticker: str):
    """Marca un ticker como recién usado para el ORDEN del historial lateral.

    Necesario porque un análisis servido desde el caché compartido (Upstash)
    conserva su timestamp ORIGINAL (que puede ser de hace semanas): sin esta
    marca, el análisis que el usuario acaba de pedir caía al FONDO de la lista.
    No se toca analysis.timestamp a propósito — es la fecha real del análisis
    y se muestra en el header; sobrescribirla mentiría sobre su antigüedad."""
    try:
        st.session_state.setdefault("_sb_last_used", {})[ticker.upper()] = \
            datetime.now().isoformat()
    except Exception:
        pass


def _sb_recency_key(analysis) -> str:
    """Clave de orden del historial: último uso en esta sesión si existe;
    si no, el timestamp del análisis. Ambos en ISO → comparables como texto."""
    last_used = (st.session_state.get("_sb_last_used") or {}).get(
        getattr(analysis, "ticker", "").upper())
    return last_used or getattr(analysis, "timestamp", "") or ""


def _prune_analyses_in_memory():
    """Mantiene en session_state.analyses solo los MAX_HISTORY_IN_MEMORY más
    recientes (por último uso / timestamp). NO borra nada de disco/nube — solo
    libera RAM. Usa la misma clave que el orden del sidebar para que un análisis
    recién pedido (aunque venga de Upstash con timestamp viejo) nunca sea el
    primero en ser expulsado."""
    analyses = st.session_state.get("analyses") or {}
    if len(analyses) <= MAX_HISTORY_IN_MEMORY:
        return
    keep = sorted(analyses.values(),
                  key=_sb_recency_key,
                  reverse=True)[:MAX_HISTORY_IN_MEMORY]
    keep_tickers = {a.ticker for a in keep}
    for t in list(analyses.keys()):
        if t not in keep_tickers:
            del st.session_state.analyses[t]


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
        "sidebar_collapsed":   False,                # columna lateral minimizada
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

    # ── Cargar historial: disco local primero (los 10 más recientes) ──
    if not st.session_state.get("_history_loaded"):
        try:
            from data.persistence import load_all_analyses as disk_load
            disk_saved = disk_load()
            valid = [a for a in disk_saved.values() if _is_valid_analysis(a)]
            valid.sort(key=lambda a: getattr(a, "timestamp", "") or "", reverse=True)
            for analysis in valid[:MAX_HISTORY_IN_MEMORY]:
                if analysis.ticker not in st.session_state.analyses:
                    st.session_state.analyses[analysis.ticker] = analysis
        except Exception:
            pass

        # ── Hidratación desde la nube (Upstash) ──────────────────────────
        # El disco de Streamlit Cloud es efímero: si se reinició el contenedor
        # llegará vacío. En ese caso rehidratamos el historial desde Redis para
        # que "se queden ahí" los últimos análisis. Solo pagamos el costo de red
        # cuando el disco NO llenó los 10 (caso reinicio). Fallback total.
        try:
            if len(st.session_state.analyses) < MAX_HISTORY_IN_MEMORY:
                from data.cache_store import (
                    get_recent_analysis_tickers, get_cached_analysis,
                )
                for tk in get_recent_analysis_tickers():
                    if len(st.session_state.analyses) >= MAX_HISTORY_IN_MEMORY:
                        break
                    if tk in st.session_state.analyses:
                        continue
                    # `solo_fresco=False`: aquí SÍ queremos los viejos, porque
                    # esta es la lista del historial. Al hacer clic en uno de
                    # más de 24 h se rehará desde cero, pero primero tiene que
                    # aparecer en la barra lateral.
                    obj = get_cached_analysis(tk, solo_fresco=False)
                    if obj is not None:
                        st.session_state.analyses[tk] = obj
        except Exception:
            pass

        _prune_analyses_in_memory()
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

        // ── Auto-ajuste del VALOR de las tarjetas ────────────────────────
        // El valor debe leerse COMPLETO y en UNA sola línea. Si el texto es
        // largo ("deteriorándose", "incertidumbre") no cabe al ancho de la
        // tarjeta, así que le bajamos la fuente hasta que quepa. Se mide el
        // ancho REAL del elemento, con lo que funciona igual en escritorio y
        // en el iframe estrecho de Whop.
        //
        // Guardas: acotado a esas 2 clases; `data-fit` recuerda TEXTO + ANCHO ya
        // ajustados para no re-medir en cada barrido (sin parpadeo ni bucles).
        // El ancho forma parte de la clave a propósito: si solo se guardara el
        // texto, al estrechar la ventana el texto seguiría siendo el mismo y la
        // tarjeta nunca se recalcularía (se quedaría desbordada). Con el ancho
        // dentro, cualquier cambio de tamaño dispara un nuevo ajuste — y como se
        // parte de fontSize='' también vuelve a crecer al ensanchar.
        // Hay además un mínimo de fuente para que nunca quede ilegible.
        var FIT_SELECTOR = '.status-pill-value, .kpi-tile-value';
        // Suelo de 7px: medido en el peor caso real (ventana de ~900px, donde la
        // fila de 4 tarjetas deja pills de solo ~96px y una palabra como
        // "Contrayendo" no entra ni a 9px). Sigue siendo legible y es preferible
        // a partir la palabra en dos o recortarla.
        var FIT_MIN_PX = 7;

        function fitText(root) {
            if (!root) return;
            try {
                var nodes = root.querySelectorAll(FIT_SELECTOR);
                for (var i = 0; i < nodes.length; i++) {
                    var el = nodes[i];
                    try {
                        // Ancho 0 = aún no visible (pestaña oculta): se ajustará
                        // cuando se muestre, en un barrido posterior.
                        if (!el.clientWidth) continue;
                        var key = (el.textContent || '') + '|' + el.clientWidth;
                        if (el.getAttribute('data-fit') === key) continue;
                        // OJO: el tamaño se aplica con prioridad `important`.
                        // Las media queries de estrecho declaran
                        // `.status-pill-value { font-size: ... !important }`, que
                        // GANA a un style inline normal: sin `important` aquí el
                        // ajuste se calculaba pero no se veía (el texto seguía
                        // desbordado justo en los anchos donde más falta hace).
                        el.style.removeProperty('font-size');   // partir del CSS
                        var size = parseFloat(window.getComputedStyle(el).fontSize);
                        var guard = 0;
                        while (el.scrollWidth > el.clientWidth + 1 &&
                               size > FIT_MIN_PX && guard++ < 60) {
                            size -= 0.5;
                            el.style.setProperty('font-size', size + 'px', 'important');
                        }
                        el.setAttribute('data-fit', key);
                    } catch (e) {}
                }
            } catch (e) {}
        }

        // Nukear en todos los documentos accesibles: el propio y window.top
        function nukeEverywhere() {
            nukeBranding(doc);
            try { if (window.top && window.top.document) nukeBranding(window.top.document); } catch (e) {}
            try { if (window.parent && window.parent.document) nukeBranding(window.parent.document); } catch (e) {}
            // El contenido de la app vive en el documento padre, no en este iframe.
            try { if (window.parent && window.parent.document) fitText(window.parent.document); } catch (e) {}
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
            st.error("ANTHROPIC_API_KEY no configurada o inválida. Verifica el archivo .env")
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


# ── Sidebar: Brand + Historial (últimos 10 análisis · 3 escaneos) ─────────
# La recomendación se codifica en la key del botón para que el CSS pinte el
# color del rating sin tocar el markup.
_REC_TO_SLUG = {
    "MUY ATRACTIVO":  "strong_buy",
    "ATRACTIVO":      "buy",
    "EN OBSERVACIÓN": "watch",
    "EVITAR":         "pass",
    "STRONG BUY":     "strong_buy",
    "BUY":            "buy",
    "WATCH":          "watch",
    "PASS":           "pass",
}


def _sb_go_home():
    st.session_state.selected_ticker = None
    st.session_state.quick_view_ticker = None
    st.session_state.scan_results = []
    st.session_state.current_scan_id = None
    st.session_state._show_scan_results = False
    st.session_state.scanner_config_open = False


def _sb_load_analysis(ticker: str):
    """Abre un análisis del historial y limpia los otros modos.

    Si el análisis tiene más de 24 h, NO se muestra tal cual: se marca como
    pendiente para que `main()` lo rehaga desde cero con su pantalla de carga.
    La bandera es necesaria porque esta función corre dentro de `with
    st.sidebar:` — llamar aquí a `run_analysis` dibujaría el esqueleto y el
    spinner DENTRO de la barra lateral."""
    st.session_state.selected_ticker = ticker
    st.session_state.quick_view_ticker = None
    st.session_state.scan_results = []
    st.session_state.current_scan_id = None
    st.session_state._show_scan_results = False
    st.session_state.scanner_config_open = False

    try:
        from data.cache_store import analisis_fresco
        guardado = (st.session_state.analyses or {}).get(ticker)
        if guardado is None or not analisis_fresco(guardado):
            st.session_state._pending_analysis = ticker
    except Exception:
        # Ante cualquier duda se rehace: es el lado que da un análisis al día.
        st.session_state._pending_analysis = ticker


def _sb_load_scan(scan_id: str):
    """Carga un escaneo guardado (disco primero, nube como respaldo) y lo
    muestra en pantalla."""
    results = []
    try:
        from data.persistence import load_scan_by_id
        results = load_scan_by_id(scan_id)
    except Exception:
        results = []
    if not results:
        # Respaldo en la nube (Upstash) — el disco de Cloud es efímero.
        try:
            from data.cache_store import get_cloud_scan_results
            from agents.screener import ScreenerResult
            for r in get_cloud_scan_results(scan_id):
                try:
                    results.append(ScreenerResult(**r))
                except Exception:
                    continue
        except Exception:
            results = results or []
    st.session_state.scan_results = results
    st.session_state.current_scan_id = scan_id
    st.session_state._show_scan_results = True
    st.session_state.selected_ticker = None
    st.session_state.quick_view_ticker = None
    st.session_state.scanner_config_open = False
    st.session_state._scan_diagnostics = {}


def _sidebar_scan_labels():
    """Devuelve los 3 escaneos más recientes como (scan_id, label, count).

    Disco primero (I/O local, barato). Solo consulta la nube (Upstash) si el
    disco NO llenó los 3 — típico tras un reinicio del contenedor con disco
    efímero. Así NO añadimos latencia de red en cada rerun cuando el disco ya
    tiene el historial. Fallback total."""
    merged = {}
    try:
        from data.persistence import get_scan_history_labels
        for sid, label, count in get_scan_history_labels():
            merged[sid] = (sid, label, count)
    except Exception:
        pass
    if len(merged) < 3:
        try:
            from data.cache_store import get_recent_cloud_scans
            for sid, label, count in get_recent_cloud_scans():
                merged.setdefault(sid, (sid, label, count))
        except Exception:
            pass
    out = sorted(merged.values(), key=lambda x: x[0], reverse=True)
    return out[:3]


@st.cache_data(show_spinner=False)
def _logo_data_uri() -> str:
    """Logo del Club DLP como data-URI en base64.

    Se incrusta en el HTML en vez de servirse como fichero: así no depende de
    rutas estáticas y se ve igual en local y en Render. Si el asset faltara,
    devuelve "" y el sidebar cae al logo tipográfico de siempre."""
    try:
        import base64
        from pathlib import Path
        p = Path(__file__).parent / "assets" / "logo_dlp.png"
        return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()
    except Exception:
        return ""


def render_sidebar():
    with st.sidebar:
        # ── Brand ───────────────────────────────────────────────────────
        _logo = _logo_data_uri()
        if _logo:
            st.markdown(
                f'<div class="sidebar-brand">'
                f'<img class="sidebar-brand-img" src="{_logo}" alt="Club DLP">'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            # Respaldo: si el PNG no está, se mantiene el logo tipográfico.
            st.markdown("""
            <div class="sidebar-brand">
                <div class="sidebar-brand-logo">◈ DLP</div>
                <div class="sidebar-brand-sub">MARKET ANALYZER</div>
            </div>
            """, unsafe_allow_html=True)

        # ── Botón minimizar columna (el CSS lo posiciona sobre el logo) ──
        if st.button("«", key="sidebar_collapse_btn", help="Minimizar la columna"):
            st.session_state.sidebar_collapsed = True
            st.rerun()

        # ── Home ─────────────────────────────────────────────────────────
        if st.button("⌂  Volver al Inicio", use_container_width=True, key="sidebar_home"):
            _sb_go_home()
            st.rerun()

        # ── Historial: Análisis de Acciones ─────────────────────────────
        st.markdown('<div class="sb-section-title">◈  Análisis · Acciones</div>',
                    unsafe_allow_html=True)

        analyses = st.session_state.get("analyses", {}) or {}
        # Orden: lo más recientemente USADO arriba (no solo lo más recién
        # generado — un análisis reutilizado de Upstash trae timestamp viejo).
        analyses_sorted = sorted(
            analyses.values(),
            key=_sb_recency_key,
            reverse=True,
        )[:MAX_HISTORY_IN_MEMORY]

        if not analyses_sorted:
            st.markdown('<div class="sb-empty">Sin análisis guardados todavía</div>',
                        unsafe_allow_html=True)
        else:
            for analysis in analyses_sorted:
                ticker = analysis.ticker
                rec = analysis.recommendation or "EN OBSERVACIÓN"
                rec_slug = _REC_TO_SLUG.get(rec, "watch")
                # Key → clase CSS: solo caracteres seguros (BRK.B → BRK_B)
                tk_safe = "".join(c if (c.isalnum() or c in "_-") else "_"
                                  for c in ticker)
                score = float(getattr(analysis, "composite_score", 0) or 0)
                color = score_color(score)
                badge_html = get_recommendation_badge(rec)

                # Tarjeta clicable: el container keyed recibe la clase
                # st-key-sbcard_… en su propio stVerticalBlock (mismo patrón
                # que sectbar_) y el CSS lo pinta como tarjeta. El sufijo
                # __rk_ codifica el rating para el acento izquierdo SIN
                # reutilizar __rec_ (así el CSS legacy no matchea jamás).
                # Termómetro (mismo .meter/.meter-dot de los KPI tiles) con el
                # dot en la posición del DLP Score y SU MISMO color, para que
                # número y dot cuenten la misma historia.
                _pct = max(0.0, min(100.0, score))
                _glow = {"#3DD68C": "61,214,140", "#E2B25C": "226,178,92",
                         "#F1495F": "241,73,95"}.get(color, "226,178,92")
                meter_html = (
                    f'<div class="meter"><span class="meter-dot" '
                    f'style="left:{_pct:.0f}%;background:{color};'
                    f'box-shadow:0 0 0 3px rgba({_glow},0.18), '
                    f'0 0 8px rgba({_glow},0.45);"></span></div>'
                )

                with st.container(key=f"sbcard_{tk_safe}__rk_{rec_slug}"):
                    st.markdown(
                        f'<div class="sb-card-head">'
                        f'<span class="sb-card-ticker">◈ {ticker}</span>'
                        f'<span class="sb-card-score" style="--sc:{color};">'
                        f'{score:.1f}'
                        f'<span class="sb-card-score-max">/100</span></span>'
                        f'</div>'
                        f'<div class="sb-badge-wrap">{badge_html}</div>'
                        f'{meter_html}',
                        unsafe_allow_html=True,
                    )
                    # Overlay invisible (CSS: absolute inset:0, opacity:0)
                    # que hace clicable TODA la tarjeta. Label real por
                    # accesibilidad y tests.
                    if st.button(f"◈ {ticker}", key=f"sbcardbtn_{tk_safe}"):
                        _sb_load_analysis(ticker)
                        st.rerun()

        # ── Separador ───────────────────────────────────────────────────
        st.markdown('<div class="sb-section-divider"></div>', unsafe_allow_html=True)

        # ── Historial: Escaneos del Mercado ─────────────────────────────
        st.markdown('<div class="sb-section-title">Escaneos · Mercado</div>',
                    unsafe_allow_html=True)

        scans = _sidebar_scan_labels()
        if not scans:
            st.markdown('<div class="sb-empty">Sin escaneos guardados todavía</div>',
                        unsafe_allow_html=True)
        else:
            for scan_id, label, count in scans:
                col_l, col_c = st.columns([6, 4], gap="small")
                with col_l:
                    if st.button(f"⊕ {label}", key=f"sb_s_{scan_id}",
                                 use_container_width=True,
                                 help=f"Cargar {label} ({count} candidatos)"):
                        _sb_load_scan(scan_id)
                        st.rerun()
                with col_c:
                    st.markdown(
                        f'<div class="sb-badge-wrap">'
                        f'<span class="sb-count-badge">{count}'
                        f'<span class="sb-count-sub">cand.</span>'
                        f'</span></div>',
                        unsafe_allow_html=True,
                    )


def _apply_sidebar_collapse():
    """Si la columna está minimizada la oculta (el contenido se reajusta solo)
    y muestra un botón »» para reabrirla. Puramente visual — no toca datos ni
    flujos; el sidebar se sigue renderizando (estado intacto), solo se oculta."""
    if not st.session_state.get("sidebar_collapsed"):
        return
    st.markdown(
        "<style>body [data-testid='stSidebar'],"
        "body section[data-testid='stSidebar']{display:none !important;}</style>",
        unsafe_allow_html=True,
    )
    if st.button("»", key="sidebar_expand_btn", help="Mostrar la columna"):
        st.session_state.sidebar_collapsed = False
        st.rerun()


def render_top_nav():
    """Barra superior compacta con un botón Home centrado. Reemplaza al
    sidebar lateral en producción (Whop iframe es cuadrado — el sidebar
    apretaba demasiado el contenido). Solo se muestra en vistas NO-welcome."""
    col_a, col_home, col_c = st.columns([1, 2, 1])
    with col_home:
        if st.button("⌂  Volver al Inicio", use_container_width=True,
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

    from data.cache_store import analisis_fresco

    # ── Un análisis vale 24 HORAS ──────────────────────────────────────────
    # Dentro de esa ventana se reutiliza (y se comparte entre miembros: eso es
    # el ahorro de créditos). Pasadas las 24 h se REHACE DESDE CERO, venga el
    # clic de la barra lateral, del buscador o del Quick View.
    #
    # Antes se reutilizaba hasta 30 días y por eso los análisis se quedaban
    # viejos: las gráficas seguían vivas pero el estudio de la IA no.
    existing = st.session_state.analyses.get(ticker)
    if existing is not None:
        # La tesis corta delata un fallback: eso nunca se reutiliza.
        thesis_len = len(getattr(existing, "investment_thesis", "") or "")
        if thesis_len > 200 and analisis_fresco(existing):
            _debug_log(f"  análisis de sesión FRESCO ({existing.timestamp[:16]}) → se reutiliza")
            st.session_state.selected_ticker = ticker
            st.session_state.quick_view_ticker = None
            st.rerun()
            return
        _debug_log(f"  análisis de sesión descartado (tesis={thesis_len}, "
                   f"fresco={analisis_fresco(existing)}) → se rehace")
        # NO se borra de session_state: si el cooldown frena el análisis, el
        # miembro debe poder seguir viendo lo que ya había en vez de una
        # pantalla vacía. Se sobreescribirá al terminar el análisis nuevo.

    # ── Caché COMPARTIDO (Upstash) — si OTRO miembro ya analizó este ticker en
    # las últimas 24 h, reutilizamos su análisis sin gastar créditos. El filtro
    # de edad va dentro de get_cached_analysis.
    # Es no-op si no hay credenciales de Upstash (vuelve al comportamiento de hoy).
    #
    # OJO CON EL ORDEN: esto va ANTES del cooldown a propósito. Reutilizar el
    # análisis de otro miembro no cuesta ni un crédito ni un segundo de servidor,
    # así que frenarlo no protegería nada y sí castigaría al miembro (con caché
    # compartido, la mayoría de aperturas son justo este caso).
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
        # El usuario ACABA de pedir este análisis: arriba del historial, aunque
        # el objeto de Upstash conserve su timestamp original.
        _sb_mark_used(ticker)
        _prune_analyses_in_memory()
        # Marca este ticker como reciente en el índice de la nube (para la barra
        # lateral tras un reinicio). No-op sin credenciales; nunca bloquea.
        try:
            from data.cache_store import record_recent_analysis
            record_recent_analysis(ticker)
        except Exception:
            pass
        st.rerun()
        return

    # ── Cooldown: freno único, justo antes de gastar ───────────────────────
    # A partir de aquí SÍ se consumen créditos (~$0.113 y ~85 s), así que este
    # es el sitio correcto para el freno. Antes vivía solo en el buscador con 60
    # minutos, y el botón del Quick View se lo saltaba; ahora cubre por igual el
    # buscador, la barra lateral y el Quick View, porque todos pasan por aquí.
    from config.settings import ANALYSIS_COOLDOWN_SEC
    _ultimo = st.session_state.get("_last_analysis_finished_at", 0)
    _pasado = time.time() - _ultimo
    if _pasado < ANALYSIS_COOLDOWN_SEC:
        _restante = max(1, int(round(ANALYSIS_COOLDOWN_SEC - _pasado)))
        st.warning(
            f"⏳ Espera **{_restante} s** para lanzar otro análisis "
            f"(freno para no saturar el servidor)."
        )
        # Se deja ver el análisis que hubiera, aunque esté viejo: mejor eso que
        # una pantalla en blanco. Al pasar el freno, otro clic lo rehará.
        if existing is not None:
            st.session_state.selected_ticker = ticker
            st.session_state.quick_view_ticker = None
        st.session_state.analyzing = False
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
    # Limpieza determinista de jerga inglesa residual (costo $0 — sin IA/red).
    # Se aplica ANTES de guardar para que el caché (Upstash/disco) almacene ya
    # la versión en español limpio. Solo toca campos narrativos; nunca enums ni
    # datos del dashboard. Fallback total: si algo falla, muestra el texto tal cual.
    try:
        from data.language_filter import clean_analysis_language
        clean_analysis_language(analysis)
    except Exception:
        pass
    st.session_state.analyses[ticker] = analysis
    st.session_state.selected_ticker = ticker
    st.session_state.quick_view_ticker = None
    st.session_state.analyzing = False
    _sb_mark_used(ticker)          # análisis recién hecho → arriba del historial
    _prune_analyses_in_memory()

    # Guardar a disco en background — no bloqueamos el rerun por IO.
    # El usuario ve el análisis listo en vez de esperar a que termine
    # el write a disco (que puede tardar 100-300ms).
    thesis_ok = len(getattr(analysis, "investment_thesis", "") or "") > 200
    if thesis_ok:
        def _save_bg():
            # Guardar a disco local (siempre; poda a los 10 más recientes)
            try:
                disk_save(analysis)
            except Exception:
                pass
            # Guardar al caché compartido Upstash (no-op si no hay credenciales).
            # Así el próximo usuario que pida este ticker en 30 días lo reutiliza,
            # y la barra lateral lo recupera tras un reinicio del contenedor.
            try:
                from data.cache_store import save_cached_analysis, record_recent_analysis
                save_cached_analysis(ticker, analysis)
                record_recent_analysis(ticker)
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
            f'<div style="color:#C08E3B;font-family:JetBrains Mono;font-size:0.85rem;">'
            f'Escaneando el mercado · {ticker} ({idx}/{total})</div>',
            unsafe_allow_html=True,
        )

    with st.spinner("Escaneando el mercado…"):
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
                # Persistir también en la nube (Upstash) para que la barra
                # lateral conserve los escaneos tras un reinicio del contenedor.
                # En un hilo aparte para no bloquear el rerun con el POST.
                # No-op sin credenciales; nunca lanza.
                def _cloud_scan_bg(sid, res):
                    try:
                        from dataclasses import asdict
                        from datetime import datetime as _dt
                        from data.persistence import scan_label
                        from data.cache_store import save_cloud_scan
                        rows = []
                        for r in res:
                            try:
                                rows.append(asdict(r))
                            except Exception:
                                try:
                                    rows.append(dict(r.__dict__))
                                except Exception:
                                    pass
                        now = _dt.now()
                        data = {"scan_id": sid, "timestamp": now.isoformat(),
                                "label": scan_label(now), "count": len(res),
                                "results": rows}
                        save_cloud_scan(sid, data)
                    except Exception:
                        pass
                import threading as _th
                _th.Thread(target=_cloud_scan_bg, args=(scan_id, list(results)),
                           daemon=True).start()
        except Exception:
            pass

    st.rerun()


# ── Helpers reutilizables para tabs de agentes ───────────────────────────

# El "Sizing" se retiró de la app (ya no mostramos position sizing). El agente de
# riesgo conserva su nombre INTERNO ("Riesgo & Sizing" — clave del icono y del
# scoring, y de los análisis ya cacheados), pero en pantalla se rotula solo
# "Riesgo". Es un alias de DISPLAY, reversible, que no toca datos ni scoring.
_AGENT_DISPLAY_ALIAS = {"Riesgo & Sizing": "Riesgo"}


def _agent_display_name(report):
    return _AGENT_DISPLAY_ALIAS.get(getattr(report, "agent_name", ""), report.agent_name)


def _agent_icon_html(agent_name) -> str:
    """Chip del ícono de una sección.

    Si la sección tiene ícono SVG propio (AGENT_ICON_SLUG) se emite el chip con
    la clase `agent-icon--<slug>`, que es la que lo dibuja desde el CSS. Si no
    lo tuviera, se cae al monograma de siempre (FN/TC/…), así ninguna sección
    se queda con el chip vacío."""
    slug = AGENT_ICON_SLUG.get(agent_name)
    if slug:
        return f'<span class="agent-icon agent-icon--{slug}"></span>'
    return f'<span class="agent-icon">{AGENT_ICONS.get(agent_name, "")}</span>'


# La convicción se guarda como enum en INGLÉS (HIGH/MEDIUM/LOW) porque de ese
# valor dependen los agentes, el scoring y los análisis ya cacheados. Aquí solo
# se traduce lo que se MUESTRA, igual que ya se hace con `quality_verdict`.
# Va aparte de _STATUS_ES a propósito: allí LOW/MEDIUM/HIGH son BAJO/MEDIO/ALTO
# (masculino, para "riesgo bajo"), pero "convicción" es femenina → BAJA/MEDIA/ALTA.
_CONVICTION_ES = {
    "HIGH":   "ALTA",
    "MEDIUM": "MEDIA",
    "LOW":    "BAJA",
}


def _conviction_es(value):
    """Convicción en español para mostrar. Si llega un valor inesperado o vacío
    se devuelve tal cual (nunca rompe ni oculta información)."""
    if not value:
        return value
    return _CONVICTION_ES.get(str(value).strip().upper(), value)


def _render_agent_header(report):
    """Header strip con icono, nombre del agente, score y conviction badge."""
    score = report.score
    color = score_color(score)
    conv_colors = {"HIGH": "#3DD68C", "MEDIUM": "#E2B25C", "LOW": "#F1495F"}
    conv_color = conv_colors.get(report.conviction, "#E2B25C")
    icon_html = _agent_icon_html(report.agent_name)
    st.markdown(f"""
    <div class="agent-header">
        <div class="agent-header-left">
            {icon_html}
            <span class="agent-name">{_agent_display_name(report)}</span>
        </div>
        <div class="agent-header-right">
            <span class="agent-score" style="color:{color};">{score:.0f}<span class="agent-score-max">/100</span></span>
            <span class="conviction-badge" style="color:{conv_color};border-color:{conv_color}40;background:{conv_color}1A;">
                {_conviction_es(report.conviction)}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _strip_ui_emoji(text):
    """Quita emojis decorativos al inicio de un título de UI (el texto queda)."""
    import re as _re
    try:
        return _re.sub(r'^[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍\s]+', '', str(text)).strip() or str(text)
    except Exception:
        return text


def _meter_scale(value, lo, hi, invert=False):
    """Escala un dato real a 0–100 para el termómetro. lo→0, hi→100 (clamp).
    invert=True cuando MENOS es mejor (P/E, deuda, EV/EBITDA…). None si no hay dato."""
    try:
        if value is None:
            return None
        v = float(value)
        pct = (v - lo) / (hi - lo) * 100.0
        pct = max(2.0, min(98.0, pct))
        return 100.0 - pct if invert else pct
    except Exception:
        return None


def _meter_html(pct):
    """Termómetro rojo→ámbar→verde con dot en la posición del dato."""
    if pct is None:
        return ""
    dot = "#F1495F" if pct < 35 else "#E2B25C" if pct < 68 else "#3DD68C"
    glow = {"#F1495F": "241,73,95", "#E2B25C": "226,178,92", "#3DD68C": "61,214,140"}[dot]
    return (f'<div class="meter"><span class="meter-dot" style="left:{pct:.0f}%;'
            f'background:{dot};box-shadow:0 0 0 3px rgba({glow},0.18), 0 0 8px rgba({glow},0.45);">'
            f'</span></div>')


def _render_metric_tiles(metrics):
    """Fila de KPI tiles. metrics = [{icon, label, value, color, tooltip?, meter?}]
    `meter` (0-100 opcional) pinta el termómetro de calidad del dato.
    El icon se acepta por compatibilidad pero NO se renderiza (sin emojis-icono)."""
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
                    <span class="kpi-tile-label">{m['label']}</span>
                    {help_html}
                </div>
                <div class="kpi-tile-value" style="color:{m['color']};">{m['value']}</div>
                {_meter_html(m.get('meter'))}
            </div>
            """, unsafe_allow_html=True)


def _render_status_pills(pills):
    """Fila de pills de estado. pills = [{label, value, level, meter?}].
    El color vive en un punto indicador y el termómetro traduce el nivel
    (o un `meter` 0-100 explícito) a posición rojo→ámbar→verde."""
    if not pills:
        return
    level_colors = {"good": "#3DD68C", "neutral": "#8D949E", "warn": "#E2B25C", "bad": "#F1495F"}
    level_meter = {"good": 88.0, "neutral": 55.0, "warn": 42.0, "bad": 12.0}
    cols = st.columns(len(pills))
    for col, p in zip(cols, pills):
        with col:
            level = p.get("level", "neutral")
            color = level_colors.get(level, "#8D949E")
            pct = p.get("meter", level_meter.get(level, 55.0))
            sub = p.get("sub", "")
            sub_html = f'<div class="status-pill-sub">{sub}</div>' if sub else ''
            # Mismo botón de ayuda que los KPI tiles: '?' arriba a la derecha
            # que muestra la explicación al pasar el ratón.
            tooltip = p.get("tooltip", "")
            help_html = f'<span class="kpi-help" data-tooltip="{tooltip}">?</span>' if tooltip else ""
            st.markdown(f"""
            <div class="status-pill">
                <div class="status-pill-header">
                    <div class="status-pill-label">{p['label']}</div>
                    {help_html}
                </div>
                <div class="status-pill-value"><span class="status-pill-dot" style="background:{color};"></span>{p['value']}</div>
                {sub_html}
                {_meter_html(pct)}
            </div>
            """, unsafe_allow_html=True)


def _signal_card_html(title, items, kind):
    """Tarjeta única que agrupa las señales (kind = 'pos'|'neg')."""
    cls = "strength-item" if kind == "pos" else "risk-item"
    title_cls = "strength" if kind == "pos" else "risk"
    rows = "".join(f'<div class="{cls}">{i}</div>' for i in items)
    return (f'<div class="signal-card signal-card--{kind}">'
            f'<div class="thesis-section-title {title_cls}">{_strip_ui_emoji(title)}</div>'
            f'{rows}</div>')


def _render_pros_cons(report, pros_title="Señales positivas", cons_title="Señales de riesgo"):
    # Cap a máximo 3 cada uno — garantiza el límite sin importar lo que devuelva
    # la IA (las muestra como "las 3 más importantes"). Ahorra y ordena la UI.
    #
    # Ambas tarjetas se emiten en UN SOLO bloque flex (no en dos st.columns): así
    # `align-items: stretch` garantiza que las dos tengan SIEMPRE la misma altura
    # — la que tenga más ítems fija la altura y la otra la iguala. Con columnas
    # separadas el height:100% no propaga por el anidado de Streamlit.
    cards = ""
    if report.pros:
        cards += _signal_card_html(pros_title, report.pros[:3], "pos")
    if report.cons:
        cards += _signal_card_html(cons_title, report.cons[:3], "neg")
    if cards:
        st.markdown(f'<div class="signal-card-row">{cards}</div>',
                    unsafe_allow_html=True)


def _sanitize_narrative(text):
    """Última línea de defensa al MOSTRAR: si el texto es un volcado de JSON
    crudo (análisis viejo cacheado), rescata solo la prosa. No-op para texto
    limpio; ante cualquier error, el texto original."""
    try:
        from agents.base import sanitize_leaked_json_text
        return sanitize_leaked_json_text(text)
    except Exception:
        return text


def _render_analysis_card(report, title="Análisis Detallado"):
    if not report.analysis:
        return
    st.markdown(f'<div class="section-title-bar">{_strip_ui_emoji(title)}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="analysis-card"><div class="analysis-text">{_sanitize_narrative(report.analysis)}</div></div>',
        unsafe_allow_html=True,
    )


def _render_insight_card(title, content, color="#E2B25C", icon="💡"):
    """Card con barra lateral fina de acento semántico. El icon se acepta por
    compatibilidad pero no se renderiza (sin emojis-icono).
    Por aquí pasan TODOS los campos narrativos de raw_data (dcf_thesis,
    key_insight, macro_verdict, dominant_narrative…): el sanitize los blinda
    contra volcados de JSON de análisis viejos."""
    if not content or not isinstance(content, str) or len(content) < 5:
        return
    content = _sanitize_narrative(content)
    st.markdown(f"""
    <div class="insight-card" style="border-left-color:{color};">
        <div class="insight-card-header">
            <span class="insight-card-title" style="color:{color};">{_strip_ui_emoji(title)}</span>
        </div>
        <div class="insight-card-body">{content}</div>
    </div>
    """, unsafe_allow_html=True)


def _safe_num(value, default=None):
    """Convierte a float si es posible, retorna default si no.
    Trata NaN e infinito como AUSENTE (default) — así un dato faltante nunca se
    imprime como "nan%" ni rompe una gráfica; se muestra "—" en su lugar."""
    try:
        if value is None or value == "" or value == "N/A":
            return default
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
            v = float(cleaned)
        else:
            v = float(value)
        # NaN (v != v) o infinito → ausente
        if v != v or v in (float("inf"), float("-inf")):
            return default
        return v
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
    """Limpia el valor de una tarjeta: quita paréntesis y descripciones largas,
    y lo traduce. YA NO trunca con "…": el valor llega COMPLETO al DOM y, si no
    cabe de ancho, fitText() le baja el tamaño de fuente para que se lea entero
    en una sola línea. `max_len` se mantiene en la firma porque los llamadores
    lo siguen pasando, pero ya no recorta nada."""
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
    return s


def _fallback_financial_health(ratios):
    """Solidez Financiera 0-100 derivada del balance REAL (determinista).

    SOLO se usa cuando el análisis cacheado no trae el sub-score de la IA
    (análisis generados durante la ventana en que el JSON del modelo venía
    incompleto): así la barra siempre existe y refleja datos reales frescos.
    Promedia los componentes disponibles; si no hay ninguno devuelve None
    (la barra simplemente no se dibuja, nunca inventa)."""
    comps = []
    de = _safe_num((ratios or {}).get("debt_to_equity"))
    if de is not None and de >= 0:
        comps.append(100 if de < 0.5 else 75 if de < 1 else 45 if de < 2 else 20)
    cr = _safe_num((ratios or {}).get("current_ratio"))
    if cr is not None and cr > 0:
        comps.append(100 if cr > 2 else 80 if cr > 1.5 else 60 if cr > 1 else 30)
    fcf = _safe_num((ratios or {}).get("fcf_yield"))
    if fcf is not None:
        comps.append(90 if fcf > 5 else 70 if fcf > 2 else 50 if fcf > 0 else 20)
    om = _safe_num((ratios or {}).get("operating_margin"))
    if om is not None:
        om = om * 100 if -1 <= om <= 1 else om   # acepta decimal (0.45) o % (45)
        comps.append(90 if om > 25 else 70 if om > 15 else 50 if om > 5 else 25)
    return round(sum(comps) / len(comps)) if comps else None


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
    # Sin ratio numérico (p. ej. "Indeterminado (falta precio…)"): "—", no un
    # trozo truncado de la frase.
    return "—"


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
        # El gauge imprime la recomendación DENTRO del título de la gráfica
        # (charts.py), así que la etiqueta hay que traducirla aquí. Se hace en
        # el llamador y no dentro de build_gauge para no crear una dependencia
        # charts→styles. El color del arco no cambia: rec_colors solo tiene
        # claves en inglés, así que el lookup fallaba antes y sigue fallando.
        fig = build_gauge(analysis.composite_score,
                          rec_display_label(analysis.recommendation))
        _chart(fig, use_container_width=True,
                        key=f"chart_overview_gauge_{analysis.ticker}")

        # Badge de recomendación
        badge_html = get_recommendation_badge(analysis.recommendation)
        st.markdown(
            f'<div style="text-align:center;margin-top:-10px;">{badge_html}</div>',
            unsafe_allow_html=True,
        )

        # Convicción (el color se elige con el enum interno; solo se traduce el texto)
        conviction_color = {"HIGH": "#3DD68C", "MEDIUM": "#C08E3B", "LOW": "#F1495F"}.get(
            analysis.conviction_level, "#C08E3B"
        )
        st.markdown(
            f'<div style="text-align:center;font-family:JetBrains Mono;font-size:0.75rem;color:{conviction_color};margin-top:4px;">'
            f'Convicción: {_conviction_es(analysis.conviction_level)}</div>',
            unsafe_allow_html=True,
        )

    with col_snow:
        fig = build_snowflake(analysis.snowflake)
        _chart(fig, use_container_width=True,
                        key=f"chart_overview_snowflake_{analysis.ticker}")

    # Fila 2: Score breakdown full-width (debajo, con todo el ancho disponible)
    fig = build_score_breakdown(analysis.score_breakdown)
    _chart(fig, use_container_width=True,
                    key=f"chart_overview_breakdown_{analysis.ticker}")

    st.markdown("---")

    # Fila 2: Info básica + Tesis + Niveles
    col_info, col_thesis = st.columns([1, 2])

    with col_info:
        st.markdown("#### Información")
        # Info en vivo (cacheada 60s): de aquí salen sector e industria, que
        # tienen respaldo TradingView y por tanto llegan también en Render.
        # Se pide UNA vez y se reutiliza abajo en las Métricas Clave.
        from data.market_data import get_company_info, get_risk_levels
        _live_info = get_company_info(analysis.ticker) or {}

        # Descripción del negocio SIN IA: se traduce la industria con un mapa
        # estático (data/industry_labels.py). La descripción larga de yfinance
        # no sirve aquí — viene en inglés y en Render llega vacía.
        #
        # BLINDAJE: si no se consigue el dato (acción poco conocida, fuentes
        # caídas, o incluso si el módulo fallara al importar), la fila
        # simplemente NO SE PINTA. Nunca se muestra "—", "Unknown" ni un error:
        # se construye el diccionario solo con lo que tiene valor real.
        try:
            from data.industry_labels import sector_es, describe_business
            _sector_txt = sector_es(_live_info.get("sector") or analysis.sector)
            _desc_txt = describe_business(_live_info.get("industry"),
                                          _live_info.get("sector") or analysis.sector)
        except Exception:
            _sector_txt = _desc_txt = ""

        def _hay(v):
            """Solo se pinta una fila si su valor es texto útil de verdad."""
            return bool(v) and str(v).strip().lower() not in (
                "", "—", "-", "n/a", "n/d", "none", "unknown", "nan")

        info_data = {}
        if _hay(analysis.company_name):
            info_data["Empresa"] = analysis.company_name
        if _hay(_sector_txt):
            info_data["Sector"] = _sector_txt
        if _hay(_desc_txt):
            info_data["Descripción"] = _desc_txt

        for k, v in info_data.items():
            # Layout grid (NO flex) — evita que key y value se solapen cuando el
            # value es largo. La Descripción lleva un modificador que le quita el
            # recorte de 2 líneas: se expande hacia abajo en vez de cortarse
            # con "…" (hay espacio de sobra en esta columna).
            cls = "overview-info-value"
            if k == "Descripción":
                cls += " overview-info-value--desc"
            st.markdown(
                f'<div class="overview-info-row">'
                f'<span class="overview-info-key">{k}</span>'
                f'<span class="{cls}">{v}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # ── Métricas Clave (4 KPIs premium con tooltips) ─────────
        if any([analysis.entry_price, analysis.target_price, analysis.risk_reward, analysis.position_size_pct]):
            st.markdown('<div class="kpi-section-title">Métricas Clave</div>', unsafe_allow_html=True)

            # El "Precio Actual" debe reflejar SIEMPRE el precio en vivo del
            # momento en que se abre el análisis — aunque el análisis venga de
            # caché (Upstash/disco/sesión). get_company_info() sobreescribe
            # current_price con el precio en vivo (TTL 60s); si no está
            # disponible, cae al entry_price persistido (mismo patrón que ya usan
            # la gráfica R/R del Overview y la pestaña de Riesgo).
            # `_live_info` ya se obtuvo arriba (misma llamada cacheada).
            _current_price = _safe_num(_live_info.get("current_price")) or _safe_num(analysis.entry_price)
            # Target de analistas de get_company_info como respaldo probado en Render.
            _target = _safe_num(analysis.target_price) or _safe_num(_live_info.get("target_price"))
            rr_num  = _safe_num(str(analysis.risk_reward or "").split(":")[0]) if analysis.risk_reward else None
            # Respaldo INFALIBLE: si el análisis cacheado no trae precio/target/RR
            # (datos bloqueados al generarse), se recalculan frescos (OHLCV o TradingView).
            if _target is None or _current_price is None or rr_num is None:
                _fr = get_risk_levels(analysis.ticker)
                if _fr:
                    _current_price = _current_price or _fr.get("current_price")
                    _target = _target or _fr.get("target")
                    rr_num  = rr_num  or _fr.get("rr")
            entry_str  = f"${_current_price:.2f}"  if _current_price else "—"
            target_str = f"${_target:.2f}" if _target else "—"
            rr_str     = (f"{rr_num:.1f}:1" if rr_num else _extract_rr_ratio(analysis.risk_reward))

            metrics = [
                {
                    "icon": "📍", "label": "Precio Actual", "value": entry_str, "color": "#E2B25C",
                    "tooltip": "Precio actual del activo en vivo (se refresca al abrir el análisis). Se usa como línea de referencia para calcular el upside hasta el precio objetivo y el downside hasta el nivel de protección.",
                },
                {
                    "icon": "🏁", "label": "Precio Objetivo", "value": target_str, "color": "#3DD68C",
                    "tooltip": "Precio donde tomar ganancias totales o parciales. Combina la resistencia técnica cercana (52W high, niveles psicológicos) con el valor intrínseco fundamental estimado.",
                },
                {
                    "icon": "⚖️", "label": "R/R Ratio", "value": rr_str,
                    "color": ("#3DD68C" if (rr_num or 0) >= 3 else
                              "#E2B25C" if (rr_num or 0) >= 2 else "#F1495F"),
                    "tooltip": "Risk/Reward Ratio — relación entre la ganancia potencial al target y la pérdida máxima al stop. Un 3:1 significa que arriesgas 1 para ganar 3. Mínimo aceptable para operar: 2:1. El color del valor indica si supera el umbral (verde ≥3, amarillo ≥2, rojo <2).",
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
                    "color": ("#3DD68C" if lt_quality >= 85 else
                              "#6FA3E0" if lt_quality >= 70 else
                              "#E2B25C" if lt_quality >= 55 else "#F1495F"),
                    "tooltip": f"Calidad estructural de largo plazo (3-7 años). Promedio de Fundamentales + Future Viability. Veredicto: {verdict_es}. Empresas con score ≥85 son COMPOUNDERS (best-in-class) que merecen hold de muy largo plazo.",
                })

            for m in metrics:
                st.markdown(f"""
                <div class="kpi-tile">
                    <div class="kpi-tile-header">
                        <span class="kpi-tile-label">{m['label']}</span>
                        <span class="kpi-help" data-tooltip="{m['tooltip']}">?</span>
                    </div>
                    <div class="kpi-tile-value" style="color:{m['color']};">{m['value']}</div>
                </div>
                """, unsafe_allow_html=True)

        # ── Vetos aplicados: ya NO se muestran en el Overview (el dato
        # analysis.vetos_applied sigue existiendo internamente para el scoring,
        # solo se quitó su visualización). ─────────────────────────

        # ── Upside/Downside, DEBAJO de los datos clave ────────────
        # Vive en esta columna (y no a lo ancho, como antes) para aprovechar el
        # hueco que quedaba libre bajo las métricas. Va en versión `compact` para
        # que quepa en la columna estrecha; el ancho lo resuelve
        # use_container_width y el eje de precio se autoescala a target/stop.
        from data.market_data import get_company_info as _gci, get_risk_levels as _grl
        _ov_info   = _gci(analysis.ticker) or {}
        _ov_price  = _safe_num(_ov_info.get("current_price")) or _safe_num(analysis.entry_price)
        _ov_stop   = _safe_num(analysis.stop_loss)
        _ov_target = _safe_num(analysis.target_price) or _safe_num(_ov_info.get("target_price"))
        # Respaldo infalible si faltan niveles (análisis cacheado con datos bloqueados)
        if _ov_stop is None or _ov_target is None or _ov_price is None:
            _fr = _grl(analysis.ticker)
            if _fr:
                _ov_price  = _ov_price  or _fr.get("current_price")
                _ov_stop   = _ov_stop   or _fr.get("stop")
                _ov_target = _ov_target or _fr.get("target")
        if _ov_price and _ov_stop and _ov_target:
            _chart(build_rr_chart(_ov_price, _ov_stop, _ov_target,
                                  analysis.ticker, compact=True),
                   use_container_width=True,
                   key=f"chart_overview_rr_{analysis.ticker}")

    with col_thesis:
        st.markdown("#### Tesis de Inversión — Orquestador")
        st.markdown(
            f'<div class="analysis-card"><div class="analysis-text">{analysis.investment_thesis}</div></div>',
            unsafe_allow_html=True,
        )

        # ── Fortalezas / Riesgos en signal-cards de IGUAL altura ──────
        # Un solo bloque flex (no dos columnas) → align-items:stretch iguala
        # la altura de ambas tarjetas a la de la más alta.
        _sr_cards = ""
        if analysis.key_strengths:
            _sr_cards += _signal_card_html("Fortalezas Clave", analysis.key_strengths, "pos")
        if analysis.key_risks:
            _sr_cards += _signal_card_html("Riesgos Clave", analysis.key_risks, "neg")
        if _sr_cards:
            st.markdown(f'<div class="signal-card-row">{_sr_cards}</div>',
                        unsafe_allow_html=True)

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

    # (La gráfica Upside/Downside se dibuja arriba, al final de `col_info`,
    # justo debajo de los datos clave.)


# ── Technical Tab ─────────────────────────────────────────────────────────
def render_technical(analysis: StockAnalysis):
    tech_report = analysis.reports.get("technical")
    if tech_report is None:
        st.info("Análisis técnico no disponible.")
        return

    # Header con score + conviction
    _render_agent_header(tech_report)

    # ── Gráfica principal (candlestick + MAs + RSI + MACD + Volumen) ──
    from data.market_data import get_price_history, get_technical_indicators
    df = get_price_history(analysis.ticker, period="2y")
    # Indicadores con respaldo INFALIBLE (OHLCV → TradingView): Stage, 52W, MA,
    # RSI, ATR SIEMPRE con datos reales, aunque Yahoo/Nasdaq estén bloqueados.
    indicators = get_technical_indicators(analysis.ticker, df)

    # ── MODO DE ANÁLISIS ───────────────────────────────────────────────────
    # Un único control, centrado y protagonista, con dos modos:
    #   Pro     → gráfica completa (velas + medias + volumen + RSI + MACD)
    #   Básico  → versión simplificada (solo el cierre, con degradado)
    # Se usan dos st.button en vez de st.segmented_control porque este último
    # no admite iconos en las etiquetas y su contenedor real es
    # data-testid="stButtonGroup" (no "stSegmentedControl"), difícil de anclar.
    # Con botones, cada uno lleva la clase estable .st-key-<key>, sobre la que
    # el CSS dibuja el icono y centra el bloque.
    PRO, BASICO = "pro", "basico"
    mode_key = "_chart_mode"

    # Cualquier análisis abre SIEMPRE en modo Pro: al cambiar la acción que se
    # está viendo se restablece el defecto.
    if st.session_state.get("_chart_mode_ticker") != analysis.ticker:
        st.session_state["_chart_mode_ticker"] = analysis.ticker
        st.session_state[mode_key] = PRO
    mode = st.session_state.get(mode_key, PRO)

    st.markdown("""
    <div class="mode-switch-head">
        <span class="mode-switch-rule"></span>
        <span class="mode-switch-label">Modo de análisis</span>
        <span class="mode-switch-rule"></span>
    </div>
    """, unsafe_allow_html=True)

    # [1,2,2,1] deja las dos columnas centrales justo en el centro de la
    # página, y el CSS centra cada botón dentro de la suya. Se les da 1/3 del
    # ancho (no 1/6) para que en un iframe estrecho el botón siga teniendo
    # sitio de sobra y la etiqueta nunca se parta.
    _ms_l, ms_pro, ms_bas, _ms_r = st.columns([1, 2, 2, 1], gap="small")
    with ms_pro:
        if st.button("Pro", key="chart_mode_pro", use_container_width=True,
                     type="primary" if mode == PRO else "secondary"):
            st.session_state[mode_key] = PRO
            st.rerun()
    with ms_bas:
        if st.button("Básico", key="chart_mode_basico", use_container_width=True,
                     type="primary" if mode == BASICO else "secondary"):
            st.session_state[mode_key] = BASICO
            st.rerun()

    is_line = (mode == BASICO)

    title = "Precio — Vista Simplificada" if is_line else "Chart Multi-Indicador"
    st.markdown(f'<div class="section-title-bar">{title}</div>', unsafe_allow_html=True)

    fig = (build_mountain_chart(df, analysis.ticker) if is_line
           else build_price_chart(df, indicators, analysis.ticker))
    _chart(
        fig, use_container_width=True,
        key=f"chart_technical_price_{analysis.ticker}_{'line' if is_line else 'candles'}",
    )

    # ── Status pills clave (Stage, RSI, MACD, Distancia 52W high) ──
    st.markdown('<div class="section-title-bar">Indicadores Clave</div>', unsafe_allow_html=True)

    # Todos los indicadores pasan por _safe_num → NaN/None se muestran como "—",
    # nunca como "nan%". (En cloud, si un dato faltara puntualmente, degrada bien.)
    stage = int(_safe_num(indicators.get("stage")) or 0)
    stage_level = "good" if stage == 2 else "neutral" if stage == 1 else "warn" if stage == 3 else "bad"
    stage_sub = {2: "Tendencia alcista", 1: "Acumulación", 3: "Distribución", 4: "Bajista"}.get(stage, "Sin definir")

    rsi = _safe_num(indicators.get("rsi_14"))
    rsi_level = "neutral" if rsi is None else ("bad" if rsi > 70 or rsi < 30 else "good" if 40 <= rsi <= 60 else "neutral")

    macd_hist = _safe_num(indicators.get("macd_hist"))
    macd_level = "neutral" if macd_hist is None else ("good" if macd_hist > 0 else "bad")
    macd_val = "—" if macd_hist is None else ("Alcista" if macd_hist > 0 else "Bajista")

    pct_high = _safe_num(indicators.get("pct_from_52w_high"))
    high_level = "neutral" if pct_high is None else ("good" if pct_high > -5 else "neutral" if pct_high > -15 else "bad")

    _render_status_pills([
        {"label": "Stage Minervini", "value": (f"Stage {stage}" if stage else "—"), "level": stage_level, "sub": stage_sub,
         "tooltip": "Etapa del ciclo de Minervini según dónde está el precio respecto a sus medias móviles. Stage 1 = acumulación (base lateral tras caer), Stage 2 = tendencia alcista confirmada (la etapa ideal para comprar), Stage 3 = distribución (techo, el dinero fuerte va saliendo), Stage 4 = tendencia bajista."},
        {"label": "RSI 14", "value": (f"{rsi:.1f}" if rsi is not None else "—"), "level": rsi_level,
         "sub": ("Sobrecomprado" if (rsi or 0) > 70 else "Sobrevendido" if (rsi is not None and rsi < 30) else "Neutral"),
         "tooltip": "Índice de Fuerza Relativa de 14 días: mide si el precio ha subido o bajado demasiado rápido. Por encima de 70 está sobrecomprado (riesgo de corrección); por debajo de 30 sobrevendido (posible rebote); entre 40 y 60 es zona neutral y saludable."},
        {"label": "MACD Hist", "value": macd_val, "level": macd_level,
         "sub": (f"{macd_hist:+.3f}" if macd_hist is not None else "sin dato"),
         "tooltip": "Histograma del MACD: distancia entre el MACD y su línea de señal. Positivo significa que el impulso alcista se acelera; negativo, que se está agotando. Suele avisar del cambio de momentum antes de que se vea en el precio."},
        {"label": "Dist. 52W High", "value": (f"{pct_high:.1f}%" if pct_high is not None else "—"), "level": high_level,
         "sub": ("Cerca del máximo" if (pct_high is not None and pct_high > -5) else "Lejos del máximo" if pct_high is not None else "sin dato"),
         "tooltip": "Cuánto le falta al precio para volver a su máximo de las últimas 52 semanas. Cerca de 0% indica fortaleza (cotiza en máximos anuales); muy negativo indica que sigue lejos de su techo del año."},
    ])

    # ── Performance vs MAs y vs SPY ──
    st.markdown('<div class="section-title-bar">Performance Relativa</div>', unsafe_allow_html=True)

    rs = tech_report.raw_data.get("rs", {}) or {}
    col_mas, col_rs = st.columns(2)

    with col_mas:
        ma_items = []
        for n, color in [(20, "#6FA3E0"), (50, "#F0C878"), (150, "#E0703F"), (200, "#F1495F")]:
            pct = _safe_num(indicators.get(f"price_vs_sma{n}_pct"))   # nan-safe
            if pct is not None:
                bar_color = "#3DD68C" if pct > 0 else "#F1495F"
                ma_items.append((f"vs SMA {n}", pct, bar_color))
        if ma_items:
            fig_ma = build_metric_bars(ma_items, height=220, title="DISTANCIA A MOVING AVERAGES")
            _chart(fig_ma, use_container_width=True,
                            key=f"chart_technical_mas_{analysis.ticker}")

    with col_rs:
        # nan-safe: análisis cacheados de producción (yfinance bloqueado) traen
        # rs en NaN. Si TODOS vienen vacíos, re-consultamos fresco (get_relative_
        # _strength funciona con datos en vivo). Nunca dibuja barras con NaN.
        rs_vals = {p: _safe_num(rs.get(p)) for p in ("rs_1m", "rs_3m", "rs_6m")}
        if all(v is None for v in rs_vals.values()):
            try:
                from data.market_data import get_relative_strength
                fresh_rs = get_relative_strength(analysis.ticker) or {}
                rs_vals = {p: _safe_num(fresh_rs.get(p)) for p in ("rs_1m", "rs_3m", "rs_6m")}
            except Exception:
                pass
        rs_items = []
        for period, label in [("rs_1m", "RS 1M"), ("rs_3m", "RS 3M"), ("rs_6m", "RS 6M")]:
            v = rs_vals.get(period)
            if v is not None:
                bar_color = "#3DD68C" if v > 0 else "#F1495F"
                rs_items.append((label, v, bar_color))
        if rs_items:
            fig_rs = build_metric_bars(rs_items, height=220, title="RELATIVE STRENGTH vs S&P 500")
            _chart(fig_rs, use_container_width=True,
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
    # nan-safe global: convierte CUALQUIER número NaN de ratios/info a None (así
    # todos los `is not None` de las tiles lo excluyen → "—", nunca "nan%").
    # Datos de producción con yfinance bloqueado llegaban en NaN.
    _nan_none = lambda d: {k: (_safe_num(v) if isinstance(v, (int, float)) else v) for k, v in d.items()}
    ratios = _nan_none(ratios)
    info = _nan_none(info)

    # ── KPI tiles: Crecimiento + Rentabilidad ─────────────────────
    st.markdown('<div class="section-title-bar">Crecimiento y Rentabilidad</div>',
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
         "color": "#3DD68C" if (rev_growth or 0) > 0 else "#F1495F",
         "meter": _meter_scale(rev_growth, -5, 30),
         "tooltip": "Crecimiento de ingresos año contra año. >15% es excelente."},
        {"icon": "🎯", "label": "ROIC",
         "value": f"{roic:.1f}%" if roic is not None else "—",
         "color": "#3DD68C" if (roic or 0) > 15 else "#E2B25C" if (roic or 0) > 8 else "#F1495F",
         "meter": _meter_scale(roic, 0, 25),
         "tooltip": "Return on Invested Capital. >15% indica negocio de alta calidad."},
        {"icon": "💵", "label": "FCF Yield",
         "value": f"{fcf_yield:.2f}%" if fcf_yield is not None else "—",
         "color": "#3DD68C" if (fcf_yield or 0) > 5 else "#E2B25C" if (fcf_yield or 0) > 2 else "#F1495F",
         "meter": _meter_scale(fcf_yield, 0, 8),
         "tooltip": "Free Cash Flow Yield. FCF / Market Cap. >5% es atractivo."},
        {"icon": "📊", "label": "Gross Margin",
         "value": f"{gross_marg:.1f}%" if gross_marg is not None else "—",
         "color": "#3DD68C" if (gross_marg or 0) > 50 else "#E2B25C" if (gross_marg or 0) > 30 else "#F1495F",
         "meter": _meter_scale(gross_marg, 20, 70),
         "tooltip": "Margen bruto: indica pricing power. >50% es excepcional."},
    ])

    # ── Valoración tiles ─────────────────────────────────────────
    st.markdown('<div class="section-title-bar">Múltiplos de Valoración</div>',
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
         "value": f"{pe:.1f}" if pe else "—", "color": "#6FA3E0",
         "meter": _meter_scale(pe, 10, 45, invert=True),
         "tooltip": "Price/Earnings (trailing). Múltiplo precio/utilidad de los últimos 12 meses. Compara contra el sector y la historia de la empresa."},
        {"icon": "🔮", "label": "P/E Forward",
         "value": f"{fwd_pe:.1f}" if fwd_pe else "—", "color": "#6FA3E0",
         "meter": _meter_scale(fwd_pe, 8, 40, invert=True),
         "tooltip": "Price/Earnings forward. Basado en el EPS estimado del próximo año. Si está bastante por debajo del trailing, indica crecimiento esperado."},
        {"icon": "🏛️", "label": "EV/EBITDA",
         "value": f"{ev_ebit:.1f}" if ev_ebit else "—", "color": "#9D8CE0",
         "meter": _meter_scale(ev_ebit, 8, 24, invert=True),
         "tooltip": "Enterprise Value / EBITDA. <12 suele ser atractivo, >20 ya es caro. Es más fiable que P/E para comparar empresas con diferente estructura de capital."},
        {"icon": "🏦", "label": "Debt/Equity",
         "value": f"{de:.2f}" if de is not None else "—",
         "color": "#3DD68C" if (de or 0) < 0.5 else "#E2B25C" if (de or 0) < 1.5 else "#F1495F",
         "meter": _meter_scale(de, 0, 2.5, invert=True),
         "tooltip": "Apalancamiento financiero (deuda/equity). <0.5 = sano, >1.5 = riesgoso. Negocios con cash flow estable toleran más deuda."},
    ])

    # Tiles secundarios (Margen operativo + P/S + adicionales)
    extra_tiles = []
    if op_marg is not None:
        extra_tiles.append({
            "icon": "⚙️", "label": "Operating Margin",
            "value": f"{op_marg:.1f}%",
            "color": "#3DD68C" if op_marg > 20 else "#E2B25C" if op_marg > 10 else "#F1495F",
            "meter": _meter_scale(op_marg, 0, 32),
            "tooltip": "Margen operativo: % de cada dólar de ingresos que queda tras costos operativos. >20% indica negocio escalable y eficiente.",
        })
    if ps is not None:
        extra_tiles.append({
            "icon": "📏", "label": "P/S Ratio",
            "value": f"{ps:.2f}",
            "color": "#9D8CE0",
            "meter": _meter_scale(ps, 1, 12, invert=True),
            "tooltip": "Price/Sales. Útil para empresas no rentables aún (SaaS, biotech). <3 suele ser razonable, >10 implica altas expectativas de crecimiento.",
        })
    roe_val = ratios.get("roe")
    if roe_val is not None:
        extra_tiles.append({
            "icon": "💼", "label": "ROE",
            "value": f"{roe_val:.1f}%",
            "color": "#3DD68C" if roe_val > 15 else "#E2B25C" if roe_val > 8 else "#F1495F",
            "meter": _meter_scale(roe_val, 0, 30),
            "tooltip": "Return on Equity: rentabilidad sobre patrimonio. >15% es excelente, indica gestión eficiente del capital de accionistas.",
        })
    cr = ratios.get("current_ratio")
    if cr is not None:
        extra_tiles.append({
            "icon": "💧", "label": "Current Ratio",
            "value": f"{cr:.2f}",
            "color": "#3DD68C" if cr > 1.5 else "#E2B25C" if cr > 1 else "#F1495F",
            "meter": _meter_scale(cr, 0.7, 2.5),
            "tooltip": "Liquidez de corto plazo: activos corrientes / pasivos corrientes. >1.5 = sólido, <1 = posible estrés de caja.",
        })

    if extra_tiles:
        _render_metric_tiles(extra_tiles[:4])

    # ── Datos directos de Yahoo Finance ──────────────────────────
    st.markdown('<div class="section-title-bar">Datos de Mercado</div>',
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
    pm_color = ("#3DD68C" if (pm_raw or 0)*100 > 20
                else "#E2B25C" if (pm_raw or 0)*100 > 10
                else "#F1495F")

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
    beta_color = ("#3DD68C" if isinstance(beta_raw, (int, float)) and beta_raw < 1
                  else "#E2B25C" if isinstance(beta_raw, (int, float)) and beta_raw <= 1.5
                  else "#F1495F")

    # Dividendo anual por acción — INFORMATIVO. No entra en el scoring ni en el
    # prompt de ningún agente: sale de get_dividend_info(), con caché propio de
    # 24 h y su propia cadena de respaldo (yfinance → TradingView → Nasdaq →
    # histórico). Se le pasa el `info` YA descargado para que el primer eslabón
    # no gaste una llamada de red extra.
    # Tres estados: importe si paga · «No» si se VERIFICÓ que no reparte ·
    # «—» solo si no respondió ninguna fuente (nunca se afirma un «No» falso).
    from data.market_data import get_dividend_info
    _div = get_dividend_info(analysis.ticker, info=info) or {}
    _div_estado = _div.get("estado", "desconocido")
    if _div_estado == "paga" and _div.get("anual"):
        div_str, div_color = f"${_div['anual']:.2f}", "#3DD68C"
        _base = ("Lo que reparte la empresa por cada acción a lo largo de un año: "
                 f"${_div['anual']:.2f}")
        if _div.get("por_pago") and _div.get("pagos_ano"):
            _per = {1: "año", 2: "semestre", 4: "trimestre",
                    12: "mes"}.get(_div["pagos_ano"], "pago")
            div_tip = (f"{_base} (${_div['por_pago']:.2f} por {_per}, "
                       f"{_div['pagos_ano']} pagos al año).")
        else:
            div_tip = f"{_base}."
    elif _div_estado == "no_paga":
        div_str, div_color = "No", "#8D949E"
        div_tip = ("Esta empresa no reparte dividendo: reinvierte todo el beneficio "
                   "en el negocio. No es bueno ni malo por sí solo.")
    else:
        div_str, div_color = "—", "#8D949E"
        div_tip = ("No se pudo verificar ahora el dividendo de esta acción. "
                   "Vuelve a mirarlo en un rato.")

    _render_metric_tiles([
        {"icon": "💎", "label": "Market Cap",
         "value": mktcap_str, "color": "#E2B25C",
         "tooltip": "Capitalización de mercado total (precio × acciones en circulación)."},
        {"icon": "📊", "label": "Profit Margin",
         "value": pm_str, "color": pm_color,
         "tooltip": "Margen neto: % de cada dólar de ingresos que queda como ganancia neta."},
        {"icon": "💰", "label": "Revenue TTM",
         "value": rev_ttm_str, "color": "#6FA3E0",
         "tooltip": "Ingresos totales de los últimos 12 meses."},
        {"icon": "📈", "label": "Beta",
         "value": beta_str, "color": beta_color,
         "tooltip": "Beta vs S&P 500. <1 = menos volátil que el índice, >1 = más volátil, 1 = correlación perfecta."},
        {"icon": "💸", "label": "Dividendo Anual",
         "value": div_str, "color": div_color,
         "tooltip": div_tip},
    ])

    # ── Desglose de sub-scores ───────────────────────────────────
    st.markdown('<div class="section-title-bar">Pilares Fundamentales</div>',
                unsafe_allow_html=True)

    # Los sub_scores guardados existen en TRES variantes (verificado en los
    # análisis reales de producción):
    #   a) el agente viejo PISABA quality/growth con la versión snowflake
    #      (reescalada ×0.8 a 0-20) y añadía "value" → escalas mezcladas;
    #   b) si el JSON del modelo venía sin sub_scores, solo quedaban las 3
    #      claves snowflake → faltaban las barras de Valoración y Solidez;
    #   c) a veces el modelo devuelve 0-100 en vez de 0-25 (visto en NU).
    # Aquí se normaliza TODO a 0-100 y se completan las barras que falten.
    q  = _safe_num(sub.get("quality"))
    g  = _safe_num(sub.get("growth"))
    v  = _safe_num(sub.get("valuation"))
    fh = _safe_num(sub.get("financial_health"))
    v_snow = _safe_num(sub.get("value"))
    if v_snow is not None:
        # Huella de la variante (a)/(b): deshacer el reescalado ×0.8 y
        # recuperar Valoración desde la clave snowflake si no existe la real.
        if q is not None:
            q = q / 0.8
        if g is not None:
            g = g / 0.8
        if v is None:
            v = v_snow / 0.8
    # Escala: si algún valor supera 25 el set viene en 0-100; si no, es 0-25.
    _vals = [x for x in (q, g, v, fh) if x is not None]
    _mult = 1.0 if _vals and max(_vals) > 25.5 else 4.0

    def _to100(x):
        return None if x is None else max(0.0, min(100.0, x * _mult))

    q, g, v, fh = _to100(q), _to100(g), _to100(v), _to100(fh)
    if fh is None:
        # Sin dato de la IA → se deriva del balance REAL ya fetcheado (fresco).
        fh = _fallback_financial_health(ratios)

    sub_items = []
    for label, val, color in [
        ("Calidad",            q,  "#E2B25C"),
        ("Crecimiento",        g,  "#3DD68C"),
        ("Valoración",         v,  "#6FA3E0"),
        ("Solidez Financiera", fh, "#9D8CE0"),
    ]:
        if val is not None:
            sub_items.append((label, float(val), color))

    if sub_items:
        fig = build_metric_bars(sub_items, height=240,
                                title="SUB-SCORES (0-100)", x_format="num",
                                x_zero_line=False, color_by_score=True)
        _chart(fig, use_container_width=True,
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
                         color="#3DD68C", icon="💎")
    _render_insight_card("Calidad de Earnings", rd.get("earnings_quality", ""),
                         color="#6FA3E0", icon="✓")

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
    st.markdown('<div class="section-title-bar">Diagnóstico del Negocio Futuro</div>',
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
        {"label": "Ventaja Defensiva",
         "value": _clean_tile_value(km.get("moat_strength"), max_len=14),
         "level": moat_level,
         "sub": _clean_tile_value(km.get("moat_type"), max_len=20),
         "tooltip": "Fuerza de la ventaja competitiva que protege a la empresa de sus rivales: marca, efectos de red, costos de cambio o escala. Cuanto más ancho es el foso, más difícil resulta que la competencia le quite márgenes y cuota."},
        {"label": "Riesgo Disrupción",
         "value": _clean_tile_value(km.get("disruption_risk"), max_len=14),
         "level": disr_level, "sub": "IA / tecnología",
         "tooltip": "Probabilidad de que la inteligencia artificial, un cambio tecnológico o un nuevo modelo de negocio dejen obsoleto lo que la empresa vende. Riesgo bajo significa un negocio difícil de desplazar en la próxima década."},
        {"label": "Crecimiento TAM",
         "value": _clean_tile_value(km.get("tam_growth"), max_len=18),
         "level": tam_level, "sub": "Mercado direccionable",
         "tooltip": "Ritmo al que crece el mercado total al que la empresa puede aspirar (TAM). Si el mercado se expande, puede crecer sin necesidad de robarle cuota a nadie; si está estancado, todo crecimiento sale del competidor."},
        {"label": "Calidad Gerencia",
         "value": _clean_tile_value(km.get("management_quality"), max_len=14),
         "level": mgmt_level, "sub": "Asignación de capital",
         "tooltip": "Calidad del equipo directivo juzgada por cómo asigna el capital: recompras a buen precio, adquisiciones sensatas, control de la dilución y reinversión con retorno alto. Es lo que más compone valor a largo plazo."},
    ])

    # ── Bar chart: 4 pilares del futuro ──
    st.markdown('<div class="section-title-bar">Pilares de Viabilidad Futura</div>',
                unsafe_allow_html=True)

    sub_items = []
    pillars = [
        ("Ventaja Competitiva",   _safe_num(sub.get("moat_quality")),                 "#E2B25C"),
        ("Espacio para Crecer",   _safe_num(sub.get("growth_runway")),                "#3DD68C"),
        ("Resistencia Disrupción", _safe_num(sub.get("disruption_resilience")),       "#6FA3E0"),
        ("Uso del Capital",       _safe_num(sub.get("management_capital_allocation")), "#9D8CE0"),
    ]
    # Guarda de escala: el modelo a veces devuelve 0-100 en vez de 0-25 (visto
    # en producción con fundamentales) → no multiplicar en ese caso.
    _fvals = [val for _, val, _ in pillars if val is not None]
    _fmult = 1.0 if _fvals and max(_fvals) > 25.5 else 4.0
    for label, val, color in pillars:
        if val is not None:
            sub_items.append((label, min(float(val) * _fmult, 100.0), color))

    if sub_items:
        fig = build_metric_bars(sub_items, height=240,
                                title="SUB-SCORES (0-100)", x_format="num",
                                x_zero_line=False, color_by_score=True)
        _chart(fig, use_container_width=True,
                        key=f"chart_future_pillars_{analysis.ticker}")

    # ── Pros / Cons ──
    _render_pros_cons(report,
                      pros_title="🚀 Top 3 Ventajas Futuras",
                      cons_title="⚠️ Top 3 Riesgos Estructurales")

    # ── Insight: Future Thesis ──
    _render_insight_card("Tesis a 5 años", rd.get("future_thesis", ""),
                         color="#E2B25C", icon="🔭")

    # Key risks específicos (lista)
    key_risks = rd.get("key_risks") or []
    if key_risks and isinstance(key_risks, list):
        st.markdown('<div class="section-title-bar">Riesgos Críticos Identificados</div>',
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
    st.markdown('<div class="section-title-bar">Indicadores Smart Money</div>',
                unsafe_allow_html=True)

    inst_raw = km.get("institutional_ownership") or ""
    short_raw = km.get("short_interest") or ""
    insider_raw = km.get("insider_buying_signal") or "neutral"
    squeeze_raw = km.get("squeeze_potential") or "low"

    # ── Relleno FRESCO de los dos tiles numéricos si el análisis cacheado los
    # trae vacíos (generado con las fuentes bloqueadas). Solo datos
    # deterministas: % institucional (get_holders_data, con respaldo Nasdaq) y
    # short interest (get_company_info, con respaldo Nasdaq/TradingView). Los
    # enums del agente (señal de insiders, squeeze) NO se inventan.
    def _tile_empty(v):
        return (not v) or str(v).strip().lower() in ("", "n/a", "n/d", "—", "none", "unknown")

    if _tile_empty(inst_raw) or _safe_num(_extract_percent(inst_raw)) is None:
        try:
            from data.market_data import get_holders_data as _ghd0
            _pct = (_ghd0(analysis.ticker) or {}).get("institutional_ownership_pct")
            if _pct is not None:
                inst_raw = f"{float(_pct):.1f}%"
        except Exception:
            pass
    if _tile_empty(short_raw) or _safe_num(_extract_percent(short_raw)) is None:
        try:
            from data.market_data import get_company_info as _gci0
            _sp = (_gci0(analysis.ticker) or {}).get("short_percent")
            if _sp is not None:
                # yfinance/Nasdaq lo dan como fracción (0.0137 = 1.37%)
                _sp = float(_sp)
                short_raw = f"{(_sp * 100 if _sp < 1 else _sp):.1f}% del float"
        except Exception:
            pass

    insider_level = "good" if "bullish" in insider_raw.lower() else "bad" if "bearish" in insider_raw.lower() else "neutral"
    squeeze_level = "good" if "high" in squeeze_raw.lower() else "neutral" if "medium" in squeeze_raw.lower() else "warn"

    # Niveles/termómetros calculados desde el DATO real (numérico, agnóstico al
    # idioma del enum). Propiedad institucional: sana entre 40-85%; >90% saturada.
    inst_num = _safe_num(_extract_percent(inst_raw))
    if inst_num is None:
        inst_level, inst_meter = "neutral", None
    elif 40 <= inst_num <= 85:
        inst_level, inst_meter = "good", _meter_scale(inst_num, 20, 78)
    elif inst_num > 85:
        inst_level, inst_meter = "warn", 55.0
    else:
        inst_level, inst_meter = "neutral", _meter_scale(inst_num, 0, 80)
    # Short interest: menos apuestas en contra = mejor (escala continua).
    short_num = _safe_num(_extract_percent(short_raw))
    short_level = ("neutral" if short_num is None else
                   "good" if short_num < 3 else
                   "neutral" if short_num < 8 else
                   "warn" if short_num < 15 else "bad")
    short_meter = _meter_scale(short_num, 0, 20, invert=True)

    _render_status_pills([
        {"label": "Propiedad Institucional",
         "value": _extract_percent(inst_raw),
         "level": inst_level, "meter": inst_meter, "sub": "% del capital en fondos",
         "tooltip": "Porcentaje del capital en manos de fondos, aseguradoras y grandes gestoras. Una participación alta indica respaldo profesional y más liquidez; si es excesiva, queda poco dinero nuevo por entrar."},
        {"label": "Señal de Insiders",
         "value": _clean_tile_value(insider_raw, max_len=12),
         "level": insider_level, "sub": "Compras vs ventas",
         "tooltip": "Saldo entre compras y ventas de directivos y consejeros de la propia empresa. Que compren con su dinero suele ser la señal más honesta de confianza; las ventas pueden deberse solo a liquidez personal."},
        {"label": "Short Interest",
         "value": _extract_percent(short_raw),
         "level": short_level, "meter": short_meter, "sub": "Apuestas a la baja",
         "tooltip": "Porcentaje de acciones vendidas en corto, es decir, apostando a que el precio caiga. Un valor alto refleja desconfianza del mercado, pero también es combustible para un rebote si esa tesis bajista falla."},
        {"label": "Potencial Squeeze",
         "value": _clean_tile_value(squeeze_raw, max_len=12),
         "level": squeeze_level, "sub": "Rebote por cierre de cortos",
         "tooltip": "Posibilidad de un short squeeze: si el precio sube, quienes vendieron en corto se ven forzados a recomprar y esa recompra acelera la subida. Depende del short interest y de los días que costaría cubrir esas posiciones."},
    ])

    # ── Top holders bar chart ──
    # Si el análisis cacheado no trae los holders (se generó en Render con
    # yfinance bloqueado), se buscan frescos: get_holders_data cachea 12h y
    # tiene respaldo Nasdaq, así que la gráfica de Propiedad Institucional
    # SIEMPRE tiene de dónde dibujar. Mismo patrón que la tabla de insiders.
    top_inst = holders_raw.get("top_institutions") or []
    if not top_inst:
        try:
            from data.market_data import get_holders_data as _ghd
            top_inst = (_ghd(analysis.ticker) or {}).get("top_institutions") or []
        except Exception:
            top_inst = []
    if top_inst:
        fig = build_holders_bars(top_inst)
        _chart(fig, use_container_width=True,
                        key=f"chart_inst_holders_{analysis.ticker}")

    # ── Actividad reciente de directivos (Insiders) ─────────────────────────
    # Si el análisis cacheado no trae las transacciones (se guardó antes de esta
    # función, o los datos venían rate-limitados), las buscamos frescas
    # (cacheadas 12h; con respaldo Nasdaq). Nunca sobrescribe datos buenos.
    insider_txns = holders_raw.get("insider_transactions") or []
    if not insider_txns:
        try:
            from data.market_data import get_holders_data
            _fresh_h = get_holders_data(analysis.ticker) or {}
            fresh_txns = _fresh_h.get("insider_transactions") or []
            if fresh_txns:
                insider_txns = fresh_txns
                holders_raw = {**holders_raw,
                               "insider_transactions": fresh_txns,
                               "recent_insider_buys": _fresh_h.get("recent_insider_buys", 0),
                               "recent_insider_sells": _fresh_h.get("recent_insider_sells", 0)}
        except Exception:
            insider_txns = []

    if insider_txns:
        n_buys = holders_raw.get("recent_insider_buys", 0) or 0
        n_sells = holders_raw.get("recent_insider_sells", 0) or 0
        st.markdown('<div class="section-title-bar">Actividad Reciente de Directivos (Insiders)</div>',
                    unsafe_allow_html=True)
        st.markdown(
            f"<div style='margin:-4px 0 10px;color:#8D949E;font-size:0.85rem;'>"
            f"En las últimas operaciones registradas: "
            f"<span style='color:#3DD68C;font-weight:700;'>{n_buys} compras</span> · "
            f"<span style='color:#F1495F;font-weight:700;'>{n_sells} ventas</span>. "
            f"Las compras de directivos con su propio dinero suelen ser la señal más valiosa "
            f"(arriesgan su patrimonio apostando a que la acción sube); las ventas casi siempre "
            f"son por liquidez personal y pesan mucho menos.</div>",
            unsafe_allow_html=True)

        def _fmt_usd(v):
            v = abs(float(v or 0))
            if v >= 1e9: return f"${v/1e9:.1f}B"
            if v >= 1e6: return f"${v/1e6:.1f}M"
            if v >= 1e3: return f"${v/1e3:.0f}K"
            return f"${v:.0f}" if v else "—"

        # Priorizar operaciones con dinero real (las más grandes primero)
        con_valor = [t for t in insider_txns if (t.get("value") or 0) > 0]
        muestra = sorted(con_valor, key=lambda t: t.get("value") or 0, reverse=True)[:6] or insider_txns[:6]

        tipo_color = {"compra": "#3DD68C", "venta": "#F1495F",
                      "concesión": "#6FA3E0", "donación": "#9D8CE0", "otra": "#5E6570"}
        rows = ""
        for t in muestra:
            c = tipo_color.get(t.get("type", "otra"), "#5E6570")
            nombre = (t.get("insider") or "—").title()
            rows += (
                f"<tr>"
                f"<td style='padding:7px 10px;color:#C9CDD3;font-size:0.82rem;'>{t.get('date','')}</td>"
                f"<td style='padding:7px 10px;color:#F2F3F5;font-size:0.82rem;font-weight:600;'>{nombre}</td>"
                f"<td style='padding:7px 10px;color:#8D949E;font-size:0.78rem;'>{t.get('position','')}</td>"
                f"<td style='padding:7px 10px;'><span style='color:{c};font-weight:700;font-size:0.78rem;text-transform:uppercase;'>{t.get('type','')}</span></td>"
                f"<td style='padding:7px 10px;text-align:right;color:#C9CDD3;font-size:0.82rem;font-family:JetBrains Mono,monospace;'>{_fmt_usd(t.get('value'))}</td>"
                f"</tr>"
            )
        _th = ("padding:8px 10px;text-align:left;color:#5E6570;font-size:0.70rem;"
               "text-transform:uppercase;letter-spacing:0.05em;")
        st.markdown(
            f"<div style='border:1px solid rgba(255,255,255,0.07);border-radius:12px;overflow:hidden;margin-bottom:14px;'>"
            f"<table style='width:100%;border-collapse:collapse;'>"
            f"<thead><tr style='background:rgba(255,255,255,0.03);'>"
            f"<th style='{_th}'>Fecha</th><th style='{_th}'>Directivo</th>"
            f"<th style='{_th}'>Cargo</th><th style='{_th}'>Operación</th>"
            f"<th style='{_th}text-align:right;'>Monto</th>"
            f"</tr></thead><tbody>{rows}</tbody></table></div>",
            unsafe_allow_html=True)

    # ── Smart Money Signal pill grande ──
    smart_raw = km.get("smart_money_signal") or "neutral"
    smart_display = _translate_status(smart_raw).upper()
    signal_color = "#3DD68C" if "accumul" in smart_raw.lower() else "#F1495F" if "distribut" in smart_raw.lower() else "#6FA3E0"
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
                         color="#9D8CE0", icon="🎯")

    _render_analysis_card(report, title="Análisis Completo de Flujo")


# ── Actualización en vivo ("Al día de hoy") ───────────────────────────────
# El análisis profundo se reutiliza hasta 30 días. Estas funciones lo mantienen
# vivo con UNA llamada barata al día (compartida entre todos los miembros) sin
# tocar ni una coma del objeto almacenado.
#
# REGLA DE ORO: la aritmética del scoring se queda en Python. El modelo solo
# dice qué áreas se mueven y a cuánto; el composite se recompone con los WEIGHTS
# de siempre y la recomendación sale de los THRESHOLDS de siempre. Así el modelo
# no puede inventarse ni una nota global ni un enum de recomendación.

_TIPO_EVENTO_ES = {
    "earnings":    "Resultados",
    "dividendo":   "Dividendo",
    "producto":    "Producto",
    "conferencia": "Conferencia",
    "operativo":   "Operativo",
    "accionista":  "Accionistas",
    "regulatorio": "Regulatorio",
    "macro":       "Mercado",
}


def _color_por_dias(dias):
    """Mismo criterio de urgencia que el tile de 'Próximo Reporte', para que
    toda la sección hable el mismo idioma de color."""
    if dias is None:
        return "#5E6570"
    if dias < 7:
        return "#F1495F"
    if dias < 30:
        return "#E2B25C"
    return "#6FA3E0"


def _fecha_es(iso):
    """'2026-09-14' → '14 SEP'. Devuelve la cadena original si no parsea."""
    meses = ("ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
             "JUL", "AGO", "SEP", "OCT", "NOV", "DIC")
    try:
        d = datetime.strptime(str(iso)[:10], "%Y-%m-%d").date()
        return f"{d.day} {meses[d.month - 1]}"
    except (ValueError, TypeError, IndexError):
        return str(iso or "")


def _agenda_normalizada(eventos):
    """Recalcula los días desde HOY y descarta lo ya pasado.

    CLAVE para el historial: un análisis guardado hace semanas trae el campo
    `dias` congelado en el momento en que se generó. Si se pintara tal cual,
    diría "en 5 días" para un evento que ya ocurrió. Aquí la única fuente de
    verdad es la FECHA; los días se vuelven a calcular siempre."""
    hoy = datetime.now().date()
    salida = []
    for e in eventos or []:
        if not isinstance(e, dict):
            continue
        try:
            f = datetime.strptime(str(e.get("fecha", ""))[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if f < hoy:
            continue
        copia = dict(e)
        copia["fecha"] = f.isoformat()
        copia["dias"] = (f - hoy).days
        salida.append(copia)
    salida.sort(key=lambda x: x["fecha"])
    return salida


def _render_agenda_catalizadores(analysis: StockAnalysis, rd: dict):
    """Agenda de eventos próximos + hechos relevantes ya comunicados.

    Fusiona lo guardado con el análisis (`raw_data`) con una consulta fresca —
    que normalmente es un acierto de caché e instantánea — para que funcione
    igual en un análisis nuevo y en uno reabierto del historial.

    Si no hay NADA que mostrar, no dibuja absolutamente nada: nunca un error,
    nunca un 'N/D' vacío."""
    import html as _html

    agenda_guardada = rd.get("agenda") or []
    hechos_guardados = rd.get("hechos_recientes") or []

    agenda_fresca, hechos_frescos = [], []
    try:
        from data.events import get_catalyst_events
        from data.market_data import get_company_info, get_earnings_data
        frescos = get_catalyst_events(
            analysis.ticker,
            get_company_info(analysis.ticker) or {},
            get_earnings_data(analysis.ticker) or {},
        ) or {}
        agenda_fresca = frescos.get("agenda") or []
        hechos_frescos = frescos.get("hechos_recientes") or []
    except Exception:
        # Si la consulta falla, se sigue con lo que quedó guardado en el análisis
        pass

    # Fusionar sin duplicar (título + fecha), priorizando lo fresco
    vistos, agenda = set(), []
    for ev in _agenda_normalizada(list(agenda_fresca) + list(agenda_guardada)):
        clave = (ev.get("titulo"), ev.get("fecha"))
        if clave in vistos:
            continue
        vistos.add(clave)
        agenda.append(ev)

    if agenda:
        st.markdown('<div class="section-title-bar">Agenda de Catalizadores</div>',
                    unsafe_allow_html=True)
        filas = []
        for ev in agenda[:10]:
            dias = ev.get("dias")
            color = _color_por_dias(dias)
            dias_txt = "HOY" if dias == 0 else f"{dias}d"
            tipo = _TIPO_EVENTO_ES.get(ev.get("tipo"), "")
            tag = f'<span class="cat-agenda-tag">{_html.escape(tipo)}</span>' if tipo else ""
            aprox = ('<span class="cat-agenda-aprox">· fecha aprox.</span>'
                     if ev.get("estimada") else "")
            desc = _html.escape(str(ev.get("desc", "") or ""))
            desc_html = f'<div class="cat-agenda-desc">{desc}</div>' if desc else ""
            filas.append(
                f'<div class="cat-agenda-row" style="border-left-color:{color};">'
                f'  <div class="cat-agenda-when">'
                f'    <div class="cat-agenda-days" style="color:{color};">{dias_txt}</div>'
                f'    <div class="cat-agenda-date">{_fecha_es(ev.get("fecha"))}</div>'
                f'  </div>'
                f'  <div class="cat-agenda-main">'
                f'    <div class="cat-agenda-title">{_html.escape(str(ev.get("titulo", "")))}'
                f'{tag}{aprox}</div>'
                f'{desc_html}'
                f'  </div>'
                f'</div>'
            )
        st.markdown(f'<div class="cat-agenda">{"".join(filas)}</div>',
                    unsafe_allow_html=True)

    # ── Hechos ya comunicados oficialmente (SEC) ──
    vistos_h, hechos = set(), []
    for h in list(hechos_frescos) + list(hechos_guardados):
        if not isinstance(h, dict) or not h.get("fecha"):
            continue
        clave = (h.get("codigo"), h.get("fecha"))
        if clave in vistos_h:
            continue
        vistos_h.add(clave)
        hechos.append(h)
    hechos.sort(key=lambda h: str(h.get("fecha", "")), reverse=True)

    if hechos:
        st.markdown('<div class="section-title-bar">Hechos Relevantes Recientes</div>',
                    unsafe_allow_html=True)
        hoy = datetime.now().date()
        filas = []
        for h in hechos[:6]:
            try:
                f = datetime.strptime(str(h["fecha"])[:10], "%Y-%m-%d").date()
                dias_txt = "hoy" if (hoy - f).days == 0 else f"-{(hoy - f).days}d"
            except (ValueError, TypeError, KeyError):
                dias_txt = ""
            desc = _html.escape(str(h.get("desc", "") or ""))
            desc_html = f'<div class="cat-agenda-desc">{desc}</div>' if desc else ""
            filas.append(
                f'<div class="cat-agenda-row" style="border-left-color:#5E6570;">'
                f'  <div class="cat-agenda-when">'
                f'    <div class="cat-agenda-days" style="color:#8D949E;">{dias_txt}</div>'
                f'    <div class="cat-agenda-date">{_fecha_es(h.get("fecha"))}</div>'
                f'  </div>'
                f'  <div class="cat-agenda-main">'
                f'    <div class="cat-agenda-title">{_html.escape(str(h.get("titulo", "")))}'
                f'<span class="cat-agenda-tag">SEC</span></div>'
                f'{desc_html}'
                f'  </div>'
                f'</div>'
            )
        st.markdown(f'<div class="cat-agenda">{"".join(filas)}</div>',
                    unsafe_allow_html=True)

    # ── Eventos que la IA detectó en la prensa y no están en la agenda ──
    # Van en su propio bloque y NUNCA mezclados con la agenda: esos vienen de
    # fuentes verificables (calendario, SEC, dividendos) y estos de titulares.
    # El modelo tiende a repetir aquí lo que ya le pasamos en la agenda pese a
    # pedirle que no lo haga, así que se filtra por FECHA de forma determinista:
    # si ya hay un evento verificado ese día, el de prensa sobra. Si no queda
    # ninguno, el bloque simplemente no se dibuja.
    fechas_agenda = {e.get("fecha") for e in agenda}
    detectados = []
    for ev in (rd.get("upcoming_events") or [])[:5]:
        if not isinstance(ev, dict) or not str(ev.get("evento", "")).strip():
            continue
        if str(ev.get("fecha", ""))[:10] in fechas_agenda:
            continue
        detectados.append(ev)

    if detectados:
        st.markdown('<div class="section-title-bar">Detectado en Noticias</div>',
                    unsafe_allow_html=True)
        colores_dir = {"alcista": "#3DD68C", "bajista": "#F1495F"}
        filas = []
        for ev in detectados:
            direccion = str(ev.get("direccion", "") or "").lower()
            color = colores_dir.get(direccion, "#E2B25C")
            impacto = str(ev.get("impacto", "") or "").strip()
            tag = (f'<span class="cat-agenda-tag">impacto {_html.escape(impacto)}</span>'
                   if impacto else "")
            cuando = _html.escape(str(ev.get("fecha", "") or "").strip())
            filas.append(
                f'<div class="cat-agenda-row" style="border-left-color:{color};">'
                f'  <div class="cat-agenda-when">'
                f'    <div class="cat-agenda-date" style="text-align:right;">{cuando}</div>'
                f'  </div>'
                f'  <div class="cat-agenda-main">'
                f'    <div class="cat-agenda-title">'
                f'{_html.escape(str(ev.get("evento", "")))}{tag}</div>'
                f'  </div>'
                f'</div>'
            )
        st.markdown(f'<div class="cat-agenda">{"".join(filas)}</div>',
                    unsafe_allow_html=True)


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
    st.markdown('<div class="section-title-bar">Catalizadores en el Horizonte</div>',
                unsafe_allow_html=True)

    next_earn = earnings.get("next_earnings", "") or km.get("next_earnings", "")
    days_to = earnings.get("days_to_next_earnings")
    if days_to is not None:
        days_str = f"{days_to}d"
        next_tooltip = (f"Próximo reporte: {next_earn}. "
                        f"Earnings inminentes (<7d) son catalizador de alta volatilidad.")
        next_color = "#F1495F" if days_to < 7 else "#E2B25C" if days_to < 30 else "#6FA3E0"
    else:
        days_str = "N/D"
        next_tooltip = ("Fecha del próximo reporte de resultados no disponible en este momento "
                        "(la fuente de datos puede estar temporalmente fuera de servicio). "
                        "Intenta reanalizar en unos minutos.")
        next_color = "#5E6570"

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
        beat_color = "#3DD68C"
    else:
        raw = km.get("earnings_beat_rate", "")
        cleaned = _clean_tile_value(raw, max_len=10) if raw else None
        if _looks_empty(cleaned):
            beat_rate_str = "N/D"
            beat_tooltip = ("Historial de beats no disponible — requiere datos detallados de earnings "
                            "que la fuente puede no exponer para todos los tickers.")
            beat_color = "#5E6570"
        else:
            beat_rate_str = cleaned
            beat_tooltip = "Beat rate estimado por el agente de catalizadores."
            beat_color = "#E2B25C"

    avg_surp = _safe_num(earnings.get("avg_surprise"))   # nan-safe
    if avg_surp is not None:
        avg_surp_str = f"{avg_surp:+.1f}%"
        avg_surp_tooltip = ("Promedio de % sorpresa en EPS sobre el consenso. "
                            "Positivo y sostenido indica momentum fundamental.")
        avg_surp_color = ("#3DD68C" if avg_surp > 5
                          else "#E2B25C" if avg_surp > 0
                          else "#F1495F")
    else:
        raw = km.get("avg_earnings_surprise", "")
        extracted = _extract_percent(raw) if raw else None
        if _looks_empty(extracted):
            avg_surp_str = "N/D"
            avg_surp_tooltip = ("Sorpresa promedio no disponible — requiere historial detallado "
                                "de earnings que la fuente puede no exponer.")
            avg_surp_color = "#5E6570"
        else:
            avg_surp_str = extracted
            avg_surp_tooltip = "Sorpresa promedio estimada por el agente de catalizadores."
            avg_surp_color = "#E2B25C"

    sentiment_raw = km.get("analyst_sentiment_trend") or "stable"
    sentiment_display = _clean_tile_value(sentiment_raw, max_len=12)
    sent_level_str = sentiment_raw.lower()
    sent_color = ("#3DD68C" if "improv" in sent_level_str else
                  "#F1495F" if "deterior" in sent_level_str else "#E2B25C")

    _render_metric_tiles([
        {"icon": "📅", "label": "Próximo Reporte",
         "value": days_str, "color": next_color, "tooltip": next_tooltip},
        {"icon": "🎯", "label": "Tasa de Aciertos",
         "value": beat_rate_str, "color": beat_color, "tooltip": beat_tooltip},
        {"icon": "🚀", "label": "Sorpresa Promedio",
         "value": avg_surp_str, "color": avg_surp_color, "tooltip": avg_surp_tooltip},
        {"icon": "📊", "label": "Tendencia Analistas",
         "value": sentiment_display, "color": sent_color,
         "tooltip": "Dirección de las revisiones de estimaciones y ratings del consenso (factor de momentum potente)."},
    ])

    # ── Historial de Earnings Surprises (bar chart) ──
    if eh and len(eh) >= 2:
        st.markdown('<div class="section-title-bar">Track Record de Earnings</div>',
                    unsafe_allow_html=True)
        fig = build_earnings_history_chart(eh)
        _chart(fig, use_container_width=True,
                        key=f"chart_catalysts_earn_{analysis.ticker}")

    # ── Agenda de eventos + hechos relevantes ──
    # Va DESPUÉS del track record para no alterar nada de lo que ya había.
    _render_agenda_catalizadores(analysis, rd)

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
                             color="#6FA3E0", icon="🔔")

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
    st.markdown('<div class="section-title-bar">Diagnóstico Macro</div>',
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
         "level": env_level, "sub": "Risk On / Off",
         "tooltip": "Apetito de riesgo general del mercado. Risk-On: los inversores compran activos de riesgo; Risk-Off: se refugian en bonos y efectivo. Marca el viento a favor o en contra para cualquier acción, por buena que sea."},
        {"label": "Momentum Sector",
         "value": _clean_tile_value(sec_raw, max_len=12),
         "level": sec_level, "sub": f"Sector: {rd.get('sector', '—')}",
         "tooltip": "Comportamiento reciente del sector de la empresa frente al resto del mercado. Un sector fuerte empuja al alza incluso a las compañías mediocres; uno débil frena a las buenas."},
        {"label": "Curva Yield",
         "value": _clean_tile_value(yc_raw, max_len=12),
         "level": yc_level, "sub": "10Y-2Y spread",
         "tooltip": "Diferencia entre el bono a 10 años y el de 2 años. Normal (positiva) indica economía sana; plana, desaceleración; invertida ha anticipado históricamente las recesiones."},
        {"label": "Nivel VIX",
         "value": _clean_tile_value(vix_raw, max_len=12),
         "level": vix_level, "sub": "Volatilidad esperada",
         "tooltip": "Índice de volatilidad esperada del mercado, conocido como el índice del miedo. Por debajo de 20 hay calma; entre 20 y 30, tensión; por encima de 30, pánico y movimientos bruscos."},
    ])

    # ── Sector heatmap ──
    from data.market_data import get_macro_data
    macro = get_macro_data() or {}
    sector_perf = macro.get("sector_performance", {})

    if sector_perf:
        st.markdown('<div class="section-title-bar">Rotación Sectorial (1Y)</div>',
                    unsafe_allow_html=True)
        # Misma gráfica que el inicio: barras + separador + números con
        # termómetro. Aquí NO hace falta snapshot ni fragmento — get_macro_data
        # ya viene cacheada a estas alturas y no hay espera que quitar.
        fig = build_sector_rotation(sector_perf)
        _chart(fig, use_container_width=True,
                        key=f"chart_macro_sector_heatmap_{analysis.ticker}")

    # ── Snapshot de indicadores macro ──
    st.markdown('<div class="section-title-bar">Snapshot Macro</div>',
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
        curr = _safe_num(data.get("current"))   # nan-safe
        chg = _safe_num(data.get("1m_change")) or 0
        if curr is not None:
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
        color = "#3DD68C" if chg >= 0 else "#F1495F"
        arrow = "▲" if chg >= 0 else "▼"
        chg_str = f"{arrow} {abs(chg):.2f}% (1M)" if curr is not None else "—"
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
                         color="#E2B25C", icon="🎯")

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
        fig = build_sentiment_gauge(report.score, height=310)
        _chart(fig, use_container_width=True,
                        key=f"chart_sent_gauge_{analysis.ticker}")

    with col_pills:
        st.markdown('<div class="section-title-bar" style="margin-top:0;">Estado de la Narrativa</div>',
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

        # ── Descripciones derivadas del estado REAL ──────────────────
        # Frases completas en vez de etiquetas sueltas ("Mejorando o
        # deteriorando"): dicen lo que de verdad está pasando con esta acción.
        _mom = mom_raw.lower()
        if "improv" in _mom or "mejor" in _mom:
            mom_sub = "El tono de las noticias mejora y empieza a acompañar al precio."
        elif "deterior" in _mom or "empeor" in _mom:
            mom_sub = "El tono de las noticias empeora; la narrativa juega en contra a corto plazo."
        else:
            mom_sub = "El tono de las noticias se mantiene estable, sin giros recientes."

        _n_news = rd.get("news_count", 0) or 0
        _tema = _clean_tile_value(narr_raw)
        if _tema and _tema != "—":
            narr_sub = (f"El foco de las {_n_news} noticias recientes está en {_tema.lower()}."
                        if _n_news else f"La narrativa dominante gira en torno a {_tema.lower()}.")
        else:
            narr_sub = (f"{_n_news} noticias recientes, sin un tema dominante claro."
                        if _n_news else "Sin noticias recientes que marquen una narrativa.")

        _cont = cont_raw.lower()
        if "buy the fear" in _cont or "miedo" in _cont:
            cont_sub = "Miedo extremo: el pesimismo parece exagerado y suele preceder rebotes."
        elif "sell the hype" in _cont or "euforia" in _cont:
            cont_sub = "Euforia extrema: el optimismo ya está en el precio, conviene cautela."
        else:
            cont_sub = "Sin extremos de miedo ni euforia: el sentimiento no da señal contraria."

        _rep = rep_raw.lower()
        if "low" in _rep or "bajo" in _rep:
            rep_sub = "Riesgo ESG y regulatorio bajo: sin frentes abiertos que amenacen la marca."
        elif "high" in _rep or "alto" in _rep:
            rep_sub = "Riesgo alto: hay frentes ESG o regulatorios que pueden dañar la valoración."
        else:
            rep_sub = "Riesgo moderado: conviene vigilar los frentes ESG y regulatorios abiertos."

        _sent_pills = [
            {"label": "Momentum Sentimiento",
             "value": _clean_tile_value(mom_raw, max_len=14),
             "level": mom_level, "sub": mom_sub,
         "tooltip": "Dirección en la que se mueve la percepción del mercado sobre la empresa en las últimas semanas: si la narrativa está mejorando o deteriorándose."},
            {"label": "Tema Narrativo",
             "value": _clean_tile_value(narr_raw, max_len=14),
             "level": "neutral",
             "sub": narr_sub,
         "tooltip": "Historia dominante que se cuenta hoy sobre la empresa en noticias y análisis. La narrativa mueve el precio a corto plazo aunque los fundamentales no hayan cambiado."},
            {"label": "Señal Contraria",
             "value": _clean_tile_value(cont_raw, max_len=14),
             "level": cont_level, "sub": cont_sub,
         "tooltip": "Lectura a contracorriente del sentimiento. Comprar el miedo: el pesimismo es exagerado y crea oportunidad. Vender la euforia: el optimismo ya está descontado en el precio y queda poco recorrido."},
            {"label": "Riesgo Reputacional",
             "value": _clean_tile_value(rep_raw, max_len=10),
             "level": rep_level, "sub": rep_sub,
         "tooltip": "Exposición a escándalos, litigios, sanciones regulatorias o problemas ESG que puedan dañar la marca y, con ella, la valoración de la empresa."},
        ]
        # 2×2 en vez de una fila de cuatro: cada llamada abre sus propias
        # columnas, así cada tarjeta ocupa la MITAD de esta columna (el doble de
        # ancho que antes) y las frases de arriba caben cómodas.
        _render_status_pills(_sent_pills[:2])
        _render_status_pills(_sent_pills[2:])

    # ── Pros / Cons ──
    _render_pros_cons(report,
                      pros_title="📈 Top 3 Señales Positivas de Sentimiento",
                      cons_title="📉 Top 3 Riesgos de Narrativa")

    # ── Narrativa dominante ──
    _render_insight_card("Narrativa Dominante", rd.get("dominant_narrative", ""),
                         color="#6FA3E0", icon="📖")

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
    st.markdown('<div class="section-title-bar">Métricas de Riesgo</div>',
                unsafe_allow_html=True)

    vol      = _safe_num(km.get("volatility_atr_pct"))
    rr_raw   = km.get("risk_reward", "")

    # Get computed values as fallback (nan-safe: el computed_risk de análisis
    # viejos de prod puede traer atr_pct en NaN → _safe_num lo vuelve None → "—")
    computed = rd.get("computed_risk", {}) or {}
    if vol is None: vol = _safe_num(computed.get("atr_pct"))

    # Recalcular Pérdida Máxima y Ganancia Potencial usando el PRECIO ACTUAL en vivo
    # (más útil que el entry hipotético del agente)
    from data.market_data import get_company_info, get_risk_levels
    info_live = get_company_info(analysis.ticker) or {}
    # nan-safe: _safe_num descarta NaN/None → nunca "+nan%"
    current_price = _safe_num(info_live.get("current_price")) or _safe_num(analysis.entry_price)
    stop_lvl   = _safe_num(analysis.stop_loss)
    # Target: cacheado → target de analistas de get_company_info (la MISMA vía
    # PROBADA que ya funciona en Render para los fundamentales) → get_risk_levels.
    target_lvl = _safe_num(analysis.target_price) or _safe_num(info_live.get("target_price"))

    # Respaldo INFALIBLE: si el análisis cacheado no trae niveles reales (se
    # generó con los datos bloqueados), los recalculamos FRESCOS con la misma
    # metodología (precio + ATR + máximo de 52 semanas), vía OHLCV o TradingView.
    if stop_lvl is None or target_lvl is None or current_price is None or vol is None:
        _fresh = get_risk_levels(analysis.ticker)
        if _fresh:
            current_price = current_price or _fresh.get("current_price")
            stop_lvl      = stop_lvl      or _fresh.get("stop")
            target_lvl    = target_lvl    or _fresh.get("target")
            vol           = vol           or _fresh.get("atr_pct")

    downside = None
    upside = None
    rr_num = None
    if current_price and stop_lvl:
        downside = (current_price - stop_lvl) / current_price * 100
    if current_price and target_lvl:
        upside = (target_lvl - current_price) / current_price * 100
    if downside and downside > 0 and upside is not None:
        rr_num = upside / downside

    rr_clean = f"{rr_num:.1f}:1" if rr_num is not None else _extract_rr_ratio(rr_raw)

    _render_metric_tiles([
        {"icon": "💔", "label": "Pérdida Máxima",
         "value": f"-{downside:.1f}%" if downside is not None else "—",
         "color": "#F1495F",
         "tooltip": "Pérdida porcentual si el precio cae al nivel de protección desde el PRECIO ACTUAL del mercado."},
        {"icon": "🚀", "label": "Ganancia Potencial",
         "value": f"+{upside:.1f}%" if upside is not None else "—",
         "color": "#3DD68C",
         "tooltip": "Ganancia porcentual si el precio alcanza el target desde el PRECIO ACTUAL del mercado."},
        {"icon": "⚖️", "label": "R/R Ratio",
         "value": rr_clean,
         "color": ("#3DD68C" if (rr_num or 0) >= 3 else
                   "#E2B25C" if (rr_num or 0) >= 2 else "#F1495F"),
         "tooltip": "Risk/Reward Ratio calculado desde el precio actual. Mínimo aceptable 2:1, ideal 3:1 o superior."},
        {"icon": "📊", "label": "Volatilidad ATR",
         "value": f"{vol:.1f}%" if vol is not None else "—",
         "color": "#6FA3E0" if (vol or 0) < 3 else "#E2B25C" if (vol or 0) < 5 else "#F1495F",
         "tooltip": "Average True Range como % del precio. >5% indica activo muy volátil con drawdowns frecuentes."},
    ])

    # ── R/R Chart visual — usando PRECIO ACTUAL como referencia ──
    # Reusa current_price/stop_lvl/target_lvl ya saneados arriba (nan-safe).
    if current_price and stop_lvl and target_lvl:
        st.markdown('<div class="section-title-bar">Upside / Downside vs Precio Actual</div>',
                    unsafe_allow_html=True)
        fig = build_rr_chart(current_price, stop_lvl, target_lvl, analysis.ticker)
        _chart(fig, use_container_width=True,
                        key=f"chart_risk_tab_rr_{analysis.ticker}")

    # ── Pros / Cons ──
    _render_pros_cons(report,
                      pros_title="✅ Top 3 Aspectos Favorables del Riesgo",
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
            f'<div style="font-size:0.7rem;color:#8D949E;text-transform:uppercase;letter-spacing:0.1em;">Score / 100</div>'
            f'<div style="font-size:0.75rem;color:{color};margin-top:4px;">{_conviction_es(report.conviction)}</div>'
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
                        f'<div style="display:flex;justify-content:space-between;font-size:0.72rem;color:#8D949E;">'
                        f'<span>{k.replace("_", " ").title()}</span><span>{v:.0f}</span></div>'
                        f'<div style="background:#1A2030;border-radius:2px;height:4px;margin-top:2px;">'
                        f'<div style="background:{color};width:{bar_width}%;height:100%;border-radius:2px;"></div>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

    with col_conv:
        st.markdown(f"#### {icon} {_agent_display_name(report)}")
        st.markdown(
            f'<div class="analysis-card"><div class="analysis-text">{_sanitize_narrative(report.analysis)}</div></div>',
            unsafe_allow_html=True,
        )

        col_p, col_c = st.columns(2)
        with col_p:
            if report.pros:
                st.markdown("**Positivos**")
                for p in report.pros[:3]:
                    st.markdown(f'<div style="color:#3DD68C;font-size:0.82rem;padding:2px 0;">✓ {p}</div>', unsafe_allow_html=True)
        with col_c:
            if report.cons:
                st.markdown("**Riesgos / Negativos**")
                for c in report.cons[:3]:
                    st.markdown(f'<div style="color:#F1495F;font-size:0.82rem;padding:2px 0;">⚠ {c}</div>', unsafe_allow_html=True)

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
                f'<div style="font-size:0.7rem;color:#8D949E;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:6px;">{label}</div>'
                f'<div style="font-size:0.85rem;color:#C8D0D8;line-height:1.6;">{val}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ── Scan Results Tab ──────────────────────────────────────────────────────
def render_scan_results():
    # ── Top action bar: volver a filtros + volver al home ──
    col_filters, col_home, _spacer = st.columns([2, 2, 6])
    with col_filters:
        if st.button("Ajustar filtros", key="scan_back_to_filters",
                     use_container_width=True,
                     help="Volver al screener para modificar los filtros"):
            st.session_state.scanner_config_open = True
            st.session_state._show_scan_results = False
            st.rerun()
    with col_home:
        if st.button("⌂ Volver al Inicio", key="scan_back_home",
                     use_container_width=True):
            st.session_state.scan_results = []
            st.session_state.current_scan_id = None
            st.session_state._show_scan_results = False
            st.rerun()

    st.markdown("## Resultados del Scan de Mercado")
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
            color = "#F1495F"
            msg = f"Error del escáner: {err}"
        elif universe < 100:
            color = "#E2B25C"
            msg = (f"El escáner examinó solo <strong>{universe} acciones</strong> "
                   f"al universo crudo (esperábamos 1000+). De ellas, <strong>{passing}</strong> "
                   f"pasaron los filtros. Puede ser rate-limit transitorio — reintenta en 1-2 min.")
        else:
            color = "#6FA3E0"
            msg = (f"✓ El escáner examinó <strong>{universe} acciones</strong> del universo crudo. "
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
                "- La fuente de datos está limitando peticiones temporalmente. Espera 1-2 minutos y vuelve a intentar.\n\n"
                "Puedes ajustar los filtros desde 'Escanear el Mercado' o lanzar un análisis individual de una acción específica."
            )
        else:
            st.info("No hay resultados de scan. Usa el botón 'Escanear el Mercado' en el home.")
        return


    # Header tabla
    headers = ["Ticker", "Empresa", "Sector", "Precio", "Market Cap", "Stage", "RS Score", "Mom 6M", "Mom 3M", "Score", "Acción"]
    col_widths = [1, 2, 2, 1, 1.2, 0.8, 1, 1, 1, 1, 1.2]

    header_html = '<div style="display:grid;grid-template-columns:' + " ".join([f"{w}fr" for w in col_widths]) + ';gap:8px;padding:6px 8px;background:#141920;border-radius:4px;margin-bottom:4px;">'
    for h in headers:
        header_html += f'<div style="font-size:0.65rem;color:#8D949E;text-transform:uppercase;letter-spacing:0.08em;font-weight:600;">{h}</div>'
    header_html += "</div>"
    st.markdown(header_html, unsafe_allow_html=True)

    for result in st.session_state.scan_results:
        color = score_color(result.screener_score)
        stage_color = {"2": "#3DD68C", "1": "#C08E3B", "0": "#8D949E"}.get(str(result.stage), "#F1495F")
        mom_color = "#3DD68C" if result.momentum_6m > 0 else "#F1495F"
        mom3_color = "#3DD68C" if result.momentum_3m > 0 else "#F1495F"

        mktcap = f"${result.market_cap / 1e9:.1f}B" if result.market_cap > 0 else "N/A"

        row_html = f"""<div style="display:grid;grid-template-columns:{" ".join([f'{w}fr' for w in col_widths])};gap:8px;padding:8px 8px;border-bottom:1px solid #1A2030;align-items:center;">
            <div style="font-family:JetBrains Mono;font-size:0.85rem;font-weight:700;color:#E0E0E0;">{result.ticker}</div>
            <div style="font-size:0.78rem;color:#C8D0D8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{result.name[:25]}</div>
            <div style="font-size:0.75rem;color:#8D949E;">{result.sector[:18]}</div>
            <div style="font-family:JetBrains Mono;font-size:0.85rem;color:#E0E0E0;">${result.price:.2f}</div>
            <div style="font-size:0.8rem;color:#8D949E;">{mktcap}</div>
            <div style="font-family:JetBrains Mono;font-size:0.85rem;font-weight:700;color:{stage_color};">S{result.stage}</div>
            <div style="font-family:JetBrains Mono;font-size:0.85rem;color:#9D8CE0;">{result.rs_score:.0f}</div>
            <div style="font-family:JetBrains Mono;font-size:0.85rem;color:{mom_color};">{'+' if result.momentum_6m > 0 else ''}{result.momentum_6m:.1f}%</div>
            <div style="font-family:JetBrains Mono;font-size:0.85rem;color:{mom3_color};">{'+' if result.momentum_3m > 0 else ''}{result.momentum_3m:.1f}%</div>
            <div style="font-family:JetBrains Mono;font-size:0.9rem;font-weight:700;color:{color};">{result.screener_score:.0f}</div>
        </div>"""
        st.markdown(row_html, unsafe_allow_html=True)

        # Botón "Ver más" → abre el Quick View (preview rápido SIN IA, GRATIS):
        # gráfica, métricas clave, noticias y performance. Reemplaza al análisis
        # completo directo desde el scan para no gastar créditos en cada acción.
        # Si el ticker ya tiene un análisis completo en sesión, lo muestra directo.
        if st.button(f"Ver más — {result.ticker}",
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
    "size":      "#E2B25C",   # naranja — tamaño / valor
    "stage":     "#3DD68C",   # verde — tendencia
    "rs":        "#9D8CE0",   # morado — fortaleza
    "momentum":  "#6FA3E0",   # azul — momentum
    "proximity": "#00D4FF",   # cyan — máximo anual
    "sector":    "#E94B7B",   # rosa — sectores
    "liquidity": "#7BA8FF",   # azul claro — liquidez
    "results":   "#F0C878",   # amarillo — cantidad
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


def _scanner_group_head(step: str, title: str, subtitle: str):
    """Encabezado de un bloque de criterios del scanner (agrupa varias cards
    bajo una misma idea: qué buscar / cómo se comporta / qué ver)."""
    st.markdown(f"""
    <div class="scanner-group-head">
        <span class="scanner-group-step">{step}</span>
        <div class="scanner-group-titles">
            <div class="scanner-group-title">{title}</div>
            <div class="scanner-group-subtitle">{subtitle}</div>
        </div>
        <span class="scanner-group-rule"></span>
    </div>
    """, unsafe_allow_html=True)


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
        if st.button("Restablecer", key="scanner_reset_top",
                     use_container_width=True,
                     help="Volver a los filtros por defecto"):
            st.session_state.scanner_filters = dict(SCANNER_DEFAULTS)
            st.rerun()

    st.markdown('<div class="scanner-section-divider"></div>', unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════════════════
    # BLOQUE 1 — QUÉ EMPRESAS BUSCAR (universo de partida)
    #   Sectores (tarjetón principal) + Tamaño + Liquidez
    # ════════════════════════════════════════════════════════════════════
    _scanner_group_head(
        "1", "Qué empresas buscar",
        "El universo de partida: en qué sectores, de qué tamaño y con cuánto movimiento diario",
    )

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
                    label = opt["label"]   # sin emoji: solo el nombre del sector
                    if st.button(label, key=f"sec_top_{opt['key']}", type=btn_type,
                                 use_container_width=True):
                        current = list(sf.get("sectors") or [])
                        if active:
                            current = [x for x in current if x != opt["key"]]
                        else:
                            current.append(opt["key"])
                        sf["sectors"] = current
                        st.rerun()

    # ── Bloque 1, fila de apoyo: Tamaño | Liquidez ──
    # Cada fila abre sus PROPIAS columnas para que ambas tarjetas queden
    # perfectamente alineadas entre sí (con dos columnas largas se desfasaban).
    b1_l, b1_r = st.columns(2, gap="medium")

    # Tamaño de la empresa (multi-select) — IZQ
    with b1_l:
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

    # Liquidez mínima (single) — DER
    with b1_r:
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

    # ════════════════════════════════════════════════════════════════════
    # BLOQUE 2 — CÓMO SE ESTÁ COMPORTANDO (lectura del precio)
    #   Tendencia + Fortaleza relativa + Momentum + Cercanía al máximo
    # ════════════════════════════════════════════════════════════════════
    _scanner_group_head(
        "2", "Cómo se está comportando",
        "La lectura del precio: en qué fase está, si lidera al mercado y cuánta inercia lleva",
    )

    # ── Bloque 2, fila 1: Tendencia | Fortaleza vs el mercado ──
    b2_l, b2_r = st.columns(2, gap="medium")

    # Tendencia técnica (multi-select) — IZQ
    with b2_l:
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

    # Fortaleza vs el mercado (single) — DER
    with b2_r:
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

    # ── Bloque 2, fila 2: Momentum | Cercanía al máximo ──
    b2b_l, b2b_r = st.columns(2, gap="medium")

    # Momentum reciente (single) — IZQ
    with b2b_l:
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

    # Cercanía al máximo anual (single) — DER
    with b2b_r:
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

    # NOTE: Sectores está arriba, en el bloque 1 (tarjetón full-width).
    #       Liquidez está arriba, junto a Tamaño (ambos definen el universo).

    # ════════════════════════════════════════════════════════════════════
    # BLOQUE 3 — QUÉ QUIERES VER (ajuste de salida)
    # ════════════════════════════════════════════════════════════════════
    _scanner_group_head(
        "3", "Qué quieres ver",
        "Cuántas acciones mostrar al final, ordenadas de mejor a peor puntaje",
    )

    # Cantidad de resultados (single) — centrada, media anchura
    _sp_res_l, res_col, _sp_res_r = st.columns([1, 2, 1], gap="medium")
    with res_col:
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
            if st.button("Ejecutar búsqueda", key="scanner_run",
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
    day_color = "#3DD68C" if day_change >= 0 else "#F1495F"
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
        st.markdown('<div class="qv-section-title">PRECIO 6 MESES</div>', unsafe_allow_html=True)
        from dashboard.charts import build_quick_chart
        fig = build_quick_chart(df, ticker)
        _chart(fig, use_container_width=True,
                        key=f"chart_quickview_price_{ticker}")

    with col_metrics:
        st.markdown('<div class="qv-section-title">MÉTRICAS CLAVE</div>', unsafe_allow_html=True)

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
            ("Market Cap",   mcap_str,   "#E2B25C"),
            ("P/E Trailing", pe_str,     "#6FA3E0"),
            ("P/E Forward",  fwd_pe_str, "#6FA3E0"),
            ("P/S",          ps_str,     "#9D8CE0"),
            ("Vol Promedio", vol_str,    "#E2B25C"),
            ("Beta",         beta_str,   "#9D8CE0"),
            ("Div Yield",    div_str,    "#3DD68C"),
        ]
        for label, val, color in metrics:
            st.markdown(f"""
            <div class="qv-metric">
                <span class="qv-metric-label">{label}</span>
                <span class="qv-metric-value" style="color:{color};">{val}</span>
            </div>
            """, unsafe_allow_html=True)

    # ── Row 2: Performance multi-timeframe ───────────────────────────
    st.markdown('<div class="qv-section-title" style="margin-top:8px;">PERFORMANCE</div>', unsafe_allow_html=True)
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
                color = "#E2B25C" if 20 < val < 80 else ("#3DD68C" if val >= 80 else "#F1495F")
                val_str = f"{val:.0f}%"
            elif label == "52W H/L":
                color = "#C8D0D8"
                val_str = f"${low_52w:.0f} / ${high_52w:.0f}"
            elif val is None:
                color = "#C8D0D8"
                val_str = "—"
            else:
                color = "#3DD68C" if val >= 0 else "#F1495F"
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
        st.markdown('<div class="qv-section-title" style="margin-top:14px;">NOTICIAS RECIENTES</div>', unsafe_allow_html=True)
        if news:
            for item in news[:5]:
                publisher = item.get("publisher", "—")
                title = item.get("title", "")
                age = item.get("age_hours", 0) or 0
                age_label = f"{age:.0f}h" if age < 48 else f"{age/24:.0f}d"
                link = item.get("link", "#")

                st.markdown(f"""
                <a href="{link}" target="_blank" class="qv-news-link">
                <div class="qv-news-item">
                    <div class="qv-news-meta">
                        <span class="qv-news-freshness">{age_label}</span>
                        <span class="qv-news-publisher">{publisher}</span>
                    </div>
                    <div class="qv-news-title">{title}</div>
                </div>
                </a>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div class="qv-empty">Sin noticias recientes disponibles</div>', unsafe_allow_html=True)

    with col_ctx:
        st.markdown('<div class="qv-section-title" style="margin-top:14px;">CONTEXTO</div>', unsafe_allow_html=True)

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
                f"EJECUTAR ANÁLISIS DLP DE {ticker}",
                use_container_width=True,
                key="qv_full_analysis",
                type="primary",
            ):
                st.session_state.quick_view_ticker = None
                run_analysis(ticker)


# ── Welcome / Central Hub ─────────────────────────────────────────────────
POPULAR_TICKERS = ["NVDA", "AAPL", "MSFT", "TSLA", "GOOGL", "META", "AMZN", "AMD", "AVGO", "NFLX", "COIN", "PLTR"]


def _sparkline_svg(closes, positive, w=56, h=18):
    """Mini-sparkline SVG puro (sin Plotly, ~300 bytes) con los cierres de los
    últimos 5 días que get_live_snapshot ya descarga. Devuelve "" si no hay al
    menos 2 puntos válidos — la tile simplemente no lo pinta. NUNCA lanza."""
    try:
        pts_in = [float(c) for c in (closes or [])
                  if isinstance(c, (int, float)) and c == c]
        if len(pts_in) < 2:
            return ""
        lo, hi = min(pts_in), max(pts_in)
        span = (hi - lo) or 1.0           # serie plana → línea recta, sin div/0
        pad = 1.5                         # aire para el stroke de 2px
        step = w / (len(pts_in) - 1)
        pts = " ".join(
            f"{i * step:.1f},{h - pad - (c - lo) / span * (h - 2 * pad):.1f}"
            for i, c in enumerate(pts_in)
        )
        color = "#3DD68C" if positive else "#F1495F"
        return (
            f'<svg class="tt-spark" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">'
            f'<polygon points="0,{h} {pts} {w},{h}" fill="{color}" fill-opacity="0.08"/>'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.6" '
            f'stroke-linecap="round" stroke-linejoin="round" '
            f'vector-effect="non-scaling-stroke"/></svg>'
        )
    except Exception:
        return ""


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
        # El container keyed (st-key-herocard) es el ANCLA CSS de toda la
        # card — antes el CSS colgaba del TEXTO del placeholder (frágil:
        # cambiar el copy rompía la card entera). Ahora el copy es libre.
        with st.container(key="herocard"):
            # ── DOS RUTAS, DOS ZONAS ─────────────────────────────────────
            # Antes las dos acciones competían en la misma franja visual y el
            # escáner pasaba desapercibido. Ahora cada ruta tiene su mitad,
            # su titular y su propio CTA, separadas por el clásico divisor
            # "O" (patrón de dos caminos). Mucho más intuitivo de un vistazo.
            zona_izq, zona_o, zona_der = st.columns([1.45, 0.12, 1], gap="small")

            with zona_izq:
                st.markdown(
                    '<div class="hz-title">◈ &nbsp;ANALIZA UNA ACCIÓN</div>'
                    '<div class="hz-sub">Busca una acción por su ticker en el '
                    'mercado: &nbsp;TSLA · NVDA · AAPL</div>',
                    unsafe_allow_html=True)

                # Ticker-tape estilo pantalla de trading floor: precios en
                # vivo desfilando en LED ámbar. Usa SOLO el caché del snapshot
                # (cero red, cero espera); sin datos aún → solo los símbolos.
                try:
                    from data.market_data import get_live_snapshot_cached
                    _tape_snap = get_live_snapshot_cached(POPULAR_TICKERS)
                except Exception:
                    _tape_snap = {}
                _items = []
                for _tk in POPULAR_TICKERS:
                    _d = _tape_snap.get(_tk, {})
                    _p = _d.get("price")
                    _c = _d.get("change_pct", 0) or 0
                    if _p:
                        _fl = "▲" if _c >= 0 else "▼"
                        _items.append(
                            f'<span class="hz-tape-item">{_tk} '
                            f'{_p:,.2f} <span class="hz-tape-chg">{_fl}'
                            f'{abs(_c):.2f}%</span></span>')
                    else:
                        _items.append(f'<span class="hz-tape-item">{_tk}</span>')
                _tape_html = '<span class="hz-tape-sep">·</span>'.join(_items)
                st.markdown(
                    f'<div class="hz-tape" aria-hidden="true"><div class="hz-tape-track">'
                    f'{_tape_html}<span class="hz-tape-sep">·</span>{_tape_html}'
                    f'<span class="hz-tape-sep">·</span></div></div>',
                    unsafe_allow_html=True)

                # st.form → Enter en el input dispara el submit (Análisis DLP):
                # el gesto universal "escribo el ticker y pulso Enter".
                with st.form(key="hero_form", border=False, enter_to_submit=True):
                    ticker_input = st.text_input(
                        label="Ticker",
                        label_visibility="collapsed",
                        placeholder="TSLA · NVDA · AAPL…",
                        key="hero_ticker_input",
                    ).upper().strip()
                    analyze_btn = st.form_submit_button(
                        "🔍  Análisis DLP", use_container_width=True, type="primary")
                st.markdown('<div class="cta-hint">escribe un ticker y pulsa '
                            'Enter</div>', unsafe_allow_html=True)

            with zona_o:
                st.markdown(
                    '<div class="hz-or"><span class="hz-or-line"></span>'
                    '<span class="hz-or-badge">O</span>'
                    '<span class="hz-or-line"></span></div>',
                    unsafe_allow_html=True)

            with zona_der:
                st.markdown(
                    '<div class="hz-title">◎ &nbsp;EXPLORA EL MERCADO</div>'
                    '<div class="hz-sub">Escanea miles de acciones al mismo '
                    'tiempo y encuentra oportunidades en el mercado</div>',
                    unsafe_allow_html=True)
                # Escáner rectangular CSS: barrido vertical que recorre el
                # panel + blips verdes que aparecen un instante y se apagan,
                # como hallazgos del escáner. Puro CSS, mismo ancho del botón.
                st.markdown(
                    '<div class="hz-scan-wrap" aria-hidden="true">'
                    '<div class="hz-scan">'
                    '<span class="hz-scan-grid"></span>'
                    '<span class="hz-scan-beam"></span>'
                    '<span class="hz-scan-blip b1"></span>'
                    '<span class="hz-scan-blip b2"></span>'
                    '<span class="hz-scan-blip b3"></span>'
                    '<span class="hz-scan-blip b4"></span>'
                    '<span class="hz-scan-blip b5"></span>'
                    '</div></div>',
                    unsafe_allow_html=True)
                scan_btn = st.button(
                    "◎  Escanear el Mercado", use_container_width=True,
                    key="hero_scan", type="primary")
                st.markdown('<div class="cta-hint">elige tus filtros antes '
                            'de lanzarlo</div>', unsafe_allow_html=True)

        if analyze_btn and ticker_input:
            # 1b. ¿Escribió el NOMBRE de la empresa en vez del ticker? (error
            # típico de principiante). Se detecta ANTES de gastar red/créditos
            # y se le enseña el ticker correcto.
            _NOMBRE_A_TICKER = {
                "APPLE": "AAPL", "TESLA": "TSLA", "NVIDIA": "NVDA",
                "MICROSOFT": "MSFT", "GOOGLE": "GOOGL", "ALPHABET": "GOOGL",
                "AMAZON": "AMZN", "FACEBOOK": "META", "NETFLIX": "NFLX",
                "COCACOLA": "KO", "COCA": "KO", "DISNEY": "DIS", "INTEL": "INTC",
                "PAYPAL": "PYPL", "ADOBE": "ADBE", "SALESFORCE": "CRM",
                "ORACLE": "ORCL", "STARBUCKS": "SBUX", "MCDONALDS": "MCD",
                "WALMART": "WMT", "BOEING": "BA", "PALANTIR": "PLTR",
                "COINBASE": "COIN", "BROADCOM": "AVGO", "QUALCOMM": "QCOM",
                "HONDA": "HMC", "TOYOTA": "TM", "SONY": "SONY", "FERRARI": "RACE",
                "VISA": "V", "MASTERCARD": "MA", "PEPSI": "PEP", "PEPSICO": "PEP",
                "NIKE": "NKE", "AIRBNB": "ABNB", "UBER": "UBER", "SPOTIFY": "SPOT",
            }
            _sugerido = _NOMBRE_A_TICKER.get(
                ticker_input.replace("-", "").replace("_", ""))
            if _sugerido and _sugerido != ticker_input:
                st.error(
                    f"❌ Para buscar una acción utiliza su **ticker** (el código de "
                    f"cotización), no el nombre de la empresa.\n\n"
                    f"Por ejemplo: no es **{ticker_input.title()}**, es **{_sugerido}**. "
                    f"Escribe **{_sugerido}** en el buscador y pulsa Enter.\n\n"
                    "_El análisis no se ejecutó — no se gastaron créditos._"
                )
            else:
                # Validar el ticker ANTES de gastar créditos (gratis, sin Claude).
                from data.market_data import validate_ticker
                is_valid, clean_ticker, error_msg = validate_ticker(ticker_input)
                if not is_valid:
                    st.error(error_msg)
                else:
                    # El cooldown vive dentro de run_analysis (freno único para
                    # buscador, sidebar y Quick View).
                    run_analysis(clean_ticker)
        if scan_btn:
            # Abre la página de configuración del scanner (no corre scan directo)
            st.session_state.scanner_config_open = True
            st.rerun()

    # ── Quick Access Tickers ──────────────────────────────────────────
    st.markdown('<div class="section-header">⊕  Acceso Rápido — Tickers Populares</div>', unsafe_allow_html=True)

    # Skeleton del grid mientras cargan los precios (~1-3s) — la página ya
    # muestra la ESTRUCTURA final (10 placeholders shimmer) en vez de una
    # cinta que no dice nada. Sin salto de layout al hidratarse.
    tickers_loader = st.empty()
    tickers_loader.markdown(
        '<div class="qt-skel-grid">'
        + '<div class="qt-skel skeleton-block"></div>' * 10
        + '</div>',
        unsafe_allow_html=True,
    )

    from data.market_data import get_live_snapshot
    snapshot = {}
    try:
        snapshot = get_live_snapshot(POPULAR_TICKERS)
    except Exception:
        pass

    # Quitar el skeleton — vamos a renderizar las cards reales abajo
    tickers_loader.empty()

    # Grid 5 cols x 2 rows — tarjetas amplias, 100% clicables, con sparkline
    # intradía (5 días, textura real de mercado) y footer ▾ que invita al clic.
    rows = [POPULAR_TICKERS[:5], POPULAR_TICKERS[5:10]]
    for row_idx, row in enumerate(rows):
        cols = st.columns(5, gap="small")
        for i, ticker in enumerate(row):
            with cols[i]:
                data = snapshot.get(ticker, {})
                price = data.get("price")
                change = data.get("change_pct", 0) or 0

                change_color = "#3DD68C" if change >= 0 else "#F1495F"
                arrow = "▲" if change >= 0 else "▼"
                price_str = f"${price:,.2f}" if price else "—"
                change_str = f"{arrow} {abs(change):.2f}%" if price else "—"

                tk_safe = "".join(c if (c.isalnum() or c in "_-") else "_"
                                  for c in ticker)
                with st.container(key=f"qtile_{tk_safe}"):
                    st.markdown(
                        f'<div class="qt-head"><span class="tt-symbol">{ticker}</span>'
                        f'<span class="tt-change" style="color:{change_color};">{change_str}</span></div>'
                        f'<div class="qt-price">{price_str}</div>'
                        f'{_sparkline_svg(data.get("closes"), change >= 0, w=120, h=30)}'
                        f'<div class="qt-foot">▾&nbsp;&nbsp;<span class="qt-foot-txt">VER TODO</span></div>',
                        unsafe_allow_html=True,
                    )
                    # Overlay invisible: TODA la tarjeta es clicable.
                    # «VER TODO» abre SIEMPRE el dashboard rápido INFORMATIVO
                    # (quick view) — nunca lanza ni abre un análisis: para eso
                    # están el buscador y el historial del sidebar.
                    # SIN help=: el tooltip envuelve el botón en wrappers
                    # (stTooltipHoverTarget) que NO se estiran → el botón solo
                    # cubría una franja de ~38px arriba y el clic real del
                    # ratón en el resto de la tarjeta (p. ej. «VER TODO») caía
                    # al vacío. Sin tooltip la cadena es directa y el overlay
                    # cubre la tarjeta ENTERA.
                    if st.button(f"◈ {ticker}", key=f"qtilebtn_{tk_safe}"):
                        st.session_state.quick_view_ticker = ticker
                        st.session_state.selected_ticker = None
                        # Desde el home SÍ se permite lanzar análisis desde el
                        # Quick View → marcamos que NO viene del scan.
                        st.session_state.quick_view_from_scan = False
                        st.rerun()

    # ── Bloque macro (pulso + rotación sectorial) ─────────────────────
    # ANTES: una cinta de carga y `get_macro_data()` bloqueando la página 4,4 s
    # en frío (esa llamada alimenta LOS DOS bloques, por eso no bastaba con
    # cachear solo la gráfica de sectores).
    #
    # AHORA: se pinta AL INSTANTE con el último registro guardado y la
    # actualización se carga por detrás dentro de un fragmento — que se
    # re-ejecuta solo, sin bloquear el resto de la página y sin que el miembro
    # toque nada. Cuando llega el dato fresco, el bloque se repinta y el
    # snapshot se actualiza para la próxima visita (la de cualquier miembro:
    # el snapshot es compartido).
    _render_bloque_macro()


def _bloque_macro_datos():
    """(datos, actualizando) para el bloque macro. NUNCA lanza.

    Máquina de estados en `session_state`:
      · sin datos aún  → devuelve el SNAPSHOT y pide una segunda pasada.
      · segunda pasada → hace la llamada real (los 4,4 s ocurren aquí dentro,
        no en el primer pintado), guarda el snapshot nuevo y termina.
      · ya listo       → repinta desde memoria, sin red.
    Si no hay snapshot (primera vez de todas), carga en vivo directamente: el
    miembro espera como antes, pero nunca ve un hueco.
    """
    estado = st.session_state.setdefault("_macro_estado", {"fase": "inicio"})

    if estado["fase"] == "listo":
        # El tick del fragmento no se desperdicia: pasados unos minutos se
        # vuelve a refrescar, así el inicio se mantiene al día solo mientras
        # alguien lo tenga abierto. `get_macro_data` tiene su propia caché de
        # 1 h, así que estas re-comprobaciones casi siempre son gratis.
        if (time.time() - float(estado.get("t", 0) or 0)) > 600:
            estado["fase"] = "refrescando"
        else:
            return estado.get("datos") or {}, False

    if estado["fase"] == "inicio":
        try:
            from data.cache_store import get_macro_snapshot
            snap = get_macro_snapshot()
        except Exception:
            snap = None
        if snap:
            # Hay último registro: se pinta ya y se refresca en la siguiente
            # pasada del fragmento.
            estado["fase"] = "refrescando"
            estado["datos"] = snap
            return snap, True
        # Sin snapshot: no queda otra que cargar en vivo aquí mismo.
        estado["fase"] = "refrescando"

    # fase "refrescando": traer los datos reales
    try:
        from data.market_data import get_macro_data
        frescos = get_macro_data() or {}
    except Exception:
        frescos = {}
    if frescos.get("sector_performance"):
        try:
            from data.cache_store import save_macro_snapshot
            save_macro_snapshot(frescos)
        except Exception:
            pass
        estado["datos"] = frescos
    estado["fase"] = "listo"
    estado["t"] = time.time()
    return estado.get("datos") or {}, False


# `run_every` hace que el fragmento vuelva solo unos segundos después del
# primer pintado: ahí es donde se hace la llamada real. Una vez en fase
# "listo" los repintados son locales (sin red) y con datos idénticos, así que
# no se ve movimiento en pantalla.
@st.fragment(run_every=3)
def _render_bloque_macro():
    macro, actualizando = _bloque_macro_datos()

    # Indicador DISCRETO de que se está refrescando — nunca una cinta que tape
    # el contenido, que es justo lo que se quería quitar.
    _punto = ('<span style="color:#5E6570;font-size:0.6rem;font-family:JetBrains Mono;'
              'letter-spacing:0.08em;margin-left:10px;">actualizando…</span>'
              if actualizando else "")
    st.markdown(f'<div class="section-header">El Mercado en Vivo{_punto}</div>',
                unsafe_allow_html=True)

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
        change_color = "#3DD68C" if chg >= 0 else "#F1495F"
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
    # Sin cinta de carga: los datos ya vienen resueltos (snapshot o frescos),
    # así que la gráfica se dibuja directamente.
    sector_perf = macro.get("sector_performance", {}) if macro else {}
    if sector_perf:
        st.markdown('<div class="section-header">Rotación Sectorial (1Y)</div>', unsafe_allow_html=True)
        from dashboard.charts import build_sector_rotation
        _chart(build_sector_rotation(sector_perf), use_container_width=True,
                        key="chart_welcome_sector_heatmap")


# ── Main App ──────────────────────────────────────────────────────────────
def main():
    # Barra lateral persistente: Home + historial (últimos 10 análisis + 3
    # escaneos). Se renderiza SIEMPRE; su contenido viene de sesión/disco/nube,
    # así que sobrevive a reinicios. _apply_sidebar_collapse solo la oculta si
    # el usuario la minimizó (no afecta datos ni flujos).
    render_sidebar()
    _apply_sidebar_collapse()

    render_header()

    # Botón "Volver al Home" centrado arriba SOLO cuando el usuario no está en
    # la welcome screen NI viendo un análisis (ese ya trae su propia franja de
    # navegación). En welcome el hero es claro; no se necesita botón redundante.
    in_welcome = (
        not st.session_state.get("selected_ticker") and
        not st.session_state.get("quick_view_ticker") and
        not st.session_state.scan_results and
        not st.session_state.get("scanner_config_open") and
        not st.session_state.get("_show_scan_results")
    )
    has_selected_analysis = (
        st.session_state.get("selected_ticker") in (st.session_state.get("analyses") or {})
    )
    if (not in_welcome) and (not has_selected_analysis):
        render_top_nav()

    # ── Análisis pendiente de rehacer ──────────────────────────────────────
    # La barra lateral no puede lanzarlo ella misma (se dibuja dentro de
    # `with st.sidebar:` y el esqueleto de carga saldría ahí dentro), así que
    # deja el ticker marcado y se ejecuta AQUÍ, en el cuerpo principal, con la
    # misma pantalla de carga y el mismo spinner progresivo que un análisis
    # nuevo. La bandera se consume antes de llamar para que no pueda reentrar.
    _pendiente = st.session_state.pop("_pending_analysis", None)
    if _pendiente:
        run_analysis(_pendiente)

    selected = st.session_state.selected_ticker
    qv = st.session_state.get("quick_view_ticker")

    # Prioridad: Quick View > Full Analysis > Scanner Config > Scan Results > Welcome
    # El quick view se muestra SIEMPRE que esté pedido — también para tickers
    # ya analizados («VER TODO» es la vista informativa; el análisis completo
    # se abre desde el buscador, el sidebar o el CTA del propio quick view).
    if qv:
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

    # Limpieza de jerga inglesa al MOSTRAR — cubre también los análisis cacheados
    # (sesión, disco y Upstash) generados antes de este filtro, para que ninguno
    # muestre términos en inglés. Es idempotente (re-aplicarlo no cambia nada) y
    # de costo $0. Fallback total ante cualquier error.
    try:
        from data.language_filter import clean_analysis_language
        clean_analysis_language(analysis)
    except Exception:
        pass

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
    compound_badge = ('<span class="compound-machine-badge">COMPOUNDER</span>'
                      if getattr(analysis, "is_compound_machine", False) else "")
    fecha_txt = analysis.timestamp[:10]

    st.markdown(
        f'<div class="stock-header">'
        f'<span class="stock-header-ticker">{analysis.ticker}</span>'
        f'<span class="stock-header-name">{analysis.company_name}</span>'
        f'<span>{rec_badge}</span>'
        f'{compound_badge}'
        f'<span class="stock-header-score" style="color:{color};">{score:.1f}<span style="font-size:0.75rem;color:#8D949E;font-weight:400;">/100</span></span>'
        f'<span style="color:#5E6570;font-family:JetBrains Mono;font-size:0.7rem;">{fecha_txt}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Barra de secciones (píldora centrada con puntitos) ──────────────────
    # Radio horizontal CENTRADO como píldora: cada opción lleva su puntito y la
    # activa se marca con borde redondeado dorado + brillo (CSS .st-key-sectbar_).
    # Sustituye a st.tabs manteniendo INTACTAS todas las render functions. Con
    # key POR TICKER cada análisis recuerda en qué sección estabas (st.tabs no
    # acepta key y se reiniciaba al cambiar de acción).
    sections = ["Overview", "Técnico", "Fundamentales", "Futuro",
                "Smart Money", "Contexto del Mercado", "Riesgo"]
    # El key del container se vuelve clase CSS (st-key-…): solo chars seguros
    # (tickers como BRK.B llevarían un punto inválido en un class name).
    _tk_safe = "".join(c if (c.isalnum() or c in "_-") else "_" for c in analysis.ticker)
    sect_key = f"sect_{analysis.ticker}"        # key del WIDGET
    # Espejo en una key NORMAL (no de widget): Streamlit RECICLA el estado de
    # los widgets que no se renderizan en un rerun, así que al cambiar de acción
    # el `sect_…` de la anterior se perdía y volvía a Overview. Este espejo sí
    # sobrevive, y es de donde se re-siembra la sección al volver al ticker.
    mem_key = f"_sectmem_{analysis.ticker}"
    if st.session_state.get(sect_key) not in sections:
        _remembered = st.session_state.get(mem_key)
        st.session_state[sect_key] = _remembered if _remembered in sections else sections[0]
    with st.container(key=f"sectbar_{_tk_safe}"):
        st.radio("Sección", sections, key=sect_key, horizontal=True,
                 label_visibility="collapsed")
    sect = st.session_state.get(sect_key) or sections[0]
    st.session_state[mem_key] = sect

    if sect == "Overview":
        render_overview(analysis)
    elif sect == "Técnico":
        render_technical(analysis)
    elif sect == "Fundamentales":
        render_fundamentals(analysis)
    elif sect == "Futuro":
        render_future(analysis)
    elif sect == "Smart Money":
        render_institutional(analysis)
    elif sect == "Contexto del Mercado":
        # Contexto del Mercado = Catalizadores + Macro + Sentimiento.
        # Cada uno mantiene sus gráficas/tarjetas/gauge intactos — solo
        # se renderizan en la misma sección con separadores claros.
        render_catalysts(analysis)
        st.markdown('<div style="margin:28px 0;border-top:1px solid #1E2530;"></div>',
                    unsafe_allow_html=True)
        render_macro(analysis)
        st.markdown('<div style="margin:28px 0;border-top:1px solid #1E2530;"></div>',
                    unsafe_allow_html=True)
        render_sentiment(analysis)
    elif sect == "Riesgo":
        render_risk(analysis)


if __name__ == "__main__":
    main()
