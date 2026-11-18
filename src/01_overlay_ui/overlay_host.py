# overlay_host.py — Main overlay host window launcher.
#
# Execution path:
#   live source (tosu_source) -> analysis_coordinator -> bridge -> overlay.js
#   audio_service -> bridge -> overlay.js
#
# Decoupled design: the frontend is source-agnostic (WebSocket, local stream, or server).
# Changing the event source only requires modifying the event producer rather than the UI.
# Replaces old legacy coupling between _BridgeRuntime and ui.py.

import logging
import json
import os
import sys
import threading
import time
from pathlib import Path

import webview

logger = logging.getLogger(__name__)

# Resolve base directory for HTML assets.
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys._MEIPASS)
else:
    _BASE_DIR = Path(__file__).resolve().parent

_WEB_DIR = _BASE_DIR / "web"

# Ensure src directories are importable
_SRC = str(Path(__file__).resolve().parent.parent)
for _sub in ("", "02_runtime_bridge", "07_model", "01_overlay_ui", os.path.join("03_engine_reference", "sr_core")):
    _p = os.path.join(_SRC, _sub) if _sub else _SRC
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ── Startup validation ──────────────────────────────────────────────────

def _get_settings_path() -> Path:
    """Returns %APPDATA%\\DanOverlay\\settings.json on Windows,
    ~/.danoverlay/settings.json elsewhere."""
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA") or Path.home())
    else:
        base = Path.home() / ".config"
    settings_dir = base / "DanOverlay"
    settings_dir.mkdir(parents=True, exist_ok=True)
    return settings_dir / "settings.json"

_REQUIRED_CONFIG = [
    "config/role_scales.json",
    "config/skin_dimensions.json",
]


