"""
DLP Market Analyzer — CLI Entry Point.
Uso: python main.py NVDA
     python main.py --scan
     streamlit run dashboard/app.py
"""
import argparse
import json
import os
import sys

def main():
    parser = argparse.ArgumentParser(
        description="DLP Market Analyzer — Sistema de Análisis Bursátil DLP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python main.py NVDA              Analiza NVIDIA
  python main.py AAPL MSFT GOOGL  Analiza múltiples tickers
  python main.py --scan            Escanea el mercado completo
  python main.py --dashboard       Lanza el terminal visual (Bloomberg-style)
        """
    )

    parser.add_argument("tickers", nargs="*", help="Tickers a analizar (ej: NVDA AAPL MSFT)")
    parser.add_argument("--scan", action="store_true", help="Escanear el mercado completo")
    parser.add_argument("--dashboard", action="store_true", help="Lanzar el dashboard visual")
    parser.add_argument("--output", choices=["text", "json"], default="text", help="Formato de salida")

    args = parser.parse_args()

    # Launch dashboard
    if args.dashboard or (not args.tickers and not args.scan):
        print("🚀 Lanzando DLP Market Analyzer...")
        os.execvp("streamlit", ["streamlit", "run", "dashboard/app.py"])
        return

    # Import aquí para no ralentizar el --help
    import anthropic
    from config.settings import ANTHROPIC_API_KEY
    from agents.orchestrator import Orchestrator
    from agents.screener import ScreenerAgent

    api_key = ANTHROPIC_API_KEY
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY no configurada.")
        print("   Crea un archivo .env con: ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    orchestrator = Orchestrator(client)

    def print_progress(agent_name: str, status: str):
        icon = {
            "Fundamentales":    "📊",
            "Técnico":          "📈",
            "Viabilidad Futura": "🔭",
            "Smart Money":      "🏦",
            "Catalizadores":    "⚡",
            "Macro & Sector":   "🌍",
            "Sentimiento":      "📰",
            "Riesgo & Sizing":  "⚖️",
            "Orquestador":      "👔",
        }.get(agent_name, "🔄")
        print(f"  {icon} {agent_name}: {status}")

    # Scan mode
    if args.scan:
        print("\n🌐 Iniciando scan del mercado (S&P500 + NASDAQ-100)...")
        screener = ScreenerAgent()

        def scan_progress(ticker, idx, total):
            if idx % 50 == 0:
                print(f"  Procesando: {idx}/{total} — {ticker}")

        results = screener.run_full_scan(callback=scan_progress)

        print(f"\n✅ Top {len(results)} candidatos encontrados:\n")
        print(f"{'Ticker':<8} {'Nombre':<30} {'Sector':<20} {'Precio':>8} {'Stage':>6} {'RS':>6} {'Mom6M':>8} {'Score':>6}")
        print("-" * 100)

        for r in results:
            stage_icon = "🟢" if r.stage == 2 else "🟡" if r.stage == 1 else "🔴"
            print(
                f"{r.ticker:<8} {r.name[:29]:<30} {r.sector[:19]:<20} "
                f"${r.price:>7.2f} {stage_icon}S{r.stage:>4} {r.rs_score:>5.0f} "
                f"{'+' if r.momentum_6m > 0 else ''}{r.momentum_6m:>6.1f}% {r.screener_score:>5.0f}"
            )

        print(f"\n💡 Usa 'python main.py {' '.join(r.ticker for r in results[:3])}' para análisis profundo")
        return

    # Análisis de tickers
    tickers = [t.upper() for t in args.tickers]
    all_results = []

    for ticker in tickers:
        print(f"\n{'='*60}")
        print(f"◈ Analizando {ticker}...")
        print(f"{'='*60}")

        analysis = orchestrator.analyze(ticker, progress_callback=print_progress)
        all_results.append(analysis)

        if args.output == "json":
            print(json.dumps(analysis.to_dict(), indent=2, ensure_ascii=False))
        else:
            _print_analysis(analysis)

    if len(all_results) > 1:
        print(f"\n{'='*60}")
        print("◈ RESUMEN COMPARATIVO")
        print(f"{'='*60}")
        print(f"{'Ticker':<8} {'Empresa':<30} {'Score':>6} {'Rec':>12} {'R/R':>6}")
        print("-" * 65)
        for a in sorted(all_results, key=lambda x: x.composite_score, reverse=True):
            rr = str(a.risk_reward) if a.risk_reward else "N/A"
            print(f"{a.ticker:<8} {a.company_name[:29]:<30} {a.composite_score:>5.1f} {a.recommendation:>12} {rr:>6}")


def _print_analysis(analysis):
    rec_symbols = {
        "STRONG BUY": "🟢🟢",
        "BUY":        "🟢",
        "WATCH":      "🟡",
        "PASS":       "🔴",
    }
    sym = rec_symbols.get(analysis.recommendation, "⚪")

    print(f"\n{sym} {analysis.recommendation} — Score: {analysis.composite_score:.1f}/100 — Conviction: {analysis.conviction_level}")
    print(f"   Empresa: {analysis.company_name} | Sector: {analysis.sector}")

    print(f"\n📊 SCORES POR AGENTE:")
    for agent, score in analysis.score_breakdown.items():
        bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
        print(f"   {agent:<15}: {bar} {score:.0f}/100")

    print(f"\n💰 SNOWFLAKE:")
    for dim, val in analysis.snowflake.items():
        stars = "★" * int(val / 4) + "☆" * (5 - int(val / 4))
        print(f"   {dim:<12}: {stars} ({val:.1f}/20)")

    if analysis.entry_price:
        print(f"\n⚖️ NIVELES:")
        print(f"   Entrada:  ${analysis.entry_price:.2f}")
        if analysis.stop_loss:
            risk = (analysis.entry_price - analysis.stop_loss) / analysis.entry_price * 100
            print(f"   Stop:     ${analysis.stop_loss:.2f}  (-{risk:.1f}%)")
        if analysis.target_price:
            reward = (analysis.target_price - analysis.entry_price) / analysis.entry_price * 100
            print(f"   Target:   ${analysis.target_price:.2f}  (+{reward:.1f}%)")
        if analysis.risk_reward:
            print(f"   R/R:      {analysis.risk_reward}")

    print(f"\n👔 TESIS (Orquestador):")
    thesis_lines = analysis.investment_thesis.split(". ")
    for line in thesis_lines[:4]:
        if line.strip():
            print(f"   {line.strip()}.")

    if analysis.key_strengths:
        print(f"\n✅ FORTALEZAS:")
        for s in analysis.key_strengths[:3]:
            print(f"   • {s}")

    if analysis.key_risks:
        print(f"\n⚠️  RIESGOS:")
        for r in analysis.key_risks[:2]:
            print(f"   • {r}")

    if analysis.vetos_applied:
        print(f"\n🚫 VETOS:")
        for v in analysis.vetos_applied:
            print(f"   • {v}")

    print(f"\n💡 Para el dashboard visual: streamlit run dashboard/app.py")


if __name__ == "__main__":
    main()
