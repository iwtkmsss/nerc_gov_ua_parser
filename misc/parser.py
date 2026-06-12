import requests
from bs4 import BeautifulSoup
import hashlib
import json
import logging
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from misc import BDB

REGULATORY_ACTS_URL = 'https://www.nerc.gov.ua/derzhavnij-kontrol/normativni-akti-dotrimannya-yakih-pereviryayetsya/u-sferi-teplopostachannya'
CONSULTATIONS_TIMELINE_URL = 'https://www.nerc.gov.ua/timeline?&type=posts&category_id=8&tag=%D0%9A%D0%BE%D0%BD%D1%81%D1%83%D0%BB%D1%8C%D1%82%D0%B0%D1%86%D1%96%D1%97%20%D0%B7%20%D0%B3%D1%80%D0%BE%D0%BC%D0%B0%D0%B4%D1%81%D1%8C%D0%BA%D1%96%D1%81%D1%82%D1%8E'
PUBLIC_DISCUSSION_RESULTS_URL = 'https://www.nerc.gov.ua/dlya-gromadskosti/konsultaciyi-z-gromadskistyu/rezultati-publichnih-gromadskih-obgovoren'
CONSULTATION_PLANS_URL = 'https://www.nerc.gov.ua/dlya-gromadskosti/konsultaciyi-z-gromadskistyu/plani-provedennya-konsultacij-z-gromadskistyu'
REQUEST_TIMEOUT = 30
HASH_VERSION = "multi_source_v4"
headers = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0"
}


def get_page(session, url):
    response = session.get(url=url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response


def canonical_url(response):
    return response.url


def normalize_text(text):
    return re.sub(r"\s+", " ", text).strip()


def is_rada_url(url):
    return "zakon.rada.gov.ua" in urlsplit(url).netloc


def is_president_url(url):
    return "president.gov.ua" in urlsplit(url).netloc


def build_rada_frame_url(url):
    parsed = urlsplit(url)
    path = parsed.path
    if not path.endswith(".frame"):
        path = f"{path}.frame"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def extract_text(html, url):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "meta", "link", "svg", "path", "form", "input", "button"]):
        tag.decompose()

    if is_president_url(url):
        content = (
            soup.find("div", class_="document_page")
            or soup.find("div", class_="article_content")
            or soup.find("div", class_="document_full")
        )
    elif is_rada_url(url):
        content = (
            soup.find(id="article")
            or soup.find(id="Text")
            or soup.find(id="content")
        )
    elif "nerc.gov.ua" in urlsplit(url).netloc:
        content = soup.find("div", class_="editor-content")
        content = content or soup.find("main", id="layout-content")
    else:
        content = None

    content = content or soup.find("main") or soup.find("article") or soup.body or soup
    return normalize_text(content.get_text(" ", strip=True))


def get_hash(session, html, url):
    if is_rada_url(url):
        try:
            frame_response = get_page(session, build_rada_frame_url(url))
            html = frame_response.text
            url = frame_response.url
        except requests.RequestException as error:
            logging.warning("Unable to load Rada frame for %s: %s", url, error)

    hash_object = hashlib.sha256()
    hash_object.update(extract_text(html, url).encode('utf-8'))
    hex_hash = hash_object.hexdigest()
    return hex_hash


def get_text_hash(text):
    hash_object = hashlib.sha256()
    hash_object.update(normalize_text(text).encode('utf-8'))
    return hash_object.hexdigest()


def get_csrf_token(session):
    response = get_page(session, 'https://www.nerc.gov.ua/csrf-token')
    return json.loads(response.text)


