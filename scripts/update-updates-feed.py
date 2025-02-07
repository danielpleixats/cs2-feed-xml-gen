import os
import sys
import locale
import feedparser
import hashlib
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from datetime import datetime
import time

base_url = 'https://www.counter-strike.net'
content_url = base_url + '/news/updates'

language_map = {
    'english': ('en', 'en_US'),
    'german': ('de', 'de_DE'),
    # 'spanish': ('es', 'es_ES')
}

try:
    options = Options()
    options.add_argument('--headless')
    options.add_experimental_option('prefs', {'intl.accept_languages': 'en-US,en;q=0.9'})
    options.add_argument('--lang=en-US')
    driver = webdriver.Chrome(options=options)
except:
    sys.exit(f'Failed to initialize the headless web browser.')

for language_name, (language_code, language_locale) in language_map.items():
    url = f'{content_url}?l={language_name}'

    try:
        driver.get(url)

        element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div[class^="blogoverviewpage_SubUpdates"]'))
        )

        html_content = driver.page_source

    except TimeoutException:
        driver.quit()
        sys.exit(f'Unable to find the updates container in the given time frame.')
    except Exception as e:
        driver.quit()
        sys.exit(f'Failed to extract the HTML data: {e}')

    soup = BeautifulSoup(html_content, 'html.parser')
    capsule_divs = soup.select('div[class*="updatecapsule_UpdateCapsule"]')

    updates = []

    locale.setlocale(locale.LC_TIME, 'en_US.UTF-8')  # Establecer el locale a inglés
    date_format = '%B %d, %Y'

    for capsule in capsule_divs:
        title = capsule.select_one('div[class*="updatecapsule_Title"]').text.strip()
        date_str = capsule.select_one('div[class*="updatecapsule_Date"]').text.strip() # Obtener el texto de la fecha
        try:
          date = datetime.strptime(date_str, date_format)
        except ValueError as e:
          print(f"Error al parsear la fecha: {e}. Cadena a parsear: '{date_str}', Formato intentado: '{date_format}'")
          continue # Saltar al siguiente elemento si la fecha no se puede parsear

        desc = capsule.select_one('div[class*="updatecapsule_Desc"]').decode_contents().strip()

        while desc.startswith('<br'):
            index = desc.index('>') + 1
            desc = desc[index:]

        updates.append({
            'guid': hashlib.sha256(f'{date.day}{date.month}{date.year}'.encode()).hexdigest(),
            'title': title,
            'date': date,
            'content': desc
        })

    github_workspace = os.getenv('GITHUB_WORKSPACE')
    if github_workspace:
        rss_feed_file = os.path.join(github_workspace, 'feeds', f'updates-feed-{language_code}.xml')
    else:
        rss_feed_file = os.path.join(os.pardir, 'feeds', f'updates-feed-{language_code}.xml')

    new_entries = []

    if os.path.exists(rss_feed_file):
        current_feed = feedparser.parse(rss_feed_file)
        existing_guids = {entry.guid for entry in current_feed.entries}

        for update in updates:
            if update['guid'] not in existing_guids:
                new_entries.append(update)
    else:
      new_entries = updates

    if new_entries:
        feed_link = f'https://raw.githubusercontent.com/danielpleixats/cs2-feed-xml-gen/refs/heads/main/feeds/updates-feed-{language_code}.xml'

        fg = FeedGenerator()
        fg.title(f'Counter-Strike 2 - Updates ({language_name.capitalize()})')
        fg.description('Counter-Strike 2 Updates Feed')
        fg.link(href=feed_link, rel='self')
        fg.language(language_code)

        all_updates = new_entries + [update for update in updates if update['guid'] in existing_guids] if os.path.exists(rss_feed_file) else new_entries
        all_updates.sort(key=lambda x: x['date'], reverse=True)
        for update in all_updates:
            fe = fg.add_entry()
            fe.source(url)
            fe.guid(update['guid'])
            fe.title(update['title'])
            fe.link({
                'href': url,
                'rel': 'alternate',
                'type': 'text/html',
                'hreflang': language_code,
                'title': update['title']
            })
            fe.pubDate(datetime.strftime(update['date'], '%Y-%m-%dT%H:%M:%SZ'))
            fe.author({'name':'Valve Corporation', 'email':'support@steampowered.com'})
            fe.content(update['content'], None, 'CDATA')
            fe.rights('Valve Corporation')

        rss_content = fg.rss_str(pretty=True)

        with open(rss_feed_file, "wb") as f:
            f.write(rss_content)

        print(f"Actualizado el feed {language_code}")
    else:
        print(f"No hay nuevas actualizaciones para {language_code}")

driver.quit()
sys.exit(0)