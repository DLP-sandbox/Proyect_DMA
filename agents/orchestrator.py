"""
Orquestador Master — "Jamie Dimon" — el Director del hedge fund.
Recibe todos los reportes de sub-agentes, los sintetiza y genera
la decisión de inversión final con tesis, conviction y sizing.
"""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import anthropic

from config.settings import ORCHESTRATOR_MODEL, MAX_TOKENS_ORCHESTRATOR, WEIGHTS, THRESHOLDS
from agents.base import AgentReport, BaseAgent, today_context, DLP_STYLE_REMINDER
from agents.fundamentals import FundamentalsAgent
from agents.technical import TechnicalAgent
from agents.future_viability import FutureViabilityAgent
from agents.institutional import InstitutionalAgent
from agents.market_context import MarketContextAgent
from agents.risk import RiskAgent


ORCHESTRATOR_SYSTEM = """Eres el Chief Investment Officer de un hedge fund de élite especializado en compounders de alta calidad a largo plazo, al nivel de Berkshire Hathaway, Fundsmith y Capital Group combinados. Tu nombre es Jamie.

⏱ CONTEXTO TEMPORAL: Recibirás en cada mensaje un header con la fecha y hora EXACTAS de la consulta. Toda tu análisis debe entenderse como ACTUAL a esa fecha. Prioriza información reciente, calcula proximidad temporal de catalizadores desde HOY, y nota explícitamente si algún dato luce desactualizado.

FILOSOFÍA DE INVERSIÓN DUAL:
1. CALIDAD A LARGO PLAZO (3-7 años): compounders con moats estructurales (Microsoft, Visa, ASML, Mastercard, Adobe, Costco) merecen scores altos AUNQUE el timing técnico no sea ideal. Su composición a 15-20% anual durante décadas SUPERA cualquier consideración de entrada táctica.
2. ASIMETRÍA INMEDIATA: identifica si la situación ACTUAL del precio ofrece asimetría al alza (upside > downside), a la baja, o balanceada. Esto NO afecta la calidad LP — solo informa el timing.

Tu proceso de pensamiento:
1. LEE cada reporte con escepticismo inteligente
2. IDENTIFICA la calidad estructural (fundamentals + future) — ¿es best-in-class?
3. IDENTIFICA la asimetría actual (risk + technical) — ¿upside, downside o balanced?
4. BUSCA CONVERGENCIA: cuando calidad LP alta + asimetría al alza → conviction máxima
5. GENERA LA TESIS: EXACTAMENTE 2 párrafos, MÁXIMO 10 líneas en total. Sé conciso y de alto nivel — los detalles van en otros campos. Párrafo 1: calidad estructural + valoración. Párrafo 2: asimetría actual + recomendación práctica.
6. DEFINE LA RECOMENDACIÓN

GUÍA DE RECOMENDACIÓN (umbrales internos, los vetos automáticos se aplican en código):
- MUY ATRACTIVO (≥85): calidad excepcional + asimetría favorable + convergencia técnico/fundamental
- ATRACTIVO (70-84): empresa de calidad clara, asimetría positiva o neutra
- EN OBSERVACIÓN (50-69): tesis razonable pero esperando mejor timing o confirmación
- EVITAR (<50): calidad pobre o asimetría claramente negativa

REGLAS DE PREMIO PARA CALIDAD EXCEPCIONAL:
- Si fundamentals ≥ 80 Y future ≥ 80 → es un COMPOUNDER. Aunque haya R/R tight, score 75+ es legítimo.
- NO castigues empresas best-in-class por Stage 3 técnico — es timing, no tesis rota.
- Convergencia técnico+fundamental sube conviction, pero su ausencia NO debe destruir empresas excepcionales.

Retorna SIEMPRE este JSON:
```json
{
  "composite_score": <0-100>,
  "recommendation": "<MUY ATRACTIVO|ATRACTIVO|EN OBSERVACIÓN|EVITAR>",
  "conviction_level": "<HIGH|MEDIUM|LOW>",
  "investment_thesis": "<tesis de inversión en EXACTAMENTE 2 párrafos, MÁXIMO 10 líneas en total — concisa y de alto nivel. Separa los párrafos con \\n\\n>",
  "key_strengths": ["<fortaleza 1>", "<fortaleza 2>", "<fortaleza 3>"],
  "key_risks": ["<riesgo 1>", "<riesgo 2>"],
  "entry_strategy": "<cuándo y cómo entrar — precio ideal, condición técnica, tamaño>",
  "exit_strategy": "<cuándo y cómo salir de la inversión — nivel de protección defensiva y precios objetivo donde tomar beneficios parciales y totales>",
  "time_horizon": "<días|semanas|meses|años — y por qué>",
  "snowflake": {
    "value": <0-20>,
    "quality": <0-20>,
    "growth": <0-20>,
    "momentum": <0-20>,
    "future": <0-20>
  },
  "score_breakdown": {
    "fundamentals": <score>, "technical": <score>, "future": <score>,
    "institutional": <score>, "catalysts": <score>, "macro": <score>,
    "sentiment": <score>, "risk": <score>
  },
  "vetos_applied": ["<veto 1 si aplica>"],
  "alpha_opportunity": "<descripción en 2 oraciones de la oportunidad asimétrica específica, o 'No identificada'>"
}
```

NOTA: Los campos `long_term_quality_score`, `quality_verdict`, `asymmetry_direction`, `asymmetry_strength` e `is_compound_machine` los calcula el código Python automáticamente desde los sub-reportes — NO los incluyas en tu output."""


