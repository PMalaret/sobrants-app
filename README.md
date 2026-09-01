# Sobrants by Luvnus — aplicación de control de inventario

Reemplazo independiente de **SobrantsV4.74.xlsm**: misma lógica, mismas
reglas de negocio, sin necesidad de Microsoft Excel. Construida en
Python + PySide6 (Qt), con los datos en una base de datos SQLite local
(`SobrantsData/sobrants.db`, junto al ejecutable). **Interfaz en 4 idiomas
(catalán, castellano, inglés, francés)**, con selector en el menú
"Idioma/Language/Langue" (se recuerda entre arranques en
`SobrantsData/settings.json`); toda la traducción vive en `app/i18n.py`,
con las 270 claves siempre en los 4 idiomas a la vez (cualquier cadena
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
| (no existía) | Pestaña **Estadísticas**, calculada desde `historic` |
| Macros VBA (~4.800 líneas) | `app/logic/rules.py` + `app/logic/repository.py` |

Ver `docs/ANALISIS_VBA.md` para el mapeo detallado macro por macro.

### Diseño del Tauler

En la franja de acciones (debajo del buscador), a la izquierda y dentro de
su propio recuadro, va **"Hay N piezas"**: el total del tablero
(`Repository.count_pieces`, un `COUNT(*)` sobre `pieces`), la suma de las
piezas de todas las posiciones, no cuántas posiciones hay ocupadas. Sale de
la base de datos, así que no depende del scroll ni de lo que esté pintado, y
se recalcula solo con cualquier cambio de datos y al cambiar de pestaña; con
una sola pieza la frase va en singular, en los 4 idiomas. Enfrente, al otro
lado de esa misma franja, los botones de imprimir y materiales tapados.

En la **barra de estado** queda la ruta de la base de datos y, a la derecha
del todo, la **leyenda de colores de ocupación**, que solo aparece mientras
se está viendo el Tauler, porque es lo que explica. Arriba a la derecha solo
queda el indicador de USB.

Las 61 posiciones se muestran en 3 bloques de columnas lado a lado (1-27,
28-54, 55-61) para que quepan todas a la vista sin scroll — igual que
hacía Hoja1 con sus bloques A:E / F:J / K:O. El tauler **siempre** tiene
exactamente esas 61 posiciones (no hay lógica para un número variable), así
que la tabla tiene una altura fija y el espacio que queda justo debajo se
aprovecha para el **panel de detalle de la posición seleccionada**
(`app/ui/position_panel.py`): alta/baja/traslado de piezas, incrustado de
forma permanente (ya no es una ventana emergente). El detalle enseña
**siempre sus 5 líneas** (el máximo de piezas por posición), tenga piezas o
no: la altura se calcula sumando la altura *real* de las filas y de la
cabecera (`_fit_detail_table_height`), así que la interfaz no cambia de
tamaño según cuántas piezas haya. Los tres buscadores
(`app/ui/search_panel.py`) viven debajo, siempre visibles: cada uno ocupa una
sola fila de bloques con el mismo formato —título encima, contenido debajo—,
el campo de texto primero y después sus tres resultados (coincidencias,
posición más antigua, unidades en Desmagatzem) con el número en grande. El
color de resaltado es fijo por buscador (`SEARCH_COLORS`), nunca depende del
material encontrado. Sus tres resultados se recalculan por el mismo camino
(`BoardTab.refresh_searches`) siempre que cambian datos, se toquen en el
Tauler o en Desmagatzem: "unidades en Desmagatzem" sale de esa otra tabla,
así que un alta o un cambio de cantidad allí también los actualiza, haya
búsqueda activa o no.

**Borrar** y **Mover pieza visible a posición** son las dos acciones sobre
la última pieza de la posición y se activan con la misma condición
(`_can_delete_row`, la regla `rules.can_delete_slot` del original): con
cualquier otra fila seleccionada salen desactivados, con el motivo en el
tooltip. El botón de mover pregunta la posición de destino en un diálogo
(`dialogs.ask_int`) y, una vez elegida, sigue exactamente por el camino de
siempre — confirmación y `Repository.move_piece`, que es quien saca la
pieza, la coloca y escribe las dos líneas de histórico.

### Colores: una sola paleta, en `app/ui/theme.py`

Ningún color se escribe dentro de un widget. Todos viven con nombre en la
paleta de `app/ui/theme.py` (`accent`, `danger`, `surface`, los cinco
niveles de ocupación, los tres colores de buscador, los de movimiento del
histórico…) y se piden desde el código:

- `theme.color("accent")` / `theme.qcolor("accent")` — un color suelto.
- `theme.css("color: $text_muted;")` — un fragmento de hoja de estilo con
  los nombres sustituidos; es lo que usan los widgets con estilo propio.
- `theme.stylesheet()` — `style.qss` entero, que lleva `$nombre` en vez de
  códigos de color.
- `theme.apply(app)` — lo que hace el arranque: estilo **Fusion**, paleta de
  Qt y hoja de estilo.

Se usa Fusion y no el estilo nativo de Windows porque Fusion pinta todos los
widgets estándar a partir de la `QPalette`: el estilo nativo se salta buena
parte de sus colores, y con una paleta distinta dejaría menús, calendarios,
barras de desplazamiento y diálogos sin cambiar.

Los nombres dicen **qué** es cada color, no de qué color es (`danger`, no
`red`), así una paleta puede usar otro tono para lo mismo sin que el nombre
mienta. La regla —cero `#rrggbb` fuera de la paleta— la vigila un test
(`tests/test_theme.py`), igual que otro vigila que las 270 claves de
traducción estén en los 4 idiomas.

El nivel de ocupación de una posición (1 a 5) es una **regla de negocio** y
vive en `rules.occupancy_level`; qué color le toca a cada nivel es una
decisión de aspecto y vive en la paleta. Los informes impresos
(`app/export.py`) toman siempre los colores de la paleta **clara**: lo que
va al papel tiene que leerse sobre blanco.

### Aspecto: qué hace la hoja de estilo

Pestañas sin caja (subrayado del color de acción en la activa), cabeceras de
tabla con un fondo un poco más oscuro que la tabla —para separarlas del
contenido de un vistazo— pero planas, sin bordes verticales ni relieve;
barras de desplazamiento sin flechas y con el pulgar redondeado, botones y
campos con esquinas de 8 px, anillo de foco visible al entrar en un campo, y
menús con aire (con las opciones resaltándose en redondeado al pasar por
encima, pero el **marco del menú cuadrado**: un menú vive dentro de una
ventanita del sistema que es rectangular, así que si se le redondea el borde
asoman las esquinas de esa ventanita por detrás; marcarla como transparente,
que es la salida habitual, en Windows las deja negras).

**Botones: una sola familia**, con dos propiedades que se ponen desde el
código, nunca con un color escrito a mano en el widget:

| Propiedad | Valores | Para qué |
|---|---|---|
| `variant` | *(nada)* / `ghost` / `danger` | peso visual: acción principal, secundaria, o destructiva |
| `compact` | `"true"` | sitios donde el espacio va justo (el panel del Tauler) |

Así todos los botones de la aplicación tienen la misma forma, la misma
altura y los mismos estados. El desactivado es un fondo claro con borde
fino, no un bloque gris relleno.

**Diálogos** (`app/ui/dialogs.py`, por donde ya pasaban todos para tener los
botones traducidos): fondo blanco como el resto de superficies de contenido,
más margen interior, y dos cosas nuevas —el botón que continúa la acción
(Aceptar, Sí) va relleno y el que la deja correr (Cancelar, No) va vacío,
decidido por el **papel** de cada botón (`ButtonRole`) y no por su texto,
así vale en los 4 idiomas; y el icono ya no es el círculo relleno del
sistema sino el de la misma familia de líneas que los botones, con su color
(azul para preguntar/informar, ámbar para avisar, rojo para error).

Los **menús** llevan icono en cada opción (candado en "Cambiar contraseña",
impresora en las de imprimir, disquete en "Copia ahora", engranaje en la
configuración…), de la misma familia y con el color del texto. En la **barra**
de menús, en cambio, solo va texto: al ponerle icono a una entrada de la
barra, Qt deja de mostrar su texto y quedaba un símbolo suelto sin decir de
qué era.

Los títulos de los menús llevan su tecla de atajo marcada desde siempre
(`&Fitxer` = Alt+F). El estilo nativo de Windows solo pinta el subrayado
mientras se tiene pulsado Alt, pero **Fusion lo pinta siempre**, así que la
aplicación le dice que no lo pinte nunca (`_AppStyle`, en `theme.py`): los
atajos siguen funcionando igual, solo que sin la raya permanente.

**Iconos: `app/ui/icons.py`.** Los emojis (`🗑️ Esborrar`) eran dibujos de
color fijo: sobre un botón azul o rojo parecían una pegatina y no seguían el
color del texto. Ahora se usan las icon fonts que ya trae Windows —**Segoe
Fluent Icons** (11) o **Segoe MDL2 Assets** (10)—, dibujadas con QPainter al
color que toque: blancas sobre un botón lleno, grises cuando está
desactivado (las dos versiones se generan a mano, porque la que genera Qt
solo con una desvanece el icono y sobre un fondo claro desaparecería). Si
ninguna de las dos fuentes existe (macOS, Linux), el botón se queda solo con
su texto, que siempre está. Los nombres de icono (`"print"`, `"delete"`…)
los vigila un test, igual que los colores.

Dos decisiones tomadas *contra* la moda, por ser un ordenador de taller:

- **Barras de desplazamiento de 14 px**, no de 8-10: tienen que poder
  agarrarse con el ratón sin apuntar fino (y con guantes, o en una pantalla
  táctil, todavía más).
- **Cabeceras y pestañas con texto oscuro**, no en gris suave: con luz de
  nave, un gris claro no se lee.

La **jerarquía de botones** se marca con una propiedad, no con un color a
mano: `setProperty("variant", "ghost")` deja el botón con el mismo tamaño
pero sin rellenar, para los que acompañan a la acción principal (los
intervalos hechos de Estadísticas, al lado de "Consultar").

Dos detalles de las tablas que se editan en línea: el **editor de celda**
(el `QLineEdit` que Qt mete dentro al editar) lleva su propio margen —con el
de los campos de formulario no cabía en la fila y el texto salía cortado—, y
las filas del detalle de posición tienen la altura justa para que el texto
respire **también mientras se escribe**.

**Lo que la hoja de estilo NO puede tocar: `QTableView::item`.** En cuanto
se le da estilo a los ítems, Qt se encarga de pintarlos y deja de aplicar el
color de fondo que pone el código en cada celda — y aquí ese color es
información (ocupación de la posición, coincidencias de los buscadores), no
decoración. Está avisado al principio de `style.qss`. El aire de las filas,
si hace falta, se da con la altura de fila desde el código; en el Tauler ni
eso, porque sus 61 posiciones tienen que caber sin scroll.

### Desmagatzem: contador de piezas y mismos colores de búsqueda

A la izquierda del botón **Imprimir desmagatzem** va el total de piezas
que hay ahora mismo en Desmagatzem (`Repository.count_desmagatzem_pieces`):
la **suma de las cantidades** de todas las líneas, no el número de líneas
(una línea de 5 unidades son 5 piezas, igual que cuenta el histórico, que
deja una entrada por unidad). Sale de la base de datos, así que no depende
del orden de la tabla ni de si hay una búsqueda resaltando filas, y se
recalcula con cada alta, baja o cambio de cantidad.

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
  (manual e intervalo), limpiar el histórico e **importar datos** (de
  Excel o de otra base de datos).
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
workflow") se ejecutan los tests y se compila `Sobrants-Windows` (carpeta
con `Sobrants.exe` y `_internal/`), descargable como artifact del run. Al
empujar un tag `vX.Y.Z` ese mismo ejecutable se publica, comprimido, como
`Sobrants-Windows.zip` en una GitHub Release. No hace falta tener Windows
para obtener el `.exe`.

**Solo se compila Windows**, que es donde se usa la aplicación; los tests
también corren allí, en el mismo sistema que el usuario final. El código
no tiene nada específico de ningún sistema y sigue arrancando en macOS y
Linux con `python run_app.py`: para tener un *binario* de esos dos hay que
compilarlo en cada uno (opción B), porque PyInstaller no compila de forma
cruzada. Volver a generarlos aquí es devolver la matriz de sistemas al job
`build` del workflow.

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

Automáticas al cerrar la aplicación y cada X horas. Todo se configura en
**Copias de seguridad → Configuración** (`app/ui/backup_dialog.py`), pide la
contraseña de administrador y se guarda en `settings.json`:

- **carpeta de destino**, elegida con el selector nativo (por defecto
  `SobrantsData/Backups/`);
- **nombre** de las copias: siempre `AAAAMMDDHHMM_<nombre>.db`, con la
  fecha delante para que ordenar por nombre sea ordenar por fecha;
- **cada cuántas horas** se hacen (4 por defecto);
- **cuántas se conservan** (25 por defecto, 1–500).

La copia nueva se crea **antes** de borrar ninguna vieja, así que un fallo
al copiar nunca cuesta una copia válida; después se eliminan las más
antiguas hasta el límite, decidiendo la antigüedad por la fecha del
**nombre** (`AAAAMMDDHHMM`), no por la fecha del fichero. La rotación solo
borra ficheros con el patrón de la aplicación, nunca otros `.db` que haya
en esa carpeta, y se aplica a cada destino por separado: si el USB no está
conectado, allí no se toca nada. Bajar el límite no borra nada en ese
momento — avisa y el recorte se aplica en la siguiente copia. Nunca
se sobrescribe una copia anterior (dos copias del mismo minuto quedan como
`…-2.db`) y cada copia se verifica (existe y mide lo mismo que el original)
antes de darla por buena.

