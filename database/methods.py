import sqlite3


class Database:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def add_user(self, tg_id):
        self.cursor.execute(
            "INSERT INTO users (telegram_id) VALUES (?)",
            (tg_id,)
        )
        self.conn.commit()

    def get_user(self, tg_id):
        query = "SELECT * FROM users WHERE telegram_id = ?;"
        self.cursor.execute(query, (tg_id,))
        result = self.cursor.fetchone()
        return dict(result) if result else None

    def update_user_field(self, tg_id, column, value):
        query = f"UPDATE users SET {column} = ? WHERE telegram_id = ?"
        self.cursor.execute(query, (value, tg_id))
        self.conn.commit()

    def get_setting(self, key):
        self.cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = self.cursor.fetchone()
        if row:
            return row["value"]
        return None

    def edit_setting(self, key, new_value):
        self.cursor.execute(
            "UPDATE settings SET value = ? WHERE key = ?",
            (new_value, key)
        )
        self.conn.commit()

    def close(self):
        self.cursor.close()
        self.conn.close()