def _resolve(rel):
    """Resolve a path relative to the install root (frozen or dev)."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[2]  # repo root
    return base / rel


def _validate_startup():
    """Check required files exist.  Returns list of missing path strings."""
    missing = []
    for rel in _REQUIRED_CONFIG:
        p = _resolve(rel)
        if not p.exists():
            missing.append(rel)
    return missing


# ── Skin dimensions ─────────────────────────────────────────────────────
#
# One table for both window styles.  `window_outer` is the size that includes
# the OS border and title bar, which is what the window needs in framed mode;
# `frameless` is the same content area with no chrome.  Keeping both in one
# place stops the numbers from drifting between the JS and the host.

def _load_skin_dimensions():
    try:
        with open(_resolve("config/skin_dimensions.json"),
                  encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        logger.warning("skin dimensions unavailable: %s", exc)
        return {"skins": {}}
    return data


_SKIN_DIMENSIONS = _load_skin_dimensions()


def get_skin_dimensions():
    """Return the per-skin size table so the UI can size the window correctly.

    Each entry is `{skin: {"layouts": {layout: {"viewport": {...}, "window_outer": {...}}}}}`.
    """
    return _SKIN_DIMENSIONS


def get_skin_canonical_window_size(skin_id: str, layout: str = "") -> tuple[int, int]:
    """Get the canonical (outer_w, outer_h) for a skin to size the Win32 window (collapsed by default)."""
    skin_str = str(skin_id)
    skin_meta = _SKIN_DIMENSIONS.get("skins", {}).get(skin_str)
    if not skin_meta:
        return 700, 320
    layouts = skin_meta.get("layouts", {})
    target_layout = layout
    if not target_layout or target_layout not in layouts:
        if "collapsed" in layouts:
            target_layout = "collapsed"
        elif "compact" in layouts and skin_str == "9":
            target_layout = "compact"
        elif "complete" in layouts:
            target_layout = "complete"
        elif "default" in layouts:
            target_layout = "default"
        else:
            target_layout = next(iter(layouts.keys()))

    spec = layouts.get(target_layout, {})
    outer = spec.get("window_outer", {})
    w = outer.get("w", 700)
    h = outer.get("h", 320)
    return int(w), int(h)


# ── Window modes ────────────────────────────────────────────────────────

# Opened on first launch; user picks resize behavior in the UI.
_APP_VERSION = "3.2"
_APP_TITLE = f"DanOverlay {_APP_VERSION} — by 8DOUL (discord: agent_ale)"
_DEFAULT_MODE = {
    "label":    f"DanOverlay {_APP_VERSION}",
    "width":    700, "height": 320, "min_size": (250, 100),
}

# Aspect ratio (width / height) locked when the user picks the "Locked" mode.
_ASPECT_RATIO = _DEFAULT_MODE["width"] / _DEFAULT_MODE["height"]  # 700/320 â‰ˆ 2.1875

# Module-level list: keeps WndProc callbacks alive to prevent GC
_aspect_wndproc_ref: list = []
# Module-level dict: maps HWND -> original WndProc address for uninstall
_aspect_orig_proc: dict[int, int] = {}
# Module-level dict: maps HWND -> active aspect ratio float
_aspect_ratios: dict[int, float] = {}


def _install_aspect_ratio_lock(hwnd: int, ratio: float) -> None:
    """Subclass the Win32 window procedure to enforce a fixed width/height ratio
    during user-driven resize.  Intercepts WM_SIZING and adjusts the proposed
    RECT so that width/height == ratio at all times.

    Only relevant on Windows.  Safe to call from a non-UI thread after the
    window has been fully created.
    """
    _aspect_ratios[hwnd] = ratio
    if hwnd in _aspect_orig_proc:
        logger.info("Updated aspect-ratio lock on HWND %s (ratio=%.4f)", hwnd, ratio)
        return

    import ctypes
    import ctypes.wintypes as W

    WM_SIZING        = 0x0214
    GWLP_WNDPROC     = -4
    WMSZ_LEFT        = 1
    WMSZ_RIGHT       = 2
    WMSZ_TOP         = 3
    WMSZ_TOPLEFT     = 4
    WMSZ_TOPRIGHT    = 5
    WMSZ_BOTTOM      = 6
    WMSZ_BOTTOMLEFT  = 7
    WMSZ_BOTTOMRIGHT = 8

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left",   ctypes.c_long),
            ("top",    ctypes.c_long),
            ("right",  ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    LRESULT = ctypes.c_longlong
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)

    user32 = ctypes.windll.user32
    user32.SetWindowLongPtrW.restype  = ctypes.c_longlong
    user32.SetWindowLongPtrW.argtypes = [W.HWND, ctypes.c_int, ctypes.c_longlong]
    user32.CallWindowProcW.restype    = ctypes.c_longlong
    user32.CallWindowProcW.argtypes   = [
        ctypes.c_longlong, W.HWND, W.UINT, W.WPARAM, W.LPARAM
    ]

    orig_proc: list[int] = [0]

    def _wndproc(hwnd_val, msg, wparam, lparam) -> int:
        if msg == WM_SIZING:
            active_ratio = _aspect_ratios.get(hwnd_val, ratio)
            rect_ptr = ctypes.cast(lparam, ctypes.POINTER(RECT))
            r = rect_ptr.contents
            w = r.right  - r.left
            h = r.bottom - r.top

            if wparam in (WMSZ_LEFT, WMSZ_RIGHT):
                # Horizontal drag — width is primary, adjust height downward
                r.bottom = r.top + max(1, round(w / active_ratio))
            elif wparam in (WMSZ_TOP, WMSZ_BOTTOM):
                # Vertical drag — height is primary, adjust width rightward
                r.right = r.left + max(1, round(h * active_ratio))
            elif wparam in (WMSZ_TOPLEFT, WMSZ_TOPRIGHT):
                # Corner drag from top — width is primary, adjust top edge
                r.top = r.bottom - max(1, round(w / active_ratio))
            else:  # BOTTOMLEFT, BOTTOMRIGHT
                # Corner drag from bottom — width is primary, adjust bottom edge
                r.bottom = r.top + max(1, round(w / active_ratio))

            return 1  # TRUE — message handled

        return user32.CallWindowProcW(orig_proc[0], hwnd_val, msg, wparam, lparam)

    proc = WNDPROC(_wndproc)
    _aspect_wndproc_ref.append(proc)  # prevent GC
    proc_addr = ctypes.cast(proc, ctypes.c_void_p).value
    orig_proc[0] = user32.SetWindowLongPtrW(W.HWND(hwnd), GWLP_WNDPROC, proc_addr)
    _aspect_orig_proc[hwnd] = orig_proc[0]  # save for uninstall
    logger.info("Aspect-ratio lock installed on HWND %s (ratio=%.4f)", hwnd, ratio)


def _show_error_dialog(title, message):
    """Show a native error dialog without requiring a console window."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR
    # On other platforms we have no console either — log is already on disk.


# ── Overlay launcher ────────────────────────────────────────────────────

