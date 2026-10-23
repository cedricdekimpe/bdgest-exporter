"""Build the public pages from the BDGest CSV exports (usage: build_pages.py).

For every collection listed in collections.conf, validates ./tmp/<key>.csv, promotes it to
./data/<key>.csv (keeping the previous one as .back) and writes ./public/<key>.html.
Nothing is touched unless every export is valid, so an error page is never published.
Also writes the home page, the gift ideas page, albums.json (global search), the service
worker, copies ./static and finally writes ./public/up.
"""
import csv
import html
import io
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Bedetheque (BDGest) redirects this URL to the canonical page of the album, whatever the slug
ALBUM_URL = 'https://www.bedetheque.com/BD-x-{}.html'
REQUIRED_COLUMNS = ('IdAlbum', 'ISBN', 'Serie', 'Num', 'Titre', 'Wishlist')
# A new export with less than this share of the previous rows is considered broken
MIN_KEPT_RATIO = 0.5
RECENT_COUNT = 5
# BDGest writes "Combat ordinaire (Le)": the article moves back in front for display
INVERTED_ARTICLE = re.compile(r"^(.*) \((L'|Le|La|Les|Un|Une|Des|The)\)$")


def read_collections(path):
    collections = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            key, collection_id, name = line.split(':', 2)
            collections.append({'key': key, 'id': int(collection_id), 'name': name})
    return collections


def parse_csv(text):
    """Returns the album rows of a BDGest export, raises ValueError if it is not one."""
    reader = csv.DictReader(io.StringIO(text.lstrip('﻿'), newline=''), delimiter=';')
    missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f'not a BDGest export (missing columns: {", ".join(missing)})')
    rows = []
    for row in reader:
        # The export goes on with other sections (IdRevue, IdParaBD...), each with its own header line
        if not row['IdAlbum'].isdigit():
            break
        rows.append(row)
    if not rows:
        raise ValueError('no album in the export')
    return rows


def normalize(text):
    return unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode().casefold()


def display_series(name):
    match = INVERTED_ARTICLE.match(name)
    if not match:
        return name
    title, article = match.groups()
    return f'{article}{title}' if article == "L'" else f'{article} {title}'


def sort_key(row):
    match = re.match(r'\d+(\.\d+)?', row['Num'])
    return normalize(row['Serie']), float(match.group()) if match else -1, normalize(row['Titre'])


def split_rows(rows):
    owned = sorted((r for r in rows if r['Wishlist'] != '1'), key=sort_key)
    wanted = sorted((r for r in rows if r['Wishlist'] == '1'), key=sort_key)
    return owned, wanted


def num_label(row):
    return row['Num'] or ('HS' if row.get('NumA') == 'HS' else '')


def isbn_digits(row):
    return re.sub(r'[^0-9X]', '', row['ISBN'].upper())


def extra_search_text(row):
    """What can be searched besides the visible series, title and ISBN: publisher and authors."""
    words = normalize(' '.join(row.get(c, '') for c in ('Editeur', 'Scenariste', 'Dessinateur'))).replace(',', ' ').split()
    return ' '.join(dict.fromkeys(words))


def ranges(numbers):
    """[1, 2, 3, 5] -> '1–3, 5'"""
    numbers, parts, i = sorted(numbers), [], 0
    while i < len(numbers):
        j = i
        while j + 1 < len(numbers) and numbers[j + 1] == numbers[j] + 1:
            j += 1
        parts.append(str(numbers[i]) if i == j else f'{numbers[i]}–{numbers[j]}')
        i = j + 1
    return ', '.join(parts)


def group_series(rows):
    """Sorted rows -> [(series, [(row, copies), ...])], identical albums merged with their number of copies."""
    groups = []
    for row in rows:
        if not groups or groups[-1][0] != row['Serie']:
            groups.append((row['Serie'], []))
        entries = groups[-1][1]
        if entries and (entries[-1][0]['Num'], entries[-1][0]['Titre']) == (row['Num'], row['Titre']):
            entries[-1] = (entries[-1][0], entries[-1][1] + 1)
        else:
            entries.append((row, 1))
    return groups