**Copia doble en USB**: si hay una unidad extraíble conectada, se hace una
segunda copia idéntica en `SobrantsBackups/` dentro del USB. Si no hay USB,
o si el USB falla, la copia principal se hace igualmente y el mensaje dice
exactamente qué ha pasado — nunca dice "duplicada" si no lo está. Con más
de un USB, la copia manual pregunta cuál; la automática usa el primero y no
pregunta nunca nada.

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
`app/ui/import_actions.py`. Las dos opciones sustituyen datos que ya están
guardados, así que las dos **piden primero la contraseña de administrador**
(`MainWindow._ask_import_password`, por el mismo `ask_password` que el
resto de acciones protegidas): si no es correcta o se cancela el diálogo,
no se abre ningún fichero y no se toca nada. El primer arranque —cuando
todavía no hay ninguna base de datos que proteger— sigue pudiendo importar
sin contraseña.

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

Cada botón vive en su pestaña: **Imprimir tauler** y **Materials tapats**
debajo del buscador del Tauler, en una zona de acciones propia (fondo gris
suave, botones alineados a la derecha, los dos del mismo tamaño y cada uno
con su color), e **Imprimir desmagatzem** en la fila de acciones de
Desmagatzem. La fila superior solo tiene el total de piezas y el indicador
de USB.
Los dos abren el diálogo de impresión **nativo** del sistema
(`QPrintDialog`) —donde se puede elegir "imprimir a PDF"— y ninguno crea
ficheros temporales. Cancelar no hace nada; un fallo de la impresora se
avisa. Al documento se le pone nombre antes de enviarlo
(`export.document_name`): **`AAAAMMDDHHMM_tauler`** y
**`AAAAMMDDHHMM_desmagatzem`**, que es el nombre de fichero que propone
Windows si se elige "Imprimir a PDF". La fecha va delante, y con ese
formato, por el mismo motivo que en las copias de seguridad: ordenar por
nombre es ordenar por fecha. El sufijo no se traduce — un nombre de fichero
no debería cambiar según el idioma en que esté abierta la aplicación.

