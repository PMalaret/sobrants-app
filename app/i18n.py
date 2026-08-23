"""Internacionalització: català i castellà, amb selector en calent.

Totes les cadenes visibles per l'usuari passen per `t(clau, **kwargs)`.
L'idioma es guarda a `SobrantsData/settings.json` i es recupera en el
següent arrencada; canviar-lo en calent implica reconstruir la finestra
(`MainWindow._rebuild_ui`), no cal reiniciar l'aplicació.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_LANG = "ca"
LANGS = {"ca": "Català", "es": "Castellano"}

_state = {"lang": DEFAULT_LANG}
_settings_path: Path | None = None


def init_settings_path(data_dir: Path) -> None:
    """Crida's una vegada a l'arrencada amb la carpeta de dades de l'app."""
    global _settings_path
    _settings_path = data_dir / "settings.json"
    if _settings_path.exists():
        try:
            data = json.loads(_settings_path.read_text(encoding="utf-8"))
            lang = data.get("language")
            if lang in LANGS:
                _state["lang"] = lang
        except (OSError, ValueError):
            pass


def get_language() -> str:
    return _state["lang"]


def set_language(lang: str) -> None:
    if lang not in LANGS:
        raise ValueError(f"Idioma desconegut: {lang}")
    _state["lang"] = lang
    if _settings_path is not None:
        try:
            _settings_path.write_text(json.dumps({"language": lang}), encoding="utf-8")
        except OSError:
            pass


def t(key: str, **kwargs) -> str:
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key  # clau sense traduir; visible expressament per detectar-ho
    text = entry.get(_state["lang"]) or entry.get(DEFAULT_LANG) or key
    return text.format(**kwargs) if kwargs else text


