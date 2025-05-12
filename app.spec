# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[
        # ('/opt/anaconda3/lib/libavcodec.60.31.102.dylib', 'libavcodec.dylib'),
        # ('/opt/anaconda3/lib/libavformat.60.16.100.dylib', 'libavformat.dylib'),
        # ('/opt/anaconda3/lib/libavdevice.60.3.100.dylib', 'libavdevice.dylib'),
        # ('/opt/anaconda3/lib/libavif.15.0.1.dylib', 'libavif.dylib'),
        # ('/opt/anaconda3/lib/libavfilter.9.12.100.dylib', 'libavfilter.dylib'),
        # ('/opt/anaconda3/lib/libavutil.58.29.100.dylib', 'libavutil.dylib'),
    ],
    datas=[
        ('config.toml', '.'),
        ('LICENSE.md', '.'),
        ('README.md', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PyQt5.QtWebEngineWidgets',
        'PyQt5.QtWebEngineCore',
        'PyQt5.QtWebEngine',
        'PyQt5.QtWebChannel',
        'PyQt5.QtWebSockets',
        'PyQt5.QtMultimediaWidgets',
        'PyQt5.QtMultimedia',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Zulution VAT Lite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon_512x512.png',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Zulution VAT Lite',
)
app = BUNDLE(
    coll,
    name='Zulution VAT Lite.app',
    icon='assets/icon_512x512.png',
    bundle_identifier=None,
    version='1.0.0',
)
