# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_dynamic_libs
from PyInstaller.utils.hooks import collect_all

datas = [('src\\01_overlay_ui\\web', 'web'), ('config', 'config'), ('tools\\bin\\msd.exe', '.')]
binaries = [('D:\\copia\\calculator-rebirth\\src\\01_overlay_ui\\ffmpeg\\ffmpeg.exe', '.')]
hiddenimports = ['sr_core', 'sr_core.algorithm', 'sr_core.osu_file_parser', 'numpy', 'pandas', 'bisect', 'heapq', 'events', 'contracts', 'tosu_source', 'analysis_coordinator', 'bridge', 'audio_service', 'chart_export', 'overlay_host', 'webview', 'requests', 'websocket', 'pythonnet', 'clr_loader', 'bottle', 'proxy_tools', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont', 'PIL.ImageFilter', 'parser', 'validator', 'feature_extractor', 'primary_sr_bridge', 'classifier', 'rank_engine', 'minacalc_estimator', 'minacalc_bridge', 'celestial_estimator', 'signicial_estimator', 'shoegazer_estimator', 'ln_course_estimator', 'resource_path']
datas += collect_data_files('pandas')
datas += collect_data_files('tzdata')
binaries += collect_dynamic_libs('numpy')
binaries += collect_dynamic_libs('pandas')
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('clr_loader')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pythonnet')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['src\\01_overlay_ui\\main.py'],
    pathex=['src', 'src\\01_overlay_ui', 'src\\02_runtime_bridge', 'src\\03_engine_reference', 'src\\07_model'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='DanOverlay 2.2.0',
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
    icon=['src\\01_overlay_ui\\web\\graph.ico'],
)