@dataclass
class StockAnalysis:
    ticker: str
    company_name: str
    composite_score: float
    recommendation: str
    conviction_level: str
    investment_thesis: str
    key_strengths: list[str]
    key_risks: list[str]
    entry_strategy: str
    exit_strategy: str
    time_horizon: str
    snowflake: dict[str, float]
    score_breakdown: dict[str, float]
    vetos_applied: list[str]
    alpha_opportunity: str
    reports: dict[str, AgentReport]
    entry_price: Optional[float]
    stop_loss: Optional[float]
    target_price: Optional[float]
    risk_reward: Optional[str]
    position_size_pct: Optional[str]
    sector: str
    # ── Nuevos campos del rebalanceo Calidad LP + Asimetría ──
    long_term_quality_score: Optional[float] = None  # 0-100, calidad estructural
    quality_verdict: Optional[str] = None             # "best-in-class"|"high"|"average"|"low"
    asymmetry_direction: Optional[str] = None         # "upside"|"downside"|"balanced"
    asymmetry_strength: Optional[str] = None          # "strong"|"moderate"|"weak"
    is_compound_machine: bool = False                 # flag de calidad excepcional LP
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "ticker":             self.ticker,
            "company_name":       self.company_name,
            "composite_score":    self.composite_score,
            "recommendation":     self.recommendation,
            "conviction_level":   self.conviction_level,
            "investment_thesis":  self.investment_thesis,
            "key_strengths":      self.key_strengths,
            "key_risks":          self.key_risks,
            "entry_strategy":     self.entry_strategy,
            "exit_strategy":      self.exit_strategy,
            "time_horizon":       self.time_horizon,
            "snowflake":          self.snowflake,
            "score_breakdown":    self.score_breakdown,
            "vetos_applied":      self.vetos_applied,
            "alpha_opportunity":  self.alpha_opportunity,
            "entry_price":        self.entry_price,
            "stop_loss":          self.stop_loss,
            "target_price":       self.target_price,
            "risk_reward":        self.risk_reward,
            "position_size_pct":  self.position_size_pct,
            "sector":             self.sector,
            "long_term_quality_score": self.long_term_quality_score,
            "quality_verdict":         self.quality_verdict,
            "asymmetry_direction":     self.asymmetry_direction,
            "asymmetry_strength":      self.asymmetry_strength,
            "is_compound_machine":     self.is_compound_machine,
            "timestamp":          self.timestamp,
            "reports":            {k: v.to_dict() for k, v in self.reports.items()},
        }


