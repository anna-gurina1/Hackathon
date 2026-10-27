"""The documented backup command must work without loading Flask or real settings."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_sqlite_backup_handles_unicode_spaces_and_preserves_source(tmp_path):
    source = tmp_path / "учебная база с пробелами.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE example (value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO example VALUES (?)", ("только тестовые данные",)
        )
    original = source.read_bytes()
    destination = tmp_path / "резервные копии"
    script = Path(__file__).resolve().parents[1] / "tools" / "backup_sqlite.py"
    result = subprocess.run(
        [sys.executable, str(script), str(source), str(destination)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=True,
        timeout=15,
    )
    backups = list(destination.glob("*.db"))
    assert len(backups) == 1
    assert "Backup created:" in result.stdout
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("SELECT value FROM example").fetchall() == [
            ("только тестовые данные",)
        ]
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert source.read_bytes() == original
