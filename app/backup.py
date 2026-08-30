"""Còpies de seguretat (equivalent a CrearBackup/IniciarBackupAutomatic).

A l'Excel original es desava una còpia del llibre cada 4 hores en una
carpeta "Backups" al costat del fitxer, conservant només les més recents.
Aquí es fa igual copiant el fitxer SQLite, amb quatre coses més que es
poden configurar (i que es recorden a `settings.json`):

  - **On**: la carpeta de destí la tria l'usuari; per defecte, `Backups`
    al costat de la base de dades, com sempre.
  - **Com es diu**: `AAAAMMDDHHMM_<nom>.db`. La data i l'hora van SEMPRE
    al davant perquè, ordenant els fitxers pel nom, quedin ordenats
    cronològicament; el nom de després el tria l'usuari.
  - **Quantes se'n guarden**: 25 per defecte. En fer-ne una de nova, si
    passen del límit s'esborren les més antigues —les de la data més
    vella al nom—, i sempre DESPRÉS d'haver desat la nova.
  - **Còpia doble**: si hi ha un llapis USB connectat, se'n fa una segona
    còpia allà. Si no n'hi ha, o si falla, la còpia principal es fa
    igualment i es diu clarament què ha passat (mai es diu que està
    duplicada si no ho està). El límit s'aplica a cada destí per separat;
    si el USB no hi és, allà no s'hi toca res.

El format del fitxer no canvia: segueix sent el mateix .db que llegeix
"Importar de base de dades".
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Quantes còpies es conserven a cada destí. L'usuari ho pot canviar des de
# la configuració; 25 és el valor de sortida.
DEFAULT_KEEP_BACKUPS = 25
# Límit de sentit comú del que es pot demanar a la configuració.
MIN_KEEP_BACKUPS = 1
MAX_KEEP_BACKUPS = 500

# Nom per defecte de les còpies, si l'usuari no en tria cap altre.
DEFAULT_PREFIX = "Backup"
# Carpeta on es deixa la còpia dins d'un USB (mai a l'arrel, per no
# escampar fitxers pel llapis).
USB_FOLDER = "SobrantsBackups"

# Fitxers que la rotació pot esborrar: només els que ha creat l'aplicació,
# ja siguin del format nou (AAAAMMDDHHMM_nom.db) o del d'abans
# (Backup_AAAAMMDD_HHMMSS.db). Així, si algú tria com a carpeta de còpies
# una carpeta amb altres .db a dins, no se'ls emporta per davant.
_OURS = re.compile(r"^(\d{12}_.+|Backup_\d{8}_\d{6})\.db$")


def sanitize_prefix(prefix: str) -> str:
    """Deixa el nom triat en una cosa que pugui ser un nom de fitxer: fora
    barres, dos punts i companyia. Si no en queda res, el de per defecte."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", (prefix or "").strip())
    return cleaned or DEFAULT_PREFIX


def backup_name(prefix: str = DEFAULT_PREFIX, when: datetime | None = None) -> str:
    """`AAAAMMDDHHMM_<nom>.db` — la data i l'hora sempre al davant."""
    when = when or datetime.now()
    return f"{when:%Y%m%d%H%M}_{sanitize_prefix(prefix)}.db"


def _unique(path: Path) -> Path:
    """Un nom que no trepitgi res: si ja existeix (dues còpies dins del
    mateix minut), s'hi afegeix -2, -3... en comptes de sobreescriure."""
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    for n in range(2, 1000):
        candidate = path.with_name(f"{stem}-{n}{suffix}")
        if not candidate.exists():
            return candidate
    raise OSError(f"No s'ha pogut trobar un nom lliure per a {path}")


