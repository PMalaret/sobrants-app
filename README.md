# Sobrants — aplicación de control de inventario

Reemplazo independiente de **SobrantsV4.74.xlsm**: misma lógica, mismas
reglas de negocio, sin necesidad de Microsoft Excel. Construida en
Python + PySide6 (Qt), con los datos en una base de datos SQLite local
(`SobrantsData/sobrants.db`, junto al ejecutable). **Interfaz en 4 idiomas
(catalán, castellano, inglés, francés)**, con selector en el menú
"🌐 Idioma/Language/Langue" (se recuerda entre arranques en
`SobrantsData/settings.json`); toda la traducción vive en `app/i18n.py`,
con las 219 claves siempre en los 4 idiomas a la vez (cualquier cadena
nueva que se añada debe seguir esa misma regla). Esta documentación y los
comentarios del código quedan en castellano por continuidad con el resto
del proyecto.

## Qué hace cada pieza

| Excel original | Aquí |
|---|---|
| Hoja1 (panel + buscadores + entrada de datos) | Pestaña **Tauler** |
| llista / Entrades (fuente de verdad de piezas por posición) | tabla `pieces` en SQLite |
| històric (auditoría) | Pestaña **Històric** + tabla `historic` |
| Materials (catálogo) | Pestaña **Materials** + tabla `materials` |
| desmagatzem | Pestaña **Desmagatzem** + tabla `desmagatzem` |
| Macros VBA (~4.800 líneas) | `app/logic/rules.py` + `app/logic/repository.py` |

Ver `docs/ANALISIS_VBA.md` para el mapeo detallado macro por macro.

### Diseño del Tauler

Las 61 posiciones se muestran en 3 bloques de columnas lado a lado (1-27,
28-54, 55-61) para que quepan todas a la vista sin scroll — igual que
hacía Hoja1 con sus bloques A:E / F:J / K:O. El tauler **siempre** tiene
exactamente esas 61 posiciones (no hay lógica para un número variable), así
que la tabla tiene una altura fija y el espacio que queda justo debajo se
aprovecha para el **panel de detalle de la posición seleccionada**
(`app/ui/position_panel.py`): alta/baja/traslado de piezas, incrustado de
forma permanente (ya no es una ventana emergente). Los tres buscadores
(`app/ui/search_panel.py`) viven debajo, siempre visibles: cada uno ocupa una
sola fila de bloques con el mismo formato —título encima, contenido debajo—,
el campo de texto primero y después sus tres resultados (coincidencias,
posición más antigua, unidades en Desmagatzem) con el número en grande. El
color de resaltado es fijo por buscador (`SEARCH_COLORS`), nunca depende del
material encontrado.

### Desmagatzem: mismos colores de búsqueda que el Tauler

Los 3 buscadores del Tauler también resaltan, con el mismo color, las filas
de Desmagatzem que coinciden (igual que `BuscaCoincidenciesDesmagatzem_Q20/
M22/M24` en el VBA original, que pintaba las celdas de la fulla desmagatzem
con el color de la propia celda de búsqueda M20/M22/M24). Los colores están
centralizados en `SEARCH_COLORS` (`app/ui/search_dialog.py`) y los reutilizan
tanto el Tauler como Desmagatzem — no hay una paleta duplicada.

### Acciones protegidas: dos contraseñas

Hay **dos contraseñas independientes** (`app/security.py`), las dos `1234`
de partida:

- `security.ADMIN` — *contraseña administrador*: copias de seguridad
  (manual e intervalo) y limpiar el histórico.
- `security.WORKER` — *contraseña trabajador*: alta y borrado de
  materiales.

Cambiar una no toca la otra. Se cambian las dos desde un único diálogo,
**Archivo → Cambiar contraseña** (`ChangePasswordDialog`), donde se elige
cuál, se escribe la actual de esa misma y la nueva dos veces. Todas las
acciones protegidas piden la suya por el mismo sitio
(`app/ui/password_dialog.py` → `ask_password`), así no puede aparecer un
tercer mecanismo por su cuenta.

No se guarda nunca en claro: en `SobrantsData/settings.json` sólo va un
PBKDF2-HMAC-SHA256 con sal aleatoria (`hashlib`, biblioteca estándar). En
una instalación nueva vale la contraseña inicial `1234`
(`security.DEFAULT_PASSWORD`, el único valor en claro del código); al
cambiarla desde **Archivo → Cambiar contraseña** se guarda el hash y la
inicial deja de servir.

