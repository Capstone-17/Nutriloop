# -*- mode: python ; coding: utf-8 -*-
"""
Nutriloop.spec
──────────────
PyInstaller specification file to compile Nutriloop into an optimized Windows
desktop executable with an instantaneous native C-level splash screen.

Features:
  1. Instant Splash Screen: Pops up in < 50ms upon double-click using native pyi_splash,
     eliminating the silence during PyInstaller bootloader extraction.
  2. Single-Instance Protection: Coordinated with Windows Named Mutex in app_desktop.py.
  3. Optimized Bundling: Excludes test suites, IDE hooks, and unused frameworks to minimize archive size.
"""

import os
import shutil
import sys
from pathlib import Path

# Prevent bytecode generation and __pycache__ directory creation during PyInstaller build
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.building.splash import Splash

block_cipher = None
REPO_ROOT = Path.cwd()

# Data files to bundle inside sys._MEIPASS
datas = [
    (str(REPO_ROOT / "artifacts"), "artifacts"),
    (str(REPO_ROOT / "assets"), "assets"),
    (str(REPO_ROOT / "bin"), "bin"),
    (str(REPO_ROOT / "datasets"), "datasets"),
    (str(REPO_ROOT / "pc"), "pc"),
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
    "unittest",
    "unittest.mock",
    "numpy.testing",
]

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
        "tkinter",
        "tcl",
        "pytest",
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "cv2",
        "sqlalchemy",
        "mysql",
        "_mysql_connector",
        "MySQLdb",
        "psycopg2",
        "pysqlite2",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Native C-level splash screen: appears in < 50ms upon double-click before archive extraction
splash_img = str(REPO_ROOT / "assets" / "splash.png")
if not os.path.exists(splash_img):
    splash_img = str(REPO_ROOT / "assets" / "Nutriloop_2.png")

# Custom dynamic Tcl script to render and animate moving gold loading bar during bootloader extraction
CUSTOM_SPLASH_TCL = r'''
proc _ipc_server {channel clientaddr clientport} {
    set client_name [format <%s:%d> $clientaddr $clientport]

    chan configure $channel \
        -buffering none \
        -encoding utf-8 \
        -eofchar \x04 \
        -translation cr
    chan event $channel readable [list _ipc_caller $channel $client_name]
}

proc _ipc_caller {channel client_name} {
    chan gets $channel cmd

    if {[chan eof $channel]} {
        chan close $channel
        exit
    } elseif {![chan blocked $channel]} {
        if {[string match "update_text*" $cmd]} {
            global status_text _cur_progress _target_progress
            set first [expr {[string first "(" $cmd] + 1}]
            set last [expr {[string last ")" $cmd] - 1}]
            set status_text [string range $cmd $first $last]
            if {$status_text eq "READY" || $status_text eq "COMPLETE_100"} {
                set _target_progress 1.0
            }
        }
    }
}

set server_socket [socket -server _ipc_server -myaddr localhost 0]
set server_port [fconfigure $server_socket -sockname]
set env(_PYI_SPLASH_IPC) [lindex $server_port 2]

image create photo splash_image
splash_image put $_image_data
unset _image_data

package require Tk

set image_width [image width splash_image]
set image_height [image height splash_image]

if {[info exists _pyi_screen_geometry]} {
    set display_x $_pyi_screen_geometry(x)
    set display_y $_pyi_screen_geometry(y)
    set display_width $_pyi_screen_geometry(width)
    set display_height $_pyi_screen_geometry(height)
} else {
    set display_x 0
    set display_y 0
    set display_width [winfo screenwidth .]
    set display_height [winfo screenheight .]
}

set x_position [expr {int($display_x + 0.5*($display_width - $image_width))}]
set y_position [expr {int($display_y + 0.5*($display_height - $image_height))}]

frame .root

canvas .root.canvas \
    -width $image_width \
    -height $image_height \
    -borderwidth 0 \
    -highlightthickness 0

.root.canvas create image \
    [expr {$image_width / 2}] \
    [expr {$image_height / 2}] \
    -image splash_image

# Dynamic Segoe UI font for percentage counter
catch {font create SplashFont -family {Segoe UI} -size 10 -weight bold}

# Progress bar geometry matching splash.png track (x=170..590, y=372..382)
set _bar_x1 172
set _bar_y1 374
set _bar_max_x2 588
set _bar_y2 380
set _bar_width [expr {$_bar_max_x2 - $_bar_x1}]
set _cur_progress 0.04
set _target_progress 0.96

# Create loading bar shapes on canvas
.root.canvas create rectangle $_bar_x1 $_bar_y1 [expr {$_bar_x1 + int($_cur_progress * $_bar_width)}] $_bar_y2 \
    -fill {#fbbf24} -outline {} -tags splash_bar
.root.canvas create rectangle $_bar_x1 $_bar_y1 [expr {$_bar_x1 + int($_cur_progress * $_bar_width)}] [expr {$_bar_y1 + 2}] \
    -fill {#fffbeb} -outline {} -tags splash_shine
.root.canvas create text [expr {$image_width / 2}] 402 \
    -text {4%} -fill {#fbbf24} -font SplashFont -tags splash_pct

proc _animate_bar {} {
    global _bar_x1 _bar_y1 _bar_y2 _bar_width _cur_progress _target_progress image_width
    if {$_cur_progress < $_target_progress} {
        set rem [expr {$_target_progress - $_cur_progress}]
        set step [expr {$rem * 0.024 + 0.003}]
        set _cur_progress [expr {$_cur_progress + $step}]
        if {$_cur_progress > $_target_progress} {
            set _cur_progress $_target_progress
        }
    }
    set cur_x [expr {int($_bar_x1 + $_cur_progress * $_bar_width)}]
    .root.canvas coords splash_bar $_bar_x1 $_bar_y1 $cur_x $_bar_y2
    .root.canvas coords splash_shine $_bar_x1 $_bar_y1 $cur_x [expr {$_bar_y1 + 2}]
    set pct [expr {int($_cur_progress * 100)}]
    .root.canvas itemconfigure splash_pct -text "$pct%"
    update idletasks
    after 35 _animate_bar
}

after 40 _animate_bar

wm attributes . -transparentcolor magenta
.root.canvas configure -background magenta

pack .root
grid .root.canvas -column 0 -row 0 -columnspan 1 -rowspan 2

wm overrideredirect . 1
wm geometry . +${x_position}+${y_position}
wm attributes . -topmost 1

raise .
'''

class AnimatedSplash(Splash):
    def generate_script(self):
        script = CUSTOM_SPLASH_TCL
        if self.script_name:
            try:
                with open(self.script_name, "w", encoding="utf-8") as f:
                    f.write(script)
            except Exception:
                pass
        return script

# Force-clean any cached splash resources so PyInstaller always compiles fresh Tcl script
if (REPO_ROOT / "build").exists():
    for stale_splash in (REPO_ROOT / "build").rglob("*Splash*"):
        try:
            if stale_splash.is_file():
                stale_splash.unlink()
        except Exception:
            pass

splash = AnimatedSplash(
    splash_img,
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,
    text_size=12,
)


exe = EXE(
    pyz,
    a.scripts,
    splash,
    splash.binaries,
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
    icon=str(REPO_ROOT / "assets" / "Nutriloop_1.ico"),
)

# Purge any __pycache__ left behind during PyInstaller analysis
try:
    for target in REPO_ROOT.rglob("__pycache__"):
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
except Exception:
    pass
