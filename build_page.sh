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
      echo "<p>Dernière mise à jour : $date</p>"
      echo "<input type='search' placeholder='Type here to filter the list' oninput='filterByName(event)' >"
      echo "<table id='bdTable'>"
      echo "<thead>"
      echo "<tr>"
      echo "<th onclick='sortTable(0)' style='cursor: pointer;'>Serie ▲▼</th>"
      echo "<th onclick='sortTable(1)' style='cursor: pointer;'>Num ▲▼</th>"
      echo "<th onclick='sortTable(2)' style='cursor: pointer;'>Titre ▲▼</th>"
      echo "<th onclick='sortTable(3)' style='cursor: pointer;'>ISBN ▲▼</th>"
      echo "</tr>"
      echo "</thead>"
      echo "<tbody>"
      sort -t';' -k3,3 -f "$file" | while IFS=";" read -r idAlbum isbn serie num numa title rest; do
        serie=$(echo "$serie" | sed -e 's/^"//' -e 's/"$//')
        title=$(echo "$title" | sed -e 's/^"//' -e 's/"$//')
        echo "<tr>"
        echo "<td>$serie</td>"
        echo "<td>$num</td>"
        echo "<td>$title</td>"
        echo "<td>$isbn</td>"
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
