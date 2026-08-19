# Previsión de absentismo por centro de trabajo

Aplicación web para **prever la tasa de absentismo mensual** (y las jornadas
perdidas que implica) de cada centro de trabajo de una cooperativa con varios
almacenes, con el fin de **dimensionar plantilla con antelación**. La previsión
es a horizonte mensual (**3 y 6 meses**) y siempre **agregada**: por centro y
turno, **nunca por persona**.

- **Stack:** Python + Streamlit (una sola URL, usable en móvil, tablet y PC).
- **Interfaz:** en español, con números y fechas en formato español.
- **Pantallas:** Resumen (panel semáforo de todos los centros), Previsión (KPIs +
  dimensionamiento de plantilla), Precisión (previsión vs. realidad + validación
  temporal), Comparativa (una tanda frente a otra), Factores (qué características
  del centro influyen en el absentismo), Segmentación (turno × puesto × carga
  dentro de un centro, para localizar el foco) y Datos (carga y recálculo).
- **Despliegue:** GitHub → Render (plan gratuito) + Turso para la persistencia.
- **Ejecución local:** `streamlit run app.py`.

---

## 🔒 Principios innegociables (privacidad)

Estos principios están reflejados en el código y en la interfaz:

1. **Solo datos agregados.** La app nunca almacena ni procesa datos de personas
   concretas ni datos de salud. Trabaja con conteos por **centro/turno/mes**.
2. **La validación rechaza datos personales.** Si un fichero subido contiene
   columnas que parezcan individuales (`nombre`, `apellidos`, `dni`, `nif`,
   `id_empleado`, `email`, `edad`, `sexo`, `genero`, `fecha_nacimiento`…), la
   carga se **rechaza** con un mensaje claro. (Ver `ingesta/validacion.py`.)
3. **El modelo NUNCA usa edad ni género** como variables predictoras. Los
   predictores son: calendario/estacionalidad, carga de trabajo, tendencia del
   propio centro y (opcional) curva de gripe. (Ver `config.py`.)
4. **Las previsiones se versionan y no se sobrescriben jamás.** Cada recálculo
   añade una tanda nueva con su fecha. (Ver `persistencia/previsiones.py`.)

---

## Requisitos

- **Python 3.11** recomendado (es el que usa el `Dockerfile` y el que mejor
  soporta Prophet). En otras versiones (p. ej. 3.14) puede que Prophet no se
  instale: la app **degrada con elegancia** a SARIMA o al modelo naive y avisa,
  sin romper.
- Dependencias en `requirements.txt` (versiones fijadas).

---

## Instalación y ejecución en LOCAL

```bash
# 1. Crear entorno virtual e instalar dependencias
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

# 2. Ejecutar
streamlit run app.py
```

Se abre en `http://localhost:8501`. **Arranca en modo prueba** (datos ficticios),
así que funciona al 100% sin cargar nada. La base de datos local se guarda en la
carpeta indicada por `DATA_DIR` (por defecto `./datos`).

### Recalcular desde la línea de comandos (job-ready)

El recálculo también puede lanzarse **fuera de la interfaz** (pensado para
programarlo como job en el futuro):

```bash
# Modo prueba: siembra datos sintéticos y calcula
python recalcular.py --modo prueba --sembrar-demo

# Modo real: usa el histórico ya cargado
python recalcular.py --modo real --motor prophet --horizonte 6
```

### Tests

```bash
pytest -q
```

---

## Modos de funcionamiento

Un selector en la barra lateral cambia entre:

- **Modo prueba (datos ficticios):** genera 6 centros con ~18 meses de histórico
  (estacionalidad con pico de invierno, repunte de verano, tendencia, ruido; el
  turno de noche sale peor). Es el modo **por defecto**. Usa una base local
  desechable, **nunca** toca los datos reales.
- **Modo real (mis datos):** usa los datos que cargues en la página **Datos**.

En pantalla siempre hay un **banner** indicando el modo activo.

---

## Formato de los ficheros de datos

