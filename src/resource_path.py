# resource_path.py -- Resolution of file paths for dev and PyInstaller frozen modes.
#
# Dev mode: resources are in project root.
# Frozen mode (exe): PyInstaller extracts assets to sys._MEIPASS (temporary directory).
#
# All modules loading config/data files MUST use resource_path() instead of __file__-based relative paths.

import os
import sys


def get_root() -> str:
    """Get project root directory.

    - Frozen (exe): sys._MEIPASS (temporary extraction folder)
    - Dev: parent folder of src/ (project root)
    """
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    # Dev: this file lives in src/, root is the parent
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    """Build resource path relative to project root.

    Examples
    --------
    resource_path("config", "anchors.json")       → .../config/anchors.json
    resource_path("Star-Rating-Rebirth-main")      → .../Star-Rating-Rebirth-main/
    """
    return os.path.join(get_root(), *parts)
