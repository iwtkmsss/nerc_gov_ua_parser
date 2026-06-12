IMPORTANT_CHANGE_URLS = {
    "https://www.nerc.gov.ua/derzhavnij-kontrol/normativni-akti-dotrimannya-yakih-pereviryayetsya/u-sferi-teplopostachannya": (
        "сторінка нормативних актів, дотримання яких перевіряється у сфері теплопостачання"
    )
}


def format_monitoring_log(user, log):
    subscribed_at = user.get("subscribed_at") or "немає даних"
    last_checked_at = log.get("last_checked_at") or "ще не перевірялось"
    last_changes_at = log.get("last_changes_at") or "змін ще не було"

    return (
        "Ви підписані на відстежування змін.\n\n"
        f"Підписка активна з: <b>{subscribed_at}</b>\n"
        f"Перевірок виконано: <b>{log.get('check_count', 0)}</b>\n"
        f"Остання перевірка: <b>{last_checked_at}</b>\n"
        f"Змін під час останньої перевірки: <b>{log.get('last_changes_count', 0)}</b>\n"
        f"Останні зміни знайдено: <b>{last_changes_at}</b>"
    )


def format_changes_message(changes):
    important_changes = [url for url in changes if url in IMPORTANT_CHANGE_URLS]
    regular_changes = [url for url in changes if url not in IMPORTANT_CHANGE_URLS]
    parts = ["Знайдено зміни на сайті НКРЕКП."]

    if important_changes:
        important_links = "\n".join(
            f"{index}. {IMPORTANT_CHANGE_URLS[url]}:\n{url}"
            for index, url in enumerate(important_changes, start=1)
        )
        parts.append(f"<b>ВАЖЛИВО</b>\n{important_links}")

    if regular_changes:
        title = "Інші зміни:" if important_changes else "Змінені сторінки:"
        links = "\n".join(f"{index}. {url}" for index, url in enumerate(regular_changes, start=1))
        parts.append(f"{title}\n{links}")

    return "\n\n".join(parts)
