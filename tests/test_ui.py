"""Browser tests of the generated pages (search, views, global search), served over a local HTTP server."""
import functools
import http.server
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

import build_pages
from tests.test_build_pages import LINES, NOW, export

NELSON = [f'{100 + n};97820000000{n:02d};"Nelson";{n};"";"Tome {n}";"Dupuis";"";1;;;;0;;;;"Bertschy";"Bertschy";0'
          for n in (1, 2, 10, 12)]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class UiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp())
        for folder in ('tmp', 'data'):
            (cls.root / folder).mkdir()
        (cls.root / 'collections.conf').write_text('kid:1:Noah\nme:2:Cédric\n', encoding='utf-8')
        (cls.root / 'tmp' / 'kid.csv').write_text(export(NELSON), encoding='utf-8')
        (cls.root / 'tmp' / 'me.csv').write_text(export(LINES), encoding='utf-8')
        build_pages.build(cls.root, NOW)

        handler = functools.partial(QuietHandler, directory=cls.root / 'public')
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.shutdown()
        shutil.rmtree(cls.root)

    def open(self, path, width=390):
        context = self.browser.new_context(viewport={'width': width, 'height': 800})
        self.addCleanup(context.close)
        page = context.new_page()
        self.errors = []
        page.on('console', lambda m: self.errors.append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: self.errors.append(str(e)))
        page.goto(self.base + path)
        return page

    def visible(self, page):
        return page.evaluate("Array.from(document.querySelectorAll('details.serie li'))"
                             ".filter(li => !li.hidden).map(li => li.dataset.num || '')")

    def test_volume_search(self):
        page = self.open('/kid.html')
        page.fill('.album-search', 'nelson 1')
        self.assertEqual(self.visible(page), ['1'])
        page.fill('.album-search', 'NELSON 12')
        self.assertEqual(self.visible(page), ['12'])
        self.assertEqual(page.inner_text('.search-count'), '1 album trouvé')
        self.assertEqual(self.errors, [])

    def test_isbn_search_on_mobile_with_dashes(self):
        page = self.open('/me.html')
        page.fill('.album-search', '978-2-8001-6700-8')
        self.assertEqual(self.visible(page), ['3'])

    def test_author_search_and_accents(self):
        page = self.open('/me.html')
        page.fill('.album-search', 'larcenet')
        self.assertEqual(self.visible(page), ['4'])
        page.fill('.album-search', 'asterix obelix')
        self.assertEqual(self.visible(page), ['10'])

    def test_no_result_message(self):
        page = self.open('/kid.html')
        page.fill('.album-search', 'zzzz')
        self.assertTrue(page.is_visible('.search-empty'))

    def test_search_is_shareable(self):
        page = self.open('/kid.html?q=nelson%202')
        self.assertEqual(self.visible(page), ['2'])
        page.fill('.album-search', 'nelson')
        self.assertTrue(page.evaluate('location.href').endswith('/kid.html?q=nelson'))

    def test_table_view_is_sortable_with_the_keyboard(self):
        page = self.open('/kid.html', width=1280)
        page.click('button[data-view=table]')
        page.focus('.table-view th:nth-child(2) button')
        page.keyboard.press('Enter')
        page.keyboard.press('Enter')
        self.assertEqual(page.get_attribute('.table-view th:nth-child(2)', 'aria-sort'), 'descending')
        numbers = page.eval_on_selector_all('.table-view tbody tr', 'rows => rows.map(r => r.cells[1].textContent)')
        self.assertEqual(numbers, ['12', '10', '2', '1'])
        page.fill('.album-search', 'nelson 10')
        self.assertEqual(page.eval_on_selector_all('.table-view tbody tr:not([hidden])', 'rows => rows.length'), 1)

    def test_a_tap_anywhere_on_a_table_row_opens_the_album(self):
        page = self.open('/kid.html')
        page.click('button[data-view=table]')
        with page.context.expect_page() as album:
            page.click('.table-view tbody tr:first-child td:first-child')
        self.assertIn('bedetheque.com/BD-x-', album.value.url)

    def test_global_search(self):
        page = self.open('/index.html')
        page.fill('#global-search', 'nelson 12')
        page.wait_for_selector('.global-results li')
        self.assertIn("✅ Noah l'a déjà", page.inner_text('.global-results'))
        page.fill('#global-search', 'nelson 11')
        page.wait_for_function("document.querySelector('.global-results').innerText.includes('🎁')")
        self.assertIn("🎁 Cédric aimerait l'avoir", page.inner_text('.global-results'))
        page.fill('#global-search', 'zzzz')
        page.wait_for_function("document.querySelector('.global-results').innerText.includes('Personne')")
        self.assertEqual(self.errors, [])

    def test_no_horizontal_scroll_on_mobile(self):
        for path in ('/index.html', '/me.html', '/a-offrir.html'):
            page = self.open(path)
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390, path)


if __name__ == '__main__':
    unittest.main()
