"""
Desktop GUI smoke test using pyautogui.
Launches invoice_gui.py, logs in with default admin/Admin, and checks that the
main window appears and a tab can be clicked.

This test must run in a real or virtual display session (not a headless CI
container without X). On Windows, it can be run while watching the screen.
"""

import os
import subprocess
import sys
import time
import tempfile
import shutil
from pathlib import Path

import pyautogui

pyautogui.FAILSAFE = True

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
APP_PY = ROOT / 'invoice_gui.py'


def run_test():
    failures = []
    tmp_dir = Path(tempfile.mkdtemp(prefix='invoicer_gui_test_'))

    # Seed a default admin user so login succeeds
    from data_store import DataStore
    ds = DataStore(tmp_dir)
    ds.ensure_files()
    ds.ensure_default_user()

    proc = subprocess.Popen(
        [sys.executable, str(APP_PY)],
        cwd=str(ROOT),
        env={**dict(os.environ), 'INVOICER_DATA_DIR': str(tmp_dir)},
    )

    try:
        # Wait for the login window
        time.sleep(2)
        try:
            login = pyautogui.getWindowsWithTitle('Login')
        except Exception as e:
            failures.append(f'pyautogui cannot enumerate windows: {e}')
            print(f'FAIL: pyautogui cannot enumerate windows: {e}')
            return 1
        if not login:
            failures.append('Login window did not appear')
            print('FAIL: Login window did not appear')
            return 1
        win = login[0]
        win.activate()
        time.sleep(0.5)

        # Enter default credentials
        pyautogui.typewrite('admin\tAdmin', interval=0.01)
        time.sleep(0.2)
        pyautogui.press('return')

        # Wait for main window
        time.sleep(2)
        main = pyautogui.getWindowsWithTitle('Invoice Generator')
        if not main:
            failures.append('Main Invoice Generator window did not appear')
            print('FAIL: Main window did not appear')
            return 1
        main_win = main[0]
        main_win.activate()
        print('PASS: Main window appeared')

        # Click a tab by coordinates — fragile; best-effort only
        try:
            # Click near the left tab bar (default tab area)
            pyautogui.click(main_win.left + 60, main_win.top + 40)
            time.sleep(0.5)
            print('PASS: Tab click executed')
        except Exception as e:
            failures.append(f'tab click failed: {e}')
            print(f'FAIL: tab click failed: {e}')

    except Exception as e:
        failures.append(f'exception: {e}')
        print(f'FAIL: {e}')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        try:
            shutil.rmtree(tmp_dir)
        except Exception:
            pass

    if failures:
        print(f'\nFAILURES ({len(failures)}):')
        for f in failures:
            print(f'  {f}')
        return 1
    print('\nGUI smoke test passed.')
    return 0


if __name__ == '__main__':
    sys.exit(run_test())
