# PROMPT — Aplicar el rediseño de DLP Analyzer a ESTA copia (Opus 4.8)

> Pega este documento COMPLETO como primer mensaje en la copia que quieras
> actualizar. Está escrito para **Opus 4.8**. No es un plan para debatir: es una
> lista de cambios concretos que **debes ejecutar**.
>
> **Esta copia genera sus análisis con IA REAL (API de Anthropic + claves del
> usuario).** El objetivo es aplicar TODO el rediseño visual y las funciones
> nuevas (gráfica Pro/Básico, termómetros rojo→verde, tarjetas de señal)
> **sin dañar en absoluto el funcionamiento de la IA ni los flujos de trabajo.**
> El rediseño es solo presentación; la IA vive en archivos que tienes
> terminantemente prohibido tocar (ver la sección ⚠️).

---

## LEE ESTO PRIMERO — POR QUÉ EL INTENTO ANTERIOR FALLÓ

Un intento previo de esta misma tarea **no cambió nada** porque el modelo fue
demasiado cauto: leyó, comparó, y concluyó "parece que ya está bien". **Eso es
un error.** Esta copia tiene el **diseño VIEJO**. Le faltan, con seguridad
absoluta, TODAS estas cosas:

- El sistema de tokens de color en `:root`.
- Las tarjetas de señal (`.signal-card`) para agrupar pros y contras.
- Los termómetros (`.meter`) rojo→ámbar→verde en las tarjetas de indicadores.
- La gráfica simplificada tipo *mountain* (`build_mountain_chart`).
- El selector **Pro / Básico** con encabezado "MODO DE ANÁLISIS".

**Tu trabajo es AÑADIR todo esto. La acción por defecto es HACER el cambio, no
saltártelo.** Solo te saltas un paso si el punto de anclaje literalmente no
existe en esta copia, y en ese caso lo REPORTAS explícitamente al final.

### Prueba de que estás en el sitio correcto (ejecútala YA)

```bash
grep -c "build_mountain_chart" dashboard/charts.py   # debe dar 0
grep -c "chart_mode_pro"       dashboard/app.py       # debe dar 0
grep -c "signal-card"          dashboard/styles.py    # debe dar 0
grep -c "\.meter-dot"          dashboard/styles.py    # debe dar 0
```

- Si **todos dan 0** → perfecto, esta copia NO tiene el rediseño. Procede.
- Si **alguno da >0** → esta copia ya tiene parte del rediseño, o estás en el
  repo equivocado. **PÁRATE y díselo al usuario** antes de tocar nada.

Nunca digas "ya está todo igual" sin haber ejecutado esta prueba y pegado su
resultado.

---

## ⚠️ ESTA COPIA USA IA REAL — QUÉ NO TOCAR JAMÁS

**Muy importante.** Esta copia **no** es la versión cliente. Genera sus análisis
con **inteligencia artificial real**, llamando a la **API de Anthropic** con las
claves del usuario. El rediseño que vas a aplicar es **100% de presentación** y
**no debe rozar** el motor de IA ni sus flujos. Si algo de lo que estás a punto
de hacer tocaría la IA, **no lo hagas y repórtalo**.

La IA y los flujos de trabajo viven aquí — **PROHIBIDO ESCRIBIR EN ELLOS**:

```
agents/*.py           ← los 13 agentes (base.py, orchestrator.py, technical.py,
                         fundamentals.py, sentiment.py, macro.py, risk.py, …).
                         Aquí se construyen los prompts y se llama a la API.
main.py               ← arranque / orquestación.
config/settings.py    ← configuración, modelos, parámetros de la API.
.env / .env.example   ← LAS CLAVES DE API. Ni leerlas hace falta. Jamás tocarlas.
data/*.py             ← capa de datos de mercado.
requirements.txt      ← dependencias.
```