Descarga las plantillas exactas desde la página **Datos** (botones de descarga).
Los CSV usan `;` como separador y UTF-8 (Excel en español los abre bien); el
lector también autodetecta `,` como separador.

### Fichero principal: `absentismo_mensual`

| columna | tipo | descripción |
|---|---|---|
| `centro` | texto | nombre del centro de trabajo |
| `turno` | texto | `manana`, `tarde`, `noche` o `todos` |
| `anio` | entero | año |
| `mes` | entero | 1–12 |
| `plantilla_media` | entero | nº medio de personas ese mes |
| `jornadas_teoricas` | entero | jornadas laborables totales del centro/turno ese mes |
| `jornadas_perdidas` | entero | jornadas perdidas por absentismo ese mes |

La tasa se calcula como `jornadas_perdidas / jornadas_teoricas`. Alternativamente,
si el fichero trae una columna **`tasa`** directa (0–1, o en % que se convierte
automáticamente), se usa esa.

### Columnas opcionales de factores (por centro/turno)

Puedes añadir al fichero de absentismo estas columnas **agregadas del centro/turno**
(nunca datos de personas). Si vienen, se usan en la página **Factores** para ver
qué característica del centro se asocia con más o menos absentismo:

| columna | tipo | descripción |
|---|---|---|
| `tipo_horario` | texto | `flexible`, `fijo` o `rotativo` |
| `rotacion_pct` | número | rotación anual de plantilla del centro (%) |
| `antiguedad_media` | número | antigüedad media de la plantilla (años) |
| `satisfaccion_media` | número | satisfacción media (encuesta anónima, p. ej. 1–10) |
| `jornada_media` | número | jornada media mensual (horas) |

### Columnas opcionales de micro-segmentación (por subgrupo)

Para la página **Segmentación** (localizar el foco DENTRO de un centro) puedes
aportar el detalle por puesto añadiendo dos columnas más, con **una fila por
centro/turno/puesto/mes**:

| columna | tipo | descripción |
|---|---|---|
| `puesto` | texto | rol/función del subgrupo (p. ej. `Preparación`, `Carretillero`) |
| `carga` | número | indicador de carga de trabajo del subgrupo (el que uséis) |

Si viene `puesto`, la app guarda el detalle para el análisis de segmentación **y**
lo agrega automáticamente a centro/turno para la previsión (no tienes que subir
los datos dos veces). Las franjas de carga (baja/media/alta) se calculan por
terciles de los datos.

> **Nota de diseño (importante):** por privacidad y por no discriminar a la
> plantilla, todo el análisis es **agregado por centro/turno/puesto**. La
> herramienta **no** hace scoring individual de personas, **no** identifica a
> trabajadores concretos, y **no** usa características protegidas (sexo, edad,
> discapacidad, afiliación sindical) como predictores.

### Fichero opcional: `gripe` (regresor externo)

| columna | tipo | descripción |
|---|---|---|
| `anio` | entero | año |
| `mes` | entero | 1–12 |
| `incidencia` | número | incidencia de gripe (p. ej. casos/100.000 hab.) |

Si no se sube, el modelo funciona igual sin él. Solo Prophet lo usa como regresor
(rellenando meses futuros con la climatología mensual); SARIMA y naive lo ignoran
porque la estacionalidad ya captura el patrón invernal.

---

## Definición de absentismo y bajas largas

Qué se cuenta como absentismo se configura en `config.py`
(`DefinicionAbsentismo`): por defecto se incluyen IT común/no laboral, ausencias
injustificadas y permisos no retribuidos, y se excluyen vacaciones, permisos
retribuidos, formación y maternidad/paternidad.

### Tratamiento de bajas largas (decisión documentada)

Las **bajas largas** (IT prolongada) son eventos puntuales de altísimo impacto
que distorsionan la serie. Como trabajamos con datos **agregados** (solo el total
mensual, no la baja individual), **no** podemos aislar una baja concreta. Por eso
el criterio es **robusto y relativo a cada centro**: un mes se considera atípico
(“baja larga”) cuando su tasa supera **`factor_baja_larga`** veces (por defecto
**2,5×**) la **mediana** del propio centro×turno. Opciones (config
`tratamiento_bajas_largas`):

