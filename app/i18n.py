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

from pathlib import Path

from app import settings

DEFAULT_LANG = "ca"
LANGS = {"ca": "Català", "es": "Castellano", "en": "English", "fr": "Français"}

_state = {"lang": DEFAULT_LANG}
_settings_path: Path | None = None


def init_settings_path(data_dir: Path) -> None:
    """Crida's una vegada a l'arrencada amb la carpeta de dades de l'app.

    L'idioma comparteix fitxer amb la resta de preferències (contrasenya,
    interval de còpies): es llegeix i s'escriu a través d'`app.settings`,
    que hi fa un llegir-modificar-desar i no se les emporta per davant.
    """
    global _settings_path
    settings.init(data_dir)
    _settings_path = settings.path()
    lang = settings.get("language")
    if lang in LANGS:
        _state["lang"] = lang


def get_language() -> str:
    return _state["lang"]


def set_language(lang: str) -> None:
    if lang not in LANGS:
        raise ValueError(f"Idioma desconegut: {lang}")
    _state["lang"] = lang
    if _settings_path is not None:
        settings.set_value("language", lang)


def format_number(value: int) -> str:
    """El número amb els separadors de milers de l'idioma de l'aplicació
    (1.248 en català, castellà i francès; 1,248 en anglès). Viu aquí, amb
    la resta de coses que depenen de l'idioma, perquè tothom qui ensenyi
    un total el pinti igual."""
    from PySide6.QtCore import QLocale

    return QLocale(get_language()).toString(value)


def t(key: str, **kwargs) -> str:
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key  # clau sense traduir; visible expressament per detectar-ho
    text = entry.get(_state["lang"]) or entry.get(DEFAULT_LANG) or key
    return text.format(**kwargs) if kwargs else text