def series_summary(entries):
    count = sum(copies for _, copies in entries)
    parts = [f"{count} album{'s' if count > 1 else ''}"]
    numbers = {int(row['Num']) for row, _ in entries if row['Num'].isdigit()}
    if numbers:
        parts.append(f'tomes {ranges(numbers)}' if len(numbers) > 1 else f'tome {ranges(numbers)}')
        missing = set(range(1, max(numbers) + 1)) - numbers
        if len(numbers) > 1 and missing:
            parts.append(f'<em>manquants {ranges(missing)}</em>')
    return ' · '.join(parts)


def attr(value):
    return html.escape(value, quote=True)


def album_item(row, copies):
    # Kept small: the pages are served without compression. Empty attributes are left out and
    # app.js opens the links in a new tab.
    data = {'num': num_label(row), 'isbn': isbn_digits(row), 'x': extra_search_text(row)}
    attributes = ''.join(f" data-{key}='{attr(value)}'" for key, value in data.items() if value)
    duplicate = f" <mark class='dup' title='Possédé en {copies} exemplaires'>×{copies}</mark>" if copies > 1 else ''
    return (f"<li{attributes}><span class='num'>{html.escape(num_label(row))}</span> "
            f"<a href='{ALBUM_URL.format(attr(row['IdAlbum']))}'>{html.escape(row['Titre'])}</a>{duplicate}</li>")


def series_list(rows):
    blocks = []
    for series, entries in group_series(rows):
        items = '\n'.join(album_item(row, copies) for row, copies in entries)
        blocks.append(f"<details class='serie' data-serie='{attr(display_series(series))}'>\n<summary><strong>{html.escape(display_series(series))}</strong> "
                      f"<small>{series_summary(entries)}</small></summary>\n<ul>\n{items}\n</ul>\n</details>")
    return "<div class='series-view'>\n" + '\n'.join(blocks) + '\n</div>'


SEARCH_BAR = ("<div class='search-bar'>\n"
              "<input type='search' class='album-search' placeholder='Série, n°, titre, ISBN, auteur…' "
              "aria-label='Rechercher dans la collection' autocomplete='off'>\n"
              "<small class='search-count' aria-live='polite'></small>\n</div>\n"
              "<p class='search-empty' hidden>Aucun album trouvé : il n'est pas dans cette liste.</p>")


def nav(collections, current=None):
    links = []
    for c in collections:
        current_attr = " aria-current='page'" if c['key'] == current else ''
        links.append(f"<li><a href='{c['key']}.html'{current_attr}>{html.escape(c['name'])}</a></li>")
    gifts_current = " aria-current='page'" if current == 'a-offrir' else ''
    return (f"<nav>\n<ul><li><a href='index.html'><strong>📚 BD</strong></a></li></ul>\n"
            f"<ul>{''.join(links)}<li><a href='a-offrir.html'{gifts_current}>🎁</a></li></ul>\n</nav>")


def layout(title, description, body):
    template = (HERE / 'templates' / 'layout.html').read_text(encoding='utf-8')
    return fill(template, {'TITLE': html.escape(title), 'DESCRIPTION': attr(description), 'BODY': body})


def fill(template, values):
    for key, value in values.items():
        template = template.replace('{{' + key + '}}', value)
    return template


def render_collection(collection, collections, rows, updated):
    owned, wanted = split_rows(rows)
    name = html.escape(collection['name'])
    gifts = (f"<p><a href='a-offrir.html#{collection['key']}'>🎁 {len(wanted)} idées cadeaux pour {name}</a></p>\n"
             if wanted else '')
    body = f"""<header class='container' id='top'>
{nav(collections, collection['key'])}
<h1>Collection de BD de {name}</h1>
</header>
<main class='container'>
<div class='stats'>
<p><strong>📚 Total :</strong> <span class='series-count'>{len(owned)} albums</span> répartis en <span class='series-count'>{len({r['Serie'] for r in owned})} séries</span></p>
{gifts}<p><small>Mis à jour le {updated}. Les tomes « manquants » sont ceux qui précèdent le dernier tome possédé.</small></p>
</div>
{SEARCH_BAR}
<div class='view-switch' role='group' aria-label='Affichage'>
<button type='button' class='outline' data-view='series' aria-pressed='true'>Par série</button>
<button type='button' class='outline' data-view='table' aria-pressed='false'>Tableau</button>
</div>
{series_list(owned)}
<div class='table-view' hidden></div>
</main>"""
    return layout(f'Collection de BD de {collection["name"]}',
                  f'Les {len(owned)} albums de BD de {collection["name"]}, pour éviter les doublons.', body)