- **`topar`** (por defecto): winsoriza el mes atípico a ese umbral (suaviza el
  pico extremo sin borrarlo).
- **`marcar`**: no cambia los valores, solo señala los meses afectados.
- **`incluir`**: deja la serie tal cual.

Así la **estacionalidad normal** (pico de invierno ~1,3× la mediana) **no se
toca**; solo se atenúan los picos genuinamente extremos.

---

## Modelo de previsión

- **Un modelo por cada combinación centro × turno** (segmentado), no uno global.
- **Motores** (seleccionables en la página Datos):
  - **Prophet** — motor principal (estacionalidad, festivos, regresor de gripe).
  - **SARIMA** (statsmodels) — alternativa.
  - **naive** — modelo simple propio (tendencia + estacionalidad mensual), sin
    dependencias externas; **siempre disponible**. Es la red de seguridad para
    la degradación elegante.
- Para cada mes previsto devuelve **valor central + intervalo de confianza al
  90%** (`lo`, `hi`), que **se ensancha** cuanto más lejos es la previsión.
- **Poco histórico → degradación elegante**: por debajo de 6 meses usa naive y
  avisa de baja fiabilidad; entre 6 y 12, ajusta pero marca fiabilidad baja.
- **Validación temporal** (entrenar con pasado, evaluar con futuro), nunca
  partición aleatoria. La página **Precisión** incluye un **backtest**
  ("ponte a fecha X con lo que se sabía entonces y predice").

---

## Persistencia y versionado — ⚠️ LEER ANTES DE DESPLEGAR

La persistencia usa **SQLite** (un fichero) en local. **La ruta se lee de la
variable de entorno `DATA_DIR`** (por defecto `./datos`).

Tablas:

- `historico(centro, turno, periodo, tasa, jornadas_perdidas, plantilla)` —
  `periodo` en formato `YYYY-MM`. Se puede actualizar (upsert).
- `previsiones(id_ejecucion, fecha_calculo, centro, turno, periodo_objetivo,
  valor, lo, hi, modelo)` — **APPEND-ONLY: nunca se sobrescribe.** Cada recálculo
  añade una tanda nueva. Cuando consultas "a una fecha", la app **lee** la
  previsión ya guardada vigente a esa fecha; **no recalcula al vuelo**.

### ⚠️ El disco de los hosts gratuitos es EFÍMERO

En Render (y en casi cualquier host gratuito) el sistema de ficheros se **borra**
en cada redespliegue o reinicio. Si guardaras el SQLite solo en disco, perderías
el histórico de previsiones. Por eso, en producción usamos **Turso** (SQLite en
la nube, plan gratuito) para que **el histórico persista**:

- Si defines `TURSO_DATABASE_URL` y `TURSO_AUTH_TOKEN`, la app usa Turso
  automáticamente para el **modo real**.
- Si no las defines, usa el fichero local en `DATA_DIR` (perfecto para local; en
  Render free se perdería al redesplegar → en ese caso **solo el modo prueba
  tiene sentido**, porque sus datos son sintéticos y regenerables).
- El **modo prueba** usa siempre un SQLite local desechable, nunca Turso.

---

## Despliegue GRATIS: GitHub → Render + Turso

Objetivo: una **URL única** `https://…onrender.com` accesible desde cualquier
dispositivo. Coste total: **0 €**.

### Paso 1 · Crear la base de datos gratuita en Turso

1. Crea una cuenta gratis en <https://turso.tech> e instala su CLI
   (o usa su panel web).
2. Crea una base de datos y obtén sus credenciales:
   ```bash
   turso db create absentismo
   turso db show absentismo --url        # → TURSO_DATABASE_URL (libsql://…)
   turso db tokens create absentismo     # → TURSO_AUTH_TOKEN
   ```
3. Guarda esos dos valores; los pegarás en Render como secretos.

### Paso 2 · Subir el proyecto a GitHub