TRANSLATIONS: dict[str, dict[str, str]] = {
    # -- Finestra principal --------------------------------------------- #
    # El nom de l'aplicació. És un nom propi: igual en els 4 idiomes, i per
    # això no hi ha cap descripció al costat (abans hi deia "— control
    # d'inventari"): el títol de la finestra és el nom, i prou.
    "app.title": {
        "ca": "Sobrants by Luvnus",
        "es": "Sobrants by Luvnus",
        "en": "Sobrants by Luvnus",
        "fr": "Sobrants by Luvnus",
    },
    "app.language": {"ca": "Idioma", "es": "Idioma", "en": "Language", "fr": "Langue"},
    "menu.file": {"ca": "&Fitxer", "es": "&Archivo", "en": "&File", "fr": "&Fichier"},
    "menu.backup_now": {
        "ca": "Còpia de seguretat ara",
        "es": "Copia de seguridad ahora",
        "en": "Backup now",
        "fr": "Sauvegarder maintenant",
    },
    "menu.print_board": {
        "ca": "Imprimir tauler", "es": "Imprimir tablero",
        "en": "Print board", "fr": "Imprimer le tableau",
    },
    "menu.print_desmagatzem": {
        "ca": "Imprimir desmagatzem", "es": "Imprimir desmagatzem",
        "en": "Print desmagatzem", "fr": "Imprimer desmagatzem",
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
        "ca": "Sobre Sobrants by Luvnus", "es": "Sobre Sobrants by Luvnus",
        "en": "About Sobrants by Luvnus", "fr": "À propos de Sobrants by Luvnus",
    },
    "about.creator": {
        "ca": "Creador: <a href=\"{url}\">{url}</a>",
        "es": "Creador: <a href=\"{url}\">{url}</a>",
        "en": "Creator: <a href=\"{url}\">{url}</a>",
        "fr": "Créateur : <a href=\"{url}\">{url}</a>",
    },
    # El nom "Raül Vives Morros" no es tradueix mai, en cap idioma.
    "about.original_idea": {
        "ca": "Idea original de Raül V.",
        "es": "Idea original de Raül V.",
        "en": "Original idea by Raül V.",
        "fr": "Idée originale de Raül V.",
    },
    "action.backup": {
        "ca": "Còpia de\nseguretat",
        "es": "Copia de\nseguridad",
        "en": "Create\nbackup",
        "fr": "Créer une\nsauvegarde",
    },
    "action.print_board": {
        "ca": "Imprimir tauler", "es": "Imprimir tablero",
        "en": "Print board", "fr": "Imprimer le tableau",
    },
    "action.print_desmagatzem": {
        "ca": "Imprimir desmagatzem", "es": "Imprimir desmagatzem",
        "en": "Print desmagatzem", "fr": "Imprimer desmagatzem",
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
    "tab.statistics": {
        "ca": "Estadístiques", "es": "Estadísticas",
        "en": "Statistics", "fr": "Statistiques",
    },

    # -- Tauler ------------------------------------------------------------ #
    "board.piece_count": {
        "ca": "Hi ha {count} peces", "es": "Hay {count} piezas",
        "en": "There are {count} pieces", "fr": "Il y a {count} pièces",
    },
    # Amb una sola peça la frase canvia en els 4 idiomes ("Hi ha 1 peces"
    # estava mal dit). És l'únic comptador que ho necessita: els altres
    # ensenyen el número entre parèntesis, sense fer frase.
    "board.piece_count_one": {
        "ca": "Hi ha 1 peça", "es": "Hay 1 pieza",
        "en": "There is 1 piece", "fr": "Il y a 1 pièce",
    },
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
    "board.search_result_desmagatzem": {
        "ca": " · {qty} ud(s) a Desmagatzem",
        "es": " · {qty} ud(s) en Desmagatzem",
        "en": " · {qty} unit(s) in Desmagatzem",
        "fr": " · {qty} unité(s) dans Desmagatzem",
    },

    # -- Diàleg de cerca ---------------------------------------------------- #
    "search.code_label": {
        "ca": "Per núm.:", "es": "Por núm.:",
        "en": "By no.:", "fr": "Par n° :",
    },
    "search.code_placeholder": {
        "ca": "Núm. de material exacte", "es": "Núm. de material exacto",
        "en": "Exact material no.", "fr": "N° de matériau exact",
    },
    "search.desc_label": {
        "ca": "Per material:", "es": "Por material:",
        "en": "By material:", "fr": "Par matériau :",
    },
    "search.desc_placeholder": {
        "ca": "Text parcial a la descripció", "es": "Texto parcial en la descripción",
        "en": "Partial text in the description", "fr": "Texte partiel dans la description",
    },
    "search.notes_label": {
        "ca": "Per notes:", "es": "Por notas:",
        "en": "By notes:", "fr": "Par notes :",
    },
    "search.notes_placeholder": {
        "ca": "Text parcial a les notes", "es": "Texto parcial en las notas",
        "en": "Partial text in the notes", "fr": "Texte partiel dans les notes",
    },
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
    "position.move_button": {
        "ca": "Moure peça visible a posició...", "es": "Mover pieza visible a posición...",
        "en": "Move visible piece to position...", "fr": "Déplacer la pièce visible vers la position...",
    },
    "position.move.ask.title": {
        "ca": "A quina posició?", "es": "¿A qué posición?",
        "en": "To which position?", "fr": "Vers quelle position ?",
    },
    "position.move.ask.label": {
        "ca": "Posició de destí (1-61) per a la peça de la posició {from_pos}:",
        "es": "Posición de destino (1-61) para la pieza de la posición {from_pos}:",
        "en": "Destination position (1-61) for the piece in position {from_pos}:",
        "fr": "Position de destination (1-61) pour la pièce de la position {from_pos} :",
    },
    "position.move.only_last.tooltip": {
        "ca": "Només es pot moure l'última peça de la posició: tria-la a la taula.",
        "es": "Solo se puede mover la última pieza de la posición: selecciónala en la tabla.",
        "en": "Only the last piece of the position can be moved: select it in the table.",
        "fr": "Seule la dernière pièce de la position peut être déplacée : sélectionnez-la dans le tableau.",
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
    "position.invalid_code.title": {
        "ca": "Núm. no vàlid", "es": "Núm. no válido",
        "en": "Invalid no.", "fr": "N° non valide",
    },
    "position.invalid_code.text": {
        "ca": "«{code}» no és un núm. de material vàlid: només s'hi admeten números positius.",
        "es": "«{code}» no es un núm. de material válido: solo se admiten números positivos.",
        "en": "«{code}» is not a valid material no.: only positive numbers are allowed.",
        "fr": "« {code} » n'est pas un n° de matériau valide : seuls les nombres positifs sont admis.",
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
    "position.delete_button": {
        "ca": "Esborrar", "es": "Borrar", "en": "Delete", "fr": "Supprimer",
    },
    "position.delete_action": {
        "ca": "Esborrar aquesta peça", "es": "Borrar esta pieza",
        "en": "Delete this piece", "fr": "Supprimer cette pièce",
    },
    "position.only_last.title": {
        "ca": "Només l'última peça", "es": "Solo la última pieza",
        "en": "Only the last piece", "fr": "Seulement la dernière pièce",
    },
    "position.only_last.text": {
        "ca": "Només es pot esborrar l'última peça de la posició. "
              "Selecciona-la (l'última fila amb dades) per poder esborrar-la.",
        "es": "Solo se puede borrar la última pieza de la posición. "
              "Selecciónala (la última fila con datos) para poder borrarla.",
        "en": "Only the last piece of the position can be deleted. "
              "Select it (the last row with data) to delete it.",
        "fr": "Seule la dernière pièce de la position peut être supprimée. "
              "Sélectionnez-la (la dernière ligne remplie) pour la supprimer.",
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
    "desmagatzem.col.cart": {"ca": "Notes", "es": "Notas", "en": "Notes", "fr": "Notes"},
    "desmagatzem.col.datetime": {"ca": "Data/hora", "es": "Fecha/hora", "en": "Date/time", "fr": "Date/heure"},
    "desmagatzem.confirm.quantities": {
        "ca": "La quantitat actual és <b>{current}</b> i la nova serà <b>{new}</b>.<br><br>",
        "es": "La cantidad actual es <b>{current}</b> y la nueva será <b>{new}</b>.<br><br>",
        "en": "The current quantity is <b>{current}</b> and the new one will be <b>{new}</b>.<br><br>",
        "fr": "La quantité actuelle est <b>{current}</b> et la nouvelle sera <b>{new}</b>.<br><br>",
    },
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
        "ca": "Nova entrada", "es": "Nueva entrada", "en": "New entry", "fr": "Nouvelle entrée",
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
        "ca": "Notes:", "es": "Notas:", "en": "Notes:", "fr": "Notes :",
    },
    "desmagatzem.cart_placeholder": {
        "ca": "Observacions opcionals", "es": "Observaciones opcionales",
        "en": "Optional notes", "fr": "Remarques facultatives",
    },
    "desmagatzem.add_button": {
        "ca": "Registrar entrada", "es": "Registrar entrada",
        "en": "Register entry", "fr": "Enregistrer l'entrée",
    },
    "desmagatzem.piece_count": {
        "ca": "Peces desmagatzem ({count})", "es": "Piezas desmagatzem ({count})",
        "en": "Desmagatzem pieces ({count})", "fr": "Pièces desmagatzem ({count})",
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
    "desmagatzem.editable_hint": {
        "ca": "Es pot editar: clica-hi i escriu (Retorn desa, Escapada cancel·la)",
        "es": "Se puede editar: haz clic y escribe (Retorno guarda, Escape cancela)",
        "en": "Editable: click and type (Enter saves, Escape cancels)",
        "fr": "Modifiable : cliquez et écrivez (Entrée enregistre, Échap annule)",
    },
    "desmagatzem.material_not_found.title": {
        "ca": "Material no trobat", "es": "Material no encontrado",
        "en": "Material not found", "fr": "Matériau introuvable",
    },
    "desmagatzem.material_not_found.text": {
        "ca": "El núm. {code} no existeix al catàleg de materials.\n\n"
              "Corregeix el número, o fes servir el núm. 1 si el material no està registrat.",
        "es": "El núm. {code} no existe en el catálogo de materiales.\n\n"
              "Corrige el número, o usa el núm. 1 si el material no está registrado.",
        "en": "Material no. {code} is not in the catalog.\n\n"
              "Correct the number, or use no. 1 for an unregistered material.",
        "fr": "Le n° {code} n'existe pas dans le catalogue des matériaux.\n\n"
              "Corrigez le numéro, ou utilisez le n° 1 pour un matériau non enregistré.",
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
    "export.col.position": {"ca": "Pos.", "es": "Pos.", "en": "Pos.", "fr": "Pos."},
    "export.col.code": {"ca": "Núm.", "es": "Núm.", "en": "No.", "fr": "N°"},
    "export.col.material": {"ca": "Material", "es": "Material", "en": "Material", "fr": "Matériau"},
    "export.col.dimensions": {"ca": "Mides", "es": "Medidas", "en": "Dimensions", "fr": "Dimensions"},
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
    "report.covered.filename": {
        "ca": "Materials tapats.txt", "es": "Materiales tapados.txt",
        "en": "Hidden materials.txt", "fr": "Matériaux masqués.txt",
    },

    # -- Missatges de negoci (repository.py / rules.py) ------------------------ #
    "err.duplicate_material": {
        "ca": "Material duplicat a les posicions: {positions}",
        "es": "Material duplicado en las posiciones: {positions}",
        "en": "Duplicate material in positions: {positions}",
        "fr": "Matériau en double dans les positions : {positions}",
    },
    "err.invalid_material_code": {
        "ca": "Entrada incorrecta. Només s'admeten números entre 0 i 999999.",
        "es": "Entrada incorrecta. Solo se admiten números entre 0 y 999999.",
        "en": "Invalid entry. Only numbers between 0 and 999999 are allowed.",
        "fr": "Saisie incorrecte. Seuls les nombres entre 0 et 999999 sont autorisés.",
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
        "ca": "Selecciona una posició a la taula per veure'n i editar-ne el detall.",
        "es": "Selecciona una posición en la tabla para ver y editar su detalle.",
        "en": "Select a position in the table to view and edit its detail.",
        "fr": "Sélectionnez une position dans le tableau pour voir et modifier son détail.",
    },

    # -- Targetes de resultats de cerca ---------------------------------------- #

    # -- Materials: alta protegida amb contrasenya ------------------------------ #
    "common.cancel": {"ca": "Cancel·lar", "es": "Cancelar", "en": "Cancel", "fr": "Annuler"},
    "common.done": {"ca": "Fet", "es": "Hecho", "en": "Done", "fr": "Terminé"},
    "common.add": {"ca": "Afegir", "es": "Añadir", "en": "Add", "fr": "Ajouter"},
    "materials.add_button": {
        "ca": "Afegir material", "es": "Añadir material",
        "en": "Add material", "fr": "Ajouter un matériau",
    },
    "menu.import": {
        "ca": "&Importar", "es": "&Importar", "en": "&Import", "fr": "&Importer",
    },
    "menu.import_excel": {
        "ca": "Importar d'Excel...", "es": "Importar de Excel...",
        "en": "Import from Excel...", "fr": "Importer depuis Excel...",
    },
    "menu.import_database": {
        "ca": "Importar de base de dades...", "es": "Importar de base de datos...",
        "en": "Import from database...", "fr": "Importer depuis une base de données...",
    },
    "import.excel.error.title": {
        "ca": "No s'ha pogut importar l'Excel", "es": "No se ha podido importar el Excel",
        "en": "Could not import the Excel file", "fr": "Impossible d'importer le fichier Excel",
    },
    "import.error.text": {
        "ca": "No s'ha canviat res.\n\n{error}",
        "es": "No se ha cambiado nada.\n\n{error}",
        "en": "Nothing has been changed.\n\n{error}",
        "fr": "Rien n'a été modifié.\n\n{error}",
    },
    "import.db.pick": {
        "ca": "Tria la base de dades a importar (.db)",
        "es": "Elige la base de datos a importar (.db)",
        "en": "Choose the database to import (.db)",
        "fr": "Choisissez la base de données à importer (.db)",
    },
    "import.db.error.title": {
        "ca": "No s'ha pogut importar", "es": "No se ha podido importar",
        "en": "Could not import", "fr": "Impossible d'importer",
    },
    "import.db.invalid": {
        "ca": "Aquest fitxer no és una base de dades de Sobrants (o està malmès).\n\nDetall: {detail}",
        "es": "Este archivo no es una base de datos de Sobrants (o está dañado).\n\nDetalle: {detail}",
        "en": "This file is not a Sobrants database (or it is damaged).\n\nDetail: {detail}",
        "fr": "Ce fichier n'est pas une base de données Sobrants (ou il est endommagé).\n\nDétail : {detail}",
    },
    "import.db.same_file": {
        "ca": "Aquesta ja és la base de dades que s'està fent servir.",
        "es": "Esta ya es la base de datos que se está usando.",
        "en": "That is already the database in use.",
        "fr": "C'est déjà la base de données utilisée.",
    },
    "import.db.confirm.title": {
        "ca": "Importar la base de dades", "es": "Importar la base de datos",
        "en": "Import the database", "fr": "Importer la base de données",
    },
    "import.db.confirm.text": {
        "ca": "El fitxer conté:\n{summary}\n\nSe substituiran TOTES les dades actuals. Abans se'n farà una còpia de seguretat. Continuar?",
        "es": "El archivo contiene:\n{summary}\n\nSe sustituirán TODOS los datos actuales. Antes se hará una copia de seguridad. ¿Continuar?",
        "en": "The file contains:\n{summary}\n\nALL current data will be replaced. A backup will be made first. Continue?",
        "fr": "Le fichier contient :\n{summary}\n\nTOUTES les données actuelles seront remplacées. Une sauvegarde sera faite avant. Continuer ?",
    },
    "import.db.done.title": {
        "ca": "Base de dades importada", "es": "Base de datos importada",
        "en": "Database imported", "fr": "Base de données importée",
    },
    "import.db.done.text": {
        "ca": "S'han importat:\n{summary}\n\nCòpia de les dades anteriors: {backup}",
        "es": "Se han importado:\n{summary}\n\nCopia de los datos anteriores: {backup}",
        "en": "Imported:\n{summary}\n\nBackup of the previous data: {backup}",
        "fr": "Importé :\n{summary}\n\nSauvegarde des données précédentes : {backup}",
    },
    "import.db.reloaded": {
        "ca": "L'aplicació ja treballa amb les dades importades.",
        "es": "La aplicación ya trabaja con los datos importados.",
        "en": "The application is now working with the imported data.",
        "fr": "L'application travaille maintenant avec les données importées.",
    },
    "print.dialog.title": {
        "ca": "Imprimir", "es": "Imprimir", "en": "Print", "fr": "Imprimer",
    },
    "print.error.title": {
        "ca": "No s'ha pogut imprimir", "es": "No se ha podido imprimir",
        "en": "Could not print", "fr": "Impossible d'imprimer",
    },
    "print.error.text": {
        "ca": "No s'ha pogut preparar la pàgina per a la impressora.",
        "es": "No se ha podido preparar la página para la impresora.",
        "en": "The page could not be prepared for the printer.",
        "fr": "La page n'a pas pu être préparée pour l'imprimante.",
    },
    "print.error.detail": {
        "ca": "No s'ha imprès res.\n\n{error}",
        "es": "No se ha impreso nada.\n\n{error}",
        "en": "Nothing has been printed.\n\n{error}",
        "fr": "Rien n'a été imprimé.\n\n{error}",
    },
    "print.sent": {
        "ca": "Enviat a la impressora.", "es": "Enviado a la impresora.",
        "en": "Sent to the printer.", "fr": "Envoyé à l'imprimante.",
    },
    "position.confirm_move.title": {
        "ca": "Moure la peça", "es": "Mover la pieza",
        "en": "Move the piece", "fr": "Déplacer la pièce",
    },
    "position.confirm_move.text": {
        "ca": "Segur que vols moure aquesta peça de la posició {from_pos} a la {to_pos}?\n\nNúm. {code} — {desc}",
        "es": "¿Seguro que quieres mover esta pieza de la posición {from_pos} a la {to_pos}?\n\nNúm. {code} — {desc}",
        "en": "Are you sure you want to move this piece from position {from_pos} to {to_pos}?\n\nNo. {code} — {desc}",
        "fr": "Voulez-vous vraiment déplacer cette pièce de la position {from_pos} vers {to_pos} ?\n\nN° {code} — {desc}",
    },
    "print.report.subtitle": {
        "ca": "{count} línies — {datetime}", "es": "{count} líneas — {datetime}",
        "en": "{count} rows — {datetime}", "fr": "{count} lignes — {datetime}",
    },
    "backup.settings.title": {
        "ca": "Configuració de les còpies de seguretat",
        "es": "Configuración de las copias de seguridad",
        "en": "Backup settings", "fr": "Configuration des sauvegardes",
    },
    "backup.settings.folder": {
        "ca": "Carpeta de còpies:", "es": "Carpeta de copias:",
        "en": "Backups folder:", "fr": "Dossier des sauvegardes :",
    },
    "backup.settings.pick_folder": {
        "ca": "Seleccionar carpeta", "es": "Seleccionar carpeta",
        "en": "Choose folder", "fr": "Choisir le dossier",
    },
    "backup.settings.name": {
        "ca": "Nom de les còpies:", "es": "Nombre de las copias:",
        "en": "Backup name:", "fr": "Nom des sauvegardes :",
    },
    "backup.settings.example": {
        "ca": "Quedaran com: {name}", "es": "Quedarán como: {name}",
        "en": "They will be named: {name}", "fr": "Elles seront nommées : {name}",
    },
    "backup.settings.interval": {
        "ca": "Cada quantes hores:", "es": "Cada cuántas horas:",
        "en": "How often:", "fr": "Fréquence :",
    },
    "backup.settings.keep": {
        "ca": "Còpies que es guarden:", "es": "Copias que se guardan:",
        "en": "Backups to keep:", "fr": "Sauvegardes à conserver :",
    },
    "backup.settings.keep_warning.title": {
        "ca": "Hi ha més còpies que el límit", "es": "Hay más copias que el límite",
        "en": "There are more backups than the limit",
        "fr": "Il y a plus de sauvegardes que la limite",
    },
    "backup.settings.keep_warning.text": {
        "ca": "Ara hi ha {existing} còpies i el límit nou és {keep}.\n\nNo se n'esborra cap ara: les més antigues aniran caient a mesura que se'n facin de noves.",
        "es": "Ahora hay {existing} copias y el nuevo límite es {keep}.\n\nNo se borra ninguna ahora: las más antiguas irán cayendo a medida que se hagan nuevas.",
        "en": "There are {existing} backups now and the new limit is {keep}.\n\nNone is deleted now: the oldest ones will be removed as new backups are made.",
        "fr": "Il y a {existing} sauvegardes et la nouvelle limite est {keep}.\n\nAucune n'est supprimée maintenant : les plus anciennes partiront au fur et à mesure.",
    },
    "backup.settings.usb": {
        "ca": "USB:", "es": "USB:", "en": "USB:", "fr": "USB :",
    },
    "backup.settings.usb_found": {
        "ca": "Connectat ({drives}): se n'hi farà una segona còpia",
        "es": "Conectado ({drives}): se hará una segunda copia",
        "en": "Connected ({drives}): a second copy will be made there",
        "fr": "Connecté ({drives}) : une deuxième copie y sera faite",
    },
    "backup.settings.usb_missing": {
        "ca": "Cap USB connectat: la còpia es farà només a la carpeta",
        "es": "Ningún USB conectado: la copia se hará solo en la carpeta",
        "en": "No USB connected: the backup will only go to the folder",
        "fr": "Aucun USB connecté : la sauvegarde ira seulement dans le dossier",
    },
    "backup.settings.folder_error.title": {
        "ca": "Carpeta no disponible", "es": "Carpeta no disponible",
        "en": "Folder not available", "fr": "Dossier non disponible",
    },
    "backup.settings.folder_error.text": {
        "ca": "No s'ha pogut fer servir «{folder}». Tria'n una altra.\n\n{error}",
        "es": "No se ha podido usar «{folder}». Elige otra.\n\n{error}",
        "en": "«{folder}» could not be used. Choose another one.\n\n{error}",
        "fr": "« {folder} » n'a pas pu être utilisé. Choisissez-en un autre.\n\n{error}",
    },
    "backup.settings.done": {
        "ca": "Les còpies aniran a: {folder}", "es": "Las copias irán a: {folder}",
        "en": "Backups will go to: {folder}", "fr": "Les sauvegardes iront vers : {folder}",
    },
    "backup.usb.pick.title": {
        "ca": "Quin USB?", "es": "¿Qué USB?", "en": "Which USB?", "fr": "Quel USB ?",
    },
    "backup.usb.pick.text": {
        "ca": "Hi ha més d'un USB connectat. On vols la segona còpia?",
        "es": "Hay más de un USB conectado. ¿Dónde quieres la segunda copia?",
        "en": "More than one USB is connected. Where do you want the second copy?",
        "fr": "Plusieurs USB sont connectés. Où voulez-vous la deuxième copie ?",
    },
    "dialog.backup.text_usb": {
        "ca": "Còpia feta per duplicat:\n  Carpeta: {path}\n  USB: {usb}",
        "es": "Copia hecha por duplicado:\n  Carpeta: {path}\n  USB: {usb}",
        "en": "Backup made twice:\n  Folder: {path}\n  USB: {usb}",
        "fr": "Sauvegarde faite en double :\n  Dossier : {path}\n  USB : {usb}",
    },
    "dialog.backup.text_usb_failed": {
        "ca": "Còpia feta NOMÉS a la carpeta:\n{path}\n\nNo s'ha pogut copiar al USB: {error}",
        "es": "Copia hecha SOLO en la carpeta:\n{path}\n\nNo se ha podido copiar al USB: {error}",
        "en": "Backup made ONLY in the folder:\n{path}\n\nIt could not be copied to the USB: {error}",
        "fr": "Sauvegarde faite SEULEMENT dans le dossier :\n{path}\n\nImpossible de copier sur l'USB : {error}",
    },
    "dialog.backup.error.title": {
        "ca": "No s'ha pogut fer la còpia", "es": "No se ha podido hacer la copia",
        "en": "The backup could not be made", "fr": "La sauvegarde n'a pas pu être faite",
    },
    "dialog.backup.error.text": {
        "ca": "No s'ha desat cap còpia.\n\n{error}",
        "es": "No se ha guardado ninguna copia.\n\n{error}",
        "en": "No backup has been saved.\n\n{error}",
        "fr": "Aucune sauvegarde n'a été enregistrée.\n\n{error}",
    },
    "menu.backups": {
        "ca": "&Còpies de seguretat", "es": "&Copias de seguridad",
        "en": "&Backups", "fr": "&Sauvegardes",
    },
    "menu.backup_interval": {
        "ca": "Configuració...", "es": "Configuración...",
        "en": "Settings...", "fr": "Configuration...",
    },
    "menu.change_password": {
        "ca": "Canviar contrasenya...", "es": "Cambiar contraseña...",
        "en": "Change password...", "fr": "Changer le mot de passe...",
    },
    "password.label_backup": {
        "ca": "Introdueix la contrasenya per fer una còpia de seguretat:",
        "es": "Introduce la contraseña para hacer una copia de seguridad:",
        "en": "Enter the password to make a backup:",
        "fr": "Entrez le mot de passe pour faire une sauvegarde :",
    },
    "password.wrong.text_backup": {
        "ca": "La contrasenya introduïda no és correcta. No s'ha fet cap còpia de seguretat.",
        "es": "La contraseña introducida no es correcta. No se ha hecho ninguna copia de seguridad.",
        "en": "The password entered is not correct. No backup has been made.",
        "fr": "Le mot de passe saisi est incorrect. Aucune sauvegarde n'a été faite.",
    },
    "password.label_interval": {
        "ca": "Introdueix la contrasenya per canviar cada quantes hores es fa la còpia:",
        "es": "Introduce la contraseña para cambiar cada cuántas horas se hace la copia:",
        "en": "Enter the password to change how often the backup is made:",
        "fr": "Entrez le mot de passe pour changer la fréquence des sauvegardes :",
    },
    "password.label_import": {
        "ca": "Introdueix la contrasenya per importar dades:",
        "es": "Introduce la contraseña para importar datos:",
        "en": "Enter the password to import data:",
        "fr": "Entrez le mot de passe pour importer des données :",
    },
    "password.wrong.text_import": {
        "ca": "La contrasenya introduïda no és correcta. No s'ha importat res.",
        "es": "La contraseña introducida no es correcta. No se ha importado nada.",
        "en": "The password entered is not correct. Nothing has been imported.",
        "fr": "Le mot de passe saisi est incorrect. Rien n'a été importé.",
    },
    "password.label_change": {
        "ca": "Introdueix la contrasenya actual:", "es": "Introduce la contraseña actual:",
        "en": "Enter the current password:", "fr": "Entrez le mot de passe actuel :",
    },
    "password.wrong.text_generic": {
        "ca": "La contrasenya introduïda no és correcta. No s'ha canviat res.",
        "es": "La contraseña introducida no es correcta. No se ha cambiado nada.",
        "en": "The password entered is not correct. Nothing has been changed.",
        "fr": "Le mot de passe saisi est incorrect. Rien n'a été modifié.",
    },
    "password.change.title": {
        "ca": "Canviar contrasenya", "es": "Cambiar contraseña",
        "en": "Change password", "fr": "Changer le mot de passe",
    },
    "password.change.new": {
        "ca": "Nova contrasenya:", "es": "Nueva contraseña:",
        "en": "New password:", "fr": "Nouveau mot de passe :",
    },
    "password.change.repeat": {
        "ca": "Repeteix la nova contrasenya:", "es": "Repite la nueva contraseña:",
        "en": "Repeat the new password:", "fr": "Répétez le nouveau mot de passe :",
    },
    "password.change.mismatch.title": {
        "ca": "No coincideixen", "es": "No coinciden",
        "en": "They do not match", "fr": "Elles ne correspondent pas",
    },
    "password.change.mismatch.text": {
        "ca": "Les dues contrasenyes no són iguals. No s'ha canviat res.",
        "es": "Las dos contraseñas no son iguales. No se ha cambiado nada.",
        "en": "The two passwords are not the same. Nothing has been changed.",
        "fr": "Les deux mots de passe ne sont pas identiques. Rien n'a été modifié.",
    },
    "password.change.done.title": {
        "ca": "Contrasenya canviada", "es": "Contraseña cambiada",
        "en": "Password changed", "fr": "Mot de passe changé",
    },
    "password.change.done.text": {
        "ca": "A partir d'ara, totes les accions protegides demanaran la contrasenya nova.",
        "es": "A partir de ahora, todas las acciones protegidas pedirán la contraseña nueva.",
        "en": "From now on, every protected action will ask for the new password.",
        "fr": "Désormais, toutes les actions protégées demanderont le nouveau mot de passe.",
    },
    "usb.connected": {
        "ca": "USB connectat: {drives}", "es": "USB conectado: {drives}",
        "en": "USB connected: {drives}", "fr": "USB connecté : {drives}",
    },
    "usb.disconnected": {
        "ca": "Cap USB connectat", "es": "Ningún USB conectado",
        "en": "No USB connected", "fr": "Aucun USB connecté",
    },
    "materials.add.confirm_overwrite.title": {
        "ca": "El material ja existeix", "es": "El material ya existe",
        "en": "The material already exists", "fr": "Le matériau existe déjà",
    },
    "common.yes": {"ca": "Sí", "es": "Sí", "en": "Yes", "fr": "Oui"},
    "common.no": {"ca": "No", "es": "No", "en": "No", "fr": "Non"},
    "common.ok": {"ca": "Acceptar", "es": "Aceptar", "en": "OK", "fr": "Accepter"},
    "historic.count": {
        "ca": "{count} moviments", "es": "{count} movimientos",
        "en": "{count} movements", "fr": "{count} mouvements",
    },
    "historic.export_excel": {
        "ca": "Exporta Excel", "es": "Exporta Excel",
        "en": "Export to Excel", "fr": "Exporter en Excel",
    },
    "historic.export.title": {
        "ca": "Exportar l'històric a Excel", "es": "Exportar el histórico a Excel",
        "en": "Export the history to Excel", "fr": "Exporter l'historique en Excel",
    },
    "historic.export.done": {
        "ca": "S'han exportat {count} moviments a:\n{path}",
        "es": "Se han exportado {count} movimientos a:\n{path}",
        "en": "{count} movements exported to:\n{path}",
        "fr": "{count} mouvements exportés vers :\n{path}",
    },
    "historic.export.error.title": {
        "ca": "No s'ha pogut exportar", "es": "No se ha podido exportar",
        "en": "Could not export", "fr": "Impossible d'exporter",
    },
    "historic.export.error.text": {
        "ca": "No s'ha pogut desar el fitxer. L'històric no s'ha tocat.\n\n{error}",
        "es": "No se ha podido guardar el archivo. El histórico no se ha tocado.\n\n{error}",
        "en": "The file could not be saved. The history has not been touched.\n\n{error}",
        "fr": "Le fichier n'a pas pu être enregistré. L'historique n'a pas été touché.\n\n{error}",
    },
    "historic.clear": {
        "ca": "Netejar", "es": "Limpiar", "en": "Clear", "fr": "Nettoyer",
    },
    "historic.clear.password": {
        "ca": "Introdueix la contrasenya d'administrador per netejar l'històric:",
        "es": "Introduce la contraseña de administrador para limpiar el histórico:",
        "en": "Enter the administrator password to clear the history:",
        "fr": "Entrez le mot de passe administrateur pour nettoyer l'historique :",
    },
    "historic.clear.confirm.title": {
        "ca": "Netejar l'històric", "es": "Limpiar el histórico",
        "en": "Clear the history", "fr": "Nettoyer l'historique",
    },
    "historic.clear.confirm.text": {
        "ca": "Ja has exportat totes les dades a Excel?\n\nS'esborrarà tot l'històric excepte "
              "l'última entrada de cada material que encara hi ha al Tauler. No es pot desfer.",
        "es": "¿Ya has exportado todos los datos a Excel?\n\nSe borrará todo el histórico excepto "
              "la última entrada de cada material que todavía está en el Tauler. No se puede deshacer.",
        "en": "Have you already exported all the data to Excel?\n\nThe whole history will be deleted "
              "except the last entry of each material still on the board. This cannot be undone.",
        "fr": "Avez-vous déjà exporté toutes les données en Excel ?\n\nTout l'historique sera supprimé "
              "sauf la dernière entrée de chaque matériau encore sur le tableau. Irréversible.",
    },
    "historic.clear.done": {
        "ca": "S'han esborrat {deleted} moviments. Se n'han conservat {kept} "
              "(l'últim de cada material que hi ha al Tauler).",
        "es": "Se han borrado {deleted} movimientos. Se han conservado {kept} "
              "(el último de cada material que hay en el Tauler).",
        "en": "{deleted} movements deleted. {kept} kept (the last one of each material on the board).",
        "fr": "{deleted} mouvements supprimés. {kept} conservés "
              "(le dernier de chaque matériau présent sur le tableau).",
    },
    "historic.clear.error": {
        "ca": "No s'ha pogut netejar l'històric; no s'hi ha tocat res.\n\n{error}",
        "es": "No se ha podido limpiar el histórico; no se ha tocado nada.\n\n{error}",
        "en": "The history could not be cleared; nothing has been touched.\n\n{error}",
        "fr": "L'historique n'a pas pu être nettoyé ; rien n'a été touché.\n\n{error}",
    },
    "password.scope.admin": {
        "ca": "Contrasenya administrador (còpies de seguretat i netejar)",
        "es": "Contraseña administrador (copias de seguridad y limpiar)",
        "en": "Administrator password (backups and clearing)",
        "fr": "Mot de passe administrateur (sauvegardes et nettoyage)",
    },
    "password.scope.worker": {
        "ca": "Contrasenya treballador (afegir i esborrar materials)",
        "es": "Contraseña trabajador (añadir y borrar materiales)",
        "en": "Worker password (adding and deleting materials)",
        "fr": "Mot de passe travailleur (ajouter et supprimer des matériaux)",
    },
    "password.change.which": {
        "ca": "Quina contrasenya vols canviar?", "es": "¿Qué contraseña quieres cambiar?",
        "en": "Which password do you want to change?", "fr": "Quel mot de passe voulez-vous changer ?",
    },
    "password.change.current": {
        "ca": "Contrasenya actual:", "es": "Contraseña actual:",
        "en": "Current password:", "fr": "Mot de passe actuel :",
    },
    "password.title": {
        "ca": "Contrasenya", "es": "Contraseña", "en": "Password", "fr": "Mot de passe",
    },
    "materials.password.label": {
        "ca": "Introdueix la contrasenya per afegir un material nou:",
        "es": "Introduce la contraseña para añadir un material nuevo:",
        "en": "Enter the password to add a new material:",
        "fr": "Entrez le mot de passe pour ajouter un nouveau matériau :",
    },
    "password.wrong.title": {
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
        "ca": "Esborrar material", "es": "Borrar material",
        "en": "Delete material", "fr": "Supprimer le matériau",
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

    # -- Estadístiques -------------------------------------------------------- #
    "stats.title": {
        "ca": "Moviments de l'històric", "es": "Movimientos del histórico",
        "en": "Movements in the history", "fr": "Mouvements de l'historique",
    },
    "stats.from": {"ca": "Des de:", "es": "Desde:", "en": "From:", "fr": "Du :"},
    "stats.to": {"ca": "Fins a:", "es": "Hasta:", "en": "To:", "fr": "Au :"},
    "stats.apply": {
        "ca": "Consultar", "es": "Consultar", "en": "Show", "fr": "Consulter",
    },
    "stats.range.today": {"ca": "Avui", "es": "Hoy", "en": "Today", "fr": "Aujourd'hui"},
    "stats.range.week": {
        "ca": "Últims 7 dies", "es": "Últimos 7 días",
        "en": "Last 7 days", "fr": "7 derniers jours",
    },
    "stats.range.month": {
        "ca": "Últims 30 dies", "es": "Últimos 30 días",
        "en": "Last 30 days", "fr": "30 derniers jours",
    },
    "stats.range.year": {
        "ca": "Últim any", "es": "Último año", "en": "Last year", "fr": "Dernière année",
    },
    "stats.col.day": {"ca": "Dia", "es": "Día", "en": "Day", "fr": "Jour"},
    "stats.col.in": {"ca": "Entrades", "es": "Entradas", "en": "In", "fr": "Entrées"},
    "stats.col.out": {"ca": "Sortides", "es": "Salidas", "en": "Out", "fr": "Sorties"},
    "stats.col.move": {"ca": "Trasllats", "es": "Traslados", "en": "Moves", "fr": "Déplacements"},
    "stats.col.total": {"ca": "Total", "es": "Total", "en": "Total", "fr": "Total"},
    "stats.col.position": {"ca": "Posició de destí", "es": "Posición de destino",
        "en": "Destination position", "fr": "Position de destination"},
    "stats.total_row": {"ca": "TOTAL", "es": "TOTAL", "en": "TOTAL", "fr": "TOTAL"},
    "stats.destinations_title": {
        "ca": "Trasllats per posició de destí",
        "es": "Traslados por posición de destino",
        "en": "Moves by destination position",
        "fr": "Déplacements par position de destination",
    },
    "stats.note": {
        "ca": "Cada trasllat es compta una sola vegada, a la posició on ha anat a parar la peça.",
        "es": "Cada traslado se cuenta una sola vez, en la posición donde ha ido a parar la pieza.",
        "en": "Each move is counted once, at the position the piece ended up in.",
        "fr": "Chaque déplacement est compté une seule fois, à la position où la pièce est arrivée.",
    },
    "stats.summary": {
        "ca": "{days} dies amb moviment — {in_count} entrades, {out_count} sortides, {move_count} trasllats",
        "es": "{days} días con movimiento — {in_count} entradas, {out_count} salidas, {move_count} traslados",
        "en": "{days} days with movement — {in_count} in, {out_count} out, {move_count} moves",
        "fr": "{days} jours avec mouvement — {in_count} entrées, {out_count} sorties, {move_count} déplacements",
    },
    "stats.empty": {
        "ca": "No hi ha cap moviment en aquest interval de dates.",
        "es": "No hay ningún movimiento en este intervalo de fechas.",
        "en": "There are no movements in this date range.",
        "fr": "Aucun mouvement dans cet intervalle de dates.",
    },
    "stats.invalid_range.text": {
        "ca": "La data final és anterior a la inicial.",
        "es": "La fecha final es anterior a la inicial.",
        "en": "The end date is earlier than the start date.",
        "fr": "La date de fin est antérieure à la date de début.",
    },
}