def _copy_verified(db_path: Path, dest_dir: Path, name: str) -> Path:
    """Copia i comprova que ha arribat sencera (existeix i fa la mateixa
    mida que l'original). Si no, esborra el que hagi quedat a mitges i
    llança l'error: val més cap còpia que una còpia fallida."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = _unique(dest_dir / name)
    shutil.copy2(db_path, dest)
    if not dest.exists() or dest.stat().st_size != db_path.stat().st_size:
        dest.unlink(missing_ok=True)
        raise OSError(f"La còpia {dest} no s'ha desat sencera")
    return dest


def create_backup(
    db_path: str | Path,
    backups_dir: str | Path | None = None,
    prefix: str = DEFAULT_PREFIX,
    keep: int = DEFAULT_KEEP_BACKUPS,
) -> Path:
    """Una còpia, comprovada, a la carpeta indicada (per defecte, `Backups`
    al costat de la base de dades). Retorna on ha quedat.

    Primer es fa la còpia nova i NOMÉS després s'esborren les que sobren:
    si la còpia falla, no s'haurà perdut cap de les que ja hi havia.
    """
    db_path = Path(db_path)
    backups_dir = Path(backups_dir) if backups_dir else default_backups_dir(db_path)
    dest = _copy_verified(db_path, backups_dir, backup_name(prefix))
    rotate_backups(backups_dir, keep=keep)
    return dest


def default_backups_dir(db_path: str | Path) -> Path:
    return Path(db_path).parent / "Backups"


@dataclass
class BackupResult:
    """Què ha passat de debò, per poder-ho dir sense inventar-se res."""

    main_path: Path | None = None
    usb_path: Path | None = None
    usb_error: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.main_path is not None

    @property
    def duplicated(self) -> bool:
        return self.usb_path is not None


def run_backup(
    db_path: str | Path,
    backups_dir: str | Path | None = None,
    prefix: str = DEFAULT_PREFIX,
    usb_root: str | Path | None = None,
    keep: int = DEFAULT_KEEP_BACKUPS,
) -> BackupResult:
    """La còpia tal com la fa l'aplicació: una a la carpeta configurada i,
    si `usb_root` hi és, una segona al llapis.

    Les dues còpies porten el mateix nom i surten del mateix fitxer, així
    que són idèntiques. La del USB és independent: si el llapis no s'hi
    deixa escriure o el treuen a mig camí, la principal no se'n ressent i
    l'error queda anotat al resultat (no s'aixeca cap excepció, perquè la
    còpia automàtica no ha d'interrompre mai la feina).
    """
    db_path = Path(db_path)
    result = BackupResult()
    name = backup_name(prefix)

    try:
        target = Path(backups_dir) if backups_dir else default_backups_dir(db_path)
        result.main_path = _copy_verified(db_path, target, name)
        rotate_backups(target, keep=keep)
    except OSError as exc:
        result.errors.append(str(exc))
        return result  # sense còpia principal no té sentit continuar

    if usb_root:
        try:
            usb_dir = Path(usb_root) / USB_FOLDER
            result.usb_path = _copy_verified(db_path, usb_dir, name)
            rotate_backups(usb_dir, keep=keep)
        except OSError as exc:
            # USB ple, protegit contra escriptura, o desconnectat a mitges.
            result.usb_error = str(exc)
    return result


def backup_age_key(path: Path):
    """Per ordenar les còpies de la més antiga a la més nova.

    S'ordena per la data que porten al NOM (AAAAMMDDHHMM), que és la que
    diu quan es va fer; si el nom és del format antic o no s'entén, es fa
    servir la data del fitxer, i aquestes van primer (són més velles). El
    nom sencer desempata, així dues còpies del mateix minut queden sempre
    en el mateix ordre.
    """
    match = re.match(r"^(\d{12})_", path.name)
    if match:
        return (1, match.group(1), path.name)
    try:
        return (0, f"{path.stat().st_mtime:020.0f}", path.name)
    except OSError:
        return (0, "0", path.name)


def list_backups(backups_dir: str | Path) -> list[Path]:
    """Les còpies fetes per l'aplicació que hi ha en una carpeta, de la més
    antiga a la més nova. Qualsevol altre .db que hi hagi no hi surt: no és
    nostre i no s'ha de tocar mai."""
    backups_dir = Path(backups_dir)
    if not backups_dir.is_dir():
        return []
    return sorted(
        (p for p in backups_dir.glob("*.db") if _OURS.match(p.name)),
        key=backup_age_key,
    )


def rotate_backups(backups_dir: str | Path, keep: int = DEFAULT_KEEP_BACKUPS) -> None:
    """Conserva només les `keep` còpies més recents FETES PER L'APLICACIÓ.

    Només es miren els fitxers que segueixen el nom de les còpies
    (`_OURS`): una base de dades qualsevol que hi hagi a la mateixa
    carpeta no es toca mai. Si el destí no existeix —p. ex. el USB que
    s'ha desconnectat— no es fa res: val més deixar-hi còpies de sobra que
    esborrar-ne cap per una desconnexió.
    """
    keep = max(int(keep), MIN_KEEP_BACKUPS)
    files = list_backups(backups_dir)
    excess = len(files) - keep
    for f in files[:max(excess, 0)]:   # els primers de la llista: els més antics
        f.unlink(missing_ok=True)
