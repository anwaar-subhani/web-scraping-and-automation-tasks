# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['script.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'pandas.plotting', 'IPython', 'sphinx', 'sklearn', 'bokeh', 'plotly', 'panel', 'jupyter', 'notebook', 'altair', 'dask', 'xarray', 'lz4', 'xyzservices', 'lxml', 'jsonschema', 'nbformat', 'argon2', 'jupyterlab', 'babel', 'ruamel', 'anyio', 'sqlalchemy', 'h5py', 'patsy', 'statsmodels', 'tables', 'qtpy', 'PyQt5', 'pyviz_comms', 'markdown', 'skimage', 'docutils', 'intake', 'nbconvert', 'mistune', 'playwright', 'zoneinfo'],
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
    name='KFB_Web_Scraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