def fetch_timeline_data(session):
    get_page(session, CONSULTATIONS_TIMELINE_URL)
    token = get_csrf_token(session)
    request_headers = {
        **headers,
        'Accept': 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
        'X-CSRF-TOKEN': token,
    }

    page = 1
    items = []
    while True:
        response = session.get(
            'https://www.nerc.gov.ua/api/timeline',
            params={
                'type': 'posts',
                'category_id': '8',
                'tag': 'Консультації з громадськістю',
                'page': page,
            },
            headers=request_headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        for date, date_items in data.get('data', {}).items():
            for item in date_items:
                items.append({
                    'date': date,
                    'time': item.get('time') or '',
                    'date_from': item.get('date_from') or '',
                    'title': item.get('title') or '',
                    'excerpt': item.get('excerpt') or '',
                    'url': item.get('url') or '',
                    'source': item.get('source') or '',
                    'tags': [tag.get('name') or '' for tag in item.get('tags') or []],
                })

        last_page = data.get('last_page') or 1
        if isinstance(last_page, list):
            last_page = last_page[0] if last_page else 1
        if page >= int(last_page):
            break
        page += 1

    items.sort(key=lambda item: (item['date_from'], item['url']))
    return items


def get_timeline_hash(session):
    items = fetch_timeline_data(session)
    payload = json.dumps(items, ensure_ascii=False, sort_keys=True)
    return get_text_hash(payload), [item['url'] for item in items if item.get('url')]


def update_tracked_url(source_url, final_url, hash_value, migrate_hashes, changes):
    site = BDB.get_url(final_url) or BDB.get_url(source_url)
    if site is None:
        BDB.replace_url(source_url, final_url, hash_value)
        return

    if migrate_hashes:
        BDB.replace_url(source_url, final_url, hash_value)
    elif hash_value != site['hash']:
        changes.append(final_url)
        BDB.replace_url(source_url, final_url, hash_value)
    elif final_url != source_url:
        BDB.replace_url(source_url, final_url, hash_value)


def check_html_url(session, source_url, migrate_hashes, changes):
    response = get_page(session, source_url)
    final_url = canonical_url(response)
    hash_value = get_hash(session, response.text, final_url)
    update_tracked_url(source_url, final_url, hash_value, migrate_hashes, changes)
    return response


def get_main_links(response, base_url, predicate=None):
    soup = BeautifulSoup(response.text, "lxml")
    content = (
        soup.find("div", class_="editor-content")
        or soup.find("main", id="layout-content")
        or soup.find("main")
    )
    if content is None:
        raise ValueError("Unable to find the content block in the parsed HTML")

    links = []
    seen = set()
    for link in content.find_all("a", href=True):
        url = urljoin(base_url, link["href"])
        if predicate is not None and not predicate(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        links.append(url)

    return links


def scraping_all_urls_from_main_url(response, base_url):
    return get_main_links(response, base_url)


def check_child_urls(session, urls, migrate_hashes, changes):
    for url in urls:
        try:
            check_html_url(session, url, migrate_hashes, changes)
        except requests.HTTPError as error:
            status_code = error.response.status_code if error.response is not None else "unknown"
            if status_code != 404:
                logging.warning("Skip unavailable url %s, status: %s", url, status_code)
        except requests.RequestException as error:
            logging.warning("Skip unavailable url %s: %s", url, error)


def check_regulatory_acts(session, migrate_hashes, changes):
    response = check_html_url(session, REGULATORY_ACTS_URL, migrate_hashes, changes)
    urls = scraping_all_urls_from_main_url(response, REGULATORY_ACTS_URL)
    check_child_urls(session, urls, migrate_hashes, changes)


def check_timeline(session, migrate_hashes, changes):
    hash_value, item_urls = get_timeline_hash(session)
    update_tracked_url(CONSULTATIONS_TIMELINE_URL, CONSULTATIONS_TIMELINE_URL, hash_value, migrate_hashes, changes)
    check_child_urls(session, item_urls, migrate_hashes, changes)


def check_public_discussion_results(session, migrate_hashes, changes):
    check_html_url(session, PUBLIC_DISCUSSION_RESULTS_URL, migrate_hashes, changes)


def check_consultation_plans(session, migrate_hashes, changes):
    response = check_html_url(session, CONSULTATION_PLANS_URL, migrate_hashes, changes)
    plan_links = get_main_links(
        response,
        CONSULTATION_PLANS_URL,
        lambda url: url.startswith(f"{CONSULTATION_PLANS_URL}/")
    )
    check_child_urls(session, plan_links, migrate_hashes, changes)


def parse():
    changes = []
    migrate_hashes = BDB.get_setting("hash_version") != HASH_VERSION

    s = requests.Session()

    check_regulatory_acts(s, migrate_hashes, changes)
    check_timeline(s, migrate_hashes, changes)
    check_public_discussion_results(s, migrate_hashes, changes)
    check_consultation_plans(s, migrate_hashes, changes)

    if migrate_hashes:
        BDB.edit_setting("hash_version", HASH_VERSION)
        return []

    return changes
