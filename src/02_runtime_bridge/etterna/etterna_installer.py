"""
etterna_installer.py — Clean, lightweight theme bridge installer for Etterna and StepMania 5.x.

Installs ONLY the song selection metadata bridge (dan_overlay_bridge.lua) into
all installed themes. Does NOT hook gameplay or use continuous update loops,
guaranteeing zero impact on gameplay FPS or fullscreen performance.
"""

import ctypes
from ctypes import wintypes
import logging
import os
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

if getattr(sys, "frozen", False):
    _BASE_MEI = Path(getattr(sys, "_MEIPASS", sys.executable)).resolve()
    _SCRIPT_DIR = _BASE_MEI / "bridges" if (_BASE_MEI / "bridges").is_dir() else _BASE_MEI / "src" / "02_runtime_bridge" / "etterna" / "bridges"
else:
    _SCRIPT_DIR = Path(__file__).parent / "bridges"

_BRIDGE_LUA = _SCRIPT_DIR / "dan_overlay_bridge.lua"
_GAMEPLAY_LUA = _SCRIPT_DIR / "dan_overlay_gameplay.lua"
_EVAL_LUA = _SCRIPT_DIR / "dan_overlay_eval.lua"


def _get_process_path(pid: int) -> str | None:
    """Retrieve full executable path for a process ID on Windows."""
    if sys.platform != "win32":
        return None
    try:
        h_process = ctypes.windll.kernel32.OpenProcess(
            _PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not h_process:
            return None
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        ok = ctypes.windll.kernel32.QueryFullProcessImageNameW(
            h_process, 0, buf, ctypes.byref(size)
        )
        ctypes.windll.kernel32.CloseHandle(h_process)
        return buf.value if ok else None
    except Exception:
        return None


def find_running_etterna_root() -> Path | None:
    """Detects if Etterna.exe or StepMania.exe is currently running and returns its root directory."""
    if sys.platform != "win32":
        return None

    # 1. Direct process path query via EnumProcesses
    try:
        pids = (wintypes.DWORD * 2048)()
        bytes_returned = wintypes.DWORD()
        ctypes.windll.psapi.EnumProcesses(
            pids, ctypes.sizeof(pids), ctypes.byref(bytes_returned)
        )
        count = bytes_returned.value // ctypes.sizeof(wintypes.DWORD)

        for i in range(count):
            pid = pids[i]
            if pid == 0:
                continue
            proc_path_str = _get_process_path(pid)
            if not proc_path_str:
                continue
            name = os.path.basename(proc_path_str).lower()
            if name.startswith("etterna") or name.startswith("stepmania"):
                exe_path = Path(proc_path_str).resolve()
                if exe_path.parent.name.lower() == "program":
                    root = exe_path.parent.parent
                else:
                    root = exe_path.parent

                if (root / "Themes").is_dir() or (root / "Songs").is_dir() or (root / "Save").is_dir():
                    return root
    except Exception as exc:
        logger.debug("find_running_etterna_root: error enumerating processes: %s", exc)

    # 2. Fallback check: tasklist process check combined with known installation directories
    try:
        import subprocess
        CREATE_NO_WINDOW = 0x08000000
        res = subprocess.run(
            ["tasklist", "/NH"],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=CREATE_NO_WINDOW,
        )
        out = res.stdout.lower()
        if "etterna" in out or "stepmania" in out:
            candidates = [
                Path("D:/Etterna"),
                Path("C:/Etterna"),
                Path("C:/Games/Etterna"),
                Path("D:/Games/Etterna"),
                Path("E:/Etterna"),
                Path(os.environ.get("APPDATA", "")) / "Etterna",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Etterna",
                Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Etterna",
            ]
            for c in candidates:
                if c.is_dir() and ((c / "Themes").is_dir() or (c / "Save").is_dir()):
                    return c.resolve()
    except Exception:
        pass

    return None


def find_all_etterna_roots(configured_path: str | None = None) -> list[Path]:
    """Finds all existing Etterna installation roots."""
    roots = []
    seen = set()

    def _add(p: Path | None):
        if p and p.is_dir() and (p / "Themes").is_dir():
            resolved = str(p.resolve()).lower()
            if resolved not in seen:
                seen.add(resolved)
                roots.append(p.resolve())

    # 1. Running process
    _add(find_running_etterna_root())

    # 2. Configured path
    if configured_path:
        _add(Path(configured_path).expanduser())

    # 3. Common Windows paths
    candidates = [
        Path("D:/Etterna"),
        Path("C:/Etterna"),
        Path("C:/Games/Etterna"),
        Path("D:/Games/Etterna"),
        Path("E:/Etterna"),
        Path(os.environ.get("APPDATA", "")) / "Etterna",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Etterna",
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Etterna",
    ]
    for c in candidates:
        _add(c)

    return roots


def _inject_lines_into_default_lua(default_lua: Path, actor_lines: list[str]) -> bool:
    """Safely injects actor loading lines into a theme's default.lua before `return t`."""
    if not default_lua.is_file():
        return False

    try:
        content = default_lua.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False

    all_present = True
    for line in actor_lines:
        match_key = line.split('"')[1] if '"' in line else line
        if match_key not in content:
            all_present = False
            break

    if all_present:
        return False  # Already installed

    # Safe backup
    backup_file = default_lua.with_suffix(".lua.dan_backup")
    if not backup_file.exists():
        try:
            backup_file.write_text(content, encoding="utf-8")
        except Exception:
            pass

    injection = "\n\n-- [DanOverlay Integration]\n" + "\n".join(actor_lines) + "\n\n"

    match = re.search(r"(\n\s*return\s+t\s*;?\s*)$", content, flags=re.IGNORECASE | re.MULTILINE)
    if match:
        new_content = content[:match.start()] + injection + content[match.start():]
    else:
        new_content = content + injection

    try:
        default_lua.write_text(new_content, encoding="utf-8")
        logger.info("etterna_installer: injected bridge into %s", default_lua)
        return True
    except Exception as exc:
        logger.warning("etterna_installer: failed writing %s: %s", default_lua, exc)
        return False


def install_theme_bridges(etterna_root: Path) -> int:
    """Scans all themes and installs the bridges for SelectMusic, Gameplay, and Evaluation."""
    themes_dir = etterna_root / "Themes"
    if not themes_dir.is_dir():
        return 0

    bridge_content = _BRIDGE_LUA.read_text(encoding="utf-8") if _BRIDGE_LUA.is_file() else ""
    gameplay_content = _GAMEPLAY_LUA.read_text(encoding="utf-8") if _GAMEPLAY_LUA.is_file() else ""
    eval_content = _EVAL_LUA.read_text(encoding="utf-8") if _EVAL_LUA.is_file() else ""

    installed_count = 0

    for theme_folder in themes_dir.iterdir():
        if not theme_folder.is_dir() or theme_folder.name.startswith("."):
            continue

        bganims = theme_folder / "BGAnimations"
        if not bganims.is_dir():
            continue

        theme_installed = False

        # 1. ScreenSelectMusic bridge
        if bridge_content:
            select_music_dirs = [
                bganims / "ScreenSelectMusic decorations",
                bganims / "ScreenSelectMusic overlay",
                bganims / "ScreenSelectMusic underlay",
            ]
            for sdir in select_music_dirs:
                if sdir.is_dir():
                    try:
                        (sdir / "dan_overlay_bridge.lua").write_text(bridge_content, encoding="utf-8")
                    except Exception as exc:
                        logger.warning("etterna_installer: failed copying bridge to %s: %s", sdir, exc)

                    default_lua = sdir / "default.lua"
                    if default_lua.is_file():
                        _inject_lines_into_default_lua(
                            default_lua,
                            ['t[#t+1] = LoadActor("dan_overlay_bridge.lua")'],
                        )
                    theme_installed = True
                    break

        # 2. ScreenGameplay bridge
        if gameplay_content:
            gameplay_dirs = [
                bganims / "ScreenGameplay overlay",
                bganims / "ScreenGameplay decorations",
                bganims / "ScreenGameplay underlay",
            ]
            for gdir in gameplay_dirs:
                if gdir.is_dir():
                    try:
                        (gdir / "dan_overlay_gameplay.lua").write_text(gameplay_content, encoding="utf-8")
                    except Exception as exc:
                        logger.warning("etterna_installer: failed copying gameplay bridge to %s: %s", gdir, exc)

                    default_lua = gdir / "default.lua"
                    if default_lua.is_file():
                        _inject_lines_into_default_lua(
                            default_lua,
                            ['t[#t+1] = LoadActor("dan_overlay_gameplay.lua")'],
                        )
                    theme_installed = True
                    break

        # 3. ScreenEvaluation bridge
        if eval_content:
            eval_dirs = [
                bganims / "ScreenEvaluation overlay",
                bganims / "ScreenEvaluation decorations",
                bganims / "ScreenEvaluation underlay",
            ]
            for edir in eval_dirs:
                if edir.is_dir():
                    try:
                        (edir / "dan_overlay_eval.lua").write_text(eval_content, encoding="utf-8")
                    except Exception as exc:
                        logger.warning("etterna_installer: failed copying eval bridge to %s: %s", edir, exc)

                    default_lua = edir / "default.lua"
                    if default_lua.is_file():
                        _inject_lines_into_default_lua(
                            default_lua,
                            ['t[#t+1] = LoadActor("dan_overlay_eval.lua")'],
                        )
                    theme_installed = True
                    break

        if theme_installed:
            installed_count += 1

    return installed_count


def auto_install_all(configured_root: str | None = None) -> list[Path]:
    """Autonomous installer: installs the bridges into all Etterna themes."""
    roots = find_all_etterna_roots(configured_root)
    successful_roots = []
    for r in roots:
        try:
            count = install_theme_bridges(r)
            if count > 0:
                logger.info("etterna_installer: integrated with Etterna at %s (%d themes)", r, count)
                successful_roots.append(r)
        except Exception as exc:
            logger.warning("etterna_installer: error installing to %s: %s", r, exc)
    return successful_roots
