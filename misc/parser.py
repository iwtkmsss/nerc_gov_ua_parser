import requests
from bs4 import BeautifulSoup
import hashlib
import logging
import re
from urllib.parse import urljoin, urlsplit, urlunsplit

from misc import BDB

URL = 'https://www.nerc.gov.ua/derzhavnij-kontrol/normativni-akti-dotrimannya-yakih-pereviryayetsya/u-sferi-teplopostachannya'
REQUEST_TIMEOUT = 30
HASH_VERSION = "site_specific_v3"
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
    else:
        content = soup.find("div", class_="editor-content")

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


def scraping_all_urls_from_main_url(response, base_url):
    soup = BeautifulSoup(response.text, "lxml")
    urls_block = soup.find("div", class_="editor-content")
    if urls_block is None:
        raise ValueError("Unable to find the urls block in the parsed HTML")

    links = []
    for url in urls_block.find_all("li"):
        link = url.find("a")
        if link is None or not link.has_attr("href"):
            continue
        links.append(urljoin(base_url, link["href"]))

    return links


def parse():
    changes = []
    migrate_hashes = BDB.get_setting("hash_version") != HASH_VERSION

    s = requests.Session()
    
    first_site = BDB.get_url(URL)

    if first_site is None:
        response = get_page(s, URL)
        final_url = canonical_url(response)
        hash_value = get_hash(s, response.text, final_url)
        BDB.replace_url(URL, final_url, hash_value)
    else:
        response = get_page(s, URL)
        final_url = canonical_url(response)
        first_site = BDB.get_url(final_url) or first_site
        hash_value = get_hash(s, response.text, final_url)
        if migrate_hashes:
            BDB.replace_url(URL, final_url, hash_value)
        elif hash_value != first_site['hash']:
            changes.append(final_url)
            BDB.replace_url(URL, final_url, hash_value)
        elif final_url != URL:
            BDB.replace_url(URL, final_url, hash_value)

    urls = scraping_all_urls_from_main_url(response, URL)
    for url in urls:
        site = BDB.get_url(url)

        try:
            response = get_page(s, url)
        except requests.HTTPError as error:
            status_code = error.response.status_code if error.response is not None else "unknown"
            if status_code != 404:
                logging.warning("Skip unavailable url %s, status: %s", url, status_code)
            continue
        except requests.RequestException as error:
            logging.warning("Skip unavailable url %s: %s", url, error)
            continue

        final_url = canonical_url(response)
        site = BDB.get_url(final_url) or site
        hash_value = get_hash(s, response.text, final_url)
        if site is None:
            BDB.replace_url(url, final_url, hash_value)
        else:
            if migrate_hashes:
                BDB.replace_url(url, final_url, hash_value)
            elif hash_value != site['hash']:
                changes.append(final_url)
                BDB.replace_url(url, final_url, hash_value)
            elif final_url != url:
                BDB.replace_url(url, final_url, hash_value)

    if migrate_hashes:
        BDB.edit_setting("hash_version", HASH_VERSION)
        return []

    return changes