## Uso en desarrollo

No hace falta compilar nada para probar un cambio: la aplicación se
arranca directamente con `python run_app.py`, en cualquiera de los tres
sistemas. El código es el mismo en todos (no hay nada específico de
macOS); lo único que cambia es cómo se activa el entorno virtual.

**macOS / Linux**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run_app.py
```

**Windows** (PowerShell, desde la carpeta del proyecto)

```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1     # cmd.exe: venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python run_app.py
```

Si PowerShell no deja ejecutar `Activate.ps1` por la política de scripts,
o bien se ejecuta una vez
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, o bien se llama al
intérprete del entorno sin activarlo, que funciona igual:

```powershell
.\venv\Scripts\python.exe run_app.py
.\venv\Scripts\python.exe -m pytest tests/ -q
```

**Versión de Python.** Lo recomendable es 3.10 o superior (es lo que usa
la compilación en GitHub Actions: 3.12). Con Python 3.9 también funciona:
`requirements.txt` fija con marcadores `python_version` las últimas
versiones de PySide6 y pytest que aún lo soportan (6.10.3 y 8.4.2), así
que `pip install -r requirements.txt` instala lo correcto en cada caso
sin tener que tocar nada.

En el primer arranque, la aplicación pregunta si quieres importar los
datos desde un `.xlsm` existente (recomendado la primera vez) o empezar
con una base de datos vacía. La base de datos y las copias de seguridad
se crean en `SobrantsData/`, junto al proyecto (esa carpeta está en
`.gitignore`); para volver a empezar de cero basta con borrarla.

Para importar sin pasar por la interfaz:

```bash
python -m app.migration.from_excel SobrantsV4.74.xlsm SobrantsData/sobrants.db
```

## Tests

```bash
python -m pytest tests/ -q
```

Incluye pruebas unitarias de cada regla de negocio y pruebas de
integración sobre una base de datos real de ejemplo. Además, los
resultados de la migración se han contrastado celda a celda contra los
valores calculados y guardados en el propio `SobrantsV4.74.xlsm` (las 61
posiciones del panel y los 3 buscadores) — ver `docs/VALIDACION.md`.

## Generar el ejecutable

### Opción A — GitHub Actions (recomendada para el .exe de Windows)

Este repo incluye `.github/workflows/build.yml`. Al hacer push (o
manualmente desde la pestaña Actions → "Compilar ejecutables" → "Run
workflow"), se generan automáticamente:

- `Sobrants-Windows.exe`
- `Sobrants-macOS`
- `Sobrants-Linux`

como artifacts descargables del run. No hace falta tener Windows para
obtener el `.exe`.

### Opción B — Compilar localmente en cada sistema operativo

PyInstaller **no compila de forma cruzada**: hay que ejecutarlo en cada
sistema operativo destino.

```bash
pip install -r requirements.txt
pyinstaller sobrants.spec --noconfirm
```

El resultado queda en `dist/Sobrants` (`dist/Sobrants.exe` en Windows).
Es un único fichero portable: cópialo donde quieras, no necesita
instalación ni Python en la máquina destino. La primera vez que se
ejecuta crea junto a sí mismo la carpeta `SobrantsData/` con la base de
datos y las copias de seguridad automáticas.

- **Windows**: ejecutar los comandos anteriores en una máquina Windows
  (o una VM). Genera `dist/Sobrants.exe`.
- **macOS**: igual, en un Mac. Genera `dist/Sobrants` (binario Mach-O).
- **Linux**: igual, en la distribución destino (usa una imagen antigua
  tipo Ubuntu 20.04 si el binario debe correr en sistemas más viejos,
  por compatibilidad de `glibc`).

## Copias de seguridad

Automáticas al cerrar la aplicación y cada X horas (4 por defecto,
configurable en **Copias de seguridad → Interval de còpies automàtiques**; el valor se
guarda en `settings.json` y se mantiene entre arranques), en
`SobrantsData/Backups/` (se conservan las 10 más recientes).

Todo lo de las copias vive en su propio menú, **Copias de seguridad**
(entre Archivo e Idioma). La copia manual está ahí y pide la
contraseña antes de empezar (si no es correcta no se toca ningún fichero).
Ya no hay botón permanente en la interfaz: en su sitio, en la fila de
acciones, está el **indicador de USB** (`app/ui/usb_indicator.py`), que se
pinta en verde si hay alguna unidad extraíble conectada y en rojo si no,
comprobándolo de verdad cada pocos segundos (`GetDriveTypeW` en Windows,
`QStorageInfo` en macOS y Linux).

Las copias automáticas **no** piden contraseña: la contraseña protege
configurarlas, no ejecutarlas, así que la aplicación nunca se queda
esperando a nadie cuando toca hacer una.

## Importar datos

Menú **Importar** (entre Archivo y Copias de seguridad),
`app/ui/import_actions.py`:

- **Importar de Excel** — el mismo flujo que el primer arranque; de hecho
  `main._ensure_database` llama a esa misma función, no a una copia.
- **Importar de base de datos** — un `.db` del mismo formato que dejan las
  copias de seguridad. Antes de tocar nada valida el fichero
  (`db.describe_database`: que sea SQLite y tenga las cuatro tablas), pide
  confirmación diciendo qué contiene, hace una copia de seguridad de los
  datos actuales con la función de siempre (`backup.create_backup`) y
  entonces sustituye el fichero; si la copia falla, restaura la de
  seguridad. Después se reabre la conexión y se reconstruye la ventana
  (`MainWindow._reload_database`), así que ninguna pestaña se queda con
  datos viejos.

## Imprimir

**Imprimir tauler** e **Imprimir desmagatzem** abren el diálogo de
impresión **nativo** del sistema (`QPrintDialog`) y pintan el mismo
contenido y formato de siempre en la impresora elegida —incluida
"imprimir a PDF", si el sistema la ofrece—. No se crea ningún fichero
temporal por el camino. Cancelar no hace nada; un fallo de la impresora se
avisa. El dibujo es compartido (`export._paint_widget_on_printer`), así que
la generación del PDF y la impresión no se duplican.

## Histórico: sin límite de filas, y cómo se limpia

La tabla es un `QTableView` con un modelo propio (`_HistoricModel`), no un
`QTableWidget`: Qt sólo pide las celdas que se ven, así que **no hay ningún
límite de filas** y decenas de miles (10.000, 50.000, 100.000) se abren al
instante. Se ordena clicando las cabeceras (con su flecha), no con botones
aparte, y no hay botón "Actualizar": se refresca sola al entrar en la
pestaña y cuando el Tauler o Desmagatzem escriben algo.

**Exporta Excel** guarda el histórico **entero** (todas las filas y
columnas, no lo que se ve), con `openpyxl` en modo *write_only*, y propone
`historic_AAAA-MM-DD.xlsx`.

**Netejar** pide la contraseña de administrador, luego confirma que ya se ha
exportado a Excel, y entonces borra el histórico **conservando la última
entrada de cada material que sigue en el Tauler**: los materiales son los
`material_code` de `pieces`, y su "última entrada" es la fila de `historic`
con el `ts` más alto (desempatando por `id`, porque `ts` va por segundos) —
no el orden en que se ve la tabla. Todo dentro de una transacción: si algo
falla, rollback y el histórico queda intacto (`Repository.clear_historic`).

## Guardado: cada cambio va al disco al momento

SQLite, en `SobrantsData/sobrants.db`. **No hay nada "en memoria a la
espera de guardar"**: cada operación del `Repository` que toca datos
(alta/baja/traslado de piezas, edición de medidas y notas, materiales,
líneas de desmagatzem y sus cantidades) se ejecuta dentro de
`Repository._transaction`, que hace `commit()` al terminar bien y
`rollback()` si salta cualquier excepción — así una operación a medias no
se queda ni acaba entrando "de rebote" con el commit de la siguiente. Con
`synchronous = FULL` (`app/data/db.py`), ese commit no vuelve hasta que el
cambio está en el disco: si un segundo después se va la luz, al reabrir la
aplicación el cambio sigue ahí. Las copias de seguridad no tienen nada que
ver con esto: son una copia adicional, no el momento en que se guarda.

Ver `tests/test_persistence.py`: cada operación se comprueba **releyendo
la base de datos desde una segunda conexión**, que es lo que vería un
arranque nuevo.

## Buscador por notas: sin "posición más antigua"

En el Excel, la casilla "posición prioritaria" del buscador por notas
(O24) se calculaba pero luego se sobrescribía siempre con un texto fijo
(ver `Módulo1`, `ActualitzarM24`): ese buscador nunca ha mostrado ninguna
posición. Aquí es igual — muestra siempre `—` (`BoardTab._oldest_text`) —,
mientras que los buscadores por núm. y por material sí muestran la suya.
El color del buscador por notas es el rosa de Excel, un punto más
intenso (`#ffa8b4`).