```bash
git init
git add .
git commit -m "Previsión de absentismo (MVP)"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/prevision-absentismo.git
git push -u origin main
```

### Paso 3 · Crear el servicio web en Render

1. En <https://render.com>: **New → Web Service** y conecta tu repositorio.
2. Render detecta el `Dockerfile` (o el `render.yaml`). Deja `runtime: docker`.
3. Elige el **plan Free**.
4. En **Environment**, añade las variables de entorno:
   - `TURSO_DATABASE_URL` = el valor `libsql://…` del paso 1.
   - `TURSO_AUTH_TOKEN` = el token del paso 1.
   - (Opcional) `APP_PASSWORD` = una contraseña para proteger el enlace.
5. **Deploy.** Al terminar tendrás tu URL pública.

> **Nota:** `DATA_DIR` ya viene definido en `render.yaml`. En el plan Free no hay
> disco persistente, pero **no lo necesitas** porque el histórico real vive en
> Turso.

### Paso 4 · Verificar la conexión con Turso (recomendado)

La app arranca en **modo prueba** y funciona aunque Turso no esté configurado, así
que puedes desplegar y demostrarla de inmediato. Para validar Turso (modo real):

1. En la app desplegada, cambia a **modo real** en la barra lateral.
2. Ve a la página **Datos → Estado actual** y pulsa **"🔌 Probar conexión con el
   almacenamiento"**. Debe decir *"Conexión correcta con: Turso…"*.
3. Si falla, revisa `TURSO_DATABASE_URL` (empieza por `libsql://`) y
   `TURSO_AUTH_TOKEN` en las variables de entorno de Render.

> El adaptador de Turso está aislado en `persistencia/db.py` (`_conectar_turso`).
> `libsql-experimental` se instala sin problemas en la imagen de Render
> (Python 3.11); en algunos entornos locales muy nuevos (p. ej. 3.14) puede no
> compilar, pero eso **no afecta al despliegue** ni al modo prueba local.

### El plan Free "duerme"

El plan gratuito de Render **suspende** el servicio tras unos ~15 min sin uso, así
que **la primera visita tras un rato tarda ~30–50 s en despertar**. Para esta app
(consulta mensual, no urgente) es perfectamente asumible.

### Protección por contraseña (opcional)

Si defines `APP_PASSWORD`, la app pide esa contraseña antes de mostrarse (sin
sistema de usuarios). Si no la defines, el enlace queda abierto.

---

## Estructura del proyecto

```
app.py                 # entrada Streamlit (enrutado + sidebar)
config.py              # definición de absentismo, umbrales, parámetros, privacidad
recalcular.py          # CLI de recálculo (job-ready, fuera de la interfaz)
ingesta/               # FuenteDatos (CSV real + API stub), validación, plantillas, bajas largas
modelo/                # motores (Prophet/SARIMA/naive), previsión, backtest, métricas
persistencia/          # SQLite/Turso: histórico y previsiones versionadas
datos_demo/            # generador de datos ficticios
ui/                    # páginas (resumen, previsión, precisión, comparativa, datos),
                       # gráficos, estilo, sidebar, auth, servicios
tests/                 # pruebas (privacidad, previsión, métricas, versionado, bajas largas)
Dockerfile
render.yaml            # despliegue Render (free + Turso)
requirements.txt       # versiones fijadas
```

### Futuro: fuente API (sin reescribir el resto)

`ingesta/fuente.py` define la interfaz `FuenteDatos`. Hoy hay una implementación
real (`FuenteCSV`) y un **stub documentado** (`FuenteAPI`) para conectar en el
futuro SuccessFactors (OData) o el WMS: bastará implementar sus dos métodos de
lectura (devolviendo datos **ya agregados**), y toda la validación de privacidad
se aplicará igual.

---

## Qué NO hace (por diseño)

- No conecta a ninguna API real (solo el stub documentado).
- No hace scoring individual ni predicción a nivel de persona.
- No usa edad ni género como predictores.
- No monta login/roles complejos (solo contraseña simple opcional).
