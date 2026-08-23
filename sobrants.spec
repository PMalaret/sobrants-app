# -*- mode: python ; coding: utf-8 -*-
# Compilación con PyInstaller: pyinstaller sobrants.spec
# Genera un ejecutable de un solo archivo, sin dependencias externas.
# En Windows produce Sobrants.exe; en macOS/Linux, el binario "Sobrants".

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
    a.binaries,
    a.datas,
    [],
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
