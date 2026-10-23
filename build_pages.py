"""Build the public pages from the BDGest CSV exports (usage: build_pages.py).

For every collection listed in collections.conf, validates ./tmp/<key>.csv, promotes it to
./data/<key>.csv (keeping the previous one as .back) and writes ./public/<key>.html.
Nothing is touched unless every export is valid, so an error page is never published.
Also writes ./public/index.html and ./public/up.
"""
import csv
import html
import io
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED_COLUMNS = ('IdAlbum', 'ISBN', 'Serie', 'Num', 'Titre', 'Wishlist')
# A new export with less than this share of the previous rows is considered broken
MIN_KEPT_RATIO = 0.5


def read_collections(path):
    collections = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            key, collection_id, name = line.split(':', 2)
            collections.append({'key': key, 'id': int(collection_id), 'name': name})
    return collections


def parse_csv(text):
    """Returns the rows of a BDGest export, raises ValueError if it is not one."""
    reader = csv.DictReader(io.StringIO(text.lstrip('﻿'), newline=''), delimiter=';')
    missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f'not a BDGest export (missing columns: {", ".join(missing)})')
    rows = [row for row in reader if row['IdAlbum']]
    if not rows:
        raise ValueError('no album in the export')
    return rows


def sort_key(row):
    series = unicodedata.normalize('NFD', row['Serie']).encode('ascii', 'ignore').decode().casefold()
    match = re.match(r'\d+(\.\d+)?', row['Num'])
    return series, float(match.group()) if match else -1, row['Titre'].casefold()


def split_rows(rows):
    owned = sorted((r for r in rows if r['Wishlist'] != '1'), key=sort_key)
    wanted = sorted((r for r in rows if r['Wishlist'] == '1'), key=sort_key)
    return owned, wanted


def table(rows, table_id):
    lines = [f"<table id='{table_id}' role='table'>", '<thead>', '<tr>']
    for index, (label, css) in enumerate([('Série', ''), ('N°', ''), ('Titre', ''), ('ISBN', " class='isbn-col'")]):
        lines.append(f"<th onclick='sortTable(this, {index})'{css} scope='col'>{label} ▲▼</th>")
    lines += ['</tr>', '</thead>', '<tbody>']
    for row in rows:
        lines.append(
            '<tr>'
            f"<td><strong>{html.escape(row['Serie'])}</strong></td>"
            f"<td>{html.escape(row['Num'])}</td>"
            f"<td>{html.escape(row['Titre'])}</td>"
            f"<td class='isbn-col'>{html.escape(row['ISBN'])}</td>"
            '</tr>')
    lines += ['</tbody>', '</table>']
    return '\n'.join(lines)


def fill(template, values):
    for key, value in values.items():
        template = template.replace('{{' + key + '}}', value)
    return template


def render_collection(template, collection, collections, rows, updated):
    owned, wanted = split_rows(rows)
    nav = '\n'.join(f"    <li><a href='./{c['key']}.html'>{html.escape(c['name'])}</a></li>" for c in collections)
    wishlist_link = wishlist_section = ''
    if wanted:
        wishlist_link = f"<p><a href='#a-offrir'>🎁 {len(wanted)} albums à offrir (liste de souhaits)</a></p>\n"
        wishlist_section = (f"<h2 id='a-offrir'>🎁 À offrir ({len(wanted)})</h2>\n"
                            f"<p><small>Albums souhaités mais pas encore possédés.</small></p>\n"
                            f"{table(wanted, 'wishTable')}")
    return fill(template, {
        'NAME': html.escape(collection['name']),
        'NAV': nav,
        'ALBUMS': str(len(owned)),
        'SERIES': str(len({r['Serie'] for r in owned})),
        'UPDATED': updated,
        'WISHLIST_LINK': wishlist_link,
        'OWNED_TABLE': table(owned, 'bdTable'),
        'WISHLIST_SECTION': wishlist_section,
    })


def render_index(template, collections, counts, updated):
    cards = '\n'.join(
        '    <div class="collection-card">\n'
        f'      <h3>📖 {html.escape(c["name"])}</h3>\n'
        f'      <p><strong>{counts[c["key"]]} albums</strong> dans la collection</p>\n'
        f'      <p><a href="{c["key"]}.html" role="button">Voir la collection →</a></p>\n'
        '    </div>\n' for c in collections)
    return fill(template, {'CARDS': cards, 'TOTAL': str(sum(counts.values())), 'UPDATED': updated})


def build(root=HERE, now=None):
    now = now or datetime.now()
    updated = now.strftime('%d/%m/%Y %H:%M')
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
    (root / 'public').mkdir(exist_ok=True)
    for c in collections:
        data_file = root / 'data' / f"{c['key']}.csv"
        if data_file.exists():
            shutil.move(data_file, f'{data_file}.back')
        shutil.move(root / 'tmp' / f"{c['key']}.csv", data_file)

    template = (HERE / 'templates' / 'collection.html').read_text(encoding='utf-8')
    counts = {}
    for c in collections:
        rows = staged[c['key']]
        counts[c['key']] = len(split_rows(rows)[0])
        page = render_collection(template, c, collections, rows, updated)
        (root / 'public' / f"{c['key']}.html").write_text(page, encoding='utf-8')

    index = render_index((HERE / 'templates' / 'index.html').read_text(encoding='utf-8'), collections, counts, updated)
    (root / 'public' / 'index.html').write_text(index, encoding='utf-8')
    # Freshness marker served as /up, written last: it only exists if everything was rebuilt
    summary = ' '.join(f'{key}={count}' for key, count in counts.items())
    (root / 'public' / 'up').write_text(f'ok {now.astimezone().isoformat(timespec="seconds")} {summary}\n', encoding='utf-8')
    return counts


if __name__ == '__main__':
    try:
        print(', '.join(f'{k}: {v} albums' for k, v in build().items()))
    except ValueError as error:
        print(f'[error] {error}', file=sys.stderr)
        sys.exit(1)
