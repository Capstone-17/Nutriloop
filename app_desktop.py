"""
app_desktop.py
──────────────
Main entrypoint for Nutriloop Desktop Standalone Executable.
Launches native Windows application window using pywebview with Edge WebView2.
Provides complete in-process bridge without needing external browser or web server.
"""

from __future__ import annotations

import logging
import os
import sys

# Prevent bytecode generation and __pycache__ directory creation
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import multiprocessing
from pathlib import Path

# Enforce 100% in-process execution and prevent loky from spawning PowerShell core-detection subprocesses on Windows
os.environ["JOBLIB_MULTIPROCESSING"] = "0"
os.environ["LOKY_MAX_CPU_COUNT"] = str(os.cpu_count() or 4)
try:
    import joblib.externals.loky.backend.context as loky_context
    loky_context.physical_cores_cache = os.cpu_count() or 4
except Exception:
    pass

import webview

from desktop_api import DesktopAPI
from backend.model_registry import registry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("Nutriloop")


def get_html_path() -> Path:
    """Resolve index.html path for both source and PyInstaller bundled environments."""
    if getattr(sys, "_MEIPASS", None):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).resolve().parent

    html_file = base_dir / "gui" / "index.html"
    if not html_file.exists():
        raise FileNotFoundError(f"GUI interface file not found at: {html_file}")
    return html_file


def get_icon_path() -> Optional[Path]:
    """Resolve Nutriloop_1.ico path for the standalone desktop window icon."""
    if getattr(sys, "_MEIPASS", None):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).resolve().parent

    for candidate in [
        base_dir / "Assets" / "Nutriloop_1.ico",
        base_dir / "gui" / "assets" / "Nutriloop_1.ico",
    ]:
        if candidate.exists():
            return candidate
    return None


def main() -> None:
    log.info("Initializing Nutriloop Desktop Application...")
    api = DesktopAPI()
    
    # Pre-load all 3 disease models into memory
    log.info("Pre-warming clinical risk models...")
    for disease in ["ckd", "hypertension", "diabetes"]:
        registry.ensure_model_loaded(disease)
        
    html_path = get_html_path()
    icon_path = get_icon_path()
    icon_str = str(icon_path) if icon_path else None

    window = webview.create_window(
        title="Nutriloop",
        url=str(html_path),
        js_api=api,
        width=1240,
        height=840,
        min_size=(960, 640),
        background_color="#0c0608",
    )

    # Ensure background daemon is terminated immediately when user closes window
    window.events.closing += lambda: api.terminate_ollama()

    log.info("Starting Desktop Window (face icon: %s)...", icon_str)
    webview.start(icon=icon_str, debug=False)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()

