"""
Persistencia de análisis y scans a disco.
Cada análisis se guarda en .history/analyses/{TICKER}.json y se recupera al abrir la app.
Cada scan se guarda en .history/scans/scan_{YYYYMMDD_HHMMSS}.json con label legible.
"""
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

HISTORY_DIR = Path(__file__).parent.parent / ".history"
ANALYSES_DIR = HISTORY_DIR / "analyses"
SCANS_DIR = HISTORY_DIR / "scans"

SPANISH_MONTHS = {
    1: "enero",   2: "febrero", 3: "marzo",     4: "abril",
    5: "mayo",    6: "junio",   7: "julio",     8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _ensure_dirs() -> None:
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
    SCANS_DIR.mkdir(parents=True, exist_ok=True)


def _make_json_safe(obj):
    """Convierte recursivamente cualquier objeto a tipos JSON-safe.
    Esto es CRÍTICO porque algunos agents guardan en raw_data dicts con
    claves de pandas.Timestamp que json.dumps NO puede serializar
    (las claves deben ser str/int/float/bool/None)."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_make_json_safe(v) for v in obj]
    # Objetos con to_dict (StockAnalysis, AgentReport)
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        try:
            return _make_json_safe(obj.to_dict())
        except Exception:
            return str(obj)
    # pandas Timestamp, datetime, etc. → str
    return str(obj)


def _safe_json_dumps(data) -> str:
    """Serializa a JSON sanitizando claves no-string primero."""
    safe = _make_json_safe(data)
    return json.dumps(safe, indent=2, ensure_ascii=False)


def _log_persistence_error(context: str, exc: Exception) -> None:
    """Log a .history/persistence_errors.log para no silenciar fallos."""
    try:
        _ensure_dirs()
        log_path = HISTORY_DIR / "persistence_errors.log"
        with log_path.open("a") as f:
            f.write(f"{datetime.now().isoformat()} [{context}] {type(exc).__name__}: {exc}\n")
    except Exception:
        pass


# ── ANALYSES ──────────────────────────────────────────────────────────────

def save_analysis(analysis) -> None:
    """Guarda un StockAnalysis en disco bajo .history/analyses/{TICKER}.json"""
    try:
        _ensure_dirs()
        path = ANALYSES_DIR / f"{analysis.ticker}.json"
        path.write_text(_safe_json_dumps(analysis.to_dict()))
    except Exception as e:
        _log_persistence_error(f"save_analysis:{getattr(analysis, 'ticker', '?')}", e)


def delete_analysis(ticker: str) -> None:
    path = ANALYSES_DIR / f"{ticker}.json"
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass


def load_all_analyses() -> dict:
    """Devuelve dict {ticker: StockAnalysis} reconstruido desde disco."""
    _ensure_dirs()
    result = {}
    for path in sorted(ANALYSES_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text())
            obj = stock_analysis_from_dict(data)
            if obj is not None:
                result[obj.ticker] = obj
        except Exception:
            continue
    return result


def stock_analysis_from_dict(d: dict):
    """Reconstruye un StockAnalysis (con sus AgentReports) desde dict."""
    from agents.base import AgentReport
    from agents.orchestrator import StockAnalysis

    reports = {}
    for k, v in (d.get("reports") or {}).items():
        if not isinstance(v, dict):
            continue
        try:
            reports[k] = AgentReport(
                agent_name=v.get("agent_name", k),
                score=float(v.get("score", 50)),
                analysis=v.get("analysis", ""),
                pros=list(v.get("pros") or []),
                cons=list(v.get("cons") or []),
                key_metrics=dict(v.get("key_metrics") or {}),
                conviction=v.get("conviction", "MEDIUM"),
                sub_scores=dict(v.get("sub_scores") or {}),
                raw_data=dict(v.get("raw_data") or {}),
                error=v.get("error"),
            )
        except Exception:
            continue

    try:
        return StockAnalysis(
            ticker=d["ticker"],
            company_name=d.get("company_name", d["ticker"]),
            composite_score=float(d.get("composite_score", 50)),
            recommendation=d.get("recommendation", "EN OBSERVACIÓN"),
            conviction_level=d.get("conviction_level", "MEDIUM"),
            investment_thesis=d.get("investment_thesis", ""),
            key_strengths=list(d.get("key_strengths") or []),
            key_risks=list(d.get("key_risks") or []),
            entry_strategy=d.get("entry_strategy", ""),
            exit_strategy=d.get("exit_strategy", ""),
            time_horizon=d.get("time_horizon", ""),
            snowflake=dict(d.get("snowflake") or {}),
            score_breakdown=dict(d.get("score_breakdown") or {}),
            vetos_applied=list(d.get("vetos_applied") or []),
            alpha_opportunity=d.get("alpha_opportunity", ""),
            reports=reports,
            entry_price=d.get("entry_price"),
            stop_loss=d.get("stop_loss"),
            target_price=d.get("target_price"),
            risk_reward=d.get("risk_reward"),
            position_size_pct=d.get("position_size_pct"),
            sector=d.get("sector", "Unknown"),
            # Campos nuevos rebalanceo — defaults None/False para backward compat
            long_term_quality_score=d.get("long_term_quality_score"),
            quality_verdict=d.get("quality_verdict"),
            asymmetry_direction=d.get("asymmetry_direction"),
            asymmetry_strength=d.get("asymmetry_strength"),
            is_compound_machine=bool(d.get("is_compound_machine", False)),
            timestamp=d.get("timestamp", datetime.now().isoformat()),
        )
    except Exception:
        return None


# ── SCANS ─────────────────────────────────────────────────────────────────

def scan_label(dt: datetime) -> str:
    """Etiqueta legible en español: 'Scan mayo 17'."""
    month_es = SPANISH_MONTHS.get(dt.month, dt.strftime("%B"))
    return f"Scan {month_es} {dt.day}"


def scan_label_with_time(dt: datetime) -> str:
    return f"{scan_label(dt)} · {dt.strftime('%H:%M')}"


def save_scan(scan_results) -> Optional[str]:
    """Guarda lista de ScreenerResult. Retorna scan_id."""
    if not scan_results:
        return None
    try:
        _ensure_dirs()
        now = datetime.now()
        scan_id = now.strftime("%Y%m%d_%H%M%S")

        results_data = []
        for r in scan_results:
            try:
                results_data.append(asdict(r))
            except Exception:
                try:
                    results_data.append(dict(r.__dict__))
                except Exception:
                    pass

        data = {
            "scan_id":   scan_id,
            "timestamp": now.isoformat(),
            "label":     scan_label(now),
            "count":     len(scan_results),
            "results":   results_data,
        }
        (SCANS_DIR / f"scan_{scan_id}.json").write_text(_safe_json_dumps(data))
        return scan_id
    except Exception as e:
        _log_persistence_error("save_scan", e)
        return None


def load_all_scans_meta() -> list[dict]:
    """Devuelve metadata de todos los scans (sin cargar results), ordenados desc por fecha."""
    _ensure_dirs()
    metas = []
    for path in SCANS_DIR.glob("scan_*.json"):
        try:
            data = json.loads(path.read_text())
            metas.append({
                "scan_id":   data.get("scan_id"),
                "timestamp": data.get("timestamp"),
                "label":     data.get("label"),
                "count":     data.get("count", 0),
            })
        except Exception:
            continue
    metas.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return metas


def get_scan_history_labels() -> list[tuple]:
    """Lista (scan_id, display_label, count) — añade hora si hay varios mismo día."""
    metas = load_all_scans_meta()

    by_day = {}
    for m in metas:
        try:
            dt = datetime.fromisoformat(m["timestamp"])
            day_key = dt.strftime("%Y-%m-%d")
            by_day.setdefault(day_key, []).append((m, dt))
        except Exception:
            continue

    out = []
    for day, items in by_day.items():
        if len(items) == 1:
            m, dt = items[0]
            out.append((m["scan_id"], scan_label(dt), m.get("count", 0)))
        else:
            for m, dt in items:
                out.append((m["scan_id"], scan_label_with_time(dt), m.get("count", 0)))

    out.sort(key=lambda x: x[0], reverse=True)
    return out


def load_scan_by_id(scan_id: str) -> list:
    """Carga los ScreenerResult de un scan específico."""
    from agents.screener import ScreenerResult
    path = SCANS_DIR / f"scan_{scan_id}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        results = []
        for r in data.get("results", []):
            try:
                results.append(ScreenerResult(**r))
            except Exception:
                continue
        return results
    except Exception:
        return []


def delete_scan(scan_id: str) -> None:
    path = SCANS_DIR / f"scan_{scan_id}.json"
    if path.exists():
        try:
            path.unlink()
        except Exception:
            pass
