#! /bin/sh

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
      echo "<table>"
      while IFS=";" read -r idAlbum isbn serie num numa title rest; do
        serie=$(sed -e 's/^"//' -e 's/"$//' <<<"$serie")
        title=$(sed -e 's/^"//' -e 's/"$//' <<<"$title")
        echo "<tr>"
        echo "<td>$serie</td>"
        echo "<td>$num</td>"
        echo "<td>$title</td>"
        echo "<td>$isbn</td>"
        echo "</tr>"
      done <$file
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
