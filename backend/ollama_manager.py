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

        # Background download state and control
        self._download_lock = threading.Lock()
        self._pause_requested = False
        self._cancel_requested = False
        self._current_client: Optional[httpx.Client] = None
        self._download_state_file = self.models_dir / "download_state.json"
        self._download_state: Dict[str, Any] = {
            "status": "idle",
            "percent": 0.0,
            "completed_bytes": 0,
            "total_bytes": 0,
            "model": None,
            "message": "Ready to install",
            "error": None,
        }
        self._load_persisted_state()

        # Ensure cleanup and pause persistence on process exit
        atexit.register(self._on_app_exit)
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

    # ──────────────────────────────────────────────────────────────────────────
    # Model Download, Pause, Resume, and Cancellation Management
    # ──────────────────────────────────────────────────────────────────────────

    def _load_persisted_state(self) -> None:
        """Load any paused or interrupted download state from disk on startup."""
        try:
            if self._download_state_file.exists():
                data = json.loads(self._download_state_file.read_text(encoding="utf-8"))
                saved_status = data.get("status")
                # If app exited while downloading or starting, treat as paused
                if saved_status in ("downloading", "starting", "paused"):
                    pct = float(data.get("percent", 0.0))
                    comp = int(data.get("completed_bytes", 0))
                    tot = int(data.get("total_bytes", 0))
                    mod = data.get("model", self.recommended_model)
                    mb_done = round(comp / (1024 * 1024), 1)
                    mb_tot = round(tot / (1024 * 1024), 1)
                    tot_str = f" ({mb_done} MB / {mb_tot} MB)" if mb_tot > 0 else ""
                    self._download_state = {
                        "status": "paused",
                        "percent": pct,
                        "completed_bytes": comp,
                        "total_bytes": tot,
                        "model": mod,
                        "message": f"Download paused at {pct}%{tot_str}. Click Resume to continue.",
                        "error": None,
                    }
                    log.info("[OllamaManager] Restored paused download state for %s at %.1f%%", mod, pct)
                elif saved_status == "success":
                    self._clear_persisted_state()
        except Exception as exc:
            log.warning("[OllamaManager] Failed to load persisted download state: %s", exc)

    def _save_persisted_state(self, state: Dict[str, Any]) -> None:
        """Atomically persist current download state to disk."""
        try:
            temp_file = self._download_state_file.with_suffix(".tmp")
            payload = {
                "status": state.get("status", "idle"),
                "percent": state.get("percent", 0.0),
                "completed_bytes": state.get("completed_bytes", 0),
                "total_bytes": state.get("total_bytes", 0),
                "model": state.get("model") or self.recommended_model,
                "message": state.get("message", ""),
                "timestamp": time.time(),
            }
            temp_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_file.replace(self._download_state_file)
        except Exception as exc:
            log.debug("[OllamaManager] Could not save download state: %s", exc)

    def _clear_persisted_state(self) -> None:
        """Remove persisted download state file."""
        try:
            if self._download_state_file.exists():
                self._download_state_file.unlink(missing_ok=True)
        except Exception as exc:
            log.debug("[OllamaManager] Could not remove download state file: %s", exc)

    def _clean_partial_blobs(self) -> None:
        """Clean any partial layer files (*-partial*) in models/blobs directory."""
        try:
            blobs_dir = self.models_dir / "blobs"
            if blobs_dir.exists():
                for p in blobs_dir.glob("*-partial*"):
                    try:
                        p.unlink(missing_ok=True)
                    except Exception:
                        pass
        except Exception as exc:
            log.warning("[OllamaManager] Exception while cleaning partial blobs: %s", exc)

    def _on_app_exit(self) -> None:
        """Invoked on application exit: save pause state if in progress and ensure daemon termination."""
        try:
            with self._download_lock:
                if self._download_state.get("status") in ("downloading", "starting"):
                    self._download_state["status"] = "paused"
                    pct = self._download_state.get("percent", 0.0)
                    comp = self._download_state.get("completed_bytes", 0)
                    tot = self._download_state.get("total_bytes", 0)
                    mb_done = round(comp / (1024 * 1024), 1)
                    mb_tot = round(tot / (1024 * 1024), 1)
                    tot_str = f" ({mb_done} MB / {mb_tot} MB)" if mb_tot > 0 else ""
                    self._download_state["message"] = f"Download paused at {pct}%{tot_str}. Click Resume to continue."
                    self._save_persisted_state(self._download_state)
                    log.info("[OllamaManager] Application exiting during download; saved state as paused.")
        except Exception:
            pass
        self.terminate_service()

    def start_model_download(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Trigger background pull of model. Terminates daemon immediately when finished."""
        target_model = model_name or self.recommended_model
        with self._download_lock:
            if self._download_state["status"] in ("downloading", "starting"):
                return {"status": "busy", "message": "Model installation already in progress."}

            self._pause_requested = False
            self._cancel_requested = False

            self._download_state = {
                "status": "starting",
                "percent": 0.0,
                "completed_bytes": 0,
                "total_bytes": 0,
                "model": target_model,
                "message": f"Starting embedded Ollama daemon to install {target_model}...",
                "error": None,
            }
            self._save_persisted_state(self._download_state)

            pull_thread = threading.Thread(
                target=self._run_download_worker,
                args=(target_model,),
                daemon=True,
            )
            pull_thread.start()
            return {"status": "started", "model": target_model}

    def pause_model_download(self) -> Dict[str, Any]:
        """Gracefully pause active model download and terminate Ollama daemon immediately."""
        with self._download_lock:
            cur_status = self._download_state.get("status")
            if cur_status == "paused":
                return {"status": "paused", "state": dict(self._download_state)}

            if cur_status not in ("downloading", "starting"):
                return {"status": "not_downloading", "message": "No active download to pause."}

            self._pause_requested = True
            self._cancel_requested = False

            self._download_state["status"] = "paused"
            pct = self._download_state.get("percent", 0.0)
            comp = self._download_state.get("completed_bytes", 0)
            tot = self._download_state.get("total_bytes", 0)
            mb_done = round(comp / (1024 * 1024), 1)
            mb_tot = round(tot / (1024 * 1024), 1)
            tot_str = f" ({mb_done} MB / {mb_tot} MB)" if mb_tot > 0 else ""
            self._download_state["message"] = f"Download paused at {pct}%{tot_str}. Click Resume to continue."
            self._save_persisted_state(self._download_state)

            client = self._current_client
            if client:
                try:
                    client.close()
                except Exception:
                    pass

        # Terminate background Ollama daemon immediately - NO background processes running!
        log.info("[OllamaManager] Pausing download and terminating background daemon.")
        self.terminate_service()

        with self._download_lock:
            return {"status": "paused", "state": dict(self._download_state)}

    def resume_model_download(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Resume a paused or interrupted model download from where it left off."""
        with self._download_lock:
            cur_status = self._download_state.get("status")
            if cur_status in ("downloading", "starting"):
                return {"status": "busy", "message": "Download is already in progress."}

            target_model = model_name or self._download_state.get("model") or self.recommended_model
            self._pause_requested = False
            self._cancel_requested = False

            pct = self._download_state.get("percent", 0.0)
            self._download_state.update({
                "status": "starting",
                "model": target_model,
                "message": f"Resuming download of {target_model} from {pct}%...",
                "error": None,
            })
            self._save_persisted_state(self._download_state)

            pull_thread = threading.Thread(
                target=self._run_download_worker,
                args=(target_model,),
                daemon=True,
            )
            pull_thread.start()
            return {"status": "resumed", "model": target_model}

    def cancel_model_download(self) -> Dict[str, Any]:
        """Cancel the download, remove partial downloads from disk, and terminate daemon."""
        with self._download_lock:
            self._cancel_requested = True
            self._pause_requested = False

            client = self._current_client
            if client:
                try:
                    client.close()
                except Exception:
                    pass

            self._download_state = {
                "status": "cancelled",
                "percent": 0.0,
                "completed_bytes": 0,
                "total_bytes": 0,
                "model": None,
                "message": "Download cancelled. Ready to install.",
                "error": None,
            }
            self._clear_persisted_state()

        # Clean partial files from disk
        self._clean_partial_blobs()

        # Terminate background Ollama daemon immediately - NO background processes running!
        log.info("[OllamaManager] Download cancelled. Terminating background daemon.")
        self.terminate_service()

        with self._download_lock:
            # Set to idle so subsequent install can start freshly
            self._download_state["status"] = "idle"
            return {"status": "cancelled", "state": dict(self._download_state)}

    def _run_download_worker(self, model_name: str) -> None:
        """Worker thread: starts daemon, streams pull with HTTP Range support, and terminates daemon immediately."""
        try:
            if self._cancel_requested or self._pause_requested:
                return

            ready = self.start_service(timeout_s=15.0)
            if not ready:
                if self._cancel_requested or self._pause_requested:
                    return
                self._set_download_error("Could not launch embedded Ollama background service.")
                return

            if self._cancel_requested or self._pause_requested:
                return

            url = f"{self.base_url}/api/pull"
            with self._download_lock:
                self._download_state["message"] = f"Connecting to pull {model_name}..."

            client = httpx.Client(timeout=1800.0)
            with self._download_lock:
                self._current_client = client

            try:
                with client.stream("POST", url, json={"name": model_name, "stream": True}) as resp:
                    if resp.status_code != 200:
                        if not (self._cancel_requested or self._pause_requested):
                            self._set_download_error(f"HTTP {resp.status_code}: {resp.text}")
                        return

                    for line in resp.iter_lines():
                        if self._cancel_requested or self._pause_requested:
                            break
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
                                pct = self._download_state.get("percent", 0.0)
                                msg = status

                            is_success = "success" in status.lower()
                            with self._download_lock:
                                self._download_state.update({
                                    "status": "success" if is_success else "downloading",
                                    "percent": 100.0 if is_success else pct,
                                    "completed_bytes": completed,
                                    "total_bytes": total,
                                    "model": model_name,
                                    "message": f"Model {model_name} successfully installed!" if is_success else msg,
                                })
                                if total > 0:
                                    self._save_persisted_state(self._download_state)

                            if is_success:
                                log.info("[OllamaManager] Download complete: %s", model_name)
                                self._clear_persisted_state()
                                break
                        except Exception:
                            pass
            finally:
                with self._download_lock:
                    self._current_client = None
                try:
                    client.close()
                except Exception:
                    pass

        except Exception as exc:
            if self._pause_requested or self._cancel_requested:
                log.info("[OllamaManager] Download worker cleanly interrupted by pause/cancel.")
                return
            log.exception("[OllamaManager] Download worker error: %s", exc)
            err_str = str(exc)
            if "unexpected EOF" in err_str or "streaming" in err_str or "Timeout" in err_str:
                err_msg = "Model download was interrupted by a network timeout or connection reset. Note: Dr. Nutriloop's Clinical Knowledge Base is already fully functional without it! You can retry or resume the download whenever you have a stable high-speed internet connection."
            else:
                err_msg = err_str
            self._set_download_error(err_msg)
        finally:
            if self._pause_requested:
                with self._download_lock:
                    self._download_state["status"] = "paused"
                    pct = self._download_state.get("percent", 0.0)
                    comp = self._download_state.get("completed_bytes", 0)
                    tot = self._download_state.get("total_bytes", 0)
                    mb_done = round(comp / (1024 * 1024), 1)
                    mb_tot = round(tot / (1024 * 1024), 1)
                    tot_str = f" ({mb_done} MB / {mb_tot} MB)" if mb_tot > 0 else ""
                    self._download_state["message"] = f"Download paused at {pct}%{tot_str}. Click Resume to continue."
                    self._save_persisted_state(self._download_state)
                log.info("[OllamaManager] Download marked paused.")
            elif self._cancel_requested:
                with self._download_lock:
                    self._download_state = {
                        "status": "idle",
                        "percent": 0.0,
                        "completed_bytes": 0,
                        "total_bytes": 0,
                        "model": None,
                        "message": "Download cancelled. Ready to install.",
                        "error": None,
                    }
                    self._clear_persisted_state()
                self._clean_partial_blobs()
                log.info("[OllamaManager] Download marked cancelled and partial blobs purged.")

            # Ensure background daemon is terminated immediately:
            # "no background processes running when application shuts off / pauses / completes"
            log.info("[OllamaManager] Terminating background daemon post-worker.")
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