Son dos formas distintas a propósito:

- El **Tauler** se imprime tal como se ve
  (`export._paint_widget_on_printer`), con dos detalles que importan en el
  papel. Primero, **llena la página**: el Tauler es mucho más apaisado (2,2
  de ancho por 1 de alto) que un A4 apaisado (1,4), así que antes tenía que
  encajar por el ancho y dejaba vacío un tercio largo de la hoja; ahora,
  mientras dura la impresión, se le da la forma de la página
  (`_shaped_like_the_page`) y el contenido se expande para ocuparla entera
  —siguen siendo las 61 posiciones, solo que con las filas más altas— y
  vuelve a su tamaño al terminar. Segundo, **no es una captura de
  pantalla**: se le pide al widget que se dibuje sobre la página
  (`QWidget.render`) con el pintor escalado, así que el texto y las líneas
  se generan a la resolución de la impresora en vez de ampliar una imagen
  del tamaño de la pantalla, que salía borrosa.
- **Desmagatzem** es un **informe**: `export.print_table_report` compone
  todas las filas de la tabla en un `QTextDocument` (HTML con `<thead>`),
  así que Qt las reparte en páginas, repite la cabecera en cada una y no
  parte filas. No depende del scroll ni de lo que se vea: si hay 500
  registros se imprimen los 500, en horizontal y respetando el orden que
  haya elegido el usuario en las cabeceras. Cada celda viaja como
  `ReportCell(texto, color)`, así que **los fondos de color de la tabla**
  (por ejemplo los resaltados de búsqueda) salen también impresos, en una
  página o en veinte. Cada página lleva su **número al pie** ("Página 2 de
  7"): `QTextDocument.print_` reparte el texto en páginas pero no sabe
  añadir nada, así que el reparto se hace a mano
  (`_print_document_with_footer`) reservando una franja para el pie.

  Al ser texto compuesto y no una captura, este PDF es **vectorial**: unas
  decenas de kB, nítido a cualquier zoom y con el texto buscable. El del
  Tauler no puede serlo: Qt sólo sabe imprimir un widget como imagen (hasta
  una etiqueta suelta acaba rasterizada), así que sale como una imagen a
  1200 ppp — impecable en papel, pero imagen.

En Desmagatzem, **Mides y Notes se editan directamente en la tabla** (un
clic abre el editor; Enter guarda, Escape cancela). El valor va a la base
de datos al momento con `Repository.update_desmagatzem_field`, que solo
acepta esos dos campos; el resto de columnas son de solo lectura. Si el
guardado falla, se avisa y la tabla vuelve a lo que hay en la base de
datos.

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

## Estadísticas

Pestaña **Estadísticas** (`app/ui/statistics_tab.py`): cuántos movimientos
ha habido y cuándo. Se calcula **sólo leyendo** el histórico
(`Repository.movement_stats` y `movement_stats_by_destination`), que es la
única fuente de verdad de los movimientos; esta pestaña no escribe ni borra
nada.

Se elige un **intervalo de fechas** (dos campos con calendario, más los
intervalos hechos: hoy, últimos 7 / 30 días, último año) y sale, día a día:

- **Entradas** — líneas `in` (piezas colocadas en el Tauler y unidades
  registradas en Desmagatzem: una por unidad).
- **Salidas** — líneas `out` (piezas borradas y unidades retiradas).
- **Traslados** — líneas `move_in`, es decir el lado del **destino**. Un
  traslado deja dos líneas en el histórico (origen y destino) y contando
  sólo la del destino sale **un movimiento por traslado**, no dos, y además
  se puede decir a qué posición ha ido a parar la pieza: eso es la tabla de
  la derecha, "Traslados por posición de destino".

Los días sin ningún movimiento no ocupan fila, y al final va la fila de
totales. Es la primera versión, a propósito sencilla: cualquier estadística
nueva debería salir de aquí mismo, del mismo intervalo y de las mismas
consultas.

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
