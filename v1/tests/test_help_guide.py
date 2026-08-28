"""
Playwright browser test for the static help guide.
Verifies that help_guide.html loads and contains expected sections.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
import sys

ROOT = Path(__file__).resolve().parent.parent
HELP_HTML = ROOT / 'help_guide.html'


def run_test():
    failures = []
    if not HELP_HTML.exists():
        failures.append('help_guide.html not found')
        print('FAIL: help_guide.html not found')
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f'file:///{HELP_HTML.as_posix()}')

        title = page.title()
        if 'Invoice Generator' not in title:
            failures.append(f'title missing Invoice Generator: {title}')
        else:
            print(f'PASS: title = {title}')

        h1 = page.locator('h1').first.inner_text()
        if not h1:
            failures.append('no h1 found')
        else:
            print(f'PASS: h1 = {h1.strip()}')

        visible_text = page.inner_text('body')
        expected_snippets = ['Invoice', 'Help', 'Guide']
        for snippet in expected_snippets:
            if snippet not in visible_text:
                failures.append(f'missing snippet: {snippet}')
            else:
                print(f'PASS: snippet found: {snippet}')

        browser.close()

    if failures:
        print(f'\nFAILURES ({len(failures)}):')
        for f in failures:
            print(f'  {f}')
        return 1
    print('\nAll help-guide automation tests passed.')
    return 0


if __name__ == '__main__':
    sys.exit(run_test())
