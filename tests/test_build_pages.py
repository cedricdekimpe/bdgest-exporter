import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import build_pages

HEADER = 'IdAlbum;ISBN;Serie;Num;NumA;Titre;Editeur;Collection;EO;DL;AI;Cote;Etat;DateAchat;PrixAchat;Note;Scenariste;Dessinateur;Wishlist'
LINES = [
    '1;9782800167008;"Dad";3;"";"Les nerfs à vif";"Dupuis";"";1;;;;0;;;;"";"";0',
    '2;9782203296626;"Astérix";10;"";"Astérix & Obélix <le retour>";"Casterman";"";1;;;;0;;;;"";"";0',
    '3;9782203296627;"Astérix";2;"";"Titre avec ; point-virgule";"Casterman";"";1;;;;0;;;;"";"";0',
    '4;9782203296628;"Astérix";1;"";"Titre sur\ndeux lignes";"Casterman";"";1;;;;0;;;;"";"";0',
    '5;9782203296629;"Nelson";11;"";"Voulu";"Dupuis";"";1;;;;0;;;;"";"";1',
]
NOW = datetime(2026, 10, 23, 6, 5)


def export(lines=LINES):
    return HEADER + '\n' + '\n'.join(lines) + '\n'


class BuildPagesTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        for folder in ('tmp', 'data', 'public'):
            (self.root / folder).mkdir()
        (self.root / 'collections.conf').write_text('# comment\ntest:1:Téést\nother:2:Other\n', encoding='utf-8')
        self.stage('test')
        self.stage('other')

    def stage(self, key, text=None):
        (self.root / 'tmp' / f'{key}.csv').write_text(text if text is not None else export(), encoding='utf-8')

    def page(self, key='test'):
        return (self.root / 'public' / f'{key}.html').read_text(encoding='utf-8')

    def test_counts_exclude_wishlist_and_header(self):
        counts = build_pages.build(self.root, NOW)
        self.assertEqual(counts, {'test': 4, 'other': 4})
        self.assertIn("<span class='series-count'>4 albums</span> répartis en <span class='series-count'>2 séries</span>", self.page())

    def test_wishlist_is_listed_apart(self):
        build_pages.build(self.root, NOW)
        owned, wanted = self.page().split("<h2 id='a-offrir'>")
        self.assertNotIn('Voulu', owned)
        self.assertIn('Voulu', wanted)

    def test_values_are_escaped(self):
        build_pages.build(self.root, NOW)
        self.assertIn('Astérix &amp; Obélix &lt;le retour&gt;', self.page())
        self.assertNotIn('<le retour>', self.page())

    def test_semicolon_and_multiline_titles_stay_in_one_row(self):
        build_pages.build(self.root, NOW)
        self.assertIn('<td>Titre avec ; point-virgule</td>', self.page())
        self.assertIn('<td>Titre sur\ndeux lignes</td>', self.page())

    def test_rows_sorted_by_series_ignoring_accents_then_number(self):
        build_pages.build(self.root, NOW)
        page = self.page()
        order = [page.index(t) for t in ('Titre sur', 'Titre avec', 'Astérix &amp; Obélix', 'Les nerfs')]
        self.assertEqual(order, sorted(order))

    def test_index_and_up(self):
        build_pages.build(self.root, NOW)
        index = (self.root / 'public' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('<strong>4 albums</strong>', index)
        self.assertIn('Total: 8 albums', index)
        self.assertIn('Mis à jour le 23/10/2026 06:05', index)
        up = (self.root / 'public' / 'up').read_text(encoding='utf-8')
        self.assertTrue(up.startswith('ok 2026-10-23T06:05:00'))
        self.assertTrue(up.strip().endswith('test=4 other=4'))

    def test_error_page_is_refused_and_nothing_changes(self):
        build_pages.build(self.root, NOW)
        before = self.page()
        self.stage('test')
        self.stage('other', 'Erreur dans les paramètres')
        with self.assertRaisesRegex(ValueError, 'not a BDGest export'):
            build_pages.build(self.root, NOW)
        self.assertEqual(self.page(), before)
        self.assertTrue((self.root / 'tmp' / 'test.csv').exists())

    def test_big_drop_is_refused(self):
        build_pages.build(self.root, NOW)
        self.stage('test', export(LINES[:1]))
        self.stage('other')
        with self.assertRaisesRegex(ValueError, 'refusing to publish'):
            build_pages.build(self.root, NOW)

    def test_previous_export_is_kept_as_back(self):
        build_pages.build(self.root, NOW)
        self.stage('test')
        self.stage('other')
        build_pages.build(self.root, NOW)
        self.assertTrue((self.root / 'data' / 'test.csv.back').exists())

    def test_search_ignores_accents(self):
        build_pages.build(self.root, NOW)
        self.assertIn("normalize('NFD')", self.page())


if __name__ == '__main__':
    unittest.main()
