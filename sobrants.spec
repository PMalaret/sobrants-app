# -*- mode: python ; coding: utf-8 -*-
# Compilación con PyInstaller: pyinstaller sobrants.spec
#
# En macOS/Linux genera un binario de un solo archivo ("Sobrants").
#
# En Windows genera modo "onedir" (carpeta dist/Sobrants/ con Sobrants.exe
# + _internal/), en vez de onefile. El onefile de PyInstaller se
# autoextrae a %TEMP% en cada arranque, un patrón que Windows Defender
# marca como falso positivo de troyano/dropper en binarios sin firmar.
# El onedir no se autoextrae y evita ese aviso.

import sys

is_windows = sys.platform.startswith("win")

a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app/data/schema.sql', 'app/data'),
        ('app/ui/style.qss', 'app/ui'),
        ('app/assets/favicon.png', 'app/assets'),
        ('app/assets/app_icon.png', 'app/assets'),
        ('app/assets/luvnus.webp', 'app/assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [] if is_windows else a.binaries,
    [] if is_windows else a.datas,
    [],
    exclude_binaries=is_windows,
    name='Sobrants',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/assets/app_icon.ico',
)

if is_windows:
    # dist/Sobrants/Sobrants.exe + dist/Sobrants/_internal/
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name='Sobrants',
    )
