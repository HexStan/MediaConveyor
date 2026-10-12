import os
import sqlite3


class DBManager:
    def __init__(self, db_path="data/media-conveyor.db"):
        self.db_path = db_path

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS meta ("
            "    key   TEXT PRIMARY KEY,"
            "    value TEXT NOT NULL"
            ")"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS file_state ("
            "    filepath              TEXT PRIMARY KEY,"
            "    success_time          REAL,"
            "    failure_count         INTEGER NOT NULL DEFAULT 0,"
            "    ffmpeg_failure_count  INTEGER NOT NULL DEFAULT 0"
            ")"
        )
        self._conn.commit()

    def get_failure_count(self, filepath):
        row = self._conn.execute(
            "SELECT failure_count FROM file_state WHERE filepath = ?", (filepath,)
        ).fetchone()
        return row[0] if row else 0

    def get_ffmpeg_failure_count(self, filepath):
        row = self._conn.execute(
            "SELECT ffmpeg_failure_count FROM file_state WHERE filepath = ?",
            (filepath,),
        ).fetchone()
        return row[0] if row else 0

    def get_success_time(self, filepath):
        row = self._conn.execute(
            "SELECT success_time FROM file_state WHERE filepath = ?", (filepath,)
        ).fetchone()
        return row[0] if row else None

    def increment_failure(self, filepath):
        self._conn.execute(
            "INSERT INTO file_state (filepath, failure_count) VALUES (?, 1)"
            " ON CONFLICT(filepath) DO UPDATE SET failure_count = failure_count + 1",
            (filepath,),
        )
        self._conn.commit()

    def increment_ffmpeg_failure(self, filepath):
        self._conn.execute(
            "INSERT INTO file_state (filepath, ffmpeg_failure_count) VALUES (?, 1)"
            " ON CONFLICT(filepath) DO UPDATE SET ffmpeg_failure_count = ffmpeg_failure_count + 1",
            (filepath,),
        )
        self._conn.commit()

    def mark_success(self, filepath, timestamp):
        self._conn.execute(
            "INSERT INTO file_state (filepath, success_time, failure_count, ffmpeg_failure_count)"
            " VALUES (?, ?, 0, 0)"
            " ON CONFLICT(filepath) DO UPDATE SET"
            "    success_time = excluded.success_time,"
            "    failure_count = 0,"
            "    ffmpeg_failure_count = 0",
            (filepath, timestamp),
        )
        self._conn.commit()

    def delete_record(self, filepath):
        self._conn.execute("DELETE FROM file_state WHERE filepath = ?", (filepath,))
        self._conn.commit()

    def get_version(self):
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'user_data_version'"
        ).fetchone()
        return int(row[0]) if row else None

    def set_version(self, version):
        self._conn.execute(
            "INSERT INTO meta (key, value) VALUES ('user_data_version', ?)"
            " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(version),),
        )
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass

    def __del__(self):
        self.close()
