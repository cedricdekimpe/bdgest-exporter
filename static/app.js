'use strict';
// Search, views, global search, barcode scanner and offline support for bd.dkmp.be.
// No inline handlers: the Content-Security-Policy only allows this file.

function normalize(text) {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function searchTokens(query) {
  return normalize(query).split(/\s+/).filter(Boolean)
    // "978-2-8001-6700-8" is an ISBN: compare it without dashes
    .map(token => /^[\d-]+x?$/.test(token) ? token.replace(/-/g, '') : token);
}

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Every token has to match. A number is a volume ("nelson 12"), part of an ISBN or a whole word of the text.
function matches(album, tokens) {
  return tokens.every(token => {
    if (/^\d+$/.test(token)) {
      return album.num === token
        || (token.length >= 4 && album.isbn.includes(token))
        || new RegExp('\\b' + escapeRegExp(token) + '\\b').test(album.q);
    }
    return album.q.includes(token);
  });
}

function storage(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(key);
    localStorage.setItem(key, value);
  } catch (e) { /* private mode: not remembered */ }
  return null;
}

// ---- Collection and gift pages ------------------------------------------------------------

function setupAlbumSearch() {
  const input = document.querySelector('.album-search');
  if (!input) return;
  const items = Array.from(document.querySelectorAll('details.serie li'));
  // The searchable text is rebuilt from the page rather than sent twice
  const albums = items.map(item => ({
    num: item.dataset.num || '',
    isbn: item.dataset.isbn || '',
    q: normalize(`${item.closest('details').dataset.serie} ${item.querySelector('a').textContent} ${item.dataset.x || ''}`),
  }));
  const count = document.querySelector('.search-count');
  const empty = document.querySelector('.search-empty');
  let tableRows = [];

  function apply() {
    const tokens = searchTokens(input.value);
    let visible = 0;
    items.forEach((item, index) => {
      const show = matches(albums[index], tokens);
      item.hidden = !show;
      if (tableRows[index]) tableRows[index].hidden = !show;
      if (show) visible++;
    });
    document.querySelectorAll('details.serie').forEach(details => {
      const any = details.querySelector('li:not([hidden])');
      details.hidden = !any;
      details.open = tokens.length > 0 && !!any;
    });
    count.textContent = tokens.length ? `${visible} album${visible > 1 ? 's' : ''} trouvé${visible > 1 ? 's' : ''}` : '';
    empty.hidden = !(tokens.length && visible === 0);
    // Shareable search: noah.html?q=nelson
    const url = new URL(location.href);
    if (input.value.trim()) url.searchParams.set('q', input.value.trim()); else url.searchParams.delete('q');
    history.replaceState(null, '', url);
  }

  input.addEventListener('input', apply);
  input.value = new URLSearchParams(location.search).get('q') || '';
  if (input.value) apply();

  setupViews(items, rows => { tableRows = rows; apply(); });
}

function setupViews(items, onTableBuilt) {
  const buttons = Array.from(document.querySelectorAll('.view-switch button'));
  const seriesView = document.querySelector('.series-view');
  const tableView = document.querySelector('.table-view');
  if (!buttons.length || !tableView) return;

  function show(view) {
    if (view === 'table' && !tableView.firstChild) onTableBuilt(buildTable(items, tableView));
    seriesView.hidden = view !== 'series';
    tableView.hidden = view !== 'table';
    buttons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.view === view)));
    storage('bd-view', view);
  }

  buttons.forEach(b => b.addEventListener('click', () => show(b.dataset.view)));
  if (storage('bd-view') === 'table') show('table');
}

// Volumes without number sort last
function volume(row) {
  const number = parseFloat(row.dataset.num);
  return Number.isNaN(number) ? Infinity : number;
}

const COLUMNS = [
  { label: 'Série', key: row => [normalize(row.dataset.serie), volume(row)] },
  { label: 'N°', key: row => [volume(row), normalize(row.dataset.serie)] },
  { label: 'Titre', key: row => [normalize(row.querySelector('a').textContent)] },
  { label: 'ISBN', key: row => [row.dataset.isbn || ''], css: 'isbn-col' },
];

function compare(a, b) {
  for (let i = 0; i < a.length; i++) {
    if (a[i] < b[i]) return -1;
    if (a[i] > b[i]) return 1;
  }
  return 0;
}

// The table is built from the series view, so the album data is only sent once
function buildTable(items, container) {
  const table = document.createElement('table');
  const head = table.createTHead().insertRow();
  COLUMNS.forEach((column, index) => {
    const th = document.createElement('th');
    th.scope = 'col';
    if (column.css) th.className = column.css;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = column.label + ' ↕';
    button.addEventListener('click', () => sortTable(table, index));
    th.appendChild(button);
    head.appendChild(th);
  });
  const body = table.createTBody();
  const rows = items.map(item => {
    const row = body.insertRow();
    Object.assign(row.dataset, item.dataset);
    row.dataset.serie = item.closest('details').dataset.serie;
    row.insertCell().textContent = row.dataset.serie;
    row.insertCell().textContent = item.dataset.num || '';
    row.insertCell().appendChild(item.querySelector('a').cloneNode(true));
    const isbn = row.insertCell();
    isbn.className = 'isbn-col';
    isbn.textContent = item.dataset.isbn || '';
    return row;
  });
  // A tap anywhere on the row opens the album, not only on the (small) title
  body.addEventListener('click', event => {
    const row = event.target.closest('tr');
    if (row && !event.target.closest('a')) row.querySelector('a').click();
  });
  container.appendChild(table);
  return rows;
}