def _find_webview2_runtime() -> str | None:
    """Scan common WebView2 install locations and return the versioned path.

    Some users have Edge/WebView2 installed under Program Files (x86) or in a
    per-user location. pywebview respects WEBVIEW2_RUNTIME_PATH if we set it
    before the window is created. We only set it when it isn't already provided
    by the environment (so a manual override still works).
    """
    if sys.platform != "win32":
        return None

    import glob

    search_roots = [
        r"C:\Program Files (x86)\Microsoft\EdgeWebView\Application",
        r"C:\Program Files\Microsoft\EdgeWebView\Application",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\EdgeWebView\Application"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\Application"),
    ]

    candidates: list[tuple[tuple[int, ...], str]] = []
    for root in search_roots:
        for entry in glob.glob(os.path.join(root, "*")):
            if not os.path.isdir(entry):
                continue
            # Versioned dirs look like "146.0.3856.109"
            parts = os.path.basename(entry).split(".")
            if len(parts) == 4 and all(p.isdigit() for p in parts):
                candidates.append((tuple(int(p) for p in parts), entry))

    if not candidates:
        return None

    # Return the highest version found
    candidates.sort(reverse=True)
    return candidates[0][1]


def _is_webview2_installed() -> bool:
    """Check whether WebView2 Runtime is registered in the Windows registry.

    This is the authoritative check used before creating the window.  The
    filesystem scan in _find_webview2_runtime() can miss per-machine installs
    that live in non-standard locations but are properly registered.
    """
    if sys.platform != "win32":
        return True  # non-Windows: assume OK, pywebview uses a different backend

    import winreg

    # WebView2 Runtime GUID — same for all versions
    _WV2_GUID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    _REG_PATHS = [
        # Per-machine install (most common)
        rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{_WV2_GUID}",
        rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WV2_GUID}",
        # Per-user install
        rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{_WV2_GUID}",
    ]
    _HIVES = [
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_READ | winreg.KEY_WOW64_32KEY),
        (winreg.HKEY_LOCAL_MACHINE, winreg.KEY_READ | winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_CURRENT_USER,  winreg.KEY_READ),
    ]

    for hive, flags in _HIVES:
        for path in _REG_PATHS:
            try:
                key = winreg.OpenKey(hive, path, 0, flags)
                winreg.CloseKey(key)
                return True
            except OSError:
                continue

    # Also accept if Edge itself is installed — it bundles WebView2
    _EDGE_PATHS = [
        rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{{56EB18F8-B008-4CBD-B6D2-8C97FE7E9062}}",  # Edge stable
    ]
    for hive, flags in _HIVES:
        for path in _EDGE_PATHS:
            try:
                key = winreg.OpenKey(hive, path, 0, flags)
                winreg.CloseKey(key)
                return True
            except OSError:
                continue

    return False


def launch():
    """Launch the Dan Overlay with the event-driven architecture."""
    # ── Pre-flight validation ──────────────────────────────────
    missing = _validate_startup()
    if missing:
        msg = "Missing required files:\n\n" + "\n".join(f"  âœ—  {m}" for m in missing)
        msg += "\n\nPlease make sure you downloaded the full distribution.\nCheck DanOverlay_error.txt for details."
        _show_error_dialog("DanOverlay — Startup Error", msg)
        return
    # ── WebView2 Runtime check ─────────────────────────
    # A blank white window is almost always caused by WebView2 not being
    # installed.  Check the registry before even trying to create the window so
    # we can show an actionable message instead of a silent blank screen.
    if not _is_webview2_installed():
        _show_error_dialog(
            "DanOverlay — Missing Component",
            "The overlay requires Microsoft WebView2 Runtime to run.\n\n"
            "If you see a blank window or the overlay doesn't open, "
            "install WebView2 Runtime from:\n\n"
            "  https://go.microsoft.com/fwlink/p/?LinkId=2124703\n\n"
            "(It's free and takes under a minute. "
            "Most PCs already have it if Microsoft Edge is installed.)",
        )
        return
    # Auto-detect WebView2 runtime when the user hasn't set the path manually.
    # Fixes black-screen issues on machines where Edge/WebView2 lives in a
    # non-default location (e.g. Program Files (x86) instead of Program Files).
    if not os.environ.get("WEBVIEW2_RUNTIME_PATH"):
        detected = _find_webview2_runtime()
        if detected:
            os.environ["WEBVIEW2_RUNTIME_PATH"] = detected
            logger.info("WebView2 runtime auto-detected: %s", detected)

    # Disable GPU for OBS capture compatibility and fix blank-screen on
    # systems with problematic GPU drivers or restrictive security policies.
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        "--disable-gpu "
        "--disable-gpu-compositing "
        "--disable-software-rasterizer "
        "--disable-gpu-sandbox "
        "--no-sandbox "
        "--allow-file-access-from-files"
    )

    overlay_url = _build_overlay_url()
    _run_overlay_session(_DEFAULT_MODE, overlay_url)


