import sys
import os
import traceback
import datetime
import platform

# Real entry point for the compiled executable. Handles startup,
# crash logging, and debugging output when outside an IDE environment.

# Ensure script directory is in sys.path so imports work across all invokers
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
if _SELF_DIR not in sys.path:
    sys.path.insert(0, _SELF_DIR)

# Log file is saved in the executable directory
if getattr(sys, "frozen", False):
    _EXE_DIR = os.path.dirname(sys.executable)
else:
    _EXE_DIR = os.path.dirname(os.path.abspath(__file__))

_CRASH_LOG = os.path.join(_EXE_DIR, "DanOverlay_error.txt")


def _write_crash_log(exc_type=None, exc_value=None, exc_tb=None, extra_msg=""):
    """Writes diagnostic info to DanOverlay_error.txt for end-user debugging."""
    try:
        with open(_CRASH_LOG, "w", encoding="utf-8") as f:
            f.write("=== DAN OVERLAY — ERROR LOG ===\n")
            f.write(f"Date/time  : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"OS         : {platform.platform()}\n")
            f.write(f"Python     : {sys.version}\n")
            f.write(f"Ejecutable : {sys.executable}\n")
            f.write(f"Frozen     : {getattr(sys, 'frozen', False)}\n")
            f.write(f"Args       : {sys.argv}\n")
            if getattr(sys, "frozen", False):
                f.write(f"_MEIPASS   : {getattr(sys, '_MEIPASS', 'N/A')}\n")
            f.write("\n")
            if extra_msg:
                f.write(f"[Contexto] {extra_msg}\n\n")
            if exc_type is not None:
                f.write("=== TRACEBACK ===\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
            else:
                f.write("(No hay traceback disponible)\n")
    except Exception:
        pass  # Prevent blocking if writing fails


# Global exception hook to capture unhandled errors
def _global_excepthook(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    _write_crash_log(exc_type, exc_value, exc_tb, extra_msg="Excepcion no controlada (excepthook)")
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = _global_excepthook


# --- CLR / Pythonnet PyInstaller Windows Fix ---
# PyInstaller puts Python DLLs inside the '_internal' folder, causing
# pythonnet to throw "Failed to resolve Python.Runtime.Loader.Initialize"
# because P/Invoke searches in the application base dir.
# We override the path manually to point to sys._MEIPASS.
if sys.platform == "win32" and getattr(sys, "frozen", False):
    os.environ["PATH"] = sys._MEIPASS + os.pathsep + os.environ.get("PATH", "")
    try:
        os.add_dll_directory(sys._MEIPASS)
    except AttributeError:
        pass

    py_dll = os.path.join(sys._MEIPASS, "python313.dll")
    if os.path.exists(py_dll):
        os.environ["PYTHONNET_PYDLL"] = py_dll
    else:
        # Fallback for other versions
        os.environ["PYTHONNET_PYDLL"] = os.path.join(sys._MEIPASS, "python3.dll")


def _show_error_dialog(title, message):
    """Show a native error dialog without requiring a console window."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)  # MB_ICONERROR


def main():
    try:
        # Actual launcher logic is in overlay_host.launch().
        from overlay_host import launch
        launch()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        _write_crash_log(*sys.exc_info(), extra_msg="Crash in overlay_host.launch()")
        _show_error_dialog(
            "DanOverlay — Critical Error",
            f"The program closed unexpectedly.\n\n"
            f"Error: {e}\n\n"
            f"Check DanOverlay_error.txt for details."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()

# Original Author: 8DOUL (Discord: agent_ale)

    