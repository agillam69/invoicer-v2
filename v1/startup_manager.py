"""
startup_manager.py
==================
Windows startup integration for Invoice Generator.

Registers the application to launch automatically at user logon by writing a
value under HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.
This makes the entry visible (and toggleable) in the Windows
"Settings > Apps > Startup" panel.

A small launcher delay is implemented by invoking the executable with a
``--delayed`` flag; the application itself sleeps briefly before showing its
window so it behaves like a delayed-run startup program.

All functions are Windows-only and degrade gracefully (returning False / no-op)
on other platforms or if the registry is inaccessible.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Registry key/value names
_RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
_VALUE_NAME = 'InvoiceGenerator'


def _is_windows() -> bool:
    return sys.platform.startswith('win')


def _launch_command() -> str:
    """Return the command string to register for startup."""
    if getattr(sys, 'frozen', False):
        exe = Path(sys.executable)
        return f'"{exe}" --delayed'
    # Running from source — launch via python interpreter
    script = Path(__file__).parent / 'invoice_gui.py'
    return f'"{sys.executable}" "{script}" --delayed'


def is_enabled() -> bool:
    """Return True if the startup entry is currently registered."""
    if not _is_windows():
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable() -> bool:
    """Register the application to run at Windows startup. Returns success."""
    if not _is_windows():
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _launch_command())
        return True
    except OSError:
        return False


def disable() -> bool:
    """Remove the startup entry. Returns success (True if removed or absent)."""
    if not _is_windows():
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
        return True
    except FileNotFoundError:
        return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """Convenience toggle. Returns success of the operation."""
    return enable() if enabled else disable()
