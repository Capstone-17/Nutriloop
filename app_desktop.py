"""
app_desktop.py
──────────────
Main entrypoint for Nutriloop Desktop Standalone Executable.
Launches native Windows application window using pywebview with Edge WebView2.
Provides complete in-process bridge without needing external browser or web server.

Optimized with:
  1. Single-Instance Guard: Prevents accidental multiple launches via Windows Named Mutex.
     Brings existing window to front on duplicate launch.
  2. Instant Window Launch: Shows window in < 300ms without blocking on heavy ML models.
  3. Background Lazy Pre-Warming: Pre-loads diagnostic models & engines in a background thread.
"""

from __future__ import annotations

import atexit
import ctypes
import http.server
import logging
import multiprocessing
import os
import shutil
import socketserver
import sys
import threading
from pathlib import Path
from typing import Any, Optional, Tuple

# Prevent bytecode generation and __pycache__ directory creation
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

# Support PyInstaller instant splash screen
try:
    import pyi_splash
except ImportError:
    pyi_splash = None


def _purge_pycache() -> None:
    """Fast removal of all __pycache__ directories across the repository."""
    try:
        base_dir = Path(__file__).resolve().parent
        for target in base_dir.rglob("__pycache__"):
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
    except Exception:
        pass


_purge_pycache()
atexit.register(_purge_pycache)

# Enforce 100% in-process execution and prevent loky from spawning PowerShell core-detection subprocesses on Windows
os.environ["JOBLIB_MULTIPROCESSING"] = "0"
os.environ["LOKY_MAX_CPU_COUNT"] = str(os.cpu_count() or 4)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("Nutriloop")

# Global reference to prevent garbage collection of the single-instance mutex
_APP_MUTEX = None


def check_single_instance() -> Tuple[bool, Optional[Any]]:
    """
    Ensure only one instance of Nutriloop runs at a time on Windows.
    If an existing instance is already running, restores and brings its window to front.
    """
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        
        mutex_name = "Local\\Nutriloop_SingleInstance_Mutex_v1"
        mutex = kernel32.CreateMutexW(None, False, mutex_name)
        last_error = kernel32.GetLastError()
        
        if last_error == 183:  # ERROR_ALREADY_EXISTS
            hwnd = user32.FindWindowW(None, "Nutriloop")
            if hwnd:
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE (9)
                user32.SetForegroundWindow(hwnd)
            return False, mutex
        return True, mutex
    except Exception:
        return True, None


class _QuietRootHandler(http.server.SimpleHTTPRequestHandler):
    """Serve frontend and common assets without console spam."""
    def __init__(self, *args, **kwargs):
        base_dir = getattr(sys, "_MEIPASS", None)
        root_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parent
        super().__init__(*args, directory=str(root_dir), **kwargs)

    def log_message(self, format, *args):
        pass  # Quiet in production console


def start_local_server() -> Tuple[str, socketserver.TCPServer]:
    """
    Start an in-process ephemeral loopback HTTP server.
    Serves both the common root /assets folder and /pc frontend without sandbox restrictions.
    """
    httpd = socketserver.TCPServer(("127.0.0.1", 0), _QuietRootHandler)
    port = httpd.server_address[1]
    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="DesktopHttpServer")
    server_thread.start()
    log.info("Desktop static server running at http://127.0.0.1:%d/", port)
    return f"http://127.0.0.1:{port}/pc/index.html", httpd


def get_icon_path() -> Optional[Path]:
    """Resolve Nutriloop_1.ico path for the standalone desktop window icon."""
    if getattr(sys, "_MEIPASS", None):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).resolve().parent

    icon_candidate = base_dir / "assets" / "Nutriloop_1.ico"
    if icon_candidate.exists():
        return icon_candidate
    return None


def _background_warmup() -> None:
    """
    Asynchronously pre-warm clinical risk models and heavy engines in the background
    while the native window and UI finish opening.
    """
    try:
        from backend.model_registry import registry
        for disease in ["ckd", "hypertension", "diabetes"]:
            registry.ensure_model_loaded(disease)
        
        # Pre-import heavy engines in background so first user action has 0ms latency
        try:
            import joblib.externals.loky.backend.context as loky_context
            loky_context.physical_cores_cache = os.cpu_count() or 4
        except Exception:
            pass
        import backend.weekly_diet_engine
        import backend.chatbot.agent
        log.info("Background model and engine warmup complete.")
    except Exception as exc:
        log.warning("Background warmup notice: %s", exc)


def main() -> None:
    global _APP_MUTEX
    
    # 1. Enforce Single-Instance Guard
    is_single, mutex = check_single_instance()
    if not is_single:
        log.info("Nutriloop is already running. Existing window focused. Exiting duplicate process.")
        sys.exit(0)
    _APP_MUTEX = mutex

    log.info("Launching Nutriloop Desktop Application...")

    # 2. Lazy-load bridge API (fast lightweight startup)
    import webview
    from desktop_api import DesktopAPI
    api = DesktopAPI()
    
    app_url, httpd = start_local_server()
    atexit.register(httpd.shutdown)
    icon_path = get_icon_path()
    icon_str = str(icon_path) if icon_path else None

    # 3. Start background pre-warming thread (non-blocking)
    threading.Thread(target=_background_warmup, daemon=True, name="ModelWarmupThread").start()

    # 4. Create and start native window immediately
    window = webview.create_window(
        title="Nutriloop",
        url=app_url,
        js_api=api,
        width=1240,
        height=840,
        min_size=(960, 640),
        background_color="#0c0608",
    )

    # Ensure splash screen closes once window is shown or loaded
    _splash_closed = False
    def _close_splash():
        nonlocal _splash_closed
        if _splash_closed:
            return
        _splash_closed = True
        if pyi_splash and pyi_splash.is_alive():
            try:
                pyi_splash.update_text("READY")
                import time
                time.sleep(0.12)
                pyi_splash.close()
            except Exception:
                pass

    try:
        window.events.shown += _close_splash
    except Exception:
        pass
    window.events.loaded += _close_splash

    # Ultra-fast, synchronous shutdown handler: terminates window, child processes, and runtime in < 30ms
    _shutting_down = False
    def _fast_shutdown():
        nonlocal _shutting_down
        if _shutting_down:
            return
        _shutting_down = True
        log.info("Initiating fast application shutdown...")

        # 1. Immediately release and close Named Mutex handle to unlock file locks
        global _APP_MUTEX
        if _APP_MUTEX:
            try:
                kernel32 = ctypes.windll.kernel32
                kernel32.ReleaseMutex(_APP_MUTEX)
                kernel32.CloseHandle(_APP_MUTEX)
                _APP_MUTEX = None
            except Exception:
                pass

        # 2. Terminate background Ollama daemon process
        try:
            api.terminate_ollama()
        except Exception:
            pass

        # 3. Synchronously kill all descendant child processes (including Edge WebView2 subprocesses)
        if os.name == "nt":
            current_pid = os.getpid()
            import subprocess
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(current_pid)],
                    creationflags=0x08000000,  # CREATE_NO_WINDOW
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=1.0,
                )
            except Exception:
                pass

        # 4. Immediate hard exit (bypasses thread joins, COM teardown delays, and DLL unload lag)
        os._exit(0)

    window.events.closing += _fast_shutdown
    window.events.closed += _fast_shutdown

    log.info("Opening Desktop Window...")
    # Safety fallback to ensure splash is never permanently stuck (daemon thread)
    splash_timer = threading.Timer(6.0, _close_splash)
    splash_timer.daemon = True
    splash_timer.start()

    webview.start(icon=icon_str, debug=False)
    _fast_shutdown()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