Por qué esto es seguro por diseño: **todo el rediseño cae en
`dashboard/styles.py`, `dashboard/charts.py` y la capa VISUAL de
`dashboard/app.py`** — dibujar gráficas, tarjetas, termómetros y estilos. Nada de
eso es donde vive la IA. Mientras no toques la lista de arriba, el
funcionamiento de la IA **no puede** cambiar.

**Cuidado especial con `dashboard/app.py`:** en esta copia, ese archivo puede
contener llamadas relacionadas con la IA (disparar un análisis, leer el
resultado del orquestador, mostrar texto generado por el modelo). Tú SOLO
cambias lo **visual**: cómo se pinta una gráfica, una tarjeta o un termómetro.
**Nunca** toques una llamada a la API, al orquestador, ni la lógica que dispara o
consume el análisis de IA. Si una línea llama a un agente, a `orchestrator`, a
`anthropic`, a `client.messages`, o lee las claves → **no es tuya, no la toques.**

Antes de editar `app.py`, ubica esas zonas para NO pisarlas:

```bash
grep -n "anthropic\|messages.create\|orchestrat\|Orchestrat\|run_analysis\|\.env\|ANTHROPIC" dashboard/app.py
```

---

## LAS DOS FUENTES QUE VAS A USAR

1. **Código exacto, listo para copiar y pegar** (tu fuente principal):
   ```
   /Users/josesilva/Documents/Claude/CEREBRO/Sintesis/REDISENO-DLP-Codigo-Exacto.md
   ```
   Contiene los 12 bloques de código (CSS y Python) extraídos LITERALMENTE de la
   copia de referencia ya desplegada. Cada sección de este prompt te dice qué
   bloque de ahí usar. **Léelo entero antes de empezar.**

2. **La copia de referencia completa** (para ver el contexto y cómo encaja cada
   pieza en su función contenedora):
   ```
   REF=/Users/josesilva/Documents/Claude/APPS-DLP/L-DLP-Analysis-CLIENTES
   Read "$REF/dashboard/styles.py"
   Read "$REF/dashboard/charts.py"
   Read "$REF/dashboard/app.py"
   git -C "$REF" show a7c1b5e        # el rediseño completo
   git -C "$REF" show 7542ec4        # el fix de los botones en iframe estrecho
   ```
   Puedes LEER esa carpeta libremente (el vault de Obsidian lo permite). Lo que
   NO puedes es escribir en ella: escribes SOLO en tu propia copia.

**Regla de oro:** el código sale del bloque exacto o del fichero de referencia.
**Nunca lo reconstruyas de memoria ni lo "mejores".** Copia y adapta el anclaje.

---

## POR QUÉ NO HAY UN PARCHE QUE APLICAR

Esta copia es un repo git distinto y ha derivado del punto base (su `app.py`
difiere ~800–900 líneas). Un `git apply` fracasaría. Por eso trabajas **bloque a
bloque**: casi todo el rediseño es **aditivo** (funciones nuevas, CSS nuevo,
bloques de render nuevos), así que lo AÑADES; y donde hay que MODIFICAR algo
existente, editas con precisión el sitio equivalente de esta copia.

Antes de empezar, saca el mapa de diferencias de nombres de función:

```bash
diff <(grep -oE "^def [a-zA-Z_]+" "$REF/dashboard/app.py" | sort) \
     <(grep -oE "^def [a-zA-Z_]+" dashboard/app.py | sort)
```

Eso te dice qué funciones tienen otro nombre o no existen aquí. Si una función
de destino tiene otro nombre, adapta; si no existe, repórtalo.

---

## GUARDARRAÍLES (INNEGOCIABLES)

1. Tocas SOLO: `dashboard/styles.py`, `dashboard/charts.py`, y la **capa visual**
   de `dashboard/app.py`. (En la versión cliente había además una cadena en
   `agents/screener.py`; en esta copia con IA ese archivo puede no existir —
   ver Paso 14, que es condicional.)
2. NUNCA tocas `agents/`, `main.py`, `config/`, `data/`, `.env`,
   `requirements.txt`, ni nada de despliegue. **Ahí vive la IA — ver la sección
   ⚠️ de arriba.**
