"""Internacionalització: català, castellà, anglès i francès, amb selector
en calent.

Totes les cadenes visibles per l'usuari passen per `t(clau, **kwargs)`.
L'idioma es guarda a `SobrantsData/settings.json` i es recupera en el
següent arrencada; canviar-lo en calent implica reconstruir la finestra
(`MainWindow._build_everything`), no cal reiniciar l'aplicació.

Qualsevol clau nova que s'afegeixi aquí ha de portar sempre els 4 idiomes
(ca/es/en/fr) — mai només un subconjunt.
"""
from __future__ import annotations

import json
from pathlib import Path

DEFAULT_LANG = "ca"
LANGS = {"ca": "Català", "es": "Castellano", "en": "English", "fr": "Français"}

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
    "app.title": {
        "ca": "Sobrants — control d'inventari",
        "es": "Sobrants — control de inventario",
        "en": "Sobrants — inventory control",
        "fr": "Sobrants — contrôle d'inventaire",
    },
    "app.language": {"ca": "Idioma", "es": "Idioma", "en": "Language", "fr": "Langue"},
    "menu.file": {"ca": "&Fitxer", "es": "&Archivo", "en": "&File", "fr": "&Fichier"},
    "menu.backup_now": {
        "ca": "Còpia de seguretat ara",
        "es": "Copia de seguridad ahora",
        "en": "Backup now",
        "fr": "Sauvegarder maintenant",
    },
    "menu.export_board": {
        "ca": "Exportar tauler a PDF…",
        "es": "Exportar tablero a PDF…",
        "en": "Export board to PDF…",
        "fr": "Exporter le tableau en PDF…",
    },
    "menu.export_desmagatzem": {
        "ca": "Exportar desmagatzem a PDF…",
        "es": "Exportar desmagatzem a PDF…",
        "en": "Export desmagatzem to PDF…",
        "fr": "Exporter desmagatzem en PDF…",
    },
    "menu.report_covered": {
        "ca": "Informe de materials tapats",
        "es": "Informe de materiales tapados",
        "en": "Hidden materials report",
        "fr": "Rapport des matériaux masqués",
    },
    "menu.exit": {"ca": "Sortir", "es": "Salir", "en": "Exit", "fr": "Quitter"},
    "menu.version": {
        "ca": "Versió {version}", "es": "Versión {version}",
        "en": "Version {version}", "fr": "Version {version}",
    },
    "menu.about": {
        "ca": "Sobre Sobrants", "es": "Sobre Sobrants",
        "en": "About Sobrants", "fr": "À propos de Sobrants",
    },
    "about.creator": {
        "ca": "Creador: <a href=\"{url}\">{url}</a>",
        "es": "Creador: <a href=\"{url}\">{url}</a>",
        "en": "Creator: <a href=\"{url}\">{url}</a>",
        "fr": "Créateur : <a href=\"{url}\">{url}</a>",
    },
    "action.backup": {
        "ca": "Còpia de\nseguretat",
        "es": "Copia de\nseguridad",
        "en": "Create\nbackup",
        "fr": "Créer une\nsauvegarde",
    },
    "action.export_board": {
        "ca": "Exportar\ntauler a PDF",
        "es": "Exportar\ntablero a PDF",
        "en": "Export\nboard to PDF",
        "fr": "Exporter\nle tableau en PDF",
    },
    "action.export_desmagatzem": {
        "ca": "Exportar\ndesmagatzem a PDF",
        "es": "Exportar\ndesmagatzem a PDF",
        "en": "Export\ndesmagatzem to PDF",
        "fr": "Exporter\ndesmagatzem en PDF",
    },
    "action.covered": {
        "ca": "Materials\ntapats",
        "es": "Materiales\ntapados",
        "en": "Hidden\nmaterials",
        "fr": "Matériaux\nmasqués",
    },
    "dialog.backup.title": {
        "ca": "Còpia de seguretat",
        "es": "Copia de seguridad",
        "en": "Backup",
        "fr": "Sauvegarde",
    },
    "dialog.backup.text": {
        "ca": "Còpia creada a:\n{path}",
        "es": "Copia creada en:\n{path}",
        "en": "Backup created at:\n{path}",
        "fr": "Sauvegarde créée dans :\n{path}",
    },
    "status.db": {
        "ca": "Base de dades: {path}",
        "es": "Base de datos: {path}",
        "en": "Database: {path}",
        "fr": "Base de données : {path}",
    },
    "status.db_backed_up": {
        "ca": "Base de dades: {path} — última còpia: ara",
        "es": "Base de datos: {path} — última copia: ahora",
        "en": "Database: {path} — last backup: now",
        "fr": "Base de données : {path} — dernière sauvegarde : maintenant",
    },
    "dialog.export_board.title": {
        "ca": "Exportar tauler",
        "es": "Exportar tablero",
        "en": "Export board",
        "fr": "Exporter le tableau",
    },
    "dialog.export_board.filename": {"ca": "tauler.pdf", "es": "tablero.pdf", "en": "board.pdf", "fr": "tableau.pdf"},
    "dialog.exported.title": {"ca": "Exportat", "es": "Exportado", "en": "Exported", "fr": "Exporté"},
    "dialog.export_board.done": {
        "ca": "Tauler exportat a:\n{path}",
        "es": "Tablero exportado a:\n{path}",
        "en": "Board exported to:\n{path}",
        "fr": "Tableau exporté dans :\n{path}",
    },
    "dialog.export_desmagatzem.title": {
        "ca": "Exportar desmagatzem",
        "es": "Exportar desmagatzem",
        "en": "Export desmagatzem",
        "fr": "Exporter desmagatzem",
    },
    "dialog.export_desmagatzem.filename": {
        "ca": "desmagatzem.pdf",
        "es": "desmagatzem.pdf",
        "en": "desmagatzem.pdf",
        "fr": "desmagatzem.pdf",
    },
    "dialog.export_desmagatzem.done": {
        "ca": "Desmagatzem exportat a:\n{path}",
        "es": "Desmagatzem exportado a:\n{path}",
        "en": "Desmagatzem exported to:\n{path}",
        "fr": "Desmagatzem exporté dans :\n{path}",
    },
    "dialog.covered.title": {
        "ca": "Materials tapats",
        "es": "Materiales tapados",
        "en": "Hidden materials",
        "fr": "Matériaux masqués",
    },
    "legend.title": {
        "ca": "Ocupació de les posicions",
        "es": "Ocupación de las posiciones",
        "en": "Position occupancy",
        "fr": "Occupation des positions",
    },
    "legend.piece_1": {"ca": "1 peça", "es": "1 pieza", "en": "1 piece", "fr": "1 pièce"},
    "legend.piece_5": {"ca": "5 (plena)", "es": "5 (llena)", "en": "5 (full)", "fr": "5 (pleine)"},
    "legend.warning": {
        "ca": "Text vermell = material diferent barrejat a la posició",
        "es": "Texto rojo = material diferente mezclado en la posición",
        "en": "Red text = different material mixed in the position",
        "fr": "Texte rouge = matériau différent mélangé dans la position",
    },

    # -- Pestanyes -------------------------------------------------------- #
    "tab.board": {"ca": "Tauler", "es": "Tablero", "en": "Board", "fr": "Tableau"},
    "tab.desmagatzem": {"ca": "Desmagatzem", "es": "Desmagatzem", "en": "Desmagatzem", "fr": "Desmagatzem"},
    "tab.historic": {"ca": "Històric", "es": "Histórico", "en": "History", "fr": "Historique"},
    "tab.materials": {"ca": "Materials", "es": "Materiales", "en": "Materials", "fr": "Matériaux"},

    # -- Tauler ------------------------------------------------------------ #
    "board.field.position": {"ca": "Pos.", "es": "Pos.", "en": "Pos.", "fr": "Pos."},
    "board.field.code": {
        "ca": "Núm.", "es": "Núm.", "en": "No.", "fr": "N°",
    },
    "board.field.material": {"ca": "Material", "es": "Material", "en": "Material", "fr": "Matériau"},
    "board.field.dimensions": {"ca": "Mides", "es": "Medidas", "en": "Dimensions", "fr": "Dimensions"},
    "board.field.notes": {"ca": "Notes", "es": "Notas", "en": "Notes", "fr": "Notes"},
    "board.hint": {
        "ca": "Doble clic sobre una posició per veure'n el detall, afegir o moure peces",
        "es": "Doble clic sobre una posición para ver el detalle, añadir o mover piezas",
        "en": "Double-click a position to see its detail, add or move pieces",
        "fr": "Double-cliquez sur une position pour voir son détail, ajouter ou déplacer des pièces",
    },
    "board.tooltip.inconsistent": {
        "ca": "Aquesta posició té més d'un material diferent entre les seves peces.",
        "es": "Esta posición tiene más de un material diferente entre sus piezas.",
        "en": "This position has more than one different material among its pieces.",
        "fr": "Cette position contient plus d'un matériau différent parmi ses pièces.",
    },
    "board.search_button": {
        "ca": "🔍  Cercar…", "es": "🔍  Buscar…", "en": "🔍  Search…", "fr": "🔍  Rechercher…",
    },
    "board.clear_search": {
        "ca": "Netejar cerca", "es": "Limpiar búsqueda", "en": "Clear search", "fr": "Effacer la recherche",
    },
    "board.search_result": {
        "ca": "{count} coincidència(es) · més antiga: posc. {oldest}",
        "es": "{count} coincidencia(s) · más antigua: posc. {oldest}",
        "en": "{count} match(es) · oldest: pos. {oldest}",
        "fr": "{count} correspondance(s) · plus ancienne : pos. {oldest}",
    },
    "board.search_result_desmagatzem": {
        "ca": " · {qty} ud(s) a Desmagatzem",
        "es": " · {qty} ud(s) en Desmagatzem",
        "en": " · {qty} unit(s) in Desmagatzem",
        "fr": " · {qty} unité(s) dans Desmagatzem",
    },

    # -- Diàleg de cerca ---------------------------------------------------- #
    "search.title": {
        "ca": "Cercar al tauler", "es": "Buscar en el tablero",
        "en": "Search the board", "fr": "Rechercher dans le tableau",
    },
    "search.code_label": {
        "ca": "Per núm. (exacte):", "es": "Por núm. (exacto):",
        "en": "By no. (exact):", "fr": "Par n° (exact) :",
    },
    "search.code_placeholder": {
        "ca": "Núm. de material exacte", "es": "Núm. de material exacto",
        "en": "Exact material no.", "fr": "N° de matériau exact",
    },
    "search.desc_label": {
        "ca": "Per material (parcial):", "es": "Por material (parcial):",
        "en": "By material (partial):", "fr": "Par matériau (partiel) :",
    },
    "search.desc_placeholder": {
        "ca": "Text parcial a la descripció", "es": "Texto parcial en la descripción",
        "en": "Partial text in the description", "fr": "Texte partiel dans la description",
    },
    "search.notes_label": {
        "ca": "Per notes (parcial):", "es": "Por notas (parcial):",
        "en": "By notes (partial):", "fr": "Par notes (partiel) :",
    },
    "search.notes_placeholder": {
        "ca": "Text parcial a les notes", "es": "Texto parcial en las notas",
        "en": "Partial text in the notes", "fr": "Texte partiel dans les notes",
    },
    "common.clear": {"ca": "Netejar", "es": "Limpiar", "en": "Clear", "fr": "Effacer"},
    "common.close": {"ca": "Tancar", "es": "Cerrar", "en": "Close", "fr": "Fermer"},

    # -- Panell de posició --------------------------------------------------- #
    "position.title": {
        "ca": "Posició {position}", "es": "Posición {position}",
        "en": "Position {position}", "fr": "Position {position}",
    },
    "position.subtitle": {
        "ca": "Posició {position}",
        "es": "Posición {position}",
        "en": "Position {position}",
        "fr": "Position {position}",
    },
    "position.detail.entered": {"ca": "Entrada", "es": "Entrada", "en": "Entered", "fr": "Entrée"},
    "position.add_box": {
        "ca": "Afegir peça a aquesta posició", "es": "Añadir pieza a esta posición",
        "en": "Add a piece to this position", "fr": "Ajouter une pièce à cette position",
    },
    "position.add_button": {
        "ca": "Afegir peça", "es": "Añadir pieza", "en": "Add piece", "fr": "Ajouter une pièce",
    },
    "position.delete_button": {
        "ca": "Esborrar última peça", "es": "Borrar última pieza",
        "en": "Delete last piece", "fr": "Supprimer la dernière pièce",
    },
    "position.move_button": {
        "ca": "Moure peça visible a posició →", "es": "Mover pieza visible a posición →",
        "en": "Move visible piece to position →", "fr": "Déplacer la pièce visible vers la position →",
    },
    "position.duplicate.title": {
        "ca": "Material duplicat", "es": "Material duplicado",
        "en": "Duplicate material", "fr": "Matériau en double",
    },
    "position.duplicate.text": {
        "ca": "Aquest material ja és a la(les) posició(ns): {positions}\n\nConfirmes afegir-lo de totes maneres?",
        "es": "Este material ya está en la(s) posición(es): {positions}\n\n¿Confirmas añadirlo de todas formas?",
        "en": "This material is already in position(s): {positions}\n\nConfirm adding it anyway?",
        "fr": "Ce matériau se trouve déjà dans la (les) position(s) : {positions}\n\nConfirmez-vous l'ajouter quand même ?",
    },
    "position.material_not_found.title": {
        "ca": "Material no trobat", "es": "Material no encontrado",
        "en": "Material not found", "fr": "Matériau introuvable",
    },
    "position.material_not_found.text": {
        "ca": "No s'ha trobat cap material amb el número {code} al catàleg. "
        "S'afegirà igualment la peça.",
        "es": "No se ha encontrado ningún material con el número {code} en el catálogo. "
        "Se añadirá la pieza igualmente.",
        "en": "No material with number {code} was found in the catalog. "
        "The piece will be added anyway.",
        "fr": "Aucun matériau portant le numéro {code} n'a été trouvé dans le catalogue. "
        "La pièce sera quand même ajoutée.",
    },
    "common.error": {"ca": "Error", "es": "Error", "en": "Error", "fr": "Erreur"},
    "position.cannot_add": {
        "ca": "No es pot afegir", "es": "No se puede añadir",
        "en": "Cannot add", "fr": "Impossible d'ajouter",
    },
    "position.no_pieces.title": {
        "ca": "Sense peces", "es": "Sin piezas", "en": "No pieces", "fr": "Aucune pièce",
    },
    "position.no_pieces.text": {
        "ca": "Aquesta posició està buida.", "es": "Esta posición está vacía.",
        "en": "This position is empty.", "fr": "Cette position est vide.",
    },
    "position.confirm_delete.title": {
        "ca": "Confirmar esborrat", "es": "Confirmar borrado",
        "en": "Confirm deletion", "fr": "Confirmer la suppression",
    },
    "position.confirm_delete.text": {
        "ca": "Segur que vols esborrar la posició {position}?\n\nNúm. {code} — {desc}",
        "es": "¿Seguro que quieres borrar la posición {position}?\n\nNúm. {code} — {desc}",
        "en": "Are you sure you want to delete position {position}?\n\nNo. {code} — {desc}",
        "fr": "Êtes-vous sûr de vouloir supprimer la position {position} ?\n\nN° {code} — {desc}",
    },
    "position.cannot_delete": {
        "ca": "No es pot esborrar", "es": "No se puede borrar",
        "en": "Cannot delete", "fr": "Impossible de supprimer",
    },
    "position.cannot_move": {
        "ca": "No es pot moure", "es": "No se puede mover",
        "en": "Cannot move", "fr": "Impossible de déplacer",
    },
    "position.moved.title": {
        "ca": "Peça moguda", "es": "Pieza movida", "en": "Piece moved", "fr": "Pièce déplacée",
    },
    "position.moved.text": {
        "ca": "Material {code} — {desc}\ntraslladada de la posició {from_pos} a la {to_pos}.",
        "es": "Material {code} — {desc}\ntrasladada de la posición {from_pos} a la {to_pos}.",
        "en": "Material {code} — {desc}\nmoved from position {from_pos} to {to_pos}.",
        "fr": "Matériau {code} — {desc}\ndéplacé de la position {from_pos} vers {to_pos}.",
    },

    # -- Històric ------------------------------------------------------------ #
    "historic.col.position": {"ca": "Pos.", "es": "Pos.", "en": "Pos.", "fr": "Pos."},
    "historic.col.code": {
        "ca": "Núm. material", "es": "Núm. material", "en": "Material no.", "fr": "N° matériau",
    },
    "historic.col.material": {"ca": "Material", "es": "Material", "en": "Material", "fr": "Matériau"},
    "historic.col.datetime": {"ca": "Data/hora", "es": "Fecha/hora", "en": "Date/time", "fr": "Date/heure"},
    "historic.col.movement": {"ca": "Moviment", "es": "Movimiento", "en": "Movement", "fr": "Mouvement"},
    "historic.kind.in": {"ca": "Entrada", "es": "Entrada", "en": "In", "fr": "Entrée"},
    "historic.kind.out": {"ca": "Sortida", "es": "Salida", "en": "Out", "fr": "Sortie"},
    "historic.kind.move_out": {
        "ca": "Trasllat (origen)", "es": "Traslado (origen)",
        "en": "Move (origin)", "fr": "Déplacement (origine)",
    },
    "historic.kind.move_in": {
        "ca": "Trasllat (destí)", "es": "Traslado (destino)",
        "en": "Move (destination)", "fr": "Déplacement (destination)",
    },
    "historic.filter_label": {
        "ca": "Filtrar per posició:", "es": "Filtrar por posición:",
        "en": "Filter by position:", "fr": "Filtrer par position :",
    },
    "historic.filter_placeholder": {
        "ca": "p.ex. 12, o 'Desmagatzem'", "es": "p.ej. 12, o 'Desmagatzem'",
        "en": "e.g. 12, or 'Desmagatzem'", "fr": "ex. 12, ou « Desmagatzem »",
    },
    "historic.sort_label": {
        "ca": "Ordenar per:", "es": "Ordenar por:", "en": "Sort by:", "fr": "Trier par :",
    },
    "historic.sort_date": {"ca": "Data", "es": "Fecha", "en": "Date", "fr": "Date"},
    "historic.sort_position": {"ca": "Pos.", "es": "Pos.", "en": "Pos.", "fr": "Pos."},
    "historic.refresh": {"ca": "Actualitzar", "es": "Actualizar", "en": "Refresh", "fr": "Actualiser"},

    # -- Materials ------------------------------------------------------------ #
    "materials.col.code": {
        "ca": "Núm. material", "es": "Núm. material", "en": "Material no.", "fr": "N° matériau",
    },
    "materials.col.description": {
        "ca": "Descripció", "es": "Descripción", "en": "Description", "fr": "Description",
    },
    "materials.search_label": {"ca": "Cercar:", "es": "Buscar:", "en": "Search:", "fr": "Rechercher :"},
    "materials.search_placeholder": {
        "ca": "Núm. o part de la descripció", "es": "Núm. o parte de la descripción",
        "en": "No. or part of the description", "fr": "N° ou partie de la description",
    },
    "materials.count": {
        "ca": "{count} materials", "es": "{count} materiales",
        "en": "{count} materials", "fr": "{count} matériaux",
    },

    # -- Desmagatzem ------------------------------------------------------------ #
    "desmagatzem.col.quantity": {"ca": "Quantitat", "es": "Cantidad", "en": "Quantity", "fr": "Quantité"},
    "desmagatzem.col.code": {
        "ca": "Núm. material", "es": "Núm. material", "en": "Material no.", "fr": "N° matériau",
    },
    "desmagatzem.col.material": {"ca": "Material", "es": "Material", "en": "Material", "fr": "Matériau"},
    "desmagatzem.col.dimensions": {"ca": "Mides", "es": "Medidas", "en": "Dimensions", "fr": "Dimensions"},
    "desmagatzem.col.cart": {"ca": "Carro/lot", "es": "Carro/lote", "en": "Cart/batch", "fr": "Chariot/lot"},
    "desmagatzem.col.datetime": {"ca": "Data/hora", "es": "Fecha/hora", "en": "Date/time", "fr": "Date/heure"},
    "desmagatzem.confirm.increase": {
        "ca": "Confirmes augmentar la quantitat? Es registrarà a l'històric.",
        "es": "¿Confirmas aumentar la cantidad? Se registrará en el histórico.",
        "en": "Confirm increasing the quantity? It will be logged in the history.",
        "fr": "Confirmez-vous l'augmentation de la quantité ? Cela sera enregistré dans l'historique.",
    },
    "desmagatzem.confirm.decrease": {
        "ca": "Confirmes disminuir la quantitat? Es registrarà a l'històric.",
        "es": "¿Confirmas disminuir la cantidad? Se registrará en el histórico.",
        "en": "Confirm decreasing the quantity? It will be logged in the history.",
        "fr": "Confirmez-vous la diminution de la quantité ? Cela sera enregistré dans l'historique.",
    },
    "desmagatzem.confirm.delete": {
        "ca": "La quantitat queda a 0: confirmes esborrar la línia? Es registrarà la baixa a l'històric.",
        "es": "La cantidad queda en 0: ¿confirmas borrar la línea? Se registrará la baja en el histórico.",
        "en": "Quantity will be 0: confirm deleting the row? The removal will be logged in the history.",
        "fr": "La quantité sera à 0 : confirmez-vous la suppression de la ligne ? "
        "Le retrait sera enregistré dans l'historique.",
    },
    "desmagatzem.form_title": {
        "ca": "Nova retirada", "es": "Nueva retirada", "en": "New removal", "fr": "Nouveau retrait",
    },
    "desmagatzem.code_placeholder": {
        "ca": "Núm. de material (utilitza '1' per a material no registrat)",
        "es": "Núm. de material (usa '1' para material no registrado)",
        "en": "Material no. (use '1' for an unregistered material)",
        "fr": "N° de matériau (utilisez « 1 » pour un matériau non enregistré)",
    },
    "desmagatzem.custom_placeholder": {
        "ca": "Només si el núm. és 1: descriu el material",
        "es": "Solo si el núm. es 1: describe el material",
        "en": "Only if the no. is 1: describe the material",
        "fr": "Seulement si le n° est 1 : décrivez le matériau",
    },
    "desmagatzem.field.code": {
        "ca": "Núm. material:", "es": "Núm. material:", "en": "Material no.:", "fr": "N° matériau :",
    },
    "desmagatzem.field.custom": {
        "ca": "Material (si núm. = 1):", "es": "Material (si núm. = 1):",
        "en": "Material (if no. = 1):", "fr": "Matériau (si n° = 1) :",
    },
    "desmagatzem.field.quantity": {
        "ca": "Quantitat:", "es": "Cantidad:", "en": "Quantity:", "fr": "Quantité :",
    },
    "desmagatzem.field.dimensions": {
        "ca": "Mides:", "es": "Medidas:", "en": "Dimensions:", "fr": "Dimensions :",
    },
    "desmagatzem.field.cart": {
        "ca": "Carro/lot:", "es": "Carro/lote:", "en": "Cart/batch:", "fr": "Chariot/lot :",
    },
    "desmagatzem.cart_placeholder": {
        "ca": "p.ex. carro 88000", "es": "p.ej. carro 88000",
        "en": "e.g. cart 88000", "fr": "ex. chariot 88000",
    },
    "desmagatzem.add_button": {
        "ca": "Registrar retirada", "es": "Registrar retirada",
        "en": "Register removal", "fr": "Enregistrer le retrait",
    },
    "desmagatzem.new_qty_label": {
        "ca": "Nova quantitat per a la línia seleccionada:",
        "es": "Nueva cantidad para la línea seleccionada:",
        "en": "New quantity for the selected row:",
        "fr": "Nouvelle quantité pour la ligne sélectionnée :",
    },
    "desmagatzem.apply_qty": {
        "ca": "Aplicar canvi de quantitat", "es": "Aplicar cambio de cantidad",
        "en": "Apply quantity change", "fr": "Appliquer le changement de quantité",
    },
    "desmagatzem.missing_code.title": {
        "ca": "Falta el núm. de material", "es": "Falta el núm. de material",
        "en": "Missing material no.", "fr": "N° de matériau manquant",
    },
    "desmagatzem.missing_code.text": {
        "ca": "Indica el núm. de material.", "es": "Indica el núm. de material.",
        "en": "Enter the material no.", "fr": "Indiquez le n° de matériau.",
    },
    "desmagatzem.cannot_register": {
        "ca": "No es pot registrar", "es": "No se puede registrar",
        "en": "Cannot register", "fr": "Impossible d'enregistrer",
    },
    "desmagatzem.no_selection.title": {
        "ca": "Sense selecció", "es": "Sin selección", "en": "No selection", "fr": "Aucune sélection",
    },
    "desmagatzem.no_selection.text": {
        "ca": "Selecciona primer una línia de la taula.", "es": "Selecciona primero una línea de la tabla.",
        "en": "Select a row in the table first.", "fr": "Sélectionnez d'abord une ligne du tableau.",
    },
    "common.confirm": {"ca": "Confirmar", "es": "Confirmar", "en": "Confirm", "fr": "Confirmer"},

    # -- Primer arrencada / migració ------------------------------------------- #
    "startup.title": {
        "ca": "Primer arrencada", "es": "Primer arranque", "en": "First launch", "fr": "Premier lancement",
    },
    "startup.text": {
        "ca": "Encara no s'ha trobat cap base de dades.\n\n"
        "Vols importar les dades des d'un fitxer Excel (SobrantsV4.74.xlsm) existent?",
        "es": "Todavía no se ha encontrado ninguna base de datos.\n\n"
        "¿Quieres importar los datos desde un archivo Excel (SobrantsV4.74.xlsm) existente?",
        "en": "No database has been found yet.\n\n"
        "Do you want to import the data from an existing Excel file (SobrantsV4.74.xlsm)?",
        "fr": "Aucune base de données n'a encore été trouvée.\n\n"
        "Voulez-vous importer les données depuis un fichier Excel existant (SobrantsV4.74.xlsm) ?",
    },
    "startup.pick_excel": {
        "ca": "Selecciona l'Excel a importar", "es": "Selecciona el Excel a importar",
        "en": "Select the Excel file to import", "fr": "Sélectionnez le fichier Excel à importer",
    },
    "startup.import_done.title": {
        "ca": "Importació completada", "es": "Importación completada",
        "en": "Import completed", "fr": "Importation terminée",
    },
    "startup.import_done.text": {
        "ca": "Dades importades:\n", "es": "Datos importados:\n",
        "en": "Imported data:\n", "fr": "Données importées :\n",
    },

    # -- Exportació / informes ------------------------------------------------- #
    "export.board.title": {
        "ca": "Tauler de sobrants", "es": "Tablero de sobrants",
        "en": "Sobrants board", "fr": "Tableau de sobrants",
    },
    "export.col.position": {"ca": "Pos.", "es": "Pos.", "en": "Pos.", "fr": "Pos."},
    "export.col.code": {"ca": "Núm.", "es": "Núm.", "en": "No.", "fr": "N°"},
    "export.col.material": {"ca": "Material", "es": "Material", "en": "Material", "fr": "Matériau"},
    "export.col.dimensions": {"ca": "Mides", "es": "Medidas", "en": "Dimensions", "fr": "Dimensions"},
    "export.col.notes": {"ca": "Notes", "es": "Notas", "en": "Notes", "fr": "Notes"},
    "export.desmagatzem.title": {
        "ca": "Desmagatzem", "es": "Desmagatzem", "en": "Desmagatzem", "fr": "Desmagatzem",
    },
    "export.col.quantity": {"ca": "Quant.", "es": "Cant.", "en": "Qty.", "fr": "Qté"},
    "export.col.cart": {"ca": "Carro/lot", "es": "Carro/lote", "en": "Cart/batch", "fr": "Chariot/lot"},
    "report.covered.title": {
        "ca": "MATERIALS TAPATS", "es": "MATERIALES TAPADOS",
        "en": "HIDDEN MATERIALS", "fr": "MATÉRIAUX MASQUÉS",
    },
    "report.covered.empty": {
        "ca": "(No s'han detectat materials tapats)",
        "es": "(No se han detectado materiales tapados)",
        "en": "(No hidden materials detected)",
        "fr": "(Aucun matériau masqué détecté)",
    },

    # -- Missatges de negoci (repository.py / rules.py) ------------------------ #
    "err.duplicate_material": {
        "ca": "Material duplicat a les posicions: {positions}",
        "es": "Material duplicado en las posiciones: {positions}",
        "en": "Duplicate material in positions: {positions}",
        "fr": "Matériau en double dans les positions : {positions}",
    },
    "err.invalid_material_code": {
        "ca": "Entrada incorrecta. Només s'admeten números entre 0 i 99999.",
        "es": "Entrada incorrecta. Solo se admiten números entre 0 y 99999.",
        "en": "Invalid entry. Only numbers between 0 and 99999 are allowed.",
        "fr": "Saisie incorrecte. Seuls les nombres entre 0 et 99999 sont autorisés.",
    },
    "err.position_full": {
        "ca": "MOVIMENT IMPOSIBLE: POSICIÓ PLENA", "es": "MOVIMIENTO IMPOSIBLE: POSICIÓN LLENA",
        "en": "IMPOSSIBLE MOVE: POSITION FULL", "fr": "DÉPLACEMENT IMPOSSIBLE : POSITION PLEINE",
    },
    "err.wrong_delete_order": {
        "ca": "ORDRE INCORRECTE: només es pot esborrar l'última peça de la posició.",
        "es": "ORDEN INCORRECTO: solo se puede borrar la última pieza de la posición.",
        "en": "WRONG ORDER: only the last piece of the position can be deleted.",
        "fr": "ORDRE INCORRECT : seule la dernière pièce de la position peut être supprimée.",
    },
    "err.cannot_move_to_self": {
        "ca": "NO ES POT MOURE ELL MATEIX", "es": "NO SE PUEDE MOVER A SÍ MISMA",
        "en": "CANNOT MOVE TO ITSELF", "fr": "IMPOSSIBLE DE DÉPLACER VERS ELLE-MÊME",
    },
    "err.no_piece_to_move": {
        "ca": "No hi ha cap peça per moure en aquesta posició.",
        "es": "No hay ninguna pieza para mover en esta posición.",
        "en": "There is no piece to move in this position.",
        "fr": "Il n'y a aucune pièce à déplacer dans cette position.",
    },
    "err.invalid_quantity": {
        "ca": "Només s'admeten quantitats entre 0 i 20.",
        "es": "Solo se admiten cantidades entre 0 y 20.",
        "en": "Only quantities between 0 and 20 are allowed.",
        "fr": "Seules les quantités entre 0 et 20 sont autorisées.",
    },
    "err.unregistered_material_text": {
        "ca": "Escriu un material no registrat.",
        "es": "Escribe un material no registrado.",
        "en": "Write an unregistered material.",
        "fr": "Écrivez un matériau non enregistré.",
    },
    "err.desmagatzem_row_not_found": {
        "ca": "Línia de desmagatzem no trobada.",
        "es": "Línea de desmagatzem no encontrada.",
        "en": "Desmagatzem row not found.",
        "fr": "Ligne de desmagatzem introuvable.",
    },
    "err.corrupt_slots": {
        "ca": "Els forats de la posició estan corromputs (han de ser consecutius des d'1)",
        "es": "Los huecos de la posición están corruptos (deben ser consecutivos desde 1)",
        "en": "The position's slots are corrupted (they must be consecutive starting from 1)",
        "fr": "Les emplacements de la position sont corrompus (ils doivent être consécutifs à partir de 1)",
    },
    "err.material_exists": {
        "ca": "Ja existeix un material amb el número {code}: «{description}».",
        "es": "Ya existe un material con el número {code}: «{description}».",
        "en": "A material with number {code} already exists: «{description}».",
        "fr": "Un matériau portant le numéro {code} existe déjà : « {description} ».",
    },
    "err.material_not_found": {
        "ca": "No existeix cap material amb el número {code}.",
        "es": "No existe ningún material con el número {code}.",
        "en": "There is no material with number {code}.",
        "fr": "Aucun matériau n'existe avec le numéro {code}.",
    },

    # -- Panell de detall de posició (incrustat sota el tauler) --------------- #
    "position.panel.placeholder": {
        "ca": "👆 Selecciona una posició a la taula per veure'n i editar-ne el detall.",
        "es": "👆 Selecciona una posición en la tabla para ver y editar su detalle.",
        "en": "👆 Select a position in the table to view and edit its detail.",
        "fr": "👆 Sélectionnez une position dans le tableau pour voir et modifier son détail.",
    },

    # -- Targetes de resultats de cerca ---------------------------------------- #
    "search.stat.matches": {
        "ca": "Coincidències", "es": "Coincidencias", "en": "Matches", "fr": "Correspondances",
    },
    "search.stat.oldest": {
        "ca": "Posició més antiga", "es": "Posición más antigua",
        "en": "Oldest position", "fr": "Position la plus ancienne",
    },
    "search.stat.desmagatzem": {
        "ca": "Unitats a Desmagatzem", "es": "Unidades en Desmagatzem",
        "en": "Units in Desmagatzem", "fr": "Unités dans Desmagatzem",
    },

    # -- Materials: alta protegida amb contrasenya ------------------------------ #
    "common.cancel": {"ca": "Cancel·lar", "es": "Cancelar", "en": "Cancel", "fr": "Annuler"},
    "common.done": {"ca": "Fet", "es": "Hecho", "en": "Done", "fr": "Terminé"},
    "common.add": {"ca": "Afegir", "es": "Añadir", "en": "Add", "fr": "Ajouter"},
    "materials.add_button": {
        "ca": "➕ Afegir material", "es": "➕ Añadir material",
        "en": "➕ Add material", "fr": "➕ Ajouter un matériau",
    },
    "materials.password.title": {
        "ca": "Contrasenya", "es": "Contraseña", "en": "Password", "fr": "Mot de passe",
    },
    "materials.password.label": {
        "ca": "Introdueix la contrasenya per afegir un material nou:",
        "es": "Introduce la contraseña para añadir un material nuevo:",
        "en": "Enter the password to add a new material:",
        "fr": "Entrez le mot de passe pour ajouter un nouveau matériau :",
    },
    "materials.password.wrong.title": {
        "ca": "Contrasenya incorrecta", "es": "Contraseña incorrecta",
        "en": "Wrong password", "fr": "Mot de passe incorrect",
    },
    "materials.password.wrong.text": {
        "ca": "La contrasenya introduïda no és correcta. No s'ha afegit cap material.",
        "es": "La contraseña introducida no es correcta. No se ha añadido ningún material.",
        "en": "The password entered is not correct. No material has been added.",
        "fr": "Le mot de passe saisi est incorrect. Aucun matériau n'a été ajouté.",
    },
    "materials.add_dialog.title": {
        "ca": "Afegir material nou", "es": "Añadir material nuevo",
        "en": "Add new material", "fr": "Ajouter un nouveau matériau",
    },
    "materials.add_dialog.code": {
        "ca": "Núm. material:", "es": "Núm. material:", "en": "Material no.:", "fr": "N° matériau :",
    },
    "materials.add_dialog.description": {
        "ca": "Descripció:", "es": "Descripción:", "en": "Description:", "fr": "Description :",
    },
    "materials.add.missing_fields": {
        "ca": "Cal indicar un número de material i una descripció.",
        "es": "Hay que indicar un número de material y una descripción.",
        "en": "A material number and a description are required.",
        "fr": "Un numéro de matériau et une description sont requis.",
    },
    "materials.add.success": {
        "ca": "Material afegit correctament.", "es": "Material añadido correctamente.",
        "en": "Material added successfully.", "fr": "Matériau ajouté avec succès.",
    },
    "materials.add.confirm_overwrite": {
        "ca": "Ja existeix un material amb el número {code} («{description}»). Vols actualitzar-ne la descripció?",
        "es": "Ya existe un material con el número {code} («{description}»). ¿Quieres actualizar su descripción?",
        "en": "A material with number {code} already exists («{description}»). "
        "Do you want to update its description?",
        "fr": "Un matériau portant le numéro {code} existe déjà (« {description} »). "
        "Voulez-vous mettre à jour sa description ?",
    },

    # -- Materials: baixa protegida amb contrasenya (mateix mecanisme que l'alta) -- #
    "materials.delete_button": {
        "ca": "🗑️ Esborrar material", "es": "🗑️ Borrar material",
        "en": "🗑️ Delete material", "fr": "🗑️ Supprimer le matériau",
    },
    "materials.password.label_delete": {
        "ca": "Introdueix la contrasenya per esborrar aquest material:",
        "es": "Introduce la contraseña para borrar este material:",
        "en": "Enter the password to delete this material:",
        "fr": "Entrez le mot de passe pour supprimer ce matériau :",
    },
    "materials.password.wrong.text_delete": {
        "ca": "La contrasenya introduïda no és correcta. No s'ha esborrat cap material.",
        "es": "La contraseña introducida no es correcta. No se ha borrado ningún material.",
        "en": "The password entered is not correct. No material has been deleted.",
        "fr": "Le mot de passe saisi est incorrect. Aucun matériau n'a été supprimé.",
    },
    "materials.delete.no_selection.title": {
        "ca": "Cap material seleccionat", "es": "Ningún material seleccionado",
        "en": "No material selected", "fr": "Aucun matériau sélectionné",
    },
    "materials.delete.no_selection.text": {
        "ca": "Selecciona primer una fila de la taula per esborrar-ne el material.",
        "es": "Selecciona primero una fila de la tabla para borrar su material.",
        "en": "First select a row in the table to delete its material.",
        "fr": "Sélectionnez d'abord une ligne du tableau pour supprimer son matériau.",
    },
    "materials.delete.confirm.title": {
        "ca": "Esborrar material", "es": "Borrar material",
        "en": "Delete material", "fr": "Supprimer le matériau",
    },
    "materials.delete.confirm.text": {
        "ca": "Segur que vols esborrar el material {code} («{description}») del catàleg? "
        "Aquesta acció no es pot desfer.",
        "es": "¿Seguro que quieres borrar el material {code} («{description}») del catálogo? "
        "Esta acción no se puede deshacer.",
        "en": "Are you sure you want to delete material {code} («{description}») from the catalog? "
        "This action cannot be undone.",
        "fr": "Voulez-vous vraiment supprimer le matériau {code} (« {description} ») du catalogue ? "
        "Cette action est irréversible.",
    },
    "materials.delete.success": {
        "ca": "Material esborrat correctament.", "es": "Material borrado correctamente.",
        "en": "Material deleted successfully.", "fr": "Matériau supprimé avec succès.",
    },
}
