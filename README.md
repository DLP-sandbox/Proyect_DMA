# DLP Market Analyzer

Aplicación de análisis bursátil multi-agente para acciones del NYSE y NASDAQ.
Cuadro de mando estilo Bloomberg construido con Streamlit y la API de Claude.

## Stack

- **Frontend / Dashboard**: Streamlit + Plotly
- **AI / Análisis**: Anthropic Claude (Sonnet para orquestación, Haiku para sub-agentes)
- **Datos de mercado**: yfinance (gratuito), ta-lib para indicadores técnicos
- **Persistencia**: disco local (no base de datos)

## Cómo correr localmente

```bash
# Crear .env con tu key de Anthropic (copiar de .env.example)
cp .env.example .env
# editar .env con tu key real

# Instalar dependencias
pip install -r requirements.txt

# Lanzar
streamlit run dashboard/app.py
```

La app abre en `http://localhost:8501`.

## Deployment

Pensada para Streamlit Community Cloud. El `secrets.toml` real se configura
en el dashboard de Streamlit Cloud — no debe vivir en el repo.

Variable requerida en producción:
- `ANTHROPIC_API_KEY`

## Estructura

```
dashboard/app.py        # entrada principal Streamlit
dashboard/styles.py     # CSS (Bloomberg dark theme)
dashboard/charts.py     # gráficas Plotly
agents/                 # orquestador + 8 sub-agentes especializados
data/market_data.py     # capa de datos (yfinance + cache)
data/persistence.py     # save/load análisis a disco
config/settings.py      # modelos, pesos del composite score, umbrales
```
