import sqlite3
from threading import RLock
from datetime import datetime


class Database:
    def __init__(self, db_file):
        self.lock = RLock()
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.migrate()

    def migrate(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER NOT NULL UNIQUE,
                tg_id INTEGER NOT NULL,
                PRIMARY KEY(id AUTOINCREMENT)
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                id INTEGER NOT NULL UNIQUE,
                url TEXT NOT NULL,
                hash TEXT NOT NULL,
                PRIMARY KEY(id AUTOINCREMENT)
            )
            """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT NOT NULL UNIQUE,
                value TEXT NOT NULL
            )
            """
        )

        user_columns = self._get_columns("users")
        if "is_subscribed" not in user_columns:
            self.cursor.execute("ALTER TABLE users ADD COLUMN is_subscribed INTEGER NOT NULL DEFAULT 0")
        if "registered_at" not in user_columns:
            self.cursor.execute("ALTER TABLE users ADD COLUMN registered_at TEXT")
        if "subscribed_at" not in user_columns:
            self.cursor.execute("ALTER TABLE users ADD COLUMN subscribed_at TEXT")
        if "job_title" not in user_columns:
            self.cursor.execute("ALTER TABLE users ADD COLUMN job_title TEXT NOT NULL DEFAULT 'user'")

        self.cursor.execute("DELETE FROM users WHERE id NOT IN (SELECT MIN(id) FROM users GROUP BY tg_id)")
        self.cursor.execute("DELETE FROM urls WHERE id NOT IN (SELECT MIN(id) FROM urls GROUP BY url)")
        self.cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_tg_id ON users(tg_id)")
        self.cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_urls_url ON urls(url)")

        self.ensure_setting("check_count", "0")
        self.ensure_setting("last_checked_at", "")
        self.ensure_setting("last_changes_count", "0")
        self.ensure_setting("last_changes_at", "")
        self.conn.commit()

    def _get_columns(self, table):
        with self.lock:
            self.cursor.execute(f"PRAGMA table_info({table})")
            return {row["name"] for row in self.cursor.fetchall()}

    @staticmethod
    def now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def add_link(self, url, hash_value):
        with self.lock:
            self.cursor.execute(
                "INSERT OR IGNORE INTO urls (url, hash) VALUES (?, ?)",
                (url, hash_value)
            )
            self.conn.commit()

    def upsert_url(self, url, hash_value):
        with self.lock:
            self.cursor.execute(
                "INSERT INTO urls (url, hash) VALUES (?, ?) "
                "ON CONFLICT(url) DO UPDATE SET hash = excluded.hash",
                (url, hash_value)
            )
            self.conn.commit()

    def replace_url(self, old_url, new_url, hash_value):
        with self.lock:
            if old_url == new_url:
                self.upsert_url(new_url, hash_value)
                return

            self.cursor.execute("DELETE FROM urls WHERE url = ? AND url != ?", (old_url, new_url))
            self.upsert_url(new_url, hash_value)
    
    def add_user(self, tg_id):
        with self.lock:
            self.cursor.execute(
                "INSERT OR IGNORE INTO users (tg_id, registered_at) VALUES (?, ?)",
                (tg_id, self.now())
            )
            self.conn.commit()    

    def get_url(self, url):
        with self.lock:
            query = "SELECT * FROM urls WHERE url = ?;"
            self.cursor.execute(query, (url,))
            result = self.cursor.fetchone()
            return dict(result) if result else None

    def get_user(self, tg_id):
        with self.lock:
            query = "SELECT * FROM users WHERE tg_id = ?;"
            self.cursor.execute(query, (tg_id,))
            result = self.cursor.fetchone()
            return dict(result) if result else None

    def update_urls_field(self, url, column, value):
        if column not in {"hash"}:
            raise ValueError(f"Unsupported urls column: {column}")
        with self.lock:
            query = f"UPDATE urls SET {column} = ? WHERE url = ?"
            self.cursor.execute(query, (value, url))
            self.conn.commit()

    def update_user_field(self, tg_id, column, value):
        if column not in {"is_subscribed", "subscribed_at", "job_title"}:
            raise ValueError(f"Unsupported users column: {column}")
        with self.lock:
            query = f"UPDATE users SET {column} = ? WHERE tg_id = ?"
            self.cursor.execute(query, (value, tg_id))
            self.conn.commit()

    def subscribe_user(self, tg_id):
        with self.lock:
            self.add_user(tg_id)
            self.cursor.execute(
                "UPDATE users SET is_subscribed = 1, subscribed_at = ? WHERE tg_id = ?",
                (self.now(), tg_id)
            )
            self.conn.commit()

    def unsubscribe_user(self, tg_id):
        with self.lock:
            self.cursor.execute(
                "UPDATE users SET is_subscribed = 0, subscribed_at = NULL WHERE tg_id = ?",
                (tg_id,)
            )
            self.conn.commit()

    def get_subscribed_users(self):
        with self.lock:
            self.cursor.execute("SELECT * FROM users WHERE is_subscribed = 1")
            return [dict(row) for row in self.cursor.fetchall()]

    def get_users_by_job_title(self, job_title):
        with self.lock:
            self.cursor.execute("SELECT * FROM users WHERE job_title = ?", (job_title,))
            return [dict(row) for row in self.cursor.fetchall()]

    def ensure_setting(self, key, value):
        with self.lock:
            self.cursor.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )

    def get_setting(self, key):
        with self.lock:
            self.cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = self.cursor.fetchone()
            if row:
                return row["value"]
            return None

    def edit_setting(self, key, new_value):
        with self.lock:
            self.cursor.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(new_value))
            )
            self.conn.commit()

    def record_check(self, changes_count):
        check_count = int(self.get_setting("check_count") or 0) + 1
        now = self.now()
        self.edit_setting("check_count", check_count)
        self.edit_setting("last_checked_at", now)
        self.edit_setting("last_changes_count", changes_count)
        if changes_count:
            self.edit_setting("last_changes_at", now)

    def get_monitoring_log(self):
        return {
            "check_count": int(self.get_setting("check_count") or 0),
            "last_checked_at": self.get_setting("last_checked_at") or "",
            "last_changes_count": int(self.get_setting("last_changes_count") or 0),
            "last_changes_at": self.get_setting("last_changes_at") or "",
        }

    def close(self):
        with self.lock:
            self.cursor.close()
            self.conn.close()
