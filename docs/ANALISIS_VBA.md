# Mapeo de VBA → Python

Inventario de las macros de `SobrantsV4.74.xlsm` (14 módulos, 6 hojas con
código, 2 formularios, ~4.800 líneas) y dónde vive su equivalente aquí.

## Lógica de negocio portada

| Macro / función VBA | Hoja/módulo original | Equivalente Python |
|---|---|---|
| `NormalitzaText` | Hoja1 | `rules.normalize_text` |
| Validación 0–99999 en `Worksheet_Change` | Hoja1 | `rules.is_valid_material_code` |
| Validación 0–20 en `Worksheet_Change` | desmagatzem | `rules.is_valid_desmagatzem_qty` |
| Control "ORDRE NO CORRECTE" (llenado sin huecos) | Hoja1 `SelectionChange`/`Change` | `rules.next_free_slot`, `Repository.add_piece` |
| Control "ORDRE INCORRECTE" al borrar | Hoja1 `Change` | `rules.can_delete_slot`, `Repository.delete_piece` |
| `ComprovarCoincidenciesL12L16` (material duplicado) | Hoja1 | `rules.find_duplicate_positions`, `DuplicateMaterialError` |
| `ActualitzarUltimesCoincidencies` / `MostrarUltimValorMesGranQue1` | Hoja1/Módulo1 | `rules.board_summary_piece`, `Repository.get_board` |
| `ActualitzarM20` / `ActualitzarM22` / `ActualitzarM24` | Hoja1/Módulo1 | `Repository.search` (`mode="code"/"description"/"notes"`) |
| `MostrarPreview` + `CopiarPreviewAFilaDinamica` + `RegistrarPreviewIDestiAHistoric` | Módulo11 | `Repository.move_piece` |
| `ActualitzarLlistaSencer` (persistir L12:O16 en llista) | Hoja1 | implícito: `pieces` es ya la fuente de verdad, no hay copia intermedia |
| `CercaMaterialIMarcaHist` (alta en desmagatzem) | Hoja6 | `Repository.add_desmagatzem_row` |
| `ActualitzaHistorialQuantitat` (+ MsgBox aumento/disminución) | Módulo11 | `Repository.update_desmagatzem_quantity`, `rules.quantity_change_kind` |
| `Apilar` (compactar filas de desmagatzem) | Módulo11 | `Repository._compact_desmagatzem` |
| `SincronitzaAmbHoja1` | Módulo11 | no aplica: al no haber dos copias de datos (Hoja1 vs desmagatzem), no hace falta sincronizar nada |
| `ComprovarIMostrarTapats_Correcte` (materiales tapados) | Módulo13 | `rules.find_covered_materials`, `Repository.covered_materials_report` |
| `CrearBackup` / `IniciarBackupAutomatic` | Módulo12 | `app/backup.py` (`create_backup`, temporizador de 4h en `MainWindow`) |
| `ImprimirHoja1` / `ImprimirDesmagatzem` | Módulo13 | `app/export.py` (exporta a PDF en vez de imprimir directamente) |
| `AplicarColorsPerCoincidencies` / `AplicarColorSegonsFilaIValorK12` (color de ocupación K12:K16) | Hoja1/Módulo2 | `rules.fill_color_for_count`, columna "Posición" del Tablero (con leyenda) |
| `MarcarInconsistencies` (texto rojo si hay material mezclado) | Hoja1/Módulo1 | `rules.has_material_inconsistency`, fila en rojo + tooltip en el Tablero |
| `BuscaCoincidenciesDesmagatzem_Q20/M22/M24` (los buscadores de Hoja1 también cuentan unidades en desmagatzem) | Módulo9 | `Repository._search_desmagatzem_quantity`, se añade al texto de cada buscador del Tablero |
| `AlternarOrdre` / `ActualitzaColorOrdre` (indicador de orden en històric) | Módulo6/Hoja4 | botones "Fecha"/"Posición" en la pestaña Histórico, con el activo resaltado |

## Deliberadamente no portado (mecánica de Excel, sin efecto en el negocio)

Estas macros existen sólo para simular un formulario dentro de la
cuadrícula de Excel. En una aplicación con formularios y widgets reales
no tienen sentido — la *regla* que protegían sigue vigente (ver tabla de
arriba), pero el truco de interfaz desaparece:

- `Worksheet_SelectionChange` (saltos de celda, `Application.OnTime`,
  `SaltarAL12`, `SaltALFilaSeguent`, `SeleccionaCelLaDeSotaUltimValorMajorQue1`)
- `PampallugueigText` (texto parpadeante)
- `ToggleCintaIAjustarAlcades`, `ConfiguracioOpcio1` (mostrar/ocultar la
  cinta de Excel, tamaños de fila)
- Protección de hoja con contraseña `"1234"` (`ProtegerHoja1ConUserInterfaceOnly`,
  `ProtegirHistoric`, `ProtegirFulladesmagatzem`, `desprotegirTot`) — la
  aplicación nueva no expone edición directa de tablas, así que no hace
  falta un candado de hoja
- Shapes de Excel (`MostrarMissatgeShape`, `AmagarMissatgeShape`,
  botones `Botón 3/4/5`, imágenes `ImgUSB_*`) → sustituidos por
  `QMessageBox`/etiquetas nativas donde aportan información real

## Reemplazado por una alternativa equivalente (no reproducible tal cual)

| Original | Por qué no aplica | Alternativa |
|---|---|---|
| `HiHaUSB` / `MonitorUSB` / `ObrirUSB` (aviso obligatorio si no hay USB) | Ligado a `Scripting.FileSystemObject` de Windows y a un flujo de backup manual a USB | Backup automático a carpeta local `SobrantsData/Backups/` cada 4h (decisión confirmada con el usuario: modernizar en vez de replicar) |
| `Shell "notepad.exe" ...` (informe de materiales tapados) | Depende del Bloc de notas de Windows | Diálogo con el mismo contenido dentro de la propia app (`MainWindow._show_covered_report`) |
| `=SI.ERROR(BUSCARV(...))` | Fórmula de hoja | `Repository.lookup_material` (consulta SQL directa, mismo fallback `"---------"`) |
| `Application.OnTime` (temporizadores) | API de Excel | `QTimer` de Qt |

## Otras utilidades del original, no portadas conscientemente

Revisadas y descartadas por ser herramientas puntuales de un desarrollador/administrador,
no parte del flujo de trabajo diario de los operarios:

- `BuscarNumeroDesmagatzem`, `BuscarMaterial`, `BuscarColumnaE`, `BuscarRefMaterials`,
  `BuscarParcialB_Materials` (Módulo9): ventanas emergentes (`InputBox`) para buscar
  puntualmente en Desmagatzem/Materials. Sustituidas por algo mejor ya presente en la
  app: los cuadros de búsqueda en vivo del Tablero y el filtro de la pestaña Materiales.
- `NetejarHistoricAmbContrasenya` (Módulo6): borra todo el histórico con una
  contraseña. No se ha portado — es una acción destructiva e irreversible; si la
  necesitáis decídmelo y la añado con una confirmación explícita en vez de una
  contraseña fija sin valor real de seguridad.
- `desprotegirTot`, `ProtegirHistoric`, `ProtegirFulladesmagatzem`,
  `ProtegerHoja1ConUserInterfaceOnly` (protección de hoja con contraseña `"1234"`):
  no aplica — la app nueva no permite editar las tablas directamente, así que no
  hace falta un candado de hoja.
- `CopiarFullaDesmagatzem` (Módulo10): utilidad de migración con rutas de disco
  del desarrollador (`C:\des\...`) de una versión anterior del archivo. No aplica.
- `PampallugueigText` (parpadeo rojo/negro del texto al buscar): mecánica de
  selección de celda de Excel sin equivalente directo; el `QLineEdit` de cada
  buscador ya cambia de borde al tener el foco, que cumple la misma función de
  "estás buscando aquí".

## Bug identificado y corregido

`ActualitzarM24` calculaba la posición más antigua para el buscador de
notas (`valorAM24`) y luego la descartaba, dejando siempre el texto fijo
`"--"` en O24. Es decir: en el Excel original ese dato nunca llegó a
verse. En la app nueva se muestra el valor calculado de verdad, igual que
en los otros dos buscadores (ver `docs/VALIDACION.md`, sección 3).