2b. En `dashboard/app.py` cambias SOLO presentación (gráficas, tarjetas,
   termómetros, estilos). **Ninguna llamada a la API, al orquestador o a un
   agente. Ninguna lógica que dispare o consuma el análisis de IA.**
3. NUNCA cambias el `key=` de un widget existente ni las claves de
   `st.session_state`. Cambiarlas resetea el estado del usuario en silencio.
4. NUNCA renombras ni borras funciones `render_*`, `_render_*`, `build_*`.
   Puedes AÑADIR nuevas.
5. NUNCA quitas `inject_protection` ni el bloqueo de clic derecho si existen.
6. `build_price_chart` **no se toca ni una línea**. El modo Pro debe seguir
   siendo la gráfica que ya existe.
7. No cambias ninguna matemática (scores, indicadores, filtros). Esto es
   presentación.
8. **Nada de commit ni push hasta que el usuario apruebe en `localhost:8501`.**

---

## LOS CAMBIOS — EJECÚTALOS EN ESTE ORDEN

Cada paso dice: **qué archivo**, **qué bloque del código exacto usar**, y **si es
AÑADIR o REEMPLAZAR**.

### PASO 1 — `styles.py`: tokens `:root`  ·  bloque **#1**
Reemplaza el `:root { … }` actual de esta copia por el del bloque #1. Si la copia
tiene variables propias dentro de su `:root` que el bloque #1 no incluye,
CONSÉRVALAS (fusiona: añade las nuevas, no borres las suyas). Valores eje que
deben quedar exactos:

```
--bg:#0A0B0D   --surface-1:#101216   --hairline: 1px casi invisible
--text-hi:#F2F3F5  --text:#C9CDD3  --text-2:#8D949E  --text-3: más tenue
--accent:#E2B25C (+ --accent-rgb)   --pos:#3DD68C (+ --pos-rgb)
--neg:#F1495F (+ --neg-rgb)         --info:#6FA3E0
--ease-out: cubic-bezier(0.23,1,0.32,1)   --dur-1/2/3: todas < 300ms
```

### PASO 2 — `styles.py`: `.analysis-text` SIN `max-width`  ·  bloque **#2**
Busca `.analysis-text` en esta copia. Si tiene `max-width`, QUÍTALO. Si no tiene
la regla, añádela igual que el bloque #2. (Un `max-width` aquí es lo que aplasta
el texto en vertical.)

### PASO 3 — `styles.py`: MODO DE ANÁLISIS + botones Pro/Básico + iconos  ·  bloque **#3**
AÑADE el bloque #3 completo. Trae: encabezado `.mode-switch-head`, los botones
anclados por `.st-key-chart_mode_pro` / `.st-key-chart_mode_basico`, el estado
activo en oro, los **dos iconos SVG** (velas rojas/verdes para Pro, mini
mountain verde para Básico) y la **media query < 640px** que evita que la
etiqueta se parta en el iframe de Whop. Cópialo TAL CUAL (los `%23` de los SVG y
la ausencia de comillas dobles son críticos).

### PASO 4 — `styles.py`: encabezados de bloque del escáner  ·  bloque **#4**
AÑADE el bloque #4 (`.scanner-group-head` y sus hijos).

### PASO 5 — `styles.py`: fix del badge del sidebar  ·  bloque **#5**
Busca `.sb-badge-wrap` en esta copia. Reemplaza su regla de padding y la de
`::before` por las del bloque #5 (padding-left holgado + punto recolocado a
`left:7px`). Si esta copia no tiene `.sb-badge-wrap`, repórtalo y sigue.

### PASO 6 — `styles.py`: signal cards + termómetros  ·  bloque **#6**
AÑADE el bloque #6 (`.signal-card`, `--pos/--neg`, `.meter`, `.meter-dot`).

