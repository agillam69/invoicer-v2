"""
Automation test runner.

Runs:
  1. test_help_guide.py   — Playwright browser test for help_guide.html (headless)
  2. test_gui_smoke.py   — pyautogui desktop smoke test for the Tkinter app

The pyautogui test requires a real Windows desktop session (interactive display).
It will fail in headless/remote/cloud environments where Windows cannot enumerate
on-screen windows.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

TESTS = [
    ('Playwright help-guide', 'test_help_guide.py'),
    ('pyautogui GUI smoke',   'test_gui_smoke.py'),
]


def main():
    results = []
    for name, script in TESTS:
        print(f'\n=== {name}: {script} ===')
        proc = subprocess.run([sys.executable, str(ROOT / script)], cwd=str(ROOT))
        results.append((name, proc.returncode))

    print('\n=== Automation test summary ===')
    for name, rc in results:
        status = 'PASS' if rc == 0 else 'FAIL'
        print(f'  [{status}] {name}')

    return 0 if all(rc == 0 for _, rc in results) else 1


if __name__ == '__main__':
    sys.exit(main())
