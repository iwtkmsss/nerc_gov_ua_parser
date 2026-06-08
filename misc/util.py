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
    links = "\n".join(f"{index}. {url}" for index, url in enumerate(changes, start=1))
    return (
        "Знайдено зміни на сайті НКРЕКП.\n\n"
        f"{links}"
    )
