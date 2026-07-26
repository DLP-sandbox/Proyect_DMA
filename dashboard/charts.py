"""
Componentes de visualización: gráfica de precios con indicadores,
tachómetro compuesto, snowflake radar, y mini-charts del sidebar.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Paleta (espejo de los tokens de diseño de styles.py) ──────────────────
BG_MAIN  = "#0A0B0D"                     # --bg
BG_CARD  = "#101216"                     # --surface-1
GRID     = "rgba(255,255,255,0.05)"      # rejilla casi invisible (Tufte)
TEXT     = "#C9CDD3"                     # --text
MUTED    = "#8D949E"                     # --text-2
GREEN    = "#3DD68C"                     # --pos
RED      = "#F1495F"                     # --neg
ORANGE   = "#E2B25C"                     # --accent (oro antiguo)
BLUE     = "#6FA3E0"                     # --info
PURPLE   = "#9D8CE0"                     # dato categórico
YELLOW   = "#F0C878"                     # --accent-hi
WHITE    = "#F2F3F5"                     # --text-hi


def _score_color(s) -> str:
    """Color de un puntaje 0-100 en la MISMA escala del termómetro
    (rojo→ámbar→verde, de peor a mejor). Fuente única de verdad para todas las
    barras que representan una CALIFICACIÓN."""
    try:
        s = float(s)
    except (TypeError, ValueError):
        return MUTED
    if s >= 80:
        return "#3DD68C"   # --pos
    if s >= 65:
        return "#63DFA3"
    if s >= 50:
        return "#E2B25C"   # --accent
    if s >= 35:
        return "#E0854E"
    return "#F1495F"       # --neg

# Config de Plotly para que NINGUNA gráfica sea manipulable: sin barra de
# herramientas, sin zoom con la rueda, sin doble clic para reencuadrar y sin
# tiradores en los ejes. Se combina con `dragmode=False` en la propia figura
# (lo aplica _chart() en app.py), que es lo que bloquea el zoom por arrastre.
# NO se usa staticPlot: eso mataría también el hover y los tooltips, que sí
# queremos conservar.
STATIC_CHART_CONFIG = {
    "displayModeBar": False,
    "displaylogo": False,
    "scrollZoom": False,
    "doubleClick": False,
    "showAxisDragHandles": False,
    "showAxisRangeEntryBoxes": False,
    "editable": False,
}

PLOTLY_LAYOUT = dict(
    paper_bgcolor=BG_MAIN,
    plot_bgcolor=BG_MAIN,
    font=dict(color=TEXT, family="JetBrains Mono, monospace", size=11),
    xaxis=dict(gridcolor=GRID, zerolinecolor=GRID, showgrid=True,
               linecolor="rgba(255,255,255,0.08)", tickfont=dict(color=MUTED, size=10)),
    yaxis=dict(gridcolor=GRID, zerolinecolor=GRID, showgrid=True,
               linecolor="rgba(0,0,0,0)", tickfont=dict(color=MUTED, size=10)),
    margin=dict(l=10, r=10, t=40, b=10),
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#15181D", bordercolor="rgba(255,255,255,0.10)",
                    font=dict(family="JetBrains Mono, monospace", size=11, color=TEXT)),
)


# ── Gráfica Principal: OHLCV + Indicadores ────────────────────────────────

def build_price_chart(df_daily: pd.DataFrame, indicators: dict, ticker: str) -> go.Figure:
    """
    Gráfica profesional estilo Bloomberg: candlesticks + MAs + RSI + MACD + Volumen.
    """
    if df_daily is None or df_daily.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sin datos de precio disponibles", x=0.5, y=0.5, showarrow=False, font=dict(color=MUTED))
        fig.update_layout(**PLOTLY_LAYOUT, height=600)
        return fig

    df = df_daily.copy()
    if isinstance(df.index, pd.DatetimeIndex):
        dates = df.index
    else:
        dates = pd.to_datetime(df.index)

    close = df["Close"]
    high  = df["High"]
    low   = df["Low"]
    open_ = df["Open"]
    vol   = df["Volume"]

    # Calcular MAs sobre el df actual
    ma20  = close.rolling(20).mean()
    ma50  = close.rolling(50).mean()
    ma150 = close.rolling(150).mean()
    ma200 = close.rolling(200).mean()

    # RSI
    try:
        import ta as ta_lib
        rsi = ta_lib.momentum.RSIIndicator(close, window=14).rsi()
        macd_ind    = ta_lib.trend.MACD(close)
        macd_line   = macd_ind.macd()
        macd_signal = macd_ind.macd_signal()
        macd_hist   = macd_ind.macd_diff()
    except Exception:
        rsi = None
        macd_line = macd_signal = macd_hist = None

    # 4 subplots: Precio | Volumen | RSI | MACD
    # NOTA: el título del subplot 1 ("NVDA — Precio") va vacío para evitar
    # que se solape con la leyenda horizontal (que también va arriba del
    # subplot 1). El título se agrega abajo como annotation custom.
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        subplot_titles=["", "Volumen", "RSI 14", "MACD"],
    )

    # ── Candlesticks ──────────────────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=dates,
        open=open_, high=high, low=low, close=close,
        name="OHLC",
        increasing_line_color=GREEN,
        decreasing_line_color=RED,
        increasing_fillcolor=GREEN,
        decreasing_fillcolor=RED,
        line=dict(width=1),
        whiskerwidth=0.4,
    ), row=1, col=1)

    # ── Moving Averages ───────────────────────────────────────────────────
    ma_styles = [
        (ma20,  "#4A9EFF",  "MA 20",  1.2),
        (ma50,  "#FFD740",  "MA 50",  1.5),
        (ma150, "#FF6B35",  "MA 150", 1.5),
        (ma200, "#FF3B5C",  "MA 200", 2.0),
    ]
    for ma, color, name, width in ma_styles:
        fig.add_trace(go.Scatter(
            x=dates, y=ma, mode="lines", name=name,
            line=dict(color=color, width=width),
            opacity=0.85,
        ), row=1, col=1)

    # ── 52W High/Low annotations ──────────────────────────────────────────
    high_52w = indicators.get("52w_high")
    low_52w  = indicators.get("52w_low")
    if high_52w:
        fig.add_hline(y=high_52w, line_dash="dash", line_color=ORANGE,
                      annotation_text=f"52W High ${high_52w:.2f}",
                      annotation_font_color=ORANGE,
                      annotation_position="bottom right", row=1, col=1)
    if low_52w:
        fig.add_hline(y=low_52w, line_dash="dash", line_color=MUTED,
                      annotation_text=f"52W Low ${low_52w:.2f}",
                      annotation_font_color=MUTED,
                      annotation_position="top right", row=1, col=1)

    # ── Volumen con color según vela ──────────────────────────────────────
    vol_colors = [GREEN if c >= o else RED for c, o in zip(close, open_)]
    fig.add_trace(go.Bar(
        x=dates, y=vol, name="Volumen",
        marker_color=vol_colors, marker_opacity=0.6,
        showlegend=False,
    ), row=2, col=1)

    # Avg volume line
    avg_vol = vol.rolling(20).mean()
    fig.add_trace(go.Scatter(
        x=dates, y=avg_vol, mode="lines", name="Vol MA20",
        line=dict(color=YELLOW, width=1.5, dash="dot"),
        showlegend=False,
    ), row=2, col=1)

    # ── RSI ───────────────────────────────────────────────────────────────
    if rsi is not None:
        fig.add_trace(go.Scatter(
            x=dates, y=rsi, mode="lines", name="RSI 14",
            line=dict(color=PURPLE, width=1.5),
            showlegend=False,
        ), row=3, col=1)
        # Zonas sobrecompra/sobreventa
        for level, color, label in [(70, RED, "70"), (30, GREEN, "30")]:
            fig.add_hline(y=level, line_dash="dot", line_color=color,
                          line_width=1, opacity=0.6, row=3, col=1)
        fig.update_yaxes(range=[0, 100], row=3, col=1)

    # ── MACD ──────────────────────────────────────────────────────────────
    if macd_line is not None:
        # Histograma MACD
        hist_colors = [GREEN if v >= 0 else RED for v in (macd_hist.fillna(0) if macd_hist is not None else [])]
        fig.add_trace(go.Bar(
            x=dates, y=macd_hist, name="MACD Hist",
            marker_color=hist_colors, marker_opacity=0.7,
            showlegend=False,
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=macd_line, mode="lines", name="MACD",
            line=dict(color=BLUE, width=1.5),
            showlegend=False,
        ), row=4, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=macd_signal, mode="lines", name="Signal",
            line=dict(color=ORANGE, width=1.5, dash="dot"),
            showlegend=False,
        ), row=4, col=1)
        fig.add_hline(y=0, line_color=MUTED, line_width=1, opacity=0.5, row=4, col=1)

    # Título "TICKER — Precio" como annotation DEBAJO de la leyenda,
    # alineado a la izquierda del subplot 1 para que NUNCA se solape con
    # la leyenda horizontal que vive arriba del subplot.
    fig.add_annotation(
        text=f"<b>{ticker} — Precio</b>",
        xref="x domain", yref="y domain",
        x=0.01, y=0.97,
        xanchor="left", yanchor="top",
        showarrow=False,
        font=dict(size=12, color=TEXT, family="JetBrains Mono, monospace"),
        bgcolor="rgba(11,14,17,0.7)",
        bordercolor="rgba(255,184,77,0.20)",
        borderwidth=1,
        borderpad=4,
        row=1, col=1,
    )

    # ── Layout ────────────────────────────────────────────────────────────
    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT, family="JetBrains Mono, monospace", size=11),
        height=700,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="center", x=0.5,
            font=dict(size=10, color=TEXT),
            bgcolor="rgba(11,14,17,0.6)",
            bordercolor="rgba(255,184,77,0.15)",
            borderwidth=1,
        ),
        margin=dict(l=10, r=10, t=55, b=10),
    )

    # Colores de ejes
    for i in range(1, 5):
        fig.update_xaxes(
            gridcolor=GRID, zerolinecolor=GRID,
            tickfont=dict(color=MUTED, size=9),
            row=i, col=1,
        )
        fig.update_yaxes(
            gridcolor=GRID, zerolinecolor=GRID,
            tickfont=dict(color=MUTED, size=9),
            row=i, col=1,
        )

    return fig


def _hex_rgb(hex_color: str) -> str:
    """'#3DD68C' → '61,214,140' (para componer rgba() en Plotly)."""
    h = hex_color.lstrip("#")
    return ",".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def build_mountain_chart(df_daily: pd.DataFrame, ticker: str, height: int = 560) -> go.Figure:
    """
    Versión simplificada: una sola línea de precio de cierre con un degradado
    suave debajo (gráfica tipo 'mountain'). Sin medias, sin RSI, sin MACD.

    El degradado se construye apilando varias bandas rellenas con `tonexty` y
    opacidad creciente hacia la línea. Se hace así a propósito, en lugar de
    usar `fillgradient`, porque las bandas apiladas funcionan en cualquier
    versión de Plotly.js.
    """
    if df_daily is None or df_daily.empty:
        fig = go.Figure()
        fig.add_annotation(text="Sin datos de precio disponibles", x=0.5, y=0.5,
                           showarrow=False, font=dict(color=MUTED))
        fig.update_layout(**PLOTLY_LAYOUT, height=height)
        return fig

    df = df_daily.copy()
    dates = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df.index)
    close = df["Close"].astype(float)

    # Color según el rendimiento del periodo completo
    up = float(close.iloc[-1]) >= float(close.iloc[0])
    line_hex = GREEN if up else RED
    rgb = _hex_rgb(line_hex)

    lo, hi = float(close.min()), float(close.max())
    span = (hi - lo) or (hi * 0.02 or 1.0)
    y_lo = lo - span * 0.18          # suelo del degradado (bajo el eje visible)
    y_hi = hi + span * 0.10

    fig = go.Figure()

    # ── Degradado ──────────────────────────────────────────────────────────
    # Se corta el área bajo la línea en estratos HORIZONTALES (niveles de
    # precio fijos), no en bandas que sigan la curva: si siguen la curva se ven
    # los escalones como las curvas de nivel de un mapa. Cada traza recorta el
    # cierre a su nivel y rellena `tonexty` contra la anterior, de modo que
    # cada estrato pinta una franja limpia. La opacidad sube con la altura →
    # brillo intenso pegado a la línea que se desvanece hacia abajo.
    n_bands = 26
    levels = np.linspace(y_lo, hi, n_bands + 1)

    fig.add_trace(go.Scatter(
        x=dates, y=np.full(len(close), y_lo), mode="lines",
        line=dict(width=0, color=f"rgba({rgb},0)"),
        hoverinfo="skip", showlegend=False,
    ))
    for k in range(1, n_bands + 1):
        frac = k / n_bands
        alpha = 0.30 * (frac ** 2.0)     # invisible abajo, vivo junto a la línea
        fig.add_trace(go.Scatter(
            x=dates, y=close.clip(lower=y_lo, upper=levels[k]), mode="lines",
            line=dict(width=0, color=f"rgba({rgb},0)"),
            fill="tonexty", fillcolor=f"rgba({rgb},{alpha:.4f})",
            hoverinfo="skip", showlegend=False,
        ))

    # ── Halo difuso justo bajo la línea, para el efecto de brillo ──────────
    fig.add_trace(go.Scatter(
        x=dates, y=close, mode="lines",
        line=dict(color=f"rgba({rgb},0.18)", width=6, shape="spline", smoothing=0.4),
        hoverinfo="skip", showlegend=False,
    ))

    # ── Línea de precio (la única traza con hover) ─────────────────────────
    fig.add_trace(go.Scatter(
        x=dates, y=close, mode="lines", name=ticker,
        line=dict(color=line_hex, width=2, shape="spline", smoothing=0.4),
        hovertemplate="%{x|%d %b %Y}<br><b>$%{y:,.2f}</b><extra></extra>",
        showlegend=False,
    ))

    # Etiqueta de esquina, igual que en la gráfica de velas
    fig.add_annotation(
        text=f"<b>{ticker} — Precio</b>",
        xref="x domain", yref="y domain",
        x=0.01, y=0.97, xanchor="left", yanchor="top",
        showarrow=False,
        font=dict(size=12, color=TEXT, family="JetBrains Mono, monospace"),
        bgcolor="rgba(10,11,13,0.7)",
        bordercolor="rgba(226,178,92,0.20)",
        borderwidth=1, borderpad=4,
    )

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_MAIN,
        font=dict(color=TEXT, family="JetBrains Mono, monospace", size=11),
        height=height,
        hovermode="x unified",
        showlegend=False,
        margin=dict(l=10, r=10, t=30, b=10),
        hoverlabel=dict(bgcolor="rgba(16,18,22,0.95)", bordercolor=f"rgba({rgb},0.35)",
                        font=dict(color=TEXT, family="JetBrains Mono, monospace", size=11)),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID,
                     tickfont=dict(color=MUTED, size=9), showspikes=False)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID,
                     tickfont=dict(color=MUTED, size=9),
                     tickprefix="$", range=[y_lo, y_hi])
    return fig


# ── Tachómetro / Gauge ────────────────────────────────────────────────────

def build_gauge(score: float, recommendation: str) -> go.Figure:
    """Tachómetro DLP Score con el número GRANDE separado del arco para
    garantizar que NUNCA se solape (issue conocido de Plotly gauge+number
    en figuras pequeñas)."""

    rec_colors = {
        "STRONG BUY": "#3DD68C",
        "BUY":        "#6FA3E0",
        "WATCH":      "#E2B25C",
        "PASS":       "#F1495F",
    }
    color = rec_colors.get(recommendation, "#E2B25C")

    # Gauge SIN número — el arco vive en la parte superior de la figura
    # (domain y=[0.32, 1.0]) dejando espacio limpio abajo para el número.
    fig = go.Figure(go.Indicator(
        mode="gauge",
        value=score,
        domain={"x": [0, 1], "y": [0.32, 1.0]},
        title={
            "text": f"<b>DLP SCORE</b><br><span style='font-size:0.7em;color:{color}'>{recommendation}</span>",
            "font": {"size": 14, "color": TEXT},
        },
        gauge={
            "axis": {
                "range": [0, 100],
                "tickwidth": 1,
                "tickcolor": MUTED,
                "tickfont": {"color": MUTED, "size": 9},
                "dtick": 20,
            },
            "bar": {"color": color, "thickness": 0.3},
            "bgcolor": BG_CARD,
            "borderwidth": 1,
            "bordercolor": GRID,
            "steps": [
                {"range": [0, 50],  "color": "#160B0D"},
                {"range": [50, 65], "color": "#15120A"},
                {"range": [65, 80], "color": "#0A1A10"},
                {"range": [80, 100],"color": "#0A1A0A"},
            ],
            "threshold": {
                "line": {"color": WHITE, "width": 2},
                "thickness": 0.75,
                "value": score,
            },
        },
    ))

    # Número grande COMO ANNOTATION SEPARADA — vive en y=0.12 (bottom 12%)
    # debajo del arco del gauge. Imposible que se solape.
    fig.add_annotation(
        x=0.5, y=0.12,
        xref="paper", yref="paper",
        text=f"<b>{score:.0f}</b><span style='font-size:0.45em;color:{MUTED}'>/100</span>",
        showarrow=False,
        font=dict(size=44, color=color, family="JetBrains Mono"),
        align="center",
    )

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_MAIN,
        font=dict(color=TEXT),
        height=320,
        margin=dict(l=20, r=20, t=55, b=20),
    )

    return fig


# ── Snowflake Radar ────────────────────────────────────────────────────────

def build_snowflake(snowflake: dict) -> go.Figure:
    """
    Radar chart estilo SimplyWallSt: 5 dimensiones de calidad (0-20 cada una).
    """
    categories = {
        "value":    "Valor",
        "quality":  "Calidad",
        "growth":   "Crecimiento",
        "momentum": "Momentum",
        "future":   "Futuro",
    }

    labels = [categories.get(k, k) for k in ["value", "quality", "growth", "momentum", "future"]]
    values = [snowflake.get(k, 10) for k in ["value", "quality", "growth", "momentum", "future"]]
    values_closed = values + [values[0]]
    labels_closed = labels + [labels[0]]

    # Color según score total
    total = sum(values)
    if total >= 70:
        fill_color = "rgba(0,255,136,0.15)"
        line_color = GREEN
    elif total >= 50:
        fill_color = "rgba(255,165,0,0.15)"
        line_color = ORANGE
    else:
        fill_color = "rgba(255,59,92,0.15)"
        line_color = RED

    # Labels combinados: "Calidad · 19" — el valor queda al lado del label en el outer ring
    combined = [f"{labels[i]}  <b>{int(values[i])}</b>" for i in range(len(labels))]
    combined_closed = combined + [combined[0]]

    fig = go.Figure()

    # Área de fondo (escala máxima)
    fig.add_trace(go.Scatterpolar(
        r=[20] * len(combined_closed),
        theta=combined_closed,
        fill="toself",
        fillcolor="rgba(30,37,48,0.4)",
        line=dict(color=GRID, width=1),
        showlegend=False,
        hoverinfo="skip",
    ))

    # Score actual (sin texto en vértices — el valor ya está en el angular axis label)
    fig.add_trace(go.Scatterpolar(
        r=values_closed,
        theta=combined_closed,
        fill="toself",
        fillcolor=fill_color,
        line=dict(color=line_color, width=2.5),
        mode="lines+markers",
        marker=dict(size=10, color=line_color, line=dict(color=BG_MAIN, width=2)),
        showlegend=False,
        hovertemplate="<b>%{theta}</b><br>Score: %{r}/20<extra></extra>",
    ))

    fig.update_layout(
        polar=dict(
            bgcolor=BG_CARD,
            radialaxis=dict(
                range=[0, 22],
                showticklabels=False,   # Sin 5/10/15/20 — el valor está en el angular label
                showline=False,
                gridcolor=GRID,
            ),
            angularaxis=dict(
                tickfont=dict(size=10, color=TEXT, family="Inter"),
                gridcolor=GRID,
                linecolor=GRID,
            ),
        ),
        paper_bgcolor=BG_MAIN,
        font=dict(color=TEXT),
        height=340,
        # Márgenes laterales generosos para que los labels largos
        # ("Crecimiento 14", "Momentum 12", "💰 Valor 11") quepan sin
        # cortarse en los extremos del radar.
        margin=dict(l=70, r=70, t=55, b=50),
        title=dict(
            text="<b>PERFIL DE CALIDAD</b>",
            font=dict(color=MUTED, size=11),
            x=0.5,
        ),
        hoverlabel=dict(
            bgcolor="#1A1F28",
            bordercolor=line_color,
            font=dict(size=11, color=TEXT, family="JetBrains Mono"),
        ),
        showlegend=False,
    )

    return fig


# ── Score Breakdown Bar Chart ──────────────────────────────────────────────

def build_score_breakdown(score_breakdown: dict) -> go.Figure:
    """Desglose horizontal premium: barras con gradiente, zonas de calidad, sin tonterías."""

    # Prefijo = el MISMO código de sección que su pestaña (FN, TC, FU…), en oro,
    # en lugar de un emoji. Refleja el badge que aparece dentro de cada sección.
    def _lbl(code, name):
        return f"<span style='color:#E2B25C'><b>{code}</b></span>  {name}"
    agent_display = {
        "fundamentals":  _lbl("FN", "Fundamentales"),
        "technical":     _lbl("TC", "Técnico"),
        "future":        _lbl("FU", "Futuro"),
        "institutional": _lbl("SM", "Smart Money"),
        "catalysts":     _lbl("CT", "Catalizadores"),
        "macro":         _lbl("MC", "Macro"),
        "sentiment":     _lbl("SN", "Sentimiento"),
        "risk":          _lbl("RS", "Riesgo"),
    }
    order = ["fundamentals", "technical", "future", "institutional",
             "catalysts", "macro", "sentiment", "risk"]

    names  = [agent_display[k] for k in order]
    scores = [float(score_breakdown.get(k, 50)) for k in order]

    # Misma escala del termómetro que el resto de barras de calificación.
    bar_colors = [_score_color(s) for s in scores]

    fig = go.Figure()

    # Zonas de calidad (background)
    fig.add_vrect(x0=0,  x1=50,  fillcolor="rgba(241,73,95,0.04)", line_width=0)
    fig.add_vrect(x0=50, x1=65,  fillcolor="rgba(226,178,92,0.04)", line_width=0)
    fig.add_vrect(x0=65, x1=80,  fillcolor="rgba(111,163,224,0.04)", line_width=0)
    fig.add_vrect(x0=80, x1=100, fillcolor="rgba(61,214,140,0.05)", line_width=0)

    # Barras background (track gris) — para dar profundidad
    fig.add_trace(go.Bar(
        y=names,
        x=[100] * len(names),
        orientation="h",
        marker=dict(color="rgba(21,24,29,0.4)", line=dict(width=0)),
        showlegend=False,
        hoverinfo="skip",
        width=0.55,
    ))

    # Barras de score reales (encima)
    fig.add_trace(go.Bar(
        y=names,
        x=scores,
        orientation="h",
        marker=dict(
            color=bar_colors,
            line=dict(width=0),
            opacity=0.92,
        ),
        text=[f"<b>{s:.0f}</b>" for s in scores],
        textposition="outside",
        textfont=dict(size=12, color=TEXT, family="JetBrains Mono"),
        showlegend=False,
        hovertemplate="<b>%{y}</b><br>Score: %{x:.0f}/100<extra></extra>",
        width=0.55,
    ))

    # Threshold lines (dotted, sin labels intrusivos)
    fig.add_vline(x=65, line_dash="dot", line_color="#E2B25C",
                  line_width=1, opacity=0.4)
    fig.add_vline(x=80, line_dash="dot", line_color=GREEN,
                  line_width=1, opacity=0.35)

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_MAIN,
        font=dict(color=TEXT, family="Inter", size=11),
        height=380,
        barmode="overlay",
        bargap=0.25,
        xaxis=dict(
            range=[0, 108],
            gridcolor="rgba(0,0,0,0)",
            tickfont=dict(color=MUTED, size=9),
            zeroline=False,
            tickvals=[0, 25, 50, 65, 80, 100],
            ticktext=["0", "25", "50", "<span style='color:#E2B25C'>65</span>", "<span style='color:#3DD68C'>80</span>", "100"],
        ),
        yaxis=dict(
            gridcolor="rgba(0,0,0,0)",
            tickfont=dict(color=TEXT, size=11, family="Inter"),
            zeroline=False,
        ),
        title=dict(
            text="<b>DESGLOSE POR ANÁLISIS</b>",
            font=dict(color=MUTED, size=11, family="JetBrains Mono"),
            x=0,
            y=0.97,
        ),
        showlegend=False,
        margin=dict(l=10, r=50, t=40, b=20),
        hovermode="y unified",
        hoverlabel=dict(bgcolor="#15181D", bordercolor="rgba(226,178,92,0.3)",
                        font=dict(size=11, family="JetBrains Mono", color=TEXT)),
    )

    return fig


# ── Mini gauge para el sidebar ────────────────────────────────────────────

def build_mini_gauge(score: float) -> go.Figure:
    """Gauge pequeño para el sidebar watchlist."""
    if score >= 80:
        color = GREEN
    elif score >= 65:
        color = BLUE
    elif score >= 50:
        color = ORANGE
    else:
        color = RED

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        number={"font": {"size": 16, "color": color, "family": "JetBrains Mono"}},
        gauge={
            "axis": {"range": [0, 100], "visible": False},
            "bar":  {"color": color, "thickness": 0.4},
            "bgcolor": BG_CARD,
            "borderwidth": 0,
            "steps": [{"range": [0, 100], "color": "#101216"}],
        },
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=5, r=5, t=5, b=5),
        height=70,
    )

    return fig


# ── Sector Performance Chart ──────────────────────────────────────────────

def build_sector_heatmap(sector_performance: dict) -> go.Figure:
    """Bar chart de rendimiento sectorial."""
    if not sector_performance:
        return go.Figure()

    sorted_items = sorted(sector_performance.items(), key=lambda x: x[1], reverse=True)
    sectors = [s for s, _ in sorted_items]
    returns = [r for _, r in sorted_items]
    colors  = [GREEN if r >= 0 else RED for r in returns]

    fig = go.Figure(go.Bar(
        y=sectors,
        x=returns,
        orientation="h",
        marker_color=colors,
        marker_opacity=0.8,
        text=[f"{'+' if r >= 0 else ''}{r:.1f}%" for r in returns],
        textposition="outside",
        textfont=dict(size=10, color=TEXT),
    ))

    fig.add_vline(x=0, line_color=MUTED, line_width=1)

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT, family="JetBrains Mono, monospace", size=11),
        height=320,
        xaxis=dict(gridcolor=GRID, tickformat=".1f", ticksuffix="%", zerolinecolor=GRID),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", zerolinecolor=GRID),
        title=dict(text="<b>RENDIMIENTO SECTORIAL (1Y)</b>", font=dict(color=MUTED, size=11), x=0),
        showlegend=False,
        margin=dict(l=10, r=60, t=40, b=10),
    )

    return fig


# ── COMPONENTES REUTILIZABLES PARA TABS DE AGENTES ─────────────────────

def build_compact_gauge(value: float, label: str = "", color: str = None,
                         max_val: float = 100, height: int = 180, suffix: str = "") -> go.Figure:
    """Mini gauge para mostrar un valor 0-100 en un tab de agente."""
    if color is None:
        color = GREEN if value >= 70 else ORANGE if value >= 50 else RED

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": f"<b>{label}</b>" if label else "",
               "font": {"size": 11, "color": MUTED}} if label else None,
        number={"font": {"size": 32, "color": color, "family": "JetBrains Mono"},
                "suffix": suffix},
        gauge={
            "axis": {"range": [0, max_val], "tickwidth": 1, "tickcolor": MUTED,
                     "tickfont": {"size": 8, "color": MUTED}, "dtick": max_val / 4},
            "bar": {"color": color, "thickness": 0.32},
            "bgcolor": BG_CARD,
            "borderwidth": 0,
            "steps": [
                {"range": [0, max_val * 0.5], "color": "rgba(255,59,92,0.06)"},
                {"range": [max_val * 0.5, max_val * 0.75], "color": "rgba(255,184,77,0.06)"},
                {"range": [max_val * 0.75, max_val], "color": "rgba(0,255,136,0.06)"},
            ],
        },
    ))
    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        font=dict(color=TEXT),
        height=height,
        margin=dict(l=10, r=10, t=30 if label else 10, b=10),
    )
    return fig


def build_rsi_gauge(rsi: float, height: int = 200) -> go.Figure:
    """Gauge específico para RSI con zonas sobrecompra/sobreventa."""
    if rsi >= 70:
        color = RED
        zone = "SOBRECOMPRADO"
    elif rsi <= 30:
        color = GREEN
        zone = "SOBREVENDIDO"
    else:
        color = BLUE
        zone = "NEUTRAL"

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=rsi,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": f"<b>RSI 14</b><br><span style='font-size:0.7em;color:{color}'>{zone}</span>",
               "font": {"size": 12, "color": MUTED}},
        number={"font": {"size": 36, "color": color, "family": "JetBrains Mono"}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": MUTED,
                     "tickfont": {"size": 8, "color": MUTED}, "dtick": 25},
            "bar": {"color": color, "thickness": 0.35},
            "bgcolor": BG_CARD,
            "borderwidth": 0,
            "steps": [
                {"range": [0, 30],  "color": "rgba(0,255,136,0.18)"},
                {"range": [30, 70], "color": "rgba(74,158,255,0.06)"},
                {"range": [70, 100], "color": "rgba(255,59,92,0.18)"},
            ],
            "threshold": {"line": {"color": WHITE, "width": 2}, "thickness": 0.75, "value": rsi},
        },
    ))
    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        font=dict(color=TEXT),
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
    )
    return fig


def build_metric_bars(items: list, height: int = 220, title: str = "",
                      x_format: str = "%", x_zero_line: bool = True,
                      color_by_score: bool = False) -> go.Figure:
    """Bar chart horizontal genérico para métricas comparativas.
    items = [(label, value, color)]

    color_by_score=True → IGNORA el color fijo de cada item y pinta la barra
    según la escala del TERMÓMETRO (rojo → ámbar → verde, 0-100), igual que el
    resto de calificaciones de la app. Además dibuja un riel de fondo 0→100 para
    que se lea como una barra de progreso. Se usa en los sub-scores de
    Fundamentales y Futuro. Con el valor por defecto (False) el comportamiento
    es EXACTAMENTE el de siempre (gráficas del análisis técnico intactas)."""
    if not items:
        return go.Figure()

    labels = [i[0] for i in items]
    values = [i[1] if isinstance(i[1], (int, float)) else 0 for i in items]
    colors = [_score_color(v) for v in values] if color_by_score else [i[2] for i in items]

    text_vals = [
        (f"{v:+.2f}%" if x_format == "%" else f"{v:.0f}" if color_by_score
         else f"{v:.2f}") if isinstance(v, (int, float)) else "—"
        for v in values
    ]

    fig = go.Figure()

    # Riel de fondo (solo en modo calificación): 0→100 tenue, para que se vea
    # cuánto falta hasta el máximo.
    if color_by_score:
        fig.add_trace(go.Bar(
            y=labels, x=[100] * len(labels), orientation="h",
            marker=dict(color="rgba(255,255,255,0.035)", line=dict(width=0)),
            width=0.62, showlegend=False, hoverinfo="skip",
        ))

    bar_kwargs = dict(
        y=labels,
        x=values,
        orientation="h",
        marker_color=colors,
        marker_opacity=0.85,
        text=text_vals,
        textposition="outside",
        textfont=dict(size=10, color=TEXT, family="JetBrains Mono"),
    )
    if color_by_score:
        # Barra algo más fina que el riel + etiqueta sin recortar contra el eje.
        bar_kwargs.update(width=0.62, showlegend=False, cliponaxis=False,
                          hovertemplate="<b>%{y}</b><br>%{x:.0f}<extra></extra>")
    fig.add_trace(go.Bar(**bar_kwargs))

    if x_zero_line and not color_by_score:
        fig.add_vline(x=0, line_color=MUTED, line_width=1, opacity=0.5)

    xaxis = dict(gridcolor=GRID, tickfont=dict(color=MUTED, size=9), zerolinecolor=MUTED,
                 ticksuffix=("%" if x_format == "%" else ""))
    if color_by_score:
        # Escala fija 0-108 para que el riel completo y las etiquetas quepan.
        xaxis.update(range=[0, 108], gridcolor="rgba(0,0,0,0)", zeroline=False,
                     tickvals=[0, 25, 50, 65, 80, 100])

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT, family="Inter", size=11),
        height=height,
        showlegend=False,
        # overlay: el riel y la barra comparten fila en vez de ponerse en paralelo.
        barmode="overlay",
        margin=dict(l=10, r=60, t=40 if title else 10, b=10),
        title=dict(text=f"<b>{title}</b>", font=dict(color=MUTED, size=11), x=0) if title else None,
        xaxis=xaxis,
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(color=TEXT, size=10), zerolinecolor=GRID),
    )
    return fig


def build_earnings_history_chart(history: list, height: int = 250) -> go.Figure:
    """Bar chart de earnings surprises históricos."""
    if not history:
        return go.Figure()

    history = list(reversed(history))  # más antiguo primero (izq) → más reciente (der)
    dates = [h.get("date", "")[:10] for h in history]
    surprises = [h.get("surprise_pct", 0) for h in history]
    colors = [GREEN if s >= 0 else RED for s in surprises]

    fig = go.Figure(go.Bar(
        x=dates,
        y=surprises,
        marker_color=colors,
        marker_opacity=0.85,
        text=[f"{s:+.1f}%" for s in surprises],
        textposition="outside",
        textfont=dict(size=10, color=TEXT, family="JetBrains Mono"),
    ))

    fig.add_hline(y=0, line_color=MUTED, line_width=1, opacity=0.6)

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT, family="JetBrains Mono", size=10),
        height=height,
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=20),
        title=dict(text="<b>HISTORIAL EARNINGS SURPRISES</b>", font=dict(color=MUTED, size=11), x=0),
        xaxis=dict(gridcolor=GRID, tickfont=dict(color=MUTED, size=9), zerolinecolor=GRID),
        yaxis=dict(gridcolor=GRID, tickfont=dict(color=MUTED, size=9), zerolinecolor=GRID,
                   ticksuffix="%"),
    )
    return fig


def build_sentiment_gauge(score: float, height: int = 240) -> go.Figure:
    """Gauge especializado para sentimiento con etiquetas (Bearish → Bullish)."""
    if score >= 75:
        color, label = GREEN, "MUY BULLISH"
    elif score >= 55:
        color, label = "#4AFF88", "BULLISH"
    elif score >= 45:
        color, label = BLUE, "NEUTRAL"
    elif score >= 30:
        color, label = ORANGE, "BEARISH"
    else:
        color, label = RED, "MUY BEARISH"

    fig = go.Figure(go.Indicator(
        mode="gauge",
        value=score,
        domain={"x": [0, 1], "y": [0.32, 1.0]},
        title={"text": f"<b>SENTIMIENTO</b><br><span style='font-size:0.75em;color:{color}'>{label}</span>",
               "font": {"size": 12, "color": MUTED}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": MUTED,
                     "tickfont": {"size": 8, "color": MUTED}, "dtick": 25},
            "bar": {"color": color, "thickness": 0.32},
            "bgcolor": BG_CARD,
            "borderwidth": 0,
            "steps": [
                {"range": [0, 30],   "color": "rgba(255,59,92,0.18)"},
                {"range": [30, 45],  "color": "rgba(255,184,77,0.12)"},
                {"range": [45, 55],  "color": "rgba(74,158,255,0.06)"},
                {"range": [55, 75],  "color": "rgba(74,255,136,0.12)"},
                {"range": [75, 100], "color": "rgba(0,255,136,0.18)"},
            ],
        },
    ))
    # Número GRANDE como annotation separada — nunca se solapa con el arco
    fig.add_annotation(
        x=0.5, y=0.12,
        xref="paper", yref="paper",
        text=f"<b>{score:.0f}</b><span style='font-size:0.5em;color:{MUTED}'>/100</span>",
        showarrow=False,
        font=dict(size=36, color=color, family="JetBrains Mono"),
        align="center",
    )
    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        font=dict(color=TEXT),
        height=height + 60,
        margin=dict(l=20, r=20, t=55, b=20),
    )
    return fig


def build_holders_bars(holders: list, height: int = 260) -> go.Figure:
    """Top holders institucionales como barras horizontales con %."""
    if not holders:
        return go.Figure()

    items = []
    for h in holders[:10]:
        name = h.get("Holder") or h.get("holder") or "Unknown"
        pct = h.get("% Out") or h.get("pctHeld") or 0
        if isinstance(pct, str):
            try:
                pct = float(pct.replace("%", "")) / (100 if "%" in str(pct) else 1)
            except Exception:
                pct = 0
        items.append((str(name)[:30], pct * 100 if pct < 1 else pct))

    items.sort(key=lambda x: x[1], reverse=True)
    items = items[:8]

    fig = go.Figure(go.Bar(
        y=[i[0] for i in items],
        x=[i[1] for i in items],
        orientation="h",
        marker=dict(color=BLUE, opacity=0.8),
        text=[f"{i[1]:.2f}%" for i in items],
        textposition="outside",
        textfont=dict(size=10, color=TEXT, family="JetBrains Mono"),
    ))

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT, family="Inter", size=10),
        height=height,
        showlegend=False,
        margin=dict(l=10, r=40, t=40, b=10),
        title=dict(text="<b>TOP 8 INSTITUCIONALES (% outstanding)</b>", font=dict(color=MUTED, size=11), x=0),
        xaxis=dict(gridcolor=GRID, tickfont=dict(color=MUTED, size=9), ticksuffix="%", zerolinecolor=MUTED),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(color=TEXT, size=9),
                   autorange="reversed", zerolinecolor=GRID),
    )
    return fig


# ── Quick View Chart (compact line + volume) ──────────────────────────────

def build_quick_chart(df: pd.DataFrame, ticker: str, period_days: int = 126) -> go.Figure:
    """Chart compacto para Vista Rápida: línea de precio + MA50 + volumen."""
    if df is None or df.empty:
        return go.Figure()

    df = df.tail(period_days)
    if df.empty:
        return go.Figure()

    close = df["Close"]
    open_ = df["Open"]
    volume = df["Volume"]
    dates = df.index

    is_up = close.iloc[-1] >= close.iloc[0]
    line_color = GREEN if is_up else RED
    fill_color = "rgba(0,255,136,0.12)" if is_up else "rgba(255,59,92,0.12)"

    ma50 = close.rolling(50).mean()
    ma200 = close.rolling(200).mean() if len(close) >= 200 else None

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.78, 0.22],
    )

    # Línea de precio con fill area
    fig.add_trace(go.Scatter(
        x=dates, y=close,
        mode="lines",
        line=dict(color=line_color, width=2.2),
        fill="tonexty",
        fillcolor=fill_color,
        name="Precio",
        showlegend=False,
        hovertemplate="<b>%{x|%d %b %Y}</b><br>$%{y:.2f}<extra></extra>",
    ), row=1, col=1)

    # Baseline invisible para el fill
    fig.add_trace(go.Scatter(
        x=dates, y=[close.min() * 0.95] * len(dates),
        mode="lines",
        line=dict(color="rgba(0,0,0,0)"),
        showlegend=False,
        hoverinfo="skip",
    ), row=1, col=1)

    # MA50 dotted
    fig.add_trace(go.Scatter(
        x=dates, y=ma50,
        mode="lines",
        line=dict(color=YELLOW, width=1.2, dash="dot"),
        name="MA 50",
        showlegend=False,
        hovertemplate="MA50 $%{y:.2f}<extra></extra>",
    ), row=1, col=1)

    if ma200 is not None:
        fig.add_trace(go.Scatter(
            x=dates, y=ma200,
            mode="lines",
            line=dict(color=ORANGE, width=1.2, dash="dash"),
            name="MA 200",
            showlegend=False,
            hovertemplate="MA200 $%{y:.2f}<extra></extra>",
        ), row=1, col=1)

    # Volumen bars
    vol_colors = [GREEN if c >= o else RED for c, o in zip(close, open_)]
    fig.add_trace(go.Bar(
        x=dates, y=volume,
        marker_color=vol_colors,
        marker_opacity=0.5,
        showlegend=False,
        hovertemplate="Vol %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT, family="JetBrains Mono, monospace", size=10),
        height=360,
        margin=dict(l=8, r=8, t=8, b=8),
        hovermode="x unified",
        showlegend=False,
    )

    fig.update_xaxes(
        gridcolor=GRID, zerolinecolor=GRID,
        tickfont=dict(color=MUTED, size=9),
        showgrid=False,
        row=1, col=1,
    )
    fig.update_yaxes(
        gridcolor=GRID, zerolinecolor=GRID,
        tickfont=dict(color=MUTED, size=9),
        tickprefix="$",
        row=1, col=1,
    )
    fig.update_xaxes(
        gridcolor=GRID, showgrid=False,
        tickfont=dict(color=MUTED, size=9),
        row=2, col=1,
    )
    fig.update_yaxes(
        showgrid=False, showticklabels=False,
        row=2, col=1,
    )

    return fig


# ── Risk/Reward Visual ────────────────────────────────────────────────────

def build_rr_chart(current_price: float, stop: float, target: float, ticker: str,
                   compact: bool = False) -> go.Figure:
    """Visualización del Upside/Downside calculado desde el PRECIO ACTUAL hasta target/stop.

    compact=True → versión más baja y con tipografía menor, para que quepa en la
    columna estrecha del Overview sin perder legibilidad. Por defecto (False) el
    resultado es el de siempre, así la pestaña de Riesgo no cambia."""
    # Guarda robusta: rechaza None, NaN, infinito y no-positivos (un `all([...])`
    # a secas NO detecta NaN, que es "truthy" → antes esto rompía la gráfica y
    # el rango del eje con nan en producción).
    def _pos(x):
        try:
            x = float(x)
        except (TypeError, ValueError):
            return False
        return x == x and x not in (float("inf"), float("-inf")) and x > 0
    if not (_pos(current_price) and _pos(stop) and _pos(target)):
        return go.Figure()
    current_price, stop, target = float(current_price), float(stop), float(target)

    downside_pct = (current_price - stop) / current_price * 100
    upside_pct   = (target - current_price) / current_price * 100
    rr           = upside_pct / downside_pct if downside_pct > 0 else 0

    fig = go.Figure()

    # ── Escalera de precios ───────────────────────────────────────────────
    # Los EXTREMOS (target arriba y protección abajo) van SIEMPRE en la columna
    # IZQUIERDA y el PRECIO ACTUAL en la DERECHA. Al vivir en lados opuestos no
    # pueden solaparse nunca, ni cuando el precio actual queda pegadísimo a uno
    # de los dos extremos (antes los tres rótulos compartían columna y en ese
    # caso se mezclaban y no se podían leer).
    LEFT_X  = 0.27                      # borde DERECHO de las etiquetas de extremos
    BAND_X0, BAND_X1 = 0.30, 0.62       # banda de precio, en el centro
    # En compacto la etiqueta de la derecha arranca antes y se acorta: con el
    # ancho de la columna del Overview, "PRECIO ACTUAL $82.25" no cabía entero
    # y se recortaba contra el borde (se perdían los céntimos).
    RIGHT_X = 0.58 if compact else 0.65  # borde IZQUIERDO de la etiqueta de precio actual
    CURRENT_NAME = "ACTUAL" if compact else "PRECIO ACTUAL"
    PCT_X = (BAND_X0 + BAND_X1) / 2     # los % van centrados dentro de la banda
    # `compact` = la versión que cabe en la columna estrecha del Overview:
    # menos alto y tipografía más pequeña, mismo layout y misma información.
    lbl_size  = 9 if compact else 11
    pct_size  = 15 if compact else 19
    fig_h     = 250 if compact else 330
    tick_size = 8 if compact else 9

    # Zonas: su ALTURA es el hueco de precio real, así que la mayor se ve al
    # instante sin tener que leer los números.
    for y0, y1, fill in [
        (stop, current_price, "rgba(241,73,95,0.16)"),      # pérdida
        (current_price, target, "rgba(61,214,140,0.16)"),   # ganancia
    ]:
        fig.add_shape(type="rect", xref="paper", x0=BAND_X0, x1=BAND_X1,
                      y0=y0, y1=y1, fillcolor=fill, line=dict(width=0), layer="below")

    # Niveles: línea corta dentro de la banda + etiqueta en SU columna, a la
    # altura de su propio precio.
    for price, color, name, dash, x_pos, anchor in [
        (target,        GREEN,  "TARGET",        "dash",  LEFT_X,  "right"),
        (stop,          RED,    "PROTECCIÓN",    "dash",  LEFT_X,  "right"),
        (current_price, ORANGE, CURRENT_NAME,   "solid", RIGHT_X, "left"),
    ]:
        fig.add_shape(type="line", xref="paper", x0=BAND_X0 - 0.02, x1=BAND_X1 + 0.02,
                      y0=price, y1=price, line=dict(color=color, width=2, dash=dash))
        fig.add_annotation(
            xref="paper", x=x_pos, y=price, xanchor=anchor, yanchor="middle",
            text=f"<b>{name}</b>  ${price:,.2f}",
            showarrow=False, align="left",
            font=dict(color=color, size=lbl_size, family="JetBrains Mono"),
            bgcolor="rgba(11,14,17,0.82)", bordercolor=color,
            borderwidth=1, borderpad=4,
        )

    # Los dos números que importan: cuánto se gana y cuánto se arriesga.
    # Un % solo se dibuja si SU zona tiene altura suficiente. Cuando el precio
    # actual casi toca al target o a la protección esa zona queda como una
    # rendija y el texto se montaría encima de las etiquetas de precio (visto
    # con GOOGL: protección 323.60 vs actual 319.74). En ese caso se omite: el
    # dato sigue estando en las etiquetas y en el R/R del título.
    # `abs()` en el downside evita imprimir "−-1.2%" cuando la protección queda
    # por ENCIMA del precio actual (análisis cacheado que el precio ya invalidó).
    _visible = (target + (target - stop) * 0.20) - (stop - (target - stop) * 0.20)
    _min_alto = abs(_visible) * 0.10
    for (y0, y1), txt, color in [
        ((current_price, target), f"<b>+{upside_pct:.1f}%</b>", GREEN),
        ((stop, current_price),   f"<b>−{abs(downside_pct):.1f}%</b>", RED),
    ]:
        if abs(y1 - y0) < _min_alto:
            continue
        y_mid = (y0 + y1) / 2
        fig.add_annotation(xref="paper", x=PCT_X, y=y_mid, xanchor="center",
                           yanchor="middle", text=txt, showarrow=False,
                           font=dict(color=color, size=pct_size, family="JetBrains Mono"))

    # Holgura arriba y abajo para que las etiquetas de los extremos quepan
    # enteras (antes se recortaban contra el borde).
    span = max(target - stop, 1e-9)
    rr_color = GREEN if rr >= 3 else (ORANGE if rr >= 2 else RED)

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT, family="JetBrains Mono, monospace", size=11),
        height=fig_h,
        showlegend=False,
        yaxis=dict(range=[stop - span * 0.20, target + span * 0.20],
                   gridcolor=GRID, zerolinecolor=GRID,
                   tickprefix="$", tickfont=dict(color=MUTED, size=tick_size)),
        xaxis=dict(range=[0, 1], showticklabels=False, showgrid=False,
                   zeroline=False, fixedrange=True),
        margin=dict(l=8 if compact else 10, r=10 if compact else 20,
                    t=44 if compact else 52, b=12 if compact else 16),
        hovermode=False,
        title=dict(
            text=(f"<b>UPSIDE / DOWNSIDE</b>  ·  R/R {rr:.1f}:1" if compact else
                  f"<b>UPSIDE / DOWNSIDE</b>  ·  R/R {rr:.1f}:1  ·  desde precio actual"),
            font=dict(color=rr_color, size=11 if compact else 13),
            x=0.01,
            y=0.97,
        ),
    )

    return fig
