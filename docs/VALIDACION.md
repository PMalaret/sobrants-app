# Validación frente al Excel original

## 1. Migración de datos

Origen: `SobrantsV4.74.xlsm` (estado real de producción).

| Tabla nueva | Hoja origen | Filas migradas |
|---|---|---:|
| materials | Materials | 4.238 |
| pieces | llista | 123 (piezas reales; se descartan los huecos "---------") |
| historic | històric | 1.362 (se ignoran ~977 filas de formato sin datos reales) |
| desmagatzem | desmagatzem | 26 |

`Entrades` no se migra como tabla propia: se comprobó en el VBA
(`ActualitzaEntrades`) que es una copia literal de `llista` regenerada en
cada búsqueda, sin datos propios — su función queda cubierta por `pieces`.

## 2. Panel principal (Tablero) — comparación posición a posición

Se recalculó el resumen de cada una de las **61 posiciones** con la lógica
Python (`Repository.get_board()`) y se comparó contra los valores
*cacheados* en las celdas de `Hoja1` del Excel original (nº material,
descripción y medidas mostrados por posición).

```
Posiciones comparadas: 61
Discrepancias: 0
```

## 3. Buscadores (M20 / M22 / M24 de Hoja1)

Se tomaron los valores que el propio Excel tenía guardados en esas celdas
de búsqueda (`M20=32946`, `M22=CLARITY`, `M24=OPT`) y se compararon los
contadores de coincidencias y la "posición prioritaria" (FIFO) calculados
por la app nueva contra los que mostraba el Excel:

| Buscador | Consulta | Coincidencias (Excel → App) | Posición prioritaria (Excel → App) |
|---|---|---|---|
| M20 (código exacto) | `32946` | 1 → 1 | 58 → 58 |
| M22 (descripción parcial) | `CLARITY` | 4 → 4 | 19 → 19 |
| M24 (notas parcial) | `OPT` | 4 → 4 | `"--"` (bug, ver README) → 43 (real) |

## 3bis. Ayudas visuales (color de ocupación, inconsistencias, cruce con Desmagatzem)

Añadidas en una segunda pasada tras revisar de nuevo el VBA a petición del
usuario. Comparadas contra el color de relleno/fuente real guardado en las
celdas de `Hoja1` para las **61 posiciones**:

```
Discrepancias de color de ocupación: 0
Discrepancias de marca de inconsistencia (texto rojo): 0
```

Y contra los valores reales guardados en `Q20`/`Q22`/`Q24` de `Hoja1`
(unidades encontradas en desmagatzem para la misma búsqueda):

| Buscador | Q20/Q22/Q24 real | Calculado por la app |
|---|---|---|
| M20 = `32946` | (vacío) | 0 |
| M22 = `CLARITY` | 6 | 6 |
| M24 = `OPT` | 1 | 1 |

## 4. Reglas de negocio — pruebas unitarias/integración

`tests/test_rules.py` (16 casos) y `tests/test_repository.py` (18 casos)
cubren, con aserciones exactas:

- Normalización de texto (acentos/mayúsculas) igual que `NormalitzaText`.
- Rango válido de códigos de material (0–99999) y cantidades de
  desmagatzem (0–20).
- Llenado ordenado de posiciones (sin huecos) y bloqueo de borrado fuera
  de orden.
- Detección de material duplicado en otra posición, con confirmación.
- Resumen de posición = pieza del slot más alto con código > 1 (sentinela
  "material no registrado" excluido, igual que el original).
- Traslado de pieza entre posiciones con doble registro en histórico
  (origen/destino) y sin dejar huecos en la posición de origen.
- Altas/bajas/cambios de cantidad en Desmagatzem con el registro en
  histórico correspondiente (verde/rojo) y compactación de filas.
- Informe de "materiales tapados".

`tests/test_backup.py` (2 casos) cubre la rotación de copias de
seguridad (máximo 10, se eliminan las más antiguas).

**Total: 41 pruebas, 41 correctas.**

## 5. Empaquetado

Se generó un binario con PyInstaller (`sobrants.spec`) en macOS como
prueba de humo del proceso de empaquetado (arranque desde cero, detección
del primer arranque, carga de `schema.sql` y `style.qss` empaquetados, y
funcionamiento con una base de datos real precargada). El mismo `.spec`
se usa para Windows y Linux vía GitHub Actions (`.github/workflows/build.yml`).