def render_gifts(collections, wanted_by_key, updated):
    sections = []
    for c in collections:
        wanted = wanted_by_key[c['key']]
        content = series_list(wanted) if wanted else '<p>Pas encore de liste de souhaits.</p>'
        sections.append(f"<section id='{c['key']}'>\n<h2>{html.escape(c['name'])} <small>({len(wanted)})</small></h2>\n{content}\n</section>")
    total = sum(len(w) for w in wanted_by_key.values())
    body = f"""<header class='container' id='top'>
{nav(collections, 'a-offrir')}
<h1>🎁 Idées cadeaux</h1>
</header>
<main class='container'>
<p>Les albums que chacun aimerait recevoir. Cliquez sur un titre pour voir l'album. Mis à jour le {updated}.</p>
{SEARCH_BAR}
{''.join(sections)}
</main>"""
    return layout('Idées cadeaux BD', f'{total} idées de BD à offrir.', body)


def purchase_date(row):
    try:
        return datetime.strptime(row.get('DateAchat', ''), '%d/%m/%Y')
    except ValueError:
        return datetime.min


def render_index(collections, owned_by_key, wanted_by_key, updated):
    cards = []
    for c in collections:
        owned = owned_by_key[c['key']]
        recent = sorted((r for r in owned if purchase_date(r) > datetime.min), key=purchase_date, reverse=True)[:RECENT_COUNT]
        recent_items = ''.join(
            f"<li><a href='{ALBUM_URL.format(attr(r['IdAlbum']))}' target='_blank' rel='noopener'>"
            f"{html.escape(display_series(r['Serie']))}{' ' + html.escape(num_label(r)) if num_label(r) else ''}"
            f"</a> <small>{purchase_date(r).strftime('%d/%m/%Y')}</small></li>" for r in recent)
        gifts = len(wanted_by_key[c['key']])
        gifts_line = f" · <a href='a-offrir.html#{c['key']}'>🎁 {gifts} idées cadeaux</a>" if gifts else ''
        recent_block = f"<p><small>Derniers ajouts :</small></p><ul class='recent'>{recent_items}</ul>" if recent else ''
        cards.append(f"""<article class='collection-card'>
<h2>📖 {html.escape(c['name'])}</h2>
<p><strong>{len(owned)} albums</strong>{gifts_line}</p>
{recent_block}
<a href='{c['key']}.html' role='button'>Voir la collection →</a>
</article>""")
    total = sum(len(o) for o in owned_by_key.values())
    total_gifts = sum(len(w) for w in wanted_by_key.values())
    body = f"""<header class='container' id='top'>
<h1>📚 Collections de BD</h1>
</header>
<main class='container'>
<article class='intro'>
<p>Vous voulez offrir une BD ? Vérifiez ici qu'elle n'est pas déjà dans une collection.</p>
<label for='global-search'><strong>Qui a déjà cet album ?</strong></label>
<div class='global-search' role='search'>
<input type='search' id='global-search' placeholder='Série, n°, titre ou ISBN…' autocomplete='off'>
<button type='button' class='scan' hidden aria-label='Scanner le code-barres'>📷</button>
</div>
<div class='scanner' hidden><video playsinline muted></video><button type='button' class='secondary scan-stop'>Fermer</button></div>
<ul class='global-results' aria-live='polite'></ul>
<a href='a-offrir.html' role='button' class='secondary'>🎁 Idées cadeaux ({total_gifts})</a>
</article>
<div class='cards'>
{''.join(cards)}
</div>
<footer><small>Mis à jour le {updated} · Total : {total} albums</small></footer>
</main>"""
    return layout('Collections de BD', f'{total} albums de BD, et {total_gifts} idées cadeaux.', body)