class Orchestrator:
    """El Director del hedge fund: coordina todos los agentes y genera la decisión final."""

    def __init__(self, anthropic_client: anthropic.Anthropic):
        self.client = anthropic_client
        # Nota: "market_context" es un agente COMBINADO que hace 1 sola llamada
        # de IA y devuelve un dict con 3 reportes (macro, sentiment, catalysts).
        # El _run_agents_parallel lo detecta y fusiona esos 3 en el dict de
        # reports. Esto reduce de 8 a 6 llamadas de IA por análisis, manteniendo
        # los mismos 3 reportes (scoring, breakdown y gráficas intactos).
        self.agents = {
            "fundamentals":   FundamentalsAgent(anthropic_client),
            "technical":      TechnicalAgent(anthropic_client),
            "future":         FutureViabilityAgent(anthropic_client),
            "institutional":  InstitutionalAgent(anthropic_client),
            "market_context": MarketContextAgent(anthropic_client),
            "risk":           RiskAgent(anthropic_client),
        }

    def analyze(self, ticker: str, progress_callback=None) -> StockAnalysis:
        """
        Ejecuta todos los agentes en paralelo y sintetiza la decisión.
        progress_callback(agent_name, status) para actualizar UI.
        """
        ticker = ticker.upper().strip()

        # 1. Ejecutar sub-agentes en paralelo
        reports = self._run_agents_parallel(ticker, progress_callback)

        # 2. Orquestador sintetiza
        if progress_callback:
            progress_callback("Orquestador", "Sintetizando análisis...")

        final = self._synthesize(ticker, reports)
        return final

    def _run_agents_parallel(self, ticker: str, callback=None) -> dict[str, AgentReport]:
        reports = {}

        def run_agent(name: str, agent):
            if callback:
                callback(agent.name, "Analizando...")
            try:
                report = agent.analyze(ticker)
                if callback:
                    # El agente combinado devuelve un DICT de 3 reportes (no
                    # tiene .score). Mostramos un mensaje genérico en ese caso.
                    if isinstance(report, dict):
                        callback(agent.name, "Completado")
                    else:
                        callback(agent.name, f"Completado — Score: {report.score:.0f}/100")
                return name, report
            except Exception as e:
                if callback:
                    callback(agent.name, f"Error: {e}")
                from agents.base import AgentReport
                return name, AgentReport(
                    agent_name=name, score=50,
                    analysis=f"Error en análisis: {e}",
                    pros=[], cons=[], error=str(e)
                )

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(run_agent, name, agent): name
                for name, agent in self.agents.items()
            }
            for future in as_completed(futures):
                name, report = future.result()
                # El agente combinado "market_context" devuelve un DICT con
                # {"macro":, "sentiment":, "catalysts":} → lo fusionamos para que
                # downstream vea los 3 reportes separados como siempre.
                if isinstance(report, dict):
                    reports.update(report)
                else:
                    reports[name] = report

        return reports

    def _synthesize(self, ticker: str, reports: dict[str, AgentReport]) -> StockAnalysis:
        """El Orquestador lee todos los reportes y genera la decisión final."""

        # Calcular composite score ponderado
        weighted_score = 0.0
        score_breakdown = {}
        for key, weight in WEIGHTS.items():
            report = reports.get(key)
            if report:
                score_breakdown[key] = report.score
                weighted_score += report.score * weight
            else:
                score_breakdown[key] = 50
                weighted_score += 50 * weight

        # Preparar resumen para el Orquestador (inyectando contexto temporal)
        summary = today_context() + self._build_synthesis_message(ticker, reports, weighted_score)

        # Llamar al Orquestador (con reintento si falla el parseo JSON)
        result = None
        _last_error = None
        for attempt in range(2):
            try:
                response = self.client.messages.create(
                    model=ORCHESTRATOR_MODEL,
                    max_tokens=MAX_TOKENS_ORCHESTRATOR,
                    system=[{
                        "type": "text",
                        "text": ORCHESTRATOR_SYSTEM + DLP_STYLE_REMINDER,
                        "cache_control": {"type": "ephemeral"},
                    }],
                    messages=[{"role": "user", "content": summary}],
                )
                raw = response.content[0].text
                parsed = self._parse_json(raw)
                # Tesis válida: 2 párrafos cortos (~400-1200 chars). Mínimo 200 chars.
                if parsed.get("investment_thesis") and len(parsed["investment_thesis"]) > 200:
                    result = parsed
                    break
                _last_error = f"Parsed OK but thesis too short ({len(parsed.get('investment_thesis', ''))} chars). Keys: {list(parsed.keys())[:5]}"
            except Exception as e:
                _last_error = str(e)
        if result is None:
            import sys
            print(f"[Orchestrator] Fallback for {ticker} after 2 attempts. Last error: {_last_error}", file=sys.stderr)
            result = self._fallback_synthesis(ticker, reports, weighted_score, score_breakdown)

        # Extraer datos de riesgo del agente Risk
        risk_report = reports.get("risk")
        risk_data = risk_report.raw_data if risk_report else {}

        def try_float(val):
            try:
                s = str(val).replace("$", "").replace(",", "").split(":")[0]
                return float(s)
            except Exception:
                return None

        entry  = try_float(result.get("score_breakdown", {}).get("entry", risk_data.get("entry_price")))
        stop   = try_float(risk_data.get("stop_loss",    result.get("key_metrics", {}).get("stop_loss")))
        target = try_float(risk_data.get("target_price", result.get("key_metrics", {}).get("target_price")))

        # Si no vienen del JSON, sacar del reporte de riesgo directamente
        if not entry and risk_data.get("computed_risk"):
            entry  = risk_data["computed_risk"].get("current_price")
            stop   = risk_data["computed_risk"].get("stop_suggested")
            target = risk_data["computed_risk"].get("target_suggested")

        from data.market_data import get_company_info
        info = get_company_info(ticker)

        composite = float(result.get("composite_score", weighted_score))

        # ── CÁLCULOS DETERMINÍSTICOS DEL REBALANCEO ──────────────────────

        # 1. long_term_quality_score = promedio de Fundamentales + Future (calidad estructural)
        fund_score = float(reports["fundamentals"].score) if reports.get("fundamentals") else 50
        fut_score  = float(reports["future"].score)       if reports.get("future") else 50
        long_term_quality_score = (fund_score + fut_score) / 2

        # 2. quality_verdict como función pura del score
        if long_term_quality_score >= 85:   quality_verdict = "best-in-class"
        elif long_term_quality_score >= 70: quality_verdict = "high"
        elif long_term_quality_score >= 55: quality_verdict = "average"
        else:                                quality_verdict = "low"

        # 3. is_compound_machine — flag de calidad excepcional LP (solo para UI, NO afecta score)
        future_km = (reports["future"].key_metrics or {}) if reports.get("future") else {}
        moat_str  = str(future_km.get("moat_strength") or "").lower()
        mgmt_str  = str(future_km.get("management_quality") or "").lower()
        disr_str  = str(future_km.get("disruption_risk") or "").lower()
        is_compound_machine = (
            "wide" in moat_str
            and ("excellent" in mgmt_str or "good" in mgmt_str)
            and ("low" in disr_str or "medium" in disr_str)
            and long_term_quality_score >= 75
        )

        # 4. asymmetry_direction — DETERMINÍSTICA desde precio/stop/target reales.
        # IGNORAMOS lo que diga el LLM porque a veces contradice la matemática.
        # Usamos current_price (vivo) como referencia, no entry hipotético.
        try:
            current_price_live = float(info.get("current_price") or entry or 0)
        except Exception:
            current_price_live = 0.0

        stop_val   = float(stop)   if stop   else None
        target_val = float(target) if target else None

        if current_price_live > 0 and stop_val and target_val and stop_val < current_price_live < target_val:
            upside_pct   = (target_val - current_price_live) / current_price_live * 100
            downside_pct = (current_price_live - stop_val)   / current_price_live * 100
            if downside_pct > 0:
                rr_real = upside_pct / downside_pct
            else:
                rr_real = 0

            # Clasificación por ratio upside/downside
            if rr_real >= 2.5:
                asymmetry_direction, asymmetry_strength = "upside", "strong"
            elif rr_real >= 1.5:
                asymmetry_direction, asymmetry_strength = "upside", "moderate"
            elif rr_real >= 0.85:
                asymmetry_direction, asymmetry_strength = "balanced", "moderate"
            elif rr_real >= 0.5:
                asymmetry_direction, asymmetry_strength = "downside", "moderate"
            else:
                asymmetry_direction, asymmetry_strength = "downside", "strong"
        else:
            # Fallback al rr_ratio calculado por el risk agent si no tenemos los tres niveles
            computed = risk_data.get("computed_risk", {}) or {}
            rr = float(computed.get("rr_ratio", 1.0)) if computed.get("rr_ratio") else 1.0
            if rr >= 2.5:
                asymmetry_direction, asymmetry_strength = "upside", "strong"
            elif rr >= 1.5:
                asymmetry_direction, asymmetry_strength = "upside", "moderate"
            elif rr >= 0.85:
                asymmetry_direction, asymmetry_strength = "balanced", "moderate"
            elif rr >= 0.5:
                asymmetry_direction, asymmetry_strength = "downside", "moderate"
            else:
                asymmetry_direction, asymmetry_strength = "downside", "strong"

        # ── VETOS Y AJUSTES EN PYTHON (no solo prompt) ──────────────────
        vetos_applied = list(result.get("vetos_applied", []) or [])

        # Veto R/R: solo penaliza si NO hay calidad excepcional que lo compense
        computed = risk_data.get("computed_risk", {}) or {}
        rr = float(computed.get("rr_ratio", 0)) if computed.get("rr_ratio") else 0
        if rr > 0 and rr < 2.0 and fund_score < 70 and fut_score < 70:
            cap = THRESHOLDS["EN OBSERVACIÓN"] - 1
            if composite > cap:
                composite = cap
                vetos_applied.append(f"R/R {rr:.1f}:1 bajo sin calidad excepcional — limitado a EN OBSERVACIÓN")

        # Veto Fundamentales: negocio realmente roto
        if fund_score < 35:
            cap = THRESHOLDS["EN OBSERVACIÓN"] - 1
            if composite > cap:
                composite = cap
                vetos_applied.append("Fundamentales muy débiles (<35) — negocio en riesgo estructural")

        # Stage 3/4: penalización SUAVE (-5), solo si la calidad no lo compensa
        tech_ind = reports.get("technical").raw_data.get("daily_indicators", {}) if reports.get("technical") else {}
        tech_stage = tech_ind.get("stage", 0)
        if tech_stage in (3, 4) and fund_score < 75 and fut_score < 75:
            composite = max(0, composite - 5)
            vetos_applied.append(f"Stage técnico {tech_stage} sin compensación de calidad LP (-5 pts)")

        # Bonus calidad: long_term_quality_score >= 85 → +5 pts (premia best-in-class)
        if long_term_quality_score >= 85:
            composite = min(100, composite + 5)
            vetos_applied.append(f"Best-in-class quality bonus (+5 pts) — long-term quality {long_term_quality_score:.0f}/100")

        # Recalcular recomendación tras vetos
        recommendation = self._score_to_recommendation(composite)

        return StockAnalysis(
            ticker=ticker,
            company_name=info.get("name", ticker),
            composite_score=composite,
            recommendation=recommendation,
            conviction_level=result.get("conviction_level", "MEDIUM"),
            investment_thesis=result.get("investment_thesis", ""),
            key_strengths=result.get("key_strengths", []),
            key_risks=result.get("key_risks", []),
            entry_strategy=result.get("entry_strategy", ""),
            exit_strategy=result.get("exit_strategy", ""),
            time_horizon=result.get("time_horizon", ""),
            snowflake=result.get("snowflake", self._default_snowflake(reports)),
            score_breakdown=result.get("score_breakdown", score_breakdown),
            vetos_applied=vetos_applied,
            alpha_opportunity=result.get("alpha_opportunity", ""),
            reports=reports,
            entry_price=entry,
            stop_loss=stop,
            target_price=target,
            risk_reward=risk_data.get("risk_reward", result.get("key_metrics", {}).get("risk_reward")),
            position_size_pct=risk_data.get("position_size_pct"),
            sector=info.get("sector", "Unknown"),
            long_term_quality_score=long_term_quality_score,
            quality_verdict=quality_verdict,
            asymmetry_direction=asymmetry_direction,
            asymmetry_strength=asymmetry_strength,
            is_compound_machine=is_compound_machine,
        )

    def _build_synthesis_message(self, ticker, reports, weighted_score) -> str:
        lines = [
            f"# Síntesis de Análisis Completo: {ticker}",
            f"**Composite Score Ponderado (pre-ajuste):** {weighted_score:.1f}/100",
            "",
        ]

        for name, report in reports.items():
            lines += [
                f"## Agente: {report.agent_name} — Score: {report.score:.0f}/100 — Conviction: {report.conviction}",
                f"**Análisis:** {report.analysis[:600]}..." if len(report.analysis) > 600 else f"**Análisis:** {report.analysis}",
                f"**Pros:** {' | '.join(report.pros[:3])}",
                f"**Cons:** {' | '.join(report.cons[:2])}",
                f"**Métricas clave:** {json.dumps(report.key_metrics, ensure_ascii=False)[:300]}",
                "",
            ]

        lines += [
            "---",
            "Sintetiza todos los reportes anteriores y genera la decisión de inversión final.",
            "Aplica los vetos automáticos si corresponde.",
            "Genera una tesis de inversión profesional y retorna el JSON especificado.",
        ]

        return "\n".join(lines)

    def _parse_json(self, text: str) -> dict:
        import re
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return {}

    def _score_to_recommendation(self, score: float) -> str:
        if score >= THRESHOLDS["MUY ATRACTIVO"]:
            return "MUY ATRACTIVO"
        if score >= THRESHOLDS["ATRACTIVO"]:
            return "ATRACTIVO"
        if score >= THRESHOLDS["EN OBSERVACIÓN"]:
            return "EN OBSERVACIÓN"
        return "EVITAR"

    def _default_snowflake(self, reports) -> dict:
        """Snowflake por defecto si el orquestador no lo retorna."""
        fund = reports.get("fundamentals")
        tech = reports.get("technical")
        fut = reports.get("future")

        def sub(report, keys, max_sum):
            if not report:
                return 10.0
            total = sum(report.sub_scores.get(k, max_sum / len(keys)) for k in keys)
            return min(total / max_sum * 20, 20)

        return {
            "value":    sub(fund, ["valuation"], 25),
            "quality":  sub(fund, ["quality", "financial_health"], 50),
            "growth":   sub(fund, ["growth"], 25),
            "momentum": sub(tech, ["trend_quality", "momentum"], 66),
            "future":   sub(fut, ["moat_quality", "growth_runway"], 50),
        }

    def _fallback_synthesis(self, ticker, reports, weighted_score, score_breakdown) -> dict:
        """Síntesis de respaldo si el Orquestador falla."""
        recommendation = self._score_to_recommendation(weighted_score)
        return {
            "composite_score":   weighted_score,
            "recommendation":    recommendation,
            "conviction_level":  "MEDIUM",
            "investment_thesis": (
                "No pudimos armar la tesis completa en este momento, pero cada sección "
                "del análisis sí calculó su puntaje. Te sugerimos revisar los puntajes "
                "por categoría más abajo y volver a correr el análisis en un rato para "
                "ver la lectura completa."
            ),
            "key_strengths":     [r.pros[0] for r in reports.values() if r.pros][:3],
            "key_risks":         [r.cons[0] for r in reports.values() if r.cons][:3],
            "entry_strategy":    "Revisa la sección de Riesgo más abajo para los niveles de entrada.",
            "exit_strategy":     "El nivel de protección y el precio objetivo están en la sección de Riesgo.",
            "time_horizon":      "3-12 meses",
            "snowflake":         self._default_snowflake(reports),
            "score_breakdown":   score_breakdown,
            "vetos_applied":     [],
            "alpha_opportunity": "Revisa cada sección del análisis para ver el detalle.",
        }