function sortTable(table, index) {
  const ths = table.tHead.rows[0].cells;
  const ascending = ths[index].getAttribute('aria-sort') !== 'ascending';
  const body = table.tBodies[0];
  const rows = Array.from(body.rows);
  rows.sort((a, b) => compare(COLUMNS[index].key(a), COLUMNS[index].key(b)) * (ascending ? 1 : -1));
  rows.forEach(row => body.appendChild(row));
  Array.from(ths).forEach((th, i) => {
    if (i === index) th.setAttribute('aria-sort', ascending ? 'ascending' : 'descending');
    else th.removeAttribute('aria-sort');
    th.querySelector('button').textContent = COLUMNS[i].label + (i === index ? (ascending ? ' ▲' : ' ▼') : ' ↕');
  });
}

// ---- Home page: "who already has this album?" --------------------------------------------

function setupGlobalSearch() {
  const input = document.getElementById('global-search');
  if (!input) return;
  const results = document.querySelector('.global-results');
  let albums = null;

  async function load() {
    if (!albums) {
      const data = await (await fetch('albums.json')).json();
      albums = data.albums.map(([key, id, series, num, title, isbn, extra, wished]) => ({
        p: data.names[key], id, s: series, n: num, t: title, w: wished === 1,
        num, isbn, q: normalize(`${series} ${title} ${isbn} ${extra}`),
      }));
    }
    return albums;
  }

  function line(text) {
    const li = document.createElement('li');
    li.textContent = text;
    return li;
  }

  async function search() {
    const tokens = searchTokens(input.value);
    if (!tokens.length || input.value.trim().length < 2) {
      results.replaceChildren();
      return;
    }
    let all;
    try {
      all = await load();
    } catch (e) {
      results.replaceChildren(line('La recherche n\'est pas disponible (hors ligne ?).'));
      return;
    }
    // One line per album, with everyone who owns or wants it
    const found = new Map();
    all.filter(a => matches(a, tokens)).forEach(a => {
      if (!found.has(a.id)) found.set(a.id, { album: a, owners: new Set(), wishers: new Set() });
      found.get(a.id)[a.w ? 'wishers' : 'owners'].add(a.p);
    });
    if (!found.size) {
      results.replaceChildren(line('❌ Personne ne l\'a encore : vous pouvez l\'offrir !'));
      return;
    }
    const items = Array.from(found.values()).slice(0, 15).map(({ album, owners, wishers }) => {
      const li = document.createElement('li');
      const status = [];
      if (owners.size) status.push(`✅ ${[...owners].join(', ')} l'${owners.size > 1 ? 'ont' : 'a'} déjà`);
      if (wishers.size) status.push(`🎁 ${[...wishers].join(', ')} aimerai${wishers.size > 1 ? 'ent' : 't'} l'avoir`);
      const strong = document.createElement('strong');
      strong.textContent = status.join(' · ');
      const link = document.createElement('a');
      link.href = `https://www.bedetheque.com/BD-x-${encodeURIComponent(album.id)}.html`;
      link.target = '_blank';
      link.rel = 'noopener';
      link.textContent = `${album.s}${album.n ? ' ' + album.n : ''} — ${album.t}`;
      li.append(strong, document.createElement('br'), link);
      return li;
    });
    if (found.size > 15) items.push(line(`… et ${found.size - 15} autres : précisez la recherche.`));
    results.replaceChildren(...items);
  }

  input.addEventListener('input', search);
  input.addEventListener('focus', () => load().catch(() => {}), { once: true });
  setupScanner(input, search);
}

// Reads the barcode (ISBN) with the camera. Only where the browser can (Chrome on Android).
function setupScanner(input, search) {
  const button = document.querySelector('.scan');
  const scanner = document.querySelector('.scanner');
  if (!button || !('BarcodeDetector' in window) || !navigator.mediaDevices) return;
  button.hidden = false;
  const video = scanner.querySelector('video');
  let stream = null;

  function stop() {
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null;
    scanner.hidden = true;
  }

  button.addEventListener('click', async () => {
    try {
      const detector = new BarcodeDetector({ formats: ['ean_13', 'ean_8', 'upc_a'] });
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      video.srcObject = stream;
      scanner.hidden = false;
      await video.play();
      while (stream) {
        const codes = await detector.detect(video).catch(() => []);
        if (codes.length) {
          input.value = codes[0].rawValue;
          stop();
          search();
          break;
        }
        await new Promise(resolve => setTimeout(resolve, 250));
      }
    } catch (e) {
      stop();
      alert('Impossible d\'utiliser la caméra. Tapez le numéro ISBN sous le code-barres.');
    }
  });
  scanner.querySelector('.scan-stop').addEventListener('click', stop);
}

// ---- Offline ----------------------------------------------------------------------------------

if ('serviceWorker' in navigator && location.protocol === 'https:') {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}

document.addEventListener('DOMContentLoaded', () => {
  // Album pages open in a new tab (set here to keep the generated pages small)
  document.querySelectorAll('a[href^="https://www.bedetheque.com/"]').forEach(link => {
    link.target = '_blank';
    link.rel = 'noopener';
  });
  setupAlbumSearch();
  setupGlobalSearch();
});
