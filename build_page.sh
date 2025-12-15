#!/bin/bash

date=$(date '+%Y-%m-%d %H:%M:%S')
firstname=$1
echo "Building page for $firstname"
tmp_file="./tmp/${firstname}.csv"
file="./data/${firstname}.csv"
if test -f "${tmp_file}"; then
  mv $file $file.back
  mv $tmp_file $file
  if test -f "${file}"; then
    echo "$file exists."

    (
      echo "<!DOCTYPE html>"
      echo "<html lang='fr'>"
      echo "<head>"
      echo "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css' >"
      echo "<title>Collection de BD de ${firstname^}</title>"
      echo "<meta charset='utf-8'>"
      echo "<meta name='viewport' content='width=device-width, initial-scale=1'>"
      echo "<meta name='color-scheme' content='light dark'>"
      echo "<style>"
      echo "  @media (max-width: 768px) {"
      echo "    table { font-size: 0.875rem; }"
      echo "    th, td { padding: 0.5rem 0.25rem; }"
      echo "    .isbn-col { display: none; }"
      echo "  }"
      echo "  .stats { "
      echo "    background: var(--pico-card-background-color);"
      echo "    padding: 1rem;"
      echo "    border-radius: var(--pico-border-radius);"
      echo "    margin-bottom: 1rem;"
      echo "  }"
      echo "  .stats p { margin: 0.5rem 0; }"
      echo "  th { user-select: none; }"
      echo "  .series-count { font-weight: bold; color: var(--pico-primary); }"
      echo "</style>"
      echo "</head>"
      echo "<body>"
      echo "<script>"
      echo "function filterByName(event) {"
      echo "  const searchTerm = event.target.value.trim().toLowerCase();"
      echo "  const listItems = document.querySelectorAll('table tr');"
      echo ""
      echo "  listItems.forEach(function(item) {"
      echo "    item.style.display = 'revert';"
      echo ""
      echo "    if (!item.innerText.toLowerCase().includes(searchTerm)) {"
      echo "      item.style.display = 'none';"
      echo "    }"
      echo "  })"
      echo "}"
      echo ""
      echo "function sortTable(columnIndex) {"
      echo "  const table = document.getElementById('bdTable');"
      echo "  const tbody = table.querySelector('tbody');"
      echo "  const rows = Array.from(tbody.querySelectorAll('tr'));"
      echo "  const isNumeric = columnIndex === 1;"
      echo ""
      echo "  rows.sort((a, b) => {"
      echo "    const aText = a.cells[columnIndex].textContent.trim();"
      echo "    const bText = b.cells[columnIndex].textContent.trim();"
      echo ""
      echo "    if (isNumeric) {"
      echo "      return parseFloat(aText) - parseFloat(bText);"
      echo "    }"
      echo "    return aText.localeCompare(bText, 'fr', { sensitivity: 'base' });"
      echo "  });"
      echo ""
      echo "  if (table.dataset.sortColumn == columnIndex && table.dataset.sortDirection == 'asc') {"
      echo "    rows.reverse();"
      echo "    table.dataset.sortDirection = 'desc';"
      echo "  } else {"
      echo "    table.dataset.sortDirection = 'asc';"
      echo "  }"
      echo "  table.dataset.sortColumn = columnIndex;"
      echo ""
      echo "  rows.forEach(row => tbody.appendChild(row));"
      echo "}"
      echo "</script>"
      echo ""
      echo "<main class='container'>"
      echo "<h1>Collection de BD de ${firstname^}</h1>"
      echo "<nav>"
      echo "<ul>"
      for fname in aidan noah cedric; do
        echo "<li><a href='./$fname.html'>${fname^}</a></li>"
      done
      echo "</ul>"
      echo "<ul>"
      echo "<li><a href='./index.html'>Accueil</a></li>"
      echo "</ul>"
      echo "</nav>"
      
      # Count total books and series
      total_books=$(wc -l < "$file")
      total_series=$(cut -d';' -f3 "$file" | sed -e 's/^"//' -e 's/"$//' | sort -u | wc -l)
      
      echo "<div class='stats'>"
      echo "<p><strong>📚 Total:</strong> <span class='series-count'>$total_books albums</span> répartis en <span class='series-count'>$total_series séries</span></p>"
      echo "<p><small>💡 Utilisez la recherche ci-dessous pour filtrer par série ou titre</small></p>"
      echo "<p><small>⬆️⬇️ Cliquez sur les en-têtes de colonnes pour trier</small></p>"
      echo "</div>"
      
      echo "<p><small>Dernière mise à jour : $date</small></p>"
      echo "<input type='search' placeholder='🔍 Rechercher une série ou un titre...' oninput='filterByName(event)' aria-label='Rechercher dans la collection'>"
      echo "<table id='bdTable' role='table'>"
      echo "<thead>"
      echo "<tr>"
      echo "<th onclick='sortTable(0)' style='cursor: pointer;' scope='col'>Série ▲▼</th>"
      echo "<th onclick='sortTable(1)' style='cursor: pointer;' scope='col'>N° ▲▼</th>"
      echo "<th onclick='sortTable(2)' style='cursor: pointer;' scope='col'>Titre ▲▼</th>"
      echo "<th onclick='sortTable(3)' style='cursor: pointer;' class='isbn-col' scope='col'>ISBN ▲▼</th>"
      echo "</tr>"
      echo "</thead>"
      echo "<tbody>"
      sort -t';' -k3,3 -f "$file" | while IFS=";" read -r idAlbum isbn serie num numa title rest; do
        serie=$(echo "$serie" | sed -e 's/^"//' -e 's/"$//')
        title=$(echo "$title" | sed -e 's/^"//' -e 's/"$//')
        # Clean up the num field
        num=$(echo "$num" | sed -e 's/^"//' -e 's/"$//')
        echo "<tr>"
        echo "<td><strong>$serie</strong></td>"
        echo "<td>$num</td>"
        echo "<td>$title</td>"
        echo "<td class='isbn-col'>$isbn</td>"
        echo "</tr>"
      done
      echo "</tbody>"
      echo "</table>"
      echo "</main>"
      echo "</body>"
      echo "</html>"
    ) >./public/$firstname.html

  else
    echo "[error] $file does not exists."
    exit 1
  fi

else
  echo "[error] $tmp_file does not exists."
  exit 1
fi
