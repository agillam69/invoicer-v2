"""
diagnose_launch.py
==================
Collect information about why Invoice Generator won't start.
Run this and send the output (or the saved log file) for support.
"""

import os
import sys
import platform
import subprocess
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXE = ROOT / 'dist' / 'Invoice Generator v1.49.exe'
LOG = Path('C:/InvoicerData/launch_diagnose.log')
LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    print(msg)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(msg + '\n')


def main():
    log('=' * 60)
    log('Invoice Generator launch diagnostics')
    log(f'Time: {__import__("datetime").datetime.now()}')
    log(f'Python: {sys.version}')
    log(f'Platform: {platform.platform()}')
    log(f'CWD: {Path.cwd()}')
    log(f'EXE path: {EXE}')
    log(f'EXE exists: {EXE.exists()}')
    if EXE.exists():
        log(f'EXE size: {EXE.stat().st_size} bytes')

    # Check OneDrive/Cloud attribute
    try:
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(EXE))
        log(f'EXE file attributes: {attrs:#x}')
    except Exception as e:
        log(f'Could not read file attributes: {e}')

    # Check data dir
    data_dir = Path('C:/InvoicerData')
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        test_file = data_dir / '.write_test'
        test_file.write_text('ok', encoding='utf-8')
        test_file.unlink()
        log(f'Data dir writable: {data_dir}')
    except Exception as e:
        log(f'Data dir NOT writable: {e}')

    # Check source Python can import
    try:
        sys.path.insert(0, str(ROOT))
        import invoice_gui
        log('invoice_gui.py imports successfully')
    except Exception as e:
        log(f'invoice_gui.py import FAILED: {e}')
        log(traceback.format_exc())

    # Try to run the exe for a few seconds and capture any console output
    if EXE.exists():
        log('Attempting to launch exe for 5 seconds...')
        try:
            env = {**os.environ, 'INVOICER_DATA_DIR': str(data_dir)}
            proc = subprocess.Popen(
                [str(EXE)],
                cwd=str(ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                out, err = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
                log('Exe stayed running for 5 seconds (no crash)')
            log(f'Exe exit code: {proc.returncode}')
            if out:
                log(f'Exe stdout:\n{out}')
            if err:
                log(f'Exe stderr:\n{err}')
        except Exception as e:
            log(f'Exe launch attempt FAILED: {e}')
            log(traceback.format_exc())

    log('=' * 60)
    log(f'Full log saved to: {LOG}')


if __name__ == '__main__':
    main()
