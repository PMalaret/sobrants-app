# Sobrants — aplicación de control de inventario

Reemplazo independiente de **SobrantsV4.74.xlsm**: misma lógica, mismas
reglas de negocio, sin necesidad de Microsoft Excel. Construida en
Python + PySide6 (Qt), con los datos en una base de datos SQLite local
(`SobrantsData/sobrants.db`, junto al ejecutable).

## Qué hace cada pieza

| Excel original | Aquí |
|---|---|
| Hoja1 (panel + buscadores + entrada de datos) | Pestaña **Tablero** |
| llista / Entrades (fuente de verdad de piezas por posición) | tabla `pieces` en SQLite |
| històric (auditoría) | Pestaña **Histórico** + tabla `historic` |
| Materials (catálogo) | Pestaña **Materiales** + tabla `materials` |
| desmagatzem | Pestaña **Desmagatzem** + tabla `desmagatzem` |
| Macros VBA (~4.800 líneas) | `app/logic/rules.py` + `app/logic/repository.py` |

Ver `docs/ANALISIS_VBA.md` para el mapeo detallado macro por macro.

## Uso en desarrollo

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python run_app.py
```

En el primer arranque, la aplicación pregunta si quieres importar los
datos desde un `.xlsm` existente (recomendado la primera vez) o empezar
con una base de datos vacía.

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

Automáticas cada 4 horas y al cerrar la aplicación, en
`SobrantsData/Backups/` (se conservan las 10 más recientes). También hay
un botón "Copia de seguridad ahora" en el menú Archivo.

## Diferencia intencionada respecto al original

En el Excel, la casilla "posición prioritaria" del buscador por notas
(O24) se calculaba pero luego se sobrescribía siempre con el texto fijo
`"--"` (código muerto: el resultado real nunca llegaba a mostrarse — ver
`Módulo1`, `ActualitzarM24`). Aquí se muestra el resultado calculado de
verdad, igual que en los otros dos buscadores. Es la única discrepancia
deliberada respecto al comportamiento observable del original; todo lo
demás se ha validado para que coincida exactamente.
