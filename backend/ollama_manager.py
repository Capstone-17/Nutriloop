"""
backend/ollama_manager.py
─────────────────────────
Lifecycle and Process Manager for embedded Ollama on Nutriloop.

Guarantees:
  1. Zero External Setup: Automatically locates bundled bin/ollama.exe.
  2. Zero Console Flashes: Uses CREATE_NO_WINDOW (0x08000000) on Windows.
  3. Portable Storage: All models are downloaded strictly inside Nutriloop_Data/models
     via OLLAMA_MODELS. Nothing is installed to Windows system directories or user home.
  4. Strict Process Termination:
     - Downloads terminate the daemon immediately upon completion or failure.
     - Chat starts the daemon on-demand and terminates it after 60 seconds of idle.
     - App shutdown (atexit) forcefully terminates any lingering processes.
  5. Offline Model Detection: Inspects the on-disk manifests without starting the daemon.
"""

from __future__ import annotations

import os
import sys

# Globally prevent Python from writing .pyc files or creating __pycache__ directories
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

import atexit
import json
import logging
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from backend.db import MODELS_DIR

log = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:3b"


class OllamaProcessManager:
    """Singleton process manager for the embedded Ollama daemon."""

    _instance: Optional[OllamaProcessManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> OllamaProcessManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_manager()
            return cls._instance

    def _init_manager(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_BASE_URL)
        self.recommended_model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        self.binary_path = self._resolve_binary_path()
        self.models_dir = MODELS_DIR
        self.models_dir.mkdir(parents=True, exist_ok=True)
        os.environ["OLLAMA_MODELS"] = str(self.models_dir.resolve())

        self._process: Optional[subprocess.Popen] = None
        self._proc_lock = threading.Lock()
        self._idle_timer: Optional[threading.Timer] = None
        self._idle_timeout_s = 60.0  # Terminate daemon after 60s of inactivity

        # Background download state
        self._download_lock = threading.Lock()
        self._download_state: Dict[str, Any] = {
            "status": "idle",
            "percent": 0.0,
            "completed_bytes": 0,
            "total_bytes": 0,
            "message": "Ready to install",
            "error": None,
        }

        # Ensure cleanup on process exit
        atexit.register(self.terminate_service)
        log.info("[OllamaManager] Initialized. Binary: %s", self.binary_path)

    # ──────────────────────────────────────────────────────────────────────────
    # Binary Resolution
    # ──────────────────────────────────────────────────────────────────────────

    def _resolve_binary_path(self) -> Optional[Path]:
        """Locate bundled ollama.exe or system binary."""
        # 1. PyInstaller bundled path (_MEIPASS/bin/ollama.exe)
        if getattr(sys, "_MEIPASS", None):
            meipass_bin = Path(sys._MEIPASS) / "bin" / ("ollama.exe" if os.name == "nt" else "ollama")
            if meipass_bin.exists():
                return meipass_bin

        # 2. Local workspace bin directory
        workspace_bin = Path(__file__).resolve().parent.parent / "bin" / ("ollama.exe" if os.name == "nt" else "ollama")
        if workspace_bin.exists():
            return workspace_bin

        # 3. System PATH fallback
        sys_which = shutil.which("ollama")
        if sys_which:
            return Path(sys_which)

        return None

    def is_binary_available(self) -> bool:
        return self.binary_path is not None and self.binary_path.exists()

    # ──────────────────────────────────────────────────────────────────────────
    # Model Detection (Zero-Daemon Disk Inspection)
    # ──────────────────────────────────────────────────────────────────────────

    def _get_manifest_dirs(self) -> List[Path]:
        """Return candidate directories where Ollama model manifests are stored."""
        dirs = [self.models_dir / "manifests"]
        env_models = os.getenv("OLLAMA_MODELS")
        if env_models:
            dirs.append(Path(env_models) / "manifests")

        user_home = Path.home() / ".ollama" / "models" / "manifests"
        dirs.append(user_home)
        return dirs

    def is_model_installed(self, model_name: Optional[str] = None) -> bool:
        """Check whether the model exists on disk without needing Ollama to be running."""
        target = (model_name or self.recommended_model).strip().lower()
        clean_name = target.split(":")[0]  # e.g., 'llama3.2'
        tag_name = target.split(":")[1] if ":" in target else "latest"

        # 1. Fast filesystem manifest check
        for m_dir in self._get_manifest_dirs():
            if not m_dir.exists():
                continue
            for manifest_file in m_dir.rglob("*"):
                if manifest_file.is_file():
                    p_str = str(manifest_file).lower().replace("\\", "/")
                    if clean_name in p_str:
                        if tag_name in p_str or manifest_file.name == tag_name or manifest_file.name == "latest":
                            return True

        # 2. Live API check if daemon happens to be active
        if self.is_service_running():
            try:
                r = httpx.get(f"{self.base_url}/api/tags", timeout=1.0)
                if r.status_code == 200:
                    models = [m.get("name", "").lower() for m in r.json().get("models", [])]
                    return any(target in m or clean_name in m for m in models)
            except Exception:
                pass

        return False

    # ──────────────────────────────────────────────────────────────────────────
    # Service Lifecycle Management
    # ──────────────────────────────────────────────────────────────────────────

    def is_service_running(self) -> bool:
        """Ping local Ollama HTTP endpoint."""
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=0.8)
            return r.status_code == 200
        except Exception:
            return False

    def start_service(self, timeout_s: float = 12.0) -> bool:
        """Launch ollama serve in background with CREATE_NO_WINDOW if not already running."""
        with self._proc_lock:
            # Cancel any pending idle termination
            self._cancel_idle_timer()

            if self.is_service_running():
                log.info("[OllamaManager] Service is already running.")
                return True

            if not self.is_binary_available():
                log.error("[OllamaManager] ollama binary not found at %s", self.binary_path)
                return False

            cmd = [str(self.binary_path), "serve"]
            log.info("[OllamaManager] Launching background daemon: %s with OLLAMA_MODELS=%s", cmd, self.models_dir)

            env = os.environ.copy()
            env["OLLAMA_MODELS"] = str(self.models_dir.resolve())
            env["OLLAMA_HOST"] = "127.0.0.1:11434"

            try:
                self._process = subprocess.Popen(
                    cmd,
                    env=env,
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception as exc:
                log.exception("[OllamaManager] Failed to launch daemon: %s", exc)
                return False

        # Wait for service readiness
        start_t = time.perf_counter()
        while time.perf_counter() - start_t < timeout_s:
            if self.is_service_running():
                log.info("[OllamaManager] Daemon ready in %.2fs", time.perf_counter() - start_t)
                return True
            time.sleep(0.3)

        log.error("[OllamaManager] Daemon failed to respond within %.1fs", timeout_s)
        self.terminate_service()
        return False

    def terminate_service(self) -> None:
        """Kill the Ollama background daemon and all child processes immediately."""
        with self._proc_lock:
            self._cancel_idle_timer()

            pid = self._process.pid if self._process else None

            # 1. Kill tracked process
            if self._process is not None:
                try:
                    if self._process.poll() is None:
                        if os.name == "nt":
                            subprocess.run(
                                ["taskkill", "/F", "/T", "/PID", str(pid)],
                                creationflags=CREATE_NO_WINDOW,
                                capture_output=True,
                            )
                        else:
                            self._process.terminate()
                            self._process.wait(timeout=2.0)
                except Exception as exc:
                    log.warning("[OllamaManager] Exception while terminating process: %s", exc)
                finally:
                    self._process = None

            # Only stop the process this manager started and still tracks.
            # Never terminate every process named ollama.exe: another app or a
            # user-managed Ollama service may be using it.
            if pid is None:
                log.info("[OllamaManager] No app-owned Ollama process to stop.")
                return

            log.info("[OllamaManager] App-owned Ollama process termination requested.")

    def schedule_idle_shutdown(self, seconds: Optional[float] = None) -> None:
        """Schedule automatic termination after seconds of no chat activity."""
        with self._proc_lock:
            self._cancel_idle_timer()
            delay = seconds or self._idle_timeout_s
            self._idle_timer = threading.Timer(delay, self._on_idle_timeout)
            self._idle_timer.daemon = True
            self._idle_timer.start()
            log.debug("[OllamaManager] Scheduled idle shutdown in %.1fs", delay)

    def _cancel_idle_timer(self) -> None:
        if self._idle_timer is not None:
            self._idle_timer.cancel()
            self._idle_timer = None

    def _on_idle_timeout(self) -> None:
        log.info("[OllamaManager] Idle timeout expired (no chat activity). Terminating daemon.")
        self.terminate_service()

    def ensure_chat_ready(self) -> bool:
        """Start daemon on-demand for chat and reset the idle timer."""
        if not self.start_service():
            return False
        self.schedule_idle_shutdown(self._idle_timeout_s)
        return True

    # ──────────────────────────────────────────────────────────────────────────
    # Model Download with Mandatory Post-Download Termination
    # ──────────────────────────────────────────────────────────────────────────

    def start_model_download(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Trigger background pull of model. Terminates daemon immediately when finished."""
        target_model = model_name or self.recommended_model
        with self._download_lock:
            if self._download_state["status"] in ("downloading", "starting"):
                return {"status": "busy", "message": "Model installation already in progress."}

            self._download_state = {
                "status": "starting",
                "percent": 0.0,
                "completed_bytes": 0,
                "total_bytes": 0,
                "message": f"Starting embedded Ollama daemon to install {target_model}...",
                "error": None,
            }

            pull_thread = threading.Thread(
                target=self._run_download_worker,
                args=(target_model,),
                daemon=True,
            )
            pull_thread.start()
            return {"status": "started", "model": target_model}

    def _run_download_worker(self, model_name: str) -> None:
        """Worker thread: starts daemon, streams pull, and terminates daemon immediately."""
        try:
            # 1. Start daemon
            ready = self.start_service(timeout_s=15.0)
            if not ready:
                self._set_download_error("Could not launch embedded Ollama background service.")
                return

            # 2. Stream pull
            url = f"{self.base_url}/api/pull"
            self._download_state["message"] = f"Connecting to pull {model_name}..."

            with httpx.Client(timeout=1800.0) as client:
                with client.stream("POST", url, json={"name": model_name, "stream": True}) as resp:
                    if resp.status_code != 200:
                        self._set_download_error(f"HTTP {resp.status_code}: {resp.text}")
                        return

                    for line in resp.iter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                            status = chunk.get("status", "")
                            total = chunk.get("total", 0)
                            completed = chunk.get("completed", 0)

                            if total > 0:
                                pct = round((completed / total) * 100.0, 1)
                                mb_done = round(completed / (1024 * 1024), 1)
                                mb_tot = round(total / (1024 * 1024), 1)
                                msg = f"Downloading {model_name}: {pct}% ({mb_done} MB / {mb_tot} MB)"
                            else:
                                pct = 0.0
                                msg = status

                            is_success = "success" in status.lower()
                            with self._download_lock:
                                self._download_state.update({
                                    "status": "success" if is_success else "downloading",
                                    "percent": 100.0 if is_success else pct,
                                    "completed_bytes": completed,
                                    "total_bytes": total,
                                    "message": f"Model {model_name} successfully installed!" if is_success else msg,
                                })

                            if is_success:
                                log.info("[OllamaManager] Download complete: %s", model_name)
                                break
                        except Exception:
                            pass

        except Exception as exc:
            log.exception("[OllamaManager] Download worker error: %s", exc)
            err_str = str(exc)
            if "unexpected EOF" in err_str or "streaming" in err_str or "Timeout" in err_str:
                err_msg = "Model download was interrupted by a network timeout or connection reset. Note: Dr. Nutriloop's Clinical Knowledge Base is already fully functional without it! You can retry the download whenever you have a stable high-speed internet connection."
            else:
                err_msg = err_str
            self._set_download_error(err_msg)
        finally:
            # 3. CRITICAL REQUIREMENT:
            # "Once downloaded, the background ollama process should be terminated."
            # "Make sure there are no unnecessary background processes running at any time."
            log.info("[OllamaManager] Terminating background daemon post-download.")
            self.terminate_service()

    def _set_download_error(self, err_msg: str) -> None:
        with self._download_lock:
            self._download_state.update({
                "status": "error",
                "error": err_msg,
                "message": f"Installation failed: {err_msg}",
            })

    def get_download_progress(self) -> Dict[str, Any]:
        with self._download_lock:
            return dict(self._download_state)


# Global singleton instance
ollama_manager = OllamaProcessManager()
