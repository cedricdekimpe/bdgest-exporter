"""Export BDGest collections to ./tmp/<filename> (usage: get_collection.py cedric.csv:1 noah.csv:2 ...).

online.bdgest.com sits behind a Cloudflare challenge that rejects plain HTTP clients,
so the login and the export run inside a real (headless) Chromium.
Reads BDGEST_LOGIN and BDGEST_PASSWORD from the environment.
"""
import glob
import os
import sys

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

LOGIN_URL = 'https://online.bdgest.com/login'
# Reuse an already installed Chromium rather than the build Playwright would download
CHROMIUM = os.environ.get('CHROMIUM_PATH') or glob.glob(os.path.expanduser('~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome'))[0]
# Cloudflare rejects the default "HeadlessChrome" User-Agent
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'
CSV_HEADER = 'IdAlbum;ISBN;Serie;Num'


def fail(message):
    print(f'[error] {message}', file=sys.stderr)
    sys.exit(1)


def login(page, email, password):
    page.goto(LOGIN_URL, wait_until='domcontentloaded')
    page.wait_for_selector('form[name=connectform] input[name=username]', state='visible', timeout=60_000)
    page.fill('form[name=connectform] input[name=username]', email)
    page.fill('form[name=connectform] input[name=password]', password)
    page.click('form[name=connectform] input[type=submit]')
    page.wait_for_load_state('load')
    page.wait_for_timeout(3000)


def main():
    exports = [(a.split(':')[0], int(a.split(':')[1])) for a in sys.argv[1:]]
    email = os.environ['BDGEST_LOGIN']
    password = os.environ['BDGEST_PASSWORD']

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM, args=['--headless=new', '--window-size=1366,900', '--disable-blink-features=AutomationControlled'])
        page = browser.new_context(locale='fr-FR', user_agent=USER_AGENT).new_page()
        for attempt in (1, 2):
            try:
                login(page, email, password)
                break
            except PlaywrightTimeoutError:
                title = page.title()
                if 'Access denied' in title:
                    fail('Cloudflare rate limit (error 1015), try again later')
                if attempt == 2:
                    fail(f'login form never became usable (page title: {title!r})')

        bodies = {}
        for filename, collection_id in exports:
            url = f'https://online.bdgest.com/exportation?filename={filename}&collection={collection_id}'
            body = page.evaluate('async (u) => (await fetch(u, {credentials: "include"})).text()', url)
            # Never let an error page (login failure, Cloudflare, "Erreur dans les paramètres"...) pass as a collection
            if not body.startswith(CSV_HEADER) or body.count('\n') < 1:
                fail(f'Export of {filename} is not a valid CSV: {body[:80]!r}')
            bodies[filename] = body
        browser.close()

    # Written only once every export is valid
    for filename, body in bodies.items():
        with open(f'./tmp/{filename}', 'w', encoding='utf-8') as f:
            f.write(body)
        print(f'{filename}: {body.count(chr(10)) - 1} albums')


main()