def _build_overlay_url() -> str:
    """Read 'skin' from settings.json and return the corresponding HTML URL.
    skin "2"  â†’ ui-2/index.html (classic horizontal design)
    skin "3"  â†’ ui-3/index.html (density graph design)
    skin "4"  â†’ ui-4/index.html (ring monolith design)
    skin "5"  â†’ ui-5/index.html (broadcast bar design)
    skin "6"  â†’ ui-6/index.html (big type design)
    anything else â†’ index.html (default design)
    """
    skin = "1"
    try:
        path = _get_settings_path()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            skin = str(data.get("skin", "1"))
    except Exception:
        pass

    if skin == "2":
        html_file = _WEB_DIR / "ui-2" / "index.html"
    elif skin == "3":
        html_file = _WEB_DIR / "ui-3" / "index.html"
    elif skin == "4":
        html_file = _WEB_DIR / "ui-4" / "index.html"
    elif skin == "5":
        html_file = _WEB_DIR / "ui-5" / "index.html"
    elif skin == "6":
        html_file = _WEB_DIR / "ui-6" / "index.html"
    elif skin == "7":
        html_file = _WEB_DIR / "ui-7" / "index.html"
    elif skin == "8":
        html_file = _WEB_DIR / "ui-8" / "index.html"
    elif skin == "9":
        html_file = _WEB_DIR / "ui-9" / "index.html"
    elif skin == "10":
        html_file = _WEB_DIR / "ui-10" / "index.html"
    elif skin == "11":
        html_file = _WEB_DIR / "ui-11" / "index.html"
    elif skin == "12":
        html_file = _WEB_DIR / "ui-12" / "index.html"
    else:
        html_file = _WEB_DIR / "index.html"

    return "file:///" + str(html_file).replace("\\", "/")