### PASO 7 — `charts.py`: paleta espejo  ·  bloque **#7**
Reemplaza las constantes de color del tope de `charts.py` (BG_MAIN, GRID, TEXT,
GREEN, RED, ORANGE, …) por las del bloque #7, y pon `plot_bgcolor=BG_MAIN` en
`PLOTLY_LAYOUT`. Son los MISMOS hex que los tokens CSS.

### PASO 8 — `charts.py`: `build_mountain_chart`  ·  bloque **#8**
AÑADE `_hex_rgb` y `build_mountain_chart` (bloque #8) justo antes del comentario
`# ── Tachómetro / Gauge ──` (o al final del archivo si ese comentario no está).
**No toca `build_price_chart`.**

### PASO 9 — `app.py`: wrapper perezoso  ·  bloque **#9**
Si esta copia usa envoltorios `def build_*(*a, **k): return _charts().build_*`,
añade la línea del bloque #9 junto a los demás. Si NO usa ese patrón (llama a
`charts.build_price_chart` directamente), IGNORA este paso y en el Paso 12 llama
a `charts.build_mountain_chart` del mismo modo que la copia llame a las suyas.

### PASO 10 — `app.py`: helpers de meters y signal cards  ·  bloque **#10**
AÑADE el bloque #10 completo (`_strip_ui_emoji`, `_meter_scale`, `_meter_html`,
`_signal_card_html`, `_render_pros_cons`, `_render_insight_card`). Son funciones
nuevas, no chocan con nada.

