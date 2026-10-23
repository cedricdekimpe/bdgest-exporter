import json
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import build_pages

HEADER = ('IdAlbum;ISBN;Serie;Num;NumA;Titre;Editeur;Collection;EO;DL;AI;Cote;Etat;DateAchat;PrixAchat;Note;'
          'Scenariste;Dessinateur;Wishlist')
LINES = [
    '1;9782800167008;"Dad";3;"";"Les nerfs à vif";"Dupuis";"";1;;;;0;01/02/2026;;;"Nob";"Nob";0',
    '2;9782203296626;"Astérix";10;"";"Astérix & Obélix <le retour>";"Casterman";"";1;;;;0;;;;"";"";0',
    '3;9782203296627;"Astérix";2;"";"Titre avec ; point-virgule";"Casterman";"";1;;;;0;;;;"";"";0',
    '4;9782203296628;"Astérix";1;"";"Titre sur\ndeux lignes";"Casterman";"";1;;;;0;03/03/2026;;;"";"";0',
    '5;9782203296629;"Nelson";11;"";"Voulu";"Dupuis";"";1;;;;0;;;;"";"";1',
    '6;9782203296630;"Combat ordinaire (Le)";4;"";"Planter des clous";"Dargaud";"";1;;;;0;;;;"Larcenet";"Larcenet";0',
]
# The real export goes on with other sections, each with its own header line
TRAILER = ['IdRevue;;Revue;Num;NumA;Titre;Editeur;Periodicite;AuNumero;DateRevue;;Cote;Etat;DateAchat;PrixAchat',
           'IdParaBD;Reference;Serie;TypeObjet;CategorieObjet;Descriptif;Editeur;Fabricant;Tirage;DateSortie']
NOW = datetime(2026, 10, 23, 6, 5)


def export(lines=LINES):
    return HEADER + '\n' + '\n'.join(lines + TRAILER) + '\n'


class BuildPagesTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        for folder in ('tmp', 'data', 'public'):
            (self.root / folder).mkdir()
        (self.root / 'collections.conf').write_text('# comment\ntest:1:Tést\nother:2:Other\n', encoding='utf-8')
        self.stage('test')
        self.stage('other')

    def stage(self, key, text=None):
        (self.root / 'tmp' / f'{key}.csv').write_text(text if text is not None else export(), encoding='utf-8')

    def page(self, name='test'):
        return (self.root / 'public' / f'{name}.html').read_text(encoding='utf-8')

    def test_other_sections_are_not_albums(self):
        build_pages.build(self.root, NOW)
        self.assertNotIn('IdRevue', self.page())
        self.assertNotIn('TypeObjet', self.page())

    def test_counts_exclude_wishlist_and_other_sections(self):
        counts = build_pages.build(self.root, NOW)
        self.assertEqual(counts, {'test': 5, 'other': 5})
        # Uptime Kuma monitors look for this marker ("0 albums" means a broken page)
        self.assertIn("<span class='series-count'>5 albums</span> répartis en <span class='series-count'>3 séries</span>",
                      self.page())

    def test_series_summary_lists_volumes_and_missing_ones(self):
        build_pages.build(self.root, NOW)
        self.assertIn('3 albums · tomes 1–2, 10 · <em>manquants 3–9</em>', self.page())

    def test_ranges(self):
        self.assertEqual(build_pages.ranges([1, 2, 3, 5, 7, 8]), '1–3, 5, 7–8')

    def test_series_names_are_displayed_naturally(self):
        self.assertEqual(build_pages.display_series('Combat ordinaire (Le)'), 'Le Combat ordinaire')
        self.assertEqual(build_pages.display_series("Agent 212 (L')"), "L'Agent 212")
        self.assertEqual(build_pages.display_series('Astérix (Hachette)'), 'Astérix (Hachette)')

    def test_wishlist_goes_to_the_gift_page_only(self):
        build_pages.build(self.root, NOW)
        self.assertNotIn('Voulu', self.page())
        self.assertIn('Voulu', self.page('a-offrir'))
        self.assertIn("a-offrir.html#test'>🎁 1 idées cadeaux", self.page())

    def test_values_are_escaped(self):
        build_pages.build(self.root, NOW)
        self.assertIn('Astérix &amp; Obélix &lt;le retour&gt;', self.page())
        self.assertNotIn('<le retour>', self.page())

    def test_semicolon_and_multiline_titles_stay_in_one_album(self):
        build_pages.build(self.root, NOW)
        self.assertIn('>Titre avec ; point-virgule</a>', self.page())
        self.assertIn('>Titre sur\ndeux lignes</a>', self.page())

    def test_duplicates_are_merged_with_a_badge(self):
        self.stage('test', export(LINES + [LINES[0].replace('1;', '7;', 1)]))
        build_pages.build(self.root, NOW)
        self.assertEqual(self.page().count('>Les nerfs à vif</a>'), 1)
        self.assertIn('×2</mark>', self.page())

    def test_title_links_to_the_bedetheque_album_page(self):
        build_pages.build(self.root, NOW)
        self.assertIn("<a href='https://www.bedetheque.com/BD-x-1.html'>Les nerfs à vif</a>", self.page())
        self.assertNotIn('amazon', self.page().lower())

    def test_authors_and_publisher_are_searchable(self):
        build_pages.build(self.root, NOW)
        self.assertIn("data-x='dargaud larcenet'", self.page())

    def test_index_has_counts_gifts_and_recent_albums(self):
        build_pages.build(self.root, NOW)
        index = self.page('index')
        self.assertIn('<strong>5 albums</strong>', index)
        self.assertIn('Total : 10 albums', index)
        self.assertIn('Idées cadeaux (2)', index)
        self.assertLess(index.index('Astérix 1'), index.index('Dad 3'))  # most recent purchase first

    def test_albums_json_for_the_global_search(self):
        build_pages.build(self.root, NOW)
        data = json.loads((self.root / 'public' / 'albums.json').read_text(encoding='utf-8'))
        self.assertEqual(data['names'], {'test': 'Tést', 'other': 'Other'})
        self.assertIn(['test', '5', 'Nelson', '11', 'Voulu', '9782203296629', 'dupuis', 1], data['albums'])

    def test_pages_are_private_and_strict(self):
        build_pages.build(self.root, NOW)
        for name in ('index', 'test', 'a-offrir'):
            page = self.page(name)
            self.assertIn("content='noindex, nofollow'", page)
            self.assertIn("script-src 'self'", page)
            self.assertNotIn('onclick', page)
            self.assertNotIn('cdn.jsdelivr', page)
        self.assertEqual((self.root / 'public' / 'robots.txt').read_text(), 'User-agent: *\nDisallow: /\n')

    def test_static_files_and_service_worker(self):
        build_pages.build(self.root, NOW)
        for name in ('app.js', 'style.css', 'pico.min.css', 'favicon.svg'):
            self.assertTrue((self.root / 'public' / name).exists(), name)
        worker = (self.root / 'public' / 'sw.js').read_text(encoding='utf-8')
        self.assertIn("const CACHE = 'bd-20261023060500';", worker)
        self.assertIn('"test.html"', worker)

    def test_up_lists_the_counts(self):
        build_pages.build(self.root, NOW)
        up = (self.root / 'public' / 'up').read_text(encoding='utf-8')
        self.assertTrue(up.startswith('ok 2026-10-23T06:05:00'))
        self.assertTrue(up.strip().endswith('test=5 other=5'))

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


if __name__ == '__main__':
    unittest.main()
