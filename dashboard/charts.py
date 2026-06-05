"""
Componentes de visualización: gráfica de precios con indicadores,
tachómetro compuesto, snowflake radar, y mini-charts del sidebar.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Paleta Bloomberg ──────────────────────────────────────────────────────
BG_MAIN  = "#0B0E11"
BG_CARD  = "#0F1419"
GRID     = "#1A2030"
TEXT     = "#E0E0E0"
MUTED    = "#7A8898"
GREEN    = "#00FF88"
RED      = "#FF3B5C"
ORANGE   = "#FFA500"
BLUE     = "#4A9EFF"
PURPLE   = "#9B59FF"
YELLOW   = "#FFD740"
WHITE    = "#FFFFFF"

PLOTLY_LAYOUT = dict(
    paper_bgcolor=BG_MAIN,
    plot_bgcolor=BG_CARD,
    font=dict(color=TEXT, family="JetBrains Mono, monospace", size=11),
    xaxis=dict(gridcolor=GRID, zerolinecolor=GRID, showgrid=True),
    yaxis=dict(gridcolor=GRID, zerolinecolor=GRID, showgrid=True),
    margin=dict(l=10, r=10, t=40, b=10),
    hovermode="x unified",
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
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        subplot_titles=[f"{ticker} — Precio", "Volumen", "RSI 14", "MACD"],
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
            yanchor="bottom", y=1.01,
            xanchor="center", x=0.5,
            font=dict(size=10, color=TEXT),
            bgcolor="rgba(11,14,17,0.6)",
            bordercolor="rgba(255,184,77,0.15)",
            borderwidth=1,
        ),
        margin=dict(l=10, r=10, t=50, b=10),
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


# ── Tachómetro / Gauge ────────────────────────────────────────────────────

def build_gauge(score: float, recommendation: str) -> go.Figure:
    """Tachómetro grande con el DLP Score."""

    rec_colors = {
        "STRONG BUY": "#00FF88",
        "BUY":        "#4A9EFF",
        "WATCH":      "#FFA500",
        "PASS":       "#FF3B5C",
    }
    color = rec_colors.get(recommendation, "#FFA500")

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={
            "text": f"<b>DLP SCORE</b><br><span style='font-size:0.7em;color:{color}'>{recommendation}</span>",
            "font": {"size": 14, "color": TEXT},
        },
        number={
            "font": {"size": 42, "color": color, "family": "JetBrains Mono"},
            "suffix": "",
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
                {"range": [0, 50],  "color": "#1A0A0A"},
                {"range": [50, 65], "color": "#1A1200"},
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

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_MAIN,
        font=dict(color=TEXT),
        height=270,
        margin=dict(l=30, r=30, t=55, b=30),
    )

    return fig


# ── Snowflake Radar ────────────────────────────────────────────────────────

def build_snowflake(snowflake: dict) -> go.Figure:
    """
    Radar chart estilo SimplyWallSt: 5 dimensiones de calidad (0-20 cada una).
    """
    categories = {
        "value":    "💰 Valor",
        "quality":  "🏆 Calidad",
        "growth":   "📈 Crecimiento",
        "momentum": "⚡ Momentum",
        "future":   "🔭 Futuro",
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

    # Labels combinados: "🏆 Calidad · 19" — el valor queda al lado del label en el outer ring
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
                tickfont=dict(size=11, color=TEXT, family="Inter"),
                gridcolor=GRID,
                linecolor=GRID,
            ),
        ),
        paper_bgcolor=BG_MAIN,
        font=dict(color=TEXT),
        height=340,
        margin=dict(l=80, r=80, t=50, b=50),
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

    agent_display = {
        "fundamentals":  "📊  Fundamentales",
        "technical":     "📈  Técnico",
        "future":        "🔭  Futuro",
        "institutional": "🏦  Smart Money",
        "catalysts":     "⚡  Catalizadores",
        "macro":         "🌍  Macro",
        "sentiment":     "📰  Sentimiento",
        "risk":          "⚖️  Riesgo",
    }
    order = ["fundamentals", "technical", "future", "institutional",
             "catalysts", "macro", "sentiment", "risk"]

    names  = [agent_display[k] for k in order]
    scores = [float(score_breakdown.get(k, 50)) for k in order]

    def color_for(s):
        if s >= 80: return "#00FF88"
        if s >= 65: return "#4AFF88"
        if s >= 50: return "#FFB84D"
        if s >= 35: return "#FF8B3D"
        return "#FF3B5C"

    bar_colors = [color_for(s) for s in scores]

    fig = go.Figure()

    # Zonas de calidad (background)
    fig.add_vrect(x0=0,  x1=50,  fillcolor="rgba(255,59,92,0.04)", line_width=0)
    fig.add_vrect(x0=50, x1=65,  fillcolor="rgba(255,184,77,0.04)", line_width=0)
    fig.add_vrect(x0=65, x1=80,  fillcolor="rgba(74,158,255,0.04)", line_width=0)
    fig.add_vrect(x0=80, x1=100, fillcolor="rgba(0,255,136,0.05)", line_width=0)

    # Barras background (track gris) — para dar profundidad
    fig.add_trace(go.Bar(
        y=names,
        x=[100] * len(names),
        orientation="h",
        marker=dict(color="rgba(30,37,48,0.4)", line=dict(width=0)),
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
    fig.add_vline(x=65, line_dash="dot", line_color="#FFB84D",
                  line_width=1, opacity=0.4)
    fig.add_vline(x=80, line_dash="dot", line_color=GREEN,
                  line_width=1, opacity=0.35)

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_CARD,
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
            ticktext=["0", "25", "50", "<span style='color:#FFB84D'>65</span>", "<span style='color:#00FF88'>80</span>", "100"],
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
        hoverlabel=dict(bgcolor="#1A1F28", bordercolor="rgba(255,184,77,0.3)",
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
            "steps": [{"range": [0, 100], "color": "#141920"}],
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
                      x_format: str = "%", x_zero_line: bool = True) -> go.Figure:
    """Bar chart horizontal genérico para métricas comparativas.
    items = [(label, value, color)]"""
    if not items:
        return go.Figure()

    labels = [i[0] for i in items]
    values = [i[1] if isinstance(i[1], (int, float)) else 0 for i in items]
    colors = [i[2] for i in items]

    text_format = "%{x:+.2f}%" if x_format == "%" else "%{x:.2f}"
    text_vals = [
        (f"{v:+.2f}%" if x_format == "%" else f"{v:.2f}") if isinstance(v, (int, float)) else "—"
        for v in values
    ]

    fig = go.Figure(go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker_color=colors,
        marker_opacity=0.85,
        text=text_vals,
        textposition="outside",
        textfont=dict(size=10, color=TEXT, family="JetBrains Mono"),
    ))

    if x_zero_line:
        fig.add_vline(x=0, line_color=MUTED, line_width=1, opacity=0.5)

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT, family="Inter", size=11),
        height=height,
        showlegend=False,
        margin=dict(l=10, r=60, t=40 if title else 10, b=10),
        title=dict(text=f"<b>{title}</b>", font=dict(color=MUTED, size=11), x=0) if title else None,
        xaxis=dict(gridcolor=GRID, tickfont=dict(color=MUTED, size=9), zerolinecolor=MUTED,
                   ticksuffix=("%" if x_format == "%" else "")),
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
        mode="gauge+number",
        value=score,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": f"<b>SENTIMIENTO</b><br><span style='font-size:0.75em;color:{color}'>{label}</span>",
               "font": {"size": 12, "color": MUTED}},
        number={"font": {"size": 34, "color": color, "family": "JetBrains Mono"}, "suffix": ""},
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
    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        font=dict(color=TEXT),
        height=height + 20,
        margin=dict(l=30, r=30, t=55, b=30),
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

def build_rr_chart(current_price: float, stop: float, target: float, ticker: str) -> go.Figure:
    """Visualización del Upside/Downside calculado desde el PRECIO ACTUAL hasta target/stop."""
    if not all([current_price, stop, target]):
        return go.Figure()

    downside_pct = (current_price - stop) / current_price * 100
    upside_pct   = (target - current_price) / current_price * 100
    rr           = upside_pct / downside_pct if downside_pct > 0 else 0

    fig = go.Figure()

    # Zona de pérdida (stop → precio actual)
    fig.add_shape(type="rect",
        x0=0, x1=1, y0=stop, y1=current_price,
        fillcolor="rgba(255,59,92,0.1)",
        line=dict(width=0),
    )

    # Zona de ganancia (precio actual → target)
    fig.add_shape(type="rect",
        x0=0, x1=1, y0=current_price, y1=target,
        fillcolor="rgba(0,255,136,0.1)",
        line=dict(width=0),
    )

    # Líneas horizontales con labels INSIDE para que no se corten
    for price, color, label, dash in [
        (current_price, ORANGE, f"PRECIO ACTUAL · ${current_price:.2f}", "solid"),
        (stop,          RED,    f"PROTECCIÓN · ${stop:.2f} (-{downside_pct:.1f}%)", "dash"),
        (target,        GREEN,  f"TARGET · ${target:.2f} (+{upside_pct:.1f}%)", "dash"),
    ]:
        fig.add_hline(y=price, line_color=color, line_width=1.8, line_dash=dash,
                      annotation_text=label,
                      annotation_position="top left",
                      annotation_xanchor="left",
                      annotation_xshift=8,
                      annotation_yshift=-2,
                      annotation_font_color=color,
                      annotation_font_size=11,
                      annotation_font_family="JetBrains Mono",
                      annotation_bgcolor="rgba(11,14,17,0.85)",
                      annotation_bordercolor=color,
                      annotation_borderwidth=1,
                      annotation_borderpad=4)

    fig.update_layout(
        paper_bgcolor=BG_MAIN,
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT, family="JetBrains Mono, monospace", size=11),
        height=300,
        showlegend=False,
        yaxis=dict(range=[stop * 0.94, target * 1.06], gridcolor=GRID, zerolinecolor=GRID,
                   tickprefix="$", tickfont=dict(color=MUTED, size=9)),
        xaxis=dict(showticklabels=False, showgrid=False, zerolinecolor=GRID),
        margin=dict(l=10, r=20, t=50, b=15),
        hovermode=False,
        title=dict(
            text=f"<b>UPSIDE / DOWNSIDE</b>  ·  R/R {rr:.1f}:1  ·  desde precio actual",
            font=dict(color=GREEN if rr >= 3 else (ORANGE if rr >= 2 else RED), size=13),
            x=0.01,
            y=0.97,
        ),
    )

    return fig