def albums_json(collections, rows_by_key):
    albums = []
    for c in collections:
        for row in rows_by_key[c['key']]:
            albums.append([c['key'], row['IdAlbum'], display_series(row['Serie']), num_label(row), row['Titre'],
                           isbn_digits(row), extra_search_text(row), 1 if row['Wishlist'] == '1' else 0])
    names = {c['key']: c['name'] for c in collections}
    # Compact: one array per album, see the fields in setupGlobalSearch() (static/app.js)
    return json.dumps({'names': names, 'albums': albums}, ensure_ascii=False, separators=(',', ':'))


def build(root=HERE, now=None):
    now = now or datetime.now()
    updated = now.strftime('%d/%m/%Y à %H:%M')
    collections = read_collections(root / 'collections.conf')

    staged = {}
    for c in collections:
        tmp_file = root / 'tmp' / f"{c['key']}.csv"
        if not tmp_file.exists():
            raise ValueError(f'{tmp_file} does not exist')
        try:
            rows = parse_csv(tmp_file.read_text(encoding='utf-8'))
        except ValueError as error:
            raise ValueError(f'{tmp_file}: {error}') from error
        data_file = root / 'data' / f"{c['key']}.csv"
        try:
            previous = len(parse_csv(data_file.read_text(encoding='utf-8'))) if data_file.exists() else 0
        except ValueError:
            previous = 0
        if len(rows) < previous * MIN_KEPT_RATIO:
            raise ValueError(f'{tmp_file} has {len(rows)} albums (previous: {previous}), refusing to publish')
        staged[c['key']] = rows

    (root / 'data').mkdir(exist_ok=True)
    public = root / 'public'
    public.mkdir(exist_ok=True)
    for c in collections:
        data_file = root / 'data' / f"{c['key']}.csv"
        if data_file.exists():
            shutil.move(data_file, f'{data_file}.back')
        shutil.move(root / 'tmp' / f"{c['key']}.csv", data_file)

    for static_file in (HERE / 'static').iterdir():
        if static_file.name != 'sw.js':
            shutil.copy(static_file, public / static_file.name)

    owned_by_key, wanted_by_key = {}, {}
    for c in collections:
        owned_by_key[c['key']], wanted_by_key[c['key']] = split_rows(staged[c['key']])
        page = render_collection(c, collections, staged[c['key']], updated)
        (public / f"{c['key']}.html").write_text(page, encoding='utf-8')
    (public / 'a-offrir.html').write_text(render_gifts(collections, wanted_by_key, updated), encoding='utf-8')
    (public / 'index.html').write_text(render_index(collections, owned_by_key, wanted_by_key, updated), encoding='utf-8')
    (public / 'albums.json').write_text(albums_json(collections, staged), encoding='utf-8')

    # The service worker caches the site for offline use; its version changes with every build
    pages = ['./', 'index.html', 'a-offrir.html', 'albums.json'] + [f"{c['key']}.html" for c in collections]
    assets = [f.name for f in (HERE / 'static').iterdir() if f.name not in ('sw.js', 'robots.txt')]
    worker = fill((HERE / 'static' / 'sw.js').read_text(encoding='utf-8'),
                  {'VERSION': now.strftime('%Y%m%d%H%M%S'), 'FILES': json.dumps(pages + sorted(assets))})
    (public / 'sw.js').write_text(worker, encoding='utf-8')

    # Freshness marker served as /up, written last: it only exists if everything was rebuilt
    counts = {key: len(owned) for key, owned in owned_by_key.items()}
    summary = ' '.join(f'{key}={count}' for key, count in counts.items())
    (public / 'up').write_text(f'ok {now.astimezone().isoformat(timespec="seconds")} {summary}\n', encoding='utf-8')
    return counts


if __name__ == '__main__':
    try:
        print(', '.join(f'{k}: {v} albums' for k, v in build().items()))
    except ValueError as error:
        print(f'[error] {error}', file=sys.stderr)
        sys.exit(1)