### PASO 11 — `app.py`: `_scanner_group_head`  ·  bloque **#11**
AÑADE `_scanner_group_head` (bloque #11) justo antes de `render_scanner_config`.

### PASO 12 — `app.py`: bloque MODO DE ANÁLISIS en la pestaña técnica  ·  bloque **#12**
En esta copia, busca la función que dibuja la pestaña técnica (probablemente
`render_technical`) y, en concreto, el punto donde llama a `build_price_chart` y
lo pinta con `st.plotly_chart`. Sustituye ese trozo por el bloque #12, que:
- calcula `mode` (Pro/Básico) con reset a Pro al cambiar de acción,
- pinta el encabezado "MODO DE ANÁLISIS",
- dibuja los dos `st.button` (`key="chart_mode_pro"` / `"chart_mode_basico"`)
  centrados con columnas `[1,2,2,1]`,
- elige `build_mountain_chart` si `is_line` o `build_price_chart` si no,
- retira la barra de Plotly con `config={"displayModeBar": False}`.

Adapta los nombres de `df`, `indicators` y `analysis.ticker` a como se llamen en
esta copia. **No inventes:** míralos en la función real antes de editar.

### PASO 13 — Escáner reorganizado en 3 bloques
Este es el único paso sin bloque de copiar-pegar, porque depende del layout de
esta copia. Abre `render_scanner_config` aquí y compárala con la de referencia
(`grep -n "_scanner_group_head\|st.columns" "$REF/dashboard/app.py"`). Reagrupa
las tarjetas así, insertando `_scanner_group_head(...)` antes de cada bloque:

```
① "Qué empresas buscar"     → Sectores (ancho completo) · Tamaño | Liquidez
② "Cómo se está comportando"→ Tendencia | Fortaleza vs mercado
                              Momentum  | Cercanía al máximo
③ "Qué quieres ver"         → Cantidad de resultados (centrada)
```
**Clave:** cada fila abre SUS PROPIAS `st.columns(2)` (no dos columnas largas
apiladas: un número impar de tarjetas desfasa la columna derecha). Las tarjetas
se mueven **intactas** — mismo `key`, misma clave de `sf`, mismo callback.
Después, verifica que `build_screener_filters(sf)` devuelve el mismo dict que
antes (Paso de verificación 5.4). Si el escáner de esta copia es muy distinto y
no puedes mapear las tarjetas con seguridad, **haz solo lo que sea seguro y
reporta el resto** en vez de arriesgar.

### PASO 14 — Textos de carga sin marca del proveedor  (CONDICIONAL)
Este paso solo aplica si esta copia tiene un escáner de mercado. Compruébalo:
```bash
ls agents/screener.py 2>/dev/null && grep -rn "TradingView\|Consultando" dashboard/app.py agents/screener.py 2>/dev/null
```
- Si NO hay escáner / no aparece esa marca → **sáltate este paso** y anótalo.
- Si lo hay: en `app.py`, el spinner → `"Escaneando el mercado…"`. Y si existe
  `agents/screener.py` con una etiqueta tipo `"Consultando TradingView…"`,
  cámbiala a `"Recopilando datos…"`. **Esa cadena de texto es la ÚNICA excepción
  a "no tocar `agents/`", y solo si existe.** No cambies nada más de ese archivo.

### PASO 15 — Termómetros y signal cards en las secciones de análisis
Con los helpers del Paso 10 ya disponibles, conéctalos donde la referencia los
usa. Mira en `$REF/dashboard/app.py` cómo se llaman:
- `_render_pros_cons(report, …)` para pros/contras en tarjetas.
- La clave opcional `meter` que `_render_metric_tiles` / `_render_status_pills`
  aceptan en cada tile, en Fundamentales, Futuro, Smart Money, Macro y
  Sentimiento (`inst_level`/`inst_meter`, `short_level`/`short_meter` para Smart
  Money).

**⚠️ AQUÍ ESTÁ EL RIESGO CON LA IA. LÉELO DESPACIO.** En esta copia los datos de
cada análisis (los `report`) **los produce el modelo de IA**, no un motor de
código, así que **la forma y los nombres de los campos pueden ser distintos** a
los de la referencia. Por eso:

- **Nunca cambies cómo se genera el `report`.** Solo cambias cómo se PINTA.
- **Lee los campos de forma defensiva.** Antes de calcular un termómetro,
  comprueba que el campo existe y es numérico; si no está, **no pintes el
  termómetro** (la clave `meter` es opcional y la tile se renderiza igual que
  antes). Patrón obligatorio:
  ```python
  val = report.get("campo") if isinstance(report, dict) else getattr(report, "campo", None)
  meter = _meter_scale(val, lo, hi) if isinstance(val, (int, float)) else None
  ```
- **Jamás inventes un valor** para rellenar un termómetro. Si el dato no está, el
  termómetro no aparece — y ya está. Un termómetro con un número inventado es
  peor que no tenerlo.
- Antes de tocar una sección, mira con qué estructura real llega su `report` en
  ESTA copia (imprime el objeto en un análisis real) y adapta los nombres de
  campo. No asumas los de la referencia.

Haz esto sección por sección. Si en alguna no logras mapear los campos con
seguridad, aplica el termómetro solo donde estés seguro y **reporta las que
dejaste sin termómetro** en vez de arriesgar un dato falso.

---

## TRAMPAS YA PAGADAS — NO LAS REPITAS

Cada una costó una iteración fallida en la referencia. Están verificadas.

**T1 — `minallowed`/`maxallowed` rompe las gráficas con subplots.** En una
figura de subplots, Plotly.js falla al escalar los ejes y **la gráfica entera
deja de pintarse** (kaleido: error 525). No uses esos atributos. `build_mountain_chart`
ya está escrito sin ellos: no los añadas.

**T2 — Los `Timestamp` tz-aware se serializan con offset.** El índice de
yfinance lleva zona horaria; en un atributo de eje se escribe como
`...-04:00`, que Plotly.js no sabe leer. Si algún día fijas un rango de fechas,
conviértelo a texto plano sin tz (`tz_localize(None)` + `strftime`).

**T3 — `data-testid="stSegmentedControl"` NO EXISTE.** El contenedor real es
`stButtonGroup`. Por eso el rediseño usa dos `st.button` anclados por
`.st-key-<key>`, no `st.segmented_control`. No lo "simplifiques" a segmented.

**T4 — `.stApp button[kind="primary"]` te pisa el diseño.** El override global
de botones primarios usa `!important` y aparece más abajo en la hoja, así que
gana por orden y convierte tu botón activo en un bloque naranja macizo que
**tapa el icono**. Por eso las reglas de los botones Pro/Básico van prefijadas
con `.stApp` (mayor especificidad) y anulan el `translateY` del hover. El bloque
#3 ya viene así: cópialo tal cual.

**T5 — En iframe estrecho la etiqueta se parte.** "Básico" salía "Bá/sic/o" en
vertical. La cura (ya en el bloque #3 y en las columnas `[1,2,2,1]` del bloque
#12): `white-space: nowrap` en el botón **y en todos sus descendientes**, más la
media query < 640px. No la quites.

**T6 — La lección de método.** `py_compile` en verde y health `200` **NO
prueban que un gráfico se dibuje**. Los fallos de Plotly ocurren en JavaScript,
en el navegador. En la referencia se entregaron dos versiones rotas por confiar
en eso. **Renderiza con kaleido y MIRA los PNG** (sección siguiente).

---

## VERIFICACIÓN (OBLIGATORIA, EN ESTE ORDEN)

**5.1** Compila todo:
```bash
python3 -m compileall -q agents data dashboard config
```

**5.2** Renderiza AMBAS gráficas con el motor real y **ABRE LOS PNG CON `Read`
PARA MIRARLOS** (no basta con que no lance excepción):
```python
import warnings; warnings.filterwarnings("ignore")
import pandas as pd
from data.market_data import get_price_history, compute_technical_indicators
from dashboard.charts import build_price_chart, build_mountain_chart
for tk in ["AAPL","NVDA","KO"]:
    df = get_price_history(tk, period="2y")
    ind = compute_technical_indicators(df) if not df.empty else {}
    build_price_chart(df, ind, tk).write_image(f"/tmp/pro_{tk}.png", width=1400, height=700)
    build_mountain_chart(df, tk).write_image(f"/tmp/bas_{tk}.png", width=1400, height=560)
build_price_chart(pd.DataFrame(), {}, "X").write_image("/tmp/e1.png", width=600, height=300)
build_mountain_chart(pd.DataFrame(), "X").write_image("/tmp/e2.png", width=600, height=300)
```
Con los ojos: en Pro, velas + 4 medias + líneas 52W + volumen + RSI(0–100) +
MACD. En Básico, línea continua con degradado **sin escalones** (si ves curvas
de nivel tipo mapa, hiciste las bandas siguiendo la curva en vez de
horizontales). Prueba también una serie bajista → la línea debe salir ROJA
(`#F1495F`), y una serie plana → sin división por cero.

**5.3** Integridad del CSS y de los SVG:
```python
import re, urllib.parse, xml.dom.minidom
from dashboard.styles import BLOOMBERG_CSS as C   # usa el nombre real de la cadena
assert C.count("{") == C.count("}"), "llaves CSS desbalanceadas"
for u in re.findall(r'url\("data:image/svg\+xml,(.*?)"\)', C):
    xml.dom.minidom.parseString(urllib.parse.unquote(u))
    assert '"' not in u
```
Y que todos los tokens que usas existen en `:root`:
```bash
for t in --accent-rgb --pos-rgb --neg-rgb --surface-1 --surface-2 --hairline \
         --text-2 --text-hi --font-mono --shadow-1 --dur-1 --ease-out; do
  grep -q -- "$t:" dashboard/styles.py && echo "✓ $t" || echo "✗ FALTA $t"
done
```

**5.4** El escáner sigue dando los mismos filtros (compara antes/después):
```python
import json
from config.settings import SCANNER_DEFAULTS
from dashboard.scanner_filters import build_screener_filters
print(json.dumps(build_screener_filters(dict(SCANNER_DEFAULTS)), sort_keys=True))
```

**5.5** Ninguna tarjeta del escáner duplicada ni perdida (cada una = 1):
```bash
for k in size_ stage_ rs_ mom_ prox_ liq_ mr_; do
  echo "$k $(grep -c "f\"$k" dashboard/app.py)"; done
```

**5.6** Localhost y log limpio:
```bash
pkill -f "streamlit run"; sleep 2
nohup python3 -m streamlit run dashboard/app.py --server.port 8501 \
      --server.headless true > /tmp/st.log 2>&1 &
sleep 6
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8501/_stcore/health   # 200
grep -icE "traceback|error|exception" /tmp/st.log                                # 0
```

**5.7 — INTEGRIDAD DE LA IA (obligatorio en esta copia).**
El rediseño no puede haber tocado el motor de IA. Demuéstralo:
```bash
# a) Ningún fichero de IA fue modificado (todo debe estar limpio salvo dashboard/)
git status --short | grep -vE "dashboard/(styles|charts|app)\.py" \
  && echo "⚠️ SE MODIFICÓ ALGO FUERA DE dashboard/ — REVISAR" \
  || echo "✓ solo se tocó dashboard/"
# b) Los agentes siguen importando sin error (no rompiste sus dependencias)
python3 -c "import agents.orchestrator, config.settings; print('✓ IA importa OK')"
```
Y en `localhost:8501`, **lanza un análisis real de una acción** y confirma que
la IA responde y el texto generado aparece igual que antes. Si el análisis de IA
no corre exactamente como antes, algo se rompió: **deténte y revísalo.**

---

## CRITERIOS DE ACEPTACIÓN (márcalos todos antes de pedir aprobación)

- [ ] La prueba de pre-estado dio 0/0/0/0 al empezar
- [ ] Tokens `:root` con los valores exactos del bloque #1
- [ ] `.analysis-text` sin `max-width`
- [ ] Badge del sidebar sin solape del punto
- [ ] Signal cards para pros/contras · Termómetros en Fundamentales, Futuro,
      Smart Money, Macro y Sentimiento
- [ ] Paleta de `charts.py` = tokens · `build_mountain_chart` añadida
- [ ] `build_price_chart` intacta byte a byte
- [ ] Encabezado "MODO DE ANÁLISIS" centrado + botones Pro/Básico con iconos SVG
- [ ] Toda acción abre en Pro · etiquetas en una línea en iframe estrecho
- [ ] Escáner en 3 bloques · `build_screener_filters` devuelve el mismo dict
- [ ] Textos de carga sin marca del proveedor
- [ ] Ambas gráficas renderizadas con kaleido **y miradas**
- [ ] CSS balanceado · SVG válidos · todos los tokens existen
- [ ] Localhost 200 · 0 errores en el log · `.env` ignorado
- [ ] **`git status` muestra SOLO `dashboard/` modificado — nada de `agents/`,
      `config/`, `data/`, `main.py`, `.env`**
- [ ] **Los agentes importan sin error · un análisis de IA real corre igual que
      antes**
- [ ] Ningún termómetro con dato inventado (los sin dato simplemente no aparecen)

---

## ENTREGA Y REPORTE

1. Levanta `localhost:8501` y **pide aprobación explícita**. Dile al usuario qué
   mirar: pestaña técnica + selector Pro/Básico, signal cards, termómetros,
   escáner reorganizado, badge del sidebar.
2. Nada de commit/push antes del visto bueno.
3. Cuando lo dé: commit explicando el *porqué* de lo no obvio (por qué no
   `minallowed`, por qué botones y no `segmented_control`, por qué el prefijo
   `.stApp`), y push.

Al terminar, reporta en español y sin adornos:
- Qué pasos quedaron **idénticos** a la referencia.
- Qué pasos tuviste que **adaptar** por la deriva de esta copia, y cómo.
- Qué pasos **no se pudieron aplicar** porque el anclaje no existe aquí (no es un
  fracaso: es información que el usuario necesita).
- Qué verificaste, con resultados reales. Si algo falló, pega la salida.
  **Nunca declares verificado algo que no ejecutaste.**

**Recuerda: la acción por defecto es HACER el cambio. Si al final crees que "ya
estaba todo igual", vuelve a la prueba de pre-estado — o no la ejecutaste, o
estás en el repo equivocado.**