def _run_overlay_session(cfg, overlay_url):
    """Run a single overlay session until the window is closed."""
    from events import EventBus, ANALYSIS_COMPLETE, MAP_CHANGED, NOTIFICATION
    from bridge import OverlayBridge
    from audio_service import AudioService
    from analysis_coordinator import AnalysisCoordinator
    from tosu_source import run as tosu_run
    try:
        from etterna import run as etterna_run
    except ImportError:
        from etterna.etterna_source import run as etterna_run

    event_bus = EventBus()
    stop_event = threading.Event()
    state_lock = threading.Lock()

    # Simple dictionary for cleanup references to avoid scattered global state
    runtime = {"bridge": None, "audio": None}
    chart_state = {"map_info": None, "analysis_result": None}

    def _remember_map(map_info):
        with state_lock:
            chart_state["map_info"] = map_info
            chart_state["analysis_result"] = None

    def _remember_analysis(result):
        with state_lock:
            chart_state["analysis_result"] = result

    event_bus.subscribe(MAP_CHANGED, _remember_map)
    event_bus.subscribe(ANALYSIS_COMPLETE, _remember_analysis)

    def on_window_closed():
        # Shut down the bridge synchronously first so no new JS calls are
        # dispatched to a window that is already being destroyed.  All other
        # cleanup (audio, tosu thread, event bus) is cheap and can run in the
        # background — we must return from this callback quickly or the Win32
        # message loop stalls and Windows shows the 'not responding' dialog.
        if runtime.get("bridge"):
            runtime["bridge"].shutdown()

        def _cleanup():
            if runtime.get("audio"):
                runtime["audio"].shutdown()
            stop_event.set()
            event_bus.shutdown()

        threading.Thread(target=_cleanup, daemon=True, name="overlay-cleanup").start()

    # Read settings from settings.json to start the window with exact skin/custom dimensions.
    # This prevents size flashes or timing bugs on first load before JS is ready.
    _start_w = cfg["width"]
    _start_h = cfg["height"]
    try:
        _settings_path = _get_settings_path()
        if _settings_path.exists():
            _saved = json.loads(_settings_path.read_text(encoding="utf-8"))
            _skin = str(_saved.get("skin", "1"))
            # Always initialize the window with the canonical dimensions of the active skin (collapsed by default)
            _start_w, _start_h = get_skin_canonical_window_size(_skin)
    except Exception as exc:
        logger.warning("Failed to load initial window size from settings: %s", exc)
    except Exception as exc:
        logger.warning("Failed to load initial window size from settings: %s", exc)

    window = webview.create_window(
        title=_APP_TITLE,
        url=overlay_url,
        width=_start_w,
        height=_start_h,
        min_size=cfg["min_size"],
        resizable=True,
        on_top=False,   # manual overlay pin toggle via Tab
        background_color="#000000",
        text_select=False,
    )
    window.events.closing += on_window_closed

    def on_start(_window):
        # Single bridge channel to execute JS calls sequentially on the webview thread.
        bridge = OverlayBridge(_window, event_bus)
        runtime["bridge"] = bridge

        def on_generate_chart():
            from chart_export import generate_chart_from_state
            import json as _json
            import threading as _thr

            print("[CHART-PY] on_generate_chart called")
            result = generate_chart_from_state(chart_state, state_lock=state_lock)
            status = result.get("status")
            message = result.get("message", "")
            chart_payload = result.get("payload")

            if status != "ok" or chart_payload is None:
                print(f"[CHART-PY] failed: status={status}, message={message}")
                if status == "busy":
                    event_bus.emit(NOTIFICATION, {"message": message or "Already generating"})
                elif status == "error":
                    event_bus.emit(NOTIFICATION, {"message": f"Error: {message}" if message else "Could not generate image"})
                return {"status": status, "message": message}

            # Push the payload to JS via evaluate_js from a background thread.
            # We CANNOT return the payload through pywebview's return value
            # because nps_data can be huge (thousands of entries) and
            # pywebview silently fails on large return values.
            # We also CANNOT call evaluate_js from inside this callback
            # because it would deadlock the pywebview UI thread.
            # Solution: spawn a thread, let this callback return first,
            # then push the data.
            def _push():
                import time
                from pathlib import Path
                time.sleep(0.1)  # let the JS callback return first
                try:
                    js_payload = _json.dumps(chart_payload, ensure_ascii=False)
                    
                    # 1. Read the autonomous chart renderer script
                    renderer_path = Path(__file__).parent / "web" / "graph" / "chart_renderer.js"
                    renderer_code = renderer_path.read_text(encoding="utf-8")
                    
                    # 2. Inject the function definition into the WebView
                    _window.evaluate_js(renderer_code)
                    
                    # 3. Store payload to avoid inline JSON size limits
                    _window.evaluate_js(f"window.__chartPayload = {js_payload};")
                    
                    # 4. Execute the render process
                    _window.evaluate_js("renderExportChart(window.__chartPayload)")
                    print("[CHART-PY] Autonomous renderExportChart executed successfully")
                except Exception as exc:
                    import traceback
                    print(f"[CHART-PY] evaluate_js error: {exc}")
                    traceback.print_exc()

            _thr.Thread(target=_push, daemon=True).start()
            print("[CHART-PY] background push scheduled")
            return {"status": "ok", "message": "Generando..."}

        _window.expose(on_generate_chart)

        _last_save_time = [0.0]
        def save_chart(base64_image: str, map_name: str) -> dict:
            """Called by JS after rendering the chart canvas to save the PNG."""
            import time
            now = time.time()
            if now - _last_save_time[0] < 1.0:
                print(f"[CHART-PY] save_chart ignored (duplicate call within 1s)")
                return {"status": "ok", "message": "Ignored duplicate"}
            _last_save_time[0] = now
            print(f"[CHART-PY] save_chart called, map_name={map_name}, b64_len={len(base64_image)}")
            result = bridge.save_chart(base64_image, map_name)
            print(f"[CHART-PY] save_chart result: {result}")
            return result

        _window.expose(save_chart)

        def log_js_error(msg: str):
            print(f"\\n{'='*50}\\n[CRITICAL JS ERROR in renderExportChart]\\n{msg}\\n{'='*50}\\n")
            event_bus.emit(NOTIFICATION, {"message": "JS rendering error. Check console."})
            
        _window.expose(log_js_error)

        def load_settings() -> str:
            """Return the saved settings JSON string, or empty string if none."""
            try:
                path = _get_settings_path()
                if path.is_file():
                    return path.read_text(encoding="utf-8")
            except Exception as exc:
                logger.warning("load_settings failed: %s", exc)
            return ""

        def save_settings(data: str) -> None:
            """Persist settings JSON to %APPDATA%/DanOverlay/settings.json."""
            try:
                parsed = json.loads(data)  # validate before writing
                _get_settings_path().write_text(data, encoding="utf-8")
                if "engine" in parsed and "coordinator" in runtime:
                    runtime["coordinator"].set_engine(parsed["engine"])
            except Exception as exc:
                logger.warning("save_settings failed: %s", exc)

        _window.expose(load_settings)
        _window.expose(save_settings)

        # Wait for the page to fully load before sending events to JS.
        # Poll evaluate_js until window.__overlayFromPython is functional.
        # During this delay all bridge._send() calls are silently buffered.
        def _wait_for_js_ready():
            import time
            waited = 0.0
            max_wait = 8.0
            while waited < max_wait:
                # Check if the JS function exists by evaluating a no-op call.
                # A try-catch inside JS will report back via pywebview's error
                # mechanism if the function doesn't exist yet.
                try:
                    ok = _window.evaluate_js(
                        "typeof window.__overlayFromPython === 'function'"
                    )
                    if ok:
                        bridge.mark_ready()
                        bridge._send({"type": "bridge-init"})
                        logger.info("bridge ready after %.1f s", waited)
                        return
                except Exception:
                    pass
                time.sleep(0.10)
                waited += 0.10
            logger.warning(
                "bridge: page not ready after %.1f s — forcing ready", max_wait
            )
            bridge.mark_ready()
        threading.Thread(
            target=_wait_for_js_ready, daemon=True, name="bridge-ready"
        ).start()

        def set_window_size_outer(w: int, h: int):
            if sys.platform != "win32":
                try:
                    _window.resize(int(w), int(h))
                except Exception:
                    pass
                return
            import ctypes
            import ctypes.wintypes as W
            try:
                hwnd_val = ctypes.windll.user32.FindWindowW(None, _APP_TITLE)
                if not hwnd_val:
                    return
                user32 = ctypes.windll.user32
                if hwnd_val in _aspect_orig_proc and h > 0:
                    _aspect_ratios[hwnd_val] = float(w) / float(h)
                SWP_NOMOVE = 0x0002
                SWP_NOZORDER = 0x0004
                SWP_NOACTIVATE = 0x0010
                user32.SetWindowPos(
                    W.HWND(hwnd_val), 0, 0, 0,
                    int(w), int(h),
                    SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)
            except Exception as exc:
                logger.warning("set_window_size_outer failed: %s", exc)

        _window.expose(set_window_size_outer)

        def switch_skin(skin_id: str) -> None:
            """Navigate the webview to the correct skin HTML.

            Returns immediately so that pywebview can deliver the JS return-value
            callback before the page is destroyed.  The actual load_url() runs in
            a daemon thread a moment later.
            """
            def _navigate():
                time.sleep(0.05)
                # Apply canonical collapsed window dimensions for the new skin immediately
                cw, ch = get_skin_canonical_window_size(skin_id)
                set_window_size_outer(cw, ch)
                time.sleep(0.08)

                if skin_id == "2":
                    html_file = _WEB_DIR / "ui-2" / "index.html"
                elif skin_id == "3":
                    html_file = _WEB_DIR / "ui-3" / "index.html"
                elif skin_id == "4":
                    html_file = _WEB_DIR / "ui-4" / "index.html"
                elif skin_id == "5":
                    html_file = _WEB_DIR / "ui-5" / "index.html"
                elif skin_id == "6":
                    html_file = _WEB_DIR / "ui-6" / "index.html"
                elif skin_id == "7":
                    html_file = _WEB_DIR / "ui-7" / "index.html"
                elif skin_id == "8":
                    html_file = _WEB_DIR / "ui-8" / "index.html"
                elif skin_id == "9":
                    html_file = _WEB_DIR / "ui-9" / "index.html"
                elif skin_id == "10":
                    html_file = _WEB_DIR / "ui-10" / "index.html"
                elif skin_id == "11":
                    html_file = _WEB_DIR / "ui-11" / "index.html"
                elif skin_id == "12":
                    html_file = _WEB_DIR / "ui-12" / "index.html"
                else:
                    html_file = _WEB_DIR / "index.html"
                new_url = "file:///" + str(html_file).replace("\\", "/")
                logger.info("switch_skin -> %s", new_url)
                _window.load_url(new_url)
                # Wait for the new page to finish loading, then initialise it.
                time.sleep(0.8)
                bridge._send({"type": "bridge-init"})
                # Re-send last-known tosu/map state so the fresh page has
                # something to show without waiting for the next change event.
                time.sleep(0.08)
                bridge.resync()

            threading.Thread(target=_navigate, daemon=True, name="switch-skin").start()

        _window.expose(switch_skin)

        # Resize mode toggle: "free" = unrestricted, "locked" = aspect-ratio enforced.
        def set_resize_mode(mode: str, ratio: float = 0.0):
            if sys.platform != "win32":
                return
            import ctypes
            import ctypes.wintypes as W
            try:
                hwnd_val = ctypes.windll.user32.FindWindowW(
                    None,
                    _APP_TITLE,
                )
                if not hwnd_val:
                    logger.warning("set_resize_mode: HWND not found")
                    return

                if mode == "locked":
                    if ratio and float(ratio) > 0:
                        lock_ratio = float(ratio)
                    else:
                        import ctypes as _ct
                        import ctypes.wintypes as _W
                        class _RECT(_ct.Structure):
                            _fields_ = [("left",_ct.c_long),("top",_ct.c_long),
                                        ("right",_ct.c_long),("bottom",_ct.c_long)]
                        _r = _RECT()
                        _ct.windll.user32.GetWindowRect(_W.HWND(hwnd_val), _ct.byref(_r))
                        _cw = _r.right - _r.left
                        _ch = _r.bottom - _r.top
                        lock_ratio = (_cw / _ch) if _ch > 0 else _ASPECT_RATIO
                    _install_aspect_ratio_lock(hwnd_val, lock_ratio)
                else:
                    # Restore the original WndProc saved when lock was installed.
                    _aspect_ratios.pop(hwnd_val, None)
                    orig = _aspect_orig_proc.pop(hwnd_val, None)
                    if orig:
                        user32 = ctypes.windll.user32
                        user32.SetWindowLongPtrW.restype  = ctypes.c_longlong
                        user32.SetWindowLongPtrW.argtypes = [W.HWND, ctypes.c_int, ctypes.c_longlong]
                        GWLP_WNDPROC = -4
                        user32.SetWindowLongPtrW(W.HWND(hwnd_val), GWLP_WNDPROC, orig)
                        _aspect_wndproc_ref.clear()
                        logger.info("Aspect-ratio lock removed from HWND %s", hwnd_val)
            except Exception as exc:
                logger.warning("set_resize_mode %s failed: %s", mode, exc)

        _window.expose(set_resize_mode)

        # Reset the window to its default 700Ã—320 size and remove any aspect lock.
        def reset_window_size():
            if sys.platform == "win32":
                import ctypes
                import ctypes.wintypes as W
                try:
                    hwnd_val = ctypes.windll.user32.FindWindowW(
                        None,
                        _APP_TITLE,
                    )
                    if hwnd_val:
                        _aspect_ratios.pop(hwnd_val, None)
                        orig = _aspect_orig_proc.pop(hwnd_val, None)
                        if orig:
                            u32 = ctypes.windll.user32
                            u32.SetWindowLongPtrW.restype  = ctypes.c_longlong
                            u32.SetWindowLongPtrW.argtypes = [W.HWND, ctypes.c_int, ctypes.c_longlong]
                            u32.SetWindowLongPtrW(W.HWND(hwnd_val), -4, orig)
                            _aspect_wndproc_ref.clear()
                except Exception as exc:
                    logger.warning("reset_window_size (win32) failed: %s", exc)
            try:
                _window.resize(_DEFAULT_MODE["width"], _DEFAULT_MODE["height"])
            except Exception as exc:
                logger.warning("reset_window_size resize failed: %s", exc)

        _window.expose(reset_window_size)

        # Resize the window to an explicit (width, height) — used by layout mode changes.
        # Pass w=-1 to keep the current width unchanged (only adjust height).
        def set_window_size(w: int, h: int):
            """Resize so the CLIENT area is exactly w x h.

            Every number in skin_dimensions.json is a viewport size (see
            docs/skin-dimensions.md), so the requested size is the client
            area and the frame plus title bar are added on top with
            AdjustWindowRectEx.  Handing the viewport straight to SetWindowPos is
            what made every skin come out ~14 px short in both axes.
            """
            target_w = int(w)
            target_h = int(h)
            if sys.platform != "win32":
                try:
                    _window.resize(target_w, target_h)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("set_window_size fallback failed: %s", exc)
                return
            import ctypes
            import ctypes.wintypes as W
            try:
                hwnd_val = ctypes.windll.user32.FindWindowW(None, _APP_TITLE)
                if not hwnd_val:
                    return

                class _RECT(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

                user32 = ctypes.windll.user32
                user32.GetWindowLongPtrW.restype = ctypes.c_longlong
                user32.GetWindowLongPtrW.argtypes = [W.HWND, ctypes.c_int]

                cur_c = _RECT()
                user32.GetClientRect(W.HWND(hwnd_val), ctypes.byref(cur_c))
                cur_client_w = max(1, cur_c.right - cur_c.left)
                cur_client_h = max(1, cur_c.bottom - cur_c.top)

                eff_client_w = cur_client_w if target_w < 0 else target_w
                eff_client_h = cur_client_h if target_h < 0 else target_h

                r = _RECT(0, 0, eff_client_w, eff_client_h)
                style = user32.GetWindowLongPtrW(W.HWND(hwnd_val), -16)
                ex_style = user32.GetWindowLongPtrW(W.HWND(hwnd_val), -20)
                user32.AdjustWindowRectEx(ctypes.byref(r), style, False, ex_style)
                final_w = r.right - r.left
                final_h = r.bottom - r.top

                if hwnd_val in _aspect_orig_proc and final_h > 0:
                    _aspect_ratios[hwnd_val] = float(final_w) / float(final_h)

                SWP_NOMOVE = 0x0002
                SWP_NOZORDER = 0x0004
                SWP_NOACTIVATE = 0x0010
                user32.SetWindowPos(
                    W.HWND(hwnd_val), 0, 0, 0,
                    int(final_w), int(final_h),
                    SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE)
            except Exception as exc:  # noqa: BLE001
                logger.warning("set_window_size (win32) failed: %s", exc)

        _window.expose(set_window_size)
        _window.expose(get_skin_dimensions)

        # Return the current window height so JS can save the real size before
        # expanding for the settings panel.
        def get_window_height() -> int:
            try:
                return int(_window.height)
            except Exception:
                return _DEFAULT_MODE["height"]

        _window.expose(get_window_height)

        def get_window_width() -> int:
            try:
                return int(_window.width)
            except Exception:
                return _DEFAULT_MODE["width"]

        _window.expose(get_window_width)



        def check_osu_running() -> dict:
            """Check whether osu! or Etterna processes are currently running."""
            osu_running = False
            etterna_running = False
            if sys.platform == "win32":
                try:
                    import subprocess
                    CREATE_NO_WINDOW = 0x08000000
                    result = subprocess.run(
                        ["tasklist", "/NH"],
                        capture_output=True, text=True, timeout=3,
                        creationflags=CREATE_NO_WINDOW
                    )
                    out = result.stdout.lower()
                    osu_running = ("osu!.exe" in out or "osu.exe" in out)
                    etterna_running = ("etterna.exe" in out or "stepmania.exe" in out)
                except Exception:
                    pass

            return {
                "osu": osu_running,
                "etterna": etterna_running,
                "running": (osu_running or etterna_running),
            }

        _window.expose(check_osu_running)

        # Toggle whether the overlay stays pinned above osu.
        # Unlike click-through, the window remains fully interactive in both states.
        _overlay_pin_state = {"active": False}

        def toggle_overlay_pin() -> bool:
            """Toggle whether the overlay stays pinned above other windows.

            True  = pinned above osu/desktop windows.
            False = normal window z-order.
            The overlay remains interactive in both states.
            Returns the new pinned state.
            """
            if sys.platform != "win32":
                _overlay_pin_state["active"] = not _overlay_pin_state["active"]
                return _overlay_pin_state["active"]

            import ctypes
            import ctypes.wintypes as W

            HWND_TOPMOST   = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE     = 0x0002
            SWP_NOSIZE     = 0x0001
            SWP_NOACTIVATE = 0x0010

            try:
                hwnd_val = ctypes.windll.user32.FindWindowW(
                    None,
                    _APP_TITLE,
                )
                if not hwnd_val:
                    logger.warning("toggle_overlay_pin: HWND not found")
                    return _overlay_pin_state["active"]

                new_active = not _overlay_pin_state["active"]
                insert_after = ctypes.c_void_p(HWND_TOPMOST if new_active else HWND_NOTOPMOST)
                flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE

                ctypes.windll.user32.SetWindowPos(
                    W.HWND(hwnd_val),
                    insert_after,
                    0, 0, 0, 0,
                    flags,
                )

                _overlay_pin_state["active"] = new_active
                logger.info("toggle_overlay_pin -> %s", "PINNED" if new_active else "UNPINNED")
            except Exception as exc:
                logger.warning("toggle_overlay_pin failed: %s", exc)

            return _overlay_pin_state["active"]

        _window.expose(toggle_overlay_pin)

        # 2. Audio service (optional — gated)
        try:
            audio = AudioService(event_bus, stop_event)
            audio.start()
            runtime["audio"] = audio
        except Exception as exc:
            logger.warning("AudioService no disponible: %s", exc)
            bridge._send({
                "type": "notification",
                "message": "Audio visualizer not available in this version",
            })

        # Analysis coordinator manages map change pipeline runs and discards stale results.
        coordinator = AnalysisCoordinator(event_bus)
        runtime["coordinator"] = coordinator

        # Starts standard live source listener (tosu_source).
        threading.Thread(
            target=tosu_run,
            args=(event_bus, stop_event),
            daemon=True,
            name="tosu-source",
        ).start()

        # Starts Etterna simfile live source listener (etterna_source).
        try:
            from etterna import run as etterna_run
        except ImportError:
            from etterna.etterna_source import run as etterna_run
        threading.Thread(
            target=etterna_run,
            args=(event_bus, stop_event),
            daemon=True,
            name="etterna-source",
        ).start()

        logger.info("overlay session started with dual osu! and Etterna monitoring")

    _icon = str(_WEB_DIR / "graph.ico")
    webview.start(on_start, window, debug=False, icon=_icon)

