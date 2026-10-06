# -*- mode: python ; coding: utf-8 -*-
"""
Nutriloop.spec
──────────────
PyInstaller specification file to compile Nutriloop into a single,
self-contained Windows executable (.exe) with zero external runtime dependencies.
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules
import sys
from pathlib import Path

block_cipher = None
REPO_ROOT = Path.cwd()

# Data files to bundle inside sys._MEIPASS
datas = [
    (str(REPO_ROOT / "artifacts"), "artifacts"),
    (str(REPO_ROOT / "bin"), "bin"),
    (str(REPO_ROOT / "datasets" / "unified_food_kb.csv"), "datasets"),
    (str(REPO_ROOT / "gui"), "gui"),
    (str(REPO_ROOT / "Assets"), "Assets"),
] + collect_data_files("sklearn")

# Hidden imports required by dynamic reflection / C-extensions
hidden_imports = [
    "webview",
    "webview.platforms.winforms",
    "clr",
    "pythonnet",
    "joblib",
    "pandas",
    "numpy",
    "sqlite3",
    "httpx",
    "pydantic",
    "scipy",
    "scipy.special",
    "scipy.optimize",
    "sklearn",
    "sklearn.calibration",
    "sklearn.ensemble",
    "sklearn.ensemble._hist_gradient_boosting",
    "sklearn.tree",
    "sklearn.preprocessing",
    "sklearn.isotonic",
    "sklearn.linear_model",
    "backend.adaptation_engine",
    "backend.agent_engine",
    "backend.chatbot.agent",
    "backend.chatbot.tools",
    "backend.chatbot.system_prompt",
    "backend.db",
    "backend.medical_knowledge",
    "backend.model_registry",
    "backend.raw_input",
    "backend.reporting",
    "backend.rules",
    "backend.safety_engine",
    "backend.schemas",
    "backend.weekly_diet_engine",
    "backend.ollama_manager",
    "desktop_api",
] + collect_submodules("sklearn")

a = Analysis(
    ["app_desktop.py"],
    pathex=[str(REPO_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "torch",
        "transformers",
        "spacy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Nutriloop",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Launch cleanly as a GUI desktop window without console popup
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(REPO_ROOT / "Assets" / "Nutriloop_1.ico"),
)