TRANSLATIONS: dict[str, dict[str, str]] = {
    # -- Finestra principal --------------------------------------------- #
    "app.title": {"ca": "Sobrants — control d'inventari", "es": "Sobrants — control de inventario"},
    "app.language": {"ca": "Idioma", "es": "Idioma"},
    "menu.file": {"ca": "&Fitxer", "es": "&Archivo"},
    "menu.backup_now": {"ca": "Còpia de seguretat ara", "es": "Copia de seguridad ahora"},
    "menu.export_board": {"ca": "Exportar tauler a PDF…", "es": "Exportar tablero a PDF…"},
    "menu.export_desmagatzem": {"ca": "Exportar desmagatzem a PDF…", "es": "Exportar desmagatzem a PDF…"},
    "menu.report_covered": {"ca": "Informe de materials tapats", "es": "Informe de materiales tapados"},
    "menu.exit": {"ca": "Sortir", "es": "Salir"},
    "action.backup": {"ca": "Còpia de\nseguretat", "es": "Copia de\nseguridad"},
    "action.export_board": {"ca": "Exportar\ntauler a PDF", "es": "Exportar\ntablero a PDF"},
    "action.export_desmagatzem": {"ca": "Exportar\ndesmagatzem a PDF", "es": "Exportar\ndesmagatzem a PDF"},
    "action.covered": {"ca": "Materials\ntapats", "es": "Materiales\ntapados"},
    "dialog.backup.title": {"ca": "Còpia de seguretat", "es": "Copia de seguridad"},
    "dialog.backup.text": {"ca": "Còpia creada a:\n{path}", "es": "Copia creada en:\n{path}"},
    "status.db": {"ca": "Base de dades: {path}", "es": "Base de datos: {path}"},
    "status.db_backed_up": {
        "ca": "Base de dades: {path} — última còpia: ara",
        "es": "Base de datos: {path} — última copia: ahora",
    },
    "dialog.export_board.title": {"ca": "Exportar tauler", "es": "Exportar tablero"},
    "dialog.export_board.filename": {"ca": "tauler.pdf", "es": "tablero.pdf"},
    "dialog.exported.title": {"ca": "Exportat", "es": "Exportado"},
    "dialog.export_board.done": {"ca": "Tauler exportat a:\n{path}", "es": "Tablero exportado a:\n{path}"},
    "dialog.export_desmagatzem.title": {"ca": "Exportar desmagatzem", "es": "Exportar desmagatzem"},
    "dialog.export_desmagatzem.filename": {"ca": "desmagatzem.pdf", "es": "desmagatzem.pdf"},
    "dialog.export_desmagatzem.done": {
        "ca": "Desmagatzem exportat a:\n{path}",
        "es": "Desmagatzem exportado a:\n{path}",
    },
    "dialog.covered.title": {"ca": "Materials tapats", "es": "Materiales tapados"},
    "legend.title": {"ca": "Ocupació de les posicions", "es": "Ocupación de las posiciones"},
    "legend.piece_1": {"ca": "1 peça", "es": "1 pieza"},
    "legend.piece_5": {"ca": "5 (plena)", "es": "5 (llena)"},
    "legend.warning": {
        "ca": "Text vermell = material diferent barrejat a la posició",
        "es": "Texto rojo = material diferente mezclado en la posición",
    },

    # -- Pestanyes -------------------------------------------------------- #
    "tab.board": {"ca": "Tauler", "es": "Tablero"},
    "tab.desmagatzem": {"ca": "Desmagatzem", "es": "Desmagatzem"},
    "tab.historic": {"ca": "Històric", "es": "Histórico"},
    "tab.materials": {"ca": "Materials", "es": "Materiales"},

    # -- Tauler ------------------------------------------------------------ #
    "board.field.position": {"ca": "Posició", "es": "Posición"},
    "board.field.code": {"ca": "Núm. material", "es": "Núm. material"},
    "board.field.material": {"ca": "Material", "es": "Material"},
    "board.field.dimensions": {"ca": "Mides", "es": "Medidas"},
    "board.field.notes": {"ca": "Notes", "es": "Notas"},
    "board.hint": {
        "ca": "Doble clic sobre una posició per veure'n el detall, afegir o moure peces",
        "es": "Doble clic sobre una posición para ver el detalle, añadir o mover piezas",
    },
    "board.tooltip.inconsistent": {
        "ca": "Aquesta posició té més d'un material diferent entre les seves peces.",
        "es": "Esta posición tiene más de un material diferente entre sus piezas.",
    },
    "board.search_button": {"ca": "🔍  Cercar…", "es": "🔍  Buscar…"},
    "board.clear_search": {"ca": "Netejar cerca", "es": "Limpiar búsqueda"},
    "board.search_result": {
        "ca": "{count} coincidència(es) · més antiga: posc. {oldest}",
        "es": "{count} coincidencia(s) · más antigua: posc. {oldest}",
    },
    "board.search_result_desmagatzem": {
        "ca": " · {qty} ud(s) a Desmagatzem",
        "es": " · {qty} ud(s) en Desmagatzem",
    },

    # -- Diàleg de cerca ---------------------------------------------------- #
    "search.title": {"ca": "Cercar al tauler", "es": "Buscar en el tablero"},
    "search.code_label": {"ca": "Per núm. (exacte):", "es": "Por núm. (exacto):"},
    "search.code_placeholder": {"ca": "Núm. de material exacte", "es": "Núm. de material exacto"},
    "search.desc_label": {"ca": "Per material (parcial):", "es": "Por material (parcial):"},
    "search.desc_placeholder": {"ca": "Text parcial a la descripció", "es": "Texto parcial en la descripción"},
    "search.notes_label": {"ca": "Per notes (parcial):", "es": "Por notas (parcial):"},
    "search.notes_placeholder": {"ca": "Text parcial a les notes", "es": "Texto parcial en las notas"},
    "common.clear": {"ca": "Netejar", "es": "Limpiar"},
    "common.close": {"ca": "Tancar", "es": "Cerrar"},

    # -- Diàleg de posició --------------------------------------------------- #
    "position.title": {"ca": "Posició {position}", "es": "Posición {position}"},
    "position.subtitle": {"ca": "Posició {position} — fins a 5 peces", "es": "Posición {position} — hasta 5 piezas"},
    "position.detail.order": {"ca": "Ordre", "es": "Orden"},
    "position.detail.entered": {"ca": "Entrada", "es": "Entrada"},
    "position.add_box": {"ca": "Afegir peça a aquesta posició", "es": "Añadir pieza a esta posición"},
    "position.add_button": {"ca": "Afegir peça", "es": "Añadir pieza"},
    "position.delete_button": {"ca": "Esborrar última peça", "es": "Borrar última pieza"},
    "position.move_button": {"ca": "Moure peça visible a posició →", "es": "Mover pieza visible a posición →"},
    "position.duplicate.title": {"ca": "Material duplicat", "es": "Material duplicado"},
    "position.duplicate.text": {
        "ca": "Aquest material ja és a la(les) posició(ns): {positions}\n\nConfirmes afegir-lo de totes maneres?",
        "es": "Este material ya está en la(s) posición(es): {positions}\n\n¿Confirmas añadirlo de todas formas?",
    },
    "common.error": {"ca": "Error", "es": "Error"},
    "position.cannot_add": {"ca": "No es pot afegir", "es": "No se puede añadir"},
    "position.no_pieces.title": {"ca": "Sense peces", "es": "Sin piezas"},
    "position.no_pieces.text": {"ca": "Aquesta posició està buida.", "es": "Esta posición está vacía."},
    "position.confirm_delete.title": {"ca": "Confirmar esborrat", "es": "Confirmar borrado"},
    "position.confirm_delete.text": {
        "ca": "Segur que vols esborrar la posició {position}?\n\nNúm. {code} — {desc}",
        "es": "¿Seguro que quieres borrar la posición {position}?\n\nNúm. {code} — {desc}",
    },
    "position.cannot_delete": {"ca": "No es pot esborrar", "es": "No se puede borrar"},
    "position.cannot_move": {"ca": "No es pot moure", "es": "No se puede mover"},
    "position.moved.title": {"ca": "Peça moguda", "es": "Pieza movida"},
    "position.moved.text": {
        "ca": "Material {code} — {desc}\ntraslladada de la posició {from_pos} a la {to_pos}.",
        "es": "Material {code} — {desc}\ntrasladada de la posición {from_pos} a la {to_pos}.",
    },

    # -- Històric ------------------------------------------------------------ #
    "historic.col.position": {"ca": "Posició", "es": "Posición"},
    "historic.col.code": {"ca": "Núm. material", "es": "Núm. material"},
    "historic.col.material": {"ca": "Material", "es": "Material"},
    "historic.col.datetime": {"ca": "Data/hora", "es": "Fecha/hora"},
    "historic.col.movement": {"ca": "Moviment", "es": "Movimiento"},
    "historic.kind.in": {"ca": "Entrada", "es": "Entrada"},
    "historic.kind.out": {"ca": "Sortida", "es": "Salida"},
    "historic.kind.move_out": {"ca": "Trasllat (origen)", "es": "Traslado (origen)"},
    "historic.kind.move_in": {"ca": "Trasllat (destí)", "es": "Traslado (destino)"},
    "historic.filter_label": {"ca": "Filtrar per posició:", "es": "Filtrar por posición:"},
    "historic.filter_placeholder": {"ca": "p.ex. 12, o 'Desmagatzem'", "es": "p.ej. 12, o 'Desmagatzem'"},
    "historic.sort_label": {"ca": "Ordenar per:", "es": "Ordenar por:"},
    "historic.sort_date": {"ca": "Data", "es": "Fecha"},
    "historic.sort_position": {"ca": "Posició", "es": "Posición"},
    "historic.refresh": {"ca": "Actualitzar", "es": "Actualizar"},

    # -- Materials ------------------------------------------------------------ #
    "materials.col.code": {"ca": "Núm. material", "es": "Núm. material"},
    "materials.col.description": {"ca": "Descripció", "es": "Descripción"},
    "materials.search_label": {"ca": "Cercar:", "es": "Buscar:"},
    "materials.search_placeholder": {"ca": "Núm. o part de la descripció", "es": "Núm. o parte de la descripción"},

    # -- Desmagatzem ------------------------------------------------------------ #
    "desmagatzem.col.quantity": {"ca": "Quantitat", "es": "Cantidad"},
    "desmagatzem.col.code": {"ca": "Núm. material", "es": "Núm. material"},
    "desmagatzem.col.material": {"ca": "Material", "es": "Material"},
    "desmagatzem.col.dimensions": {"ca": "Mides", "es": "Medidas"},
    "desmagatzem.col.cart": {"ca": "Carro/lot", "es": "Carro/lote"},
    "desmagatzem.col.datetime": {"ca": "Data/hora", "es": "Fecha/hora"},
    "desmagatzem.confirm.increase": {
        "ca": "Confirmes augmentar la quantitat? Es registrarà a l'històric.",
        "es": "¿Confirmas aumentar la cantidad? Se registrará en el histórico.",
    },
    "desmagatzem.confirm.decrease": {
        "ca": "Confirmes disminuir la quantitat? Es registrarà a l'històric.",
        "es": "¿Confirmas disminuir la cantidad? Se registrará en el histórico.",
    },
    "desmagatzem.confirm.delete": {
        "ca": "La quantitat queda a 0: confirmes esborrar la línia? Es registrarà la baixa a l'històric.",
        "es": "La cantidad queda en 0: ¿confirmas borrar la línea? Se registrará la baja en el histórico.",
    },
    "desmagatzem.form_title": {"ca": "Nova retirada", "es": "Nueva retirada"},
    "desmagatzem.code_placeholder": {
        "ca": "Núm. de material (utilitza '1' per a material no registrat)",
        "es": "Núm. de material (usa '1' para material no registrado)",
    },
    "desmagatzem.custom_placeholder": {
        "ca": "Només si el núm. és 1: descriu el material",
        "es": "Solo si el núm. es 1: describe el material",
    },
    "desmagatzem.field.code": {"ca": "Núm. material:", "es": "Núm. material:"},
    "desmagatzem.field.custom": {"ca": "Material (si núm. = 1):", "es": "Material (si núm. = 1):"},
    "desmagatzem.field.quantity": {"ca": "Quantitat:", "es": "Cantidad:"},
    "desmagatzem.field.dimensions": {"ca": "Mides:", "es": "Medidas:"},
    "desmagatzem.field.cart": {"ca": "Carro/lot:", "es": "Carro/lote:"},
    "desmagatzem.cart_placeholder": {"ca": "p.ex. carro 88000", "es": "p.ej. carro 88000"},
    "desmagatzem.add_button": {"ca": "Registrar retirada", "es": "Registrar retirada"},
    "desmagatzem.new_qty_label": {
        "ca": "Nova quantitat per a la línia seleccionada:",
        "es": "Nueva cantidad para la línea seleccionada:",
    },
    "desmagatzem.apply_qty": {"ca": "Aplicar canvi de quantitat", "es": "Aplicar cambio de cantidad"},
    "desmagatzem.missing_code.title": {"ca": "Falta el núm. de material", "es": "Falta el núm. de material"},
    "desmagatzem.missing_code.text": {"ca": "Indica el núm. de material.", "es": "Indica el núm. de material."},
    "desmagatzem.cannot_register": {"ca": "No es pot registrar", "es": "No se puede registrar"},
    "desmagatzem.no_selection.title": {"ca": "Sense selecció", "es": "Sin selección"},
    "desmagatzem.no_selection.text": {
        "ca": "Selecciona primer una línia de la taula.",
        "es": "Selecciona primero una línea de la tabla.",
    },
    "common.confirm": {"ca": "Confirmar", "es": "Confirmar"},

    # -- Primer arrencada / migració ------------------------------------------- #
    "startup.title": {"ca": "Primer arrencada", "es": "Primer arranque"},
    "startup.text": {
        "ca": "Encara no s'ha trobat cap base de dades.\n\n"
        "Vols importar les dades des d'un fitxer Excel (SobrantsV4.74.xlsm) existent?",
        "es": "Todavía no se ha encontrado ninguna base de datos.\n\n"
        "¿Quieres importar los datos desde un archivo Excel (SobrantsV4.74.xlsm) existente?",
    },
    "startup.pick_excel": {"ca": "Selecciona l'Excel a importar", "es": "Selecciona el Excel a importar"},
    "startup.import_done.title": {"ca": "Importació completada", "es": "Importación completada"},
    "startup.import_done.text": {"ca": "Dades importades:\n", "es": "Datos importados:\n"},

    # -- Exportació / informes ------------------------------------------------- #
    "export.board.title": {"ca": "Tauler de sobrants", "es": "Tablero de sobrants"},
    "export.col.position": {"ca": "Posició", "es": "Posición"},
    "export.col.code": {"ca": "Núm.", "es": "Núm."},
    "export.col.material": {"ca": "Material", "es": "Material"},
    "export.col.dimensions": {"ca": "Mides", "es": "Medidas"},
    "export.col.notes": {"ca": "Notes", "es": "Notas"},
    "export.desmagatzem.title": {"ca": "Desmagatzem", "es": "Desmagatzem"},
    "export.col.quantity": {"ca": "Quant.", "es": "Cant."},
    "export.col.cart": {"ca": "Carro/lot", "es": "Carro/lote"},
    "report.covered.title": {"ca": "MATERIALS TAPATS", "es": "MATERIALES TAPADOS"},
    "report.covered.empty": {
        "ca": "(No s'han detectat materials tapats)",
        "es": "(No se han detectado materiales tapados)",
    },

    # -- Missatges de negoci (repository.py / rules.py) ------------------------ #
    "err.duplicate_material": {
        "ca": "Material duplicat a les posicions: {positions}",
        "es": "Material duplicado en las posiciones: {positions}",
    },
    "err.invalid_material_code": {
        "ca": "Entrada incorrecta. Només s'admeten números entre 0 i 99999.",
        "es": "Entrada incorrecta. Solo se admiten números entre 0 y 99999.",
    },
    "err.position_full": {"ca": "MOVIMENT IMPOSIBLE: POSICIÓ PLENA", "es": "MOVIMIENTO IMPOSIBLE: POSICIÓN LLENA"},
    "err.wrong_delete_order": {
        "ca": "ORDRE INCORRECTE: només es pot esborrar l'última peça de la posició.",
        "es": "ORDEN INCORRECTO: solo se puede borrar la última pieza de la posición.",
    },
    "err.cannot_move_to_self": {"ca": "NO ES POT MOURE ELL MATEIX", "es": "NO SE PUEDE MOVER A SÍ MISMA"},
    "err.no_piece_to_move": {
        "ca": "No hi ha cap peça per moure en aquesta posició.",
        "es": "No hay ninguna pieza para mover en esta posición.",
    },
    "err.invalid_quantity": {
        "ca": "Només s'admeten quantitats entre 0 i 20.",
        "es": "Solo se admiten cantidades entre 0 y 20.",
    },
    "err.unregistered_material_text": {
        "ca": "Escriu un material no registrat.",
        "es": "Escribe un material no registrado.",
    },
    "err.desmagatzem_row_not_found": {
        "ca": "Línia de desmagatzem no trobada.",
        "es": "Línea de desmagatzem no encontrada.",
    },
    "err.corrupt_slots": {
        "ca": "Els forats de la posició estan corromputs (han de ser consecutius des d'1)",
        "es": "Los huecos de la posición están corruptos (deben ser consecutivos desde 1)",
    },
}
