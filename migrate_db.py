"""One-time update of an EXISTING app.db for the new course studio.

    python migrate_db.py

What it does (the old data stays):
  1. makes a copy: app.db.bak
  2. company_profile: adds the column is_pro (default 0 = not Pro)
  3. course: knowledge_type and duration may be empty now

A fresh database (no app.db yet) does not need this: it is created by run.py.
"""
import re
import shutil
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parent / "app.db"


def columns(con, table):
    return {row[1]: row for row in con.execute(f"PRAGMA table_info({table})")}


def main():
    if not DB.exists():
        print("app.db not found - nothing to migrate (run.py will create a new database).")
        return
    shutil.copy(DB, str(DB) + ".bak")
    print("Backup saved: app.db.bak")

    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys=OFF")

    if "is_pro" not in columns(con, "company_profile"):
        con.execute("ALTER TABLE company_profile ADD COLUMN is_pro BOOLEAN NOT NULL DEFAULT 0")
        print("company_profile.is_pro added")
    else:
        print("company_profile.is_pro already exists")

    cols = columns(con, "course")
    if cols["knowledge_type"][3] or cols["duration"][3]:  # 3 = NOT NULL flag
        sql = con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='course'").fetchone()[0]
        new_sql = re.sub(r"(knowledge_type\s+\w+(?:\(\d+\))?)\s+NOT NULL", r"\1", sql)
        new_sql = re.sub(r"(duration\s+\w+)\s+NOT NULL", r"\1", new_sql)
        new_sql = new_sql.replace("CREATE TABLE course", "CREATE TABLE course_new", 1)
        con.execute(new_sql)
        con.execute("INSERT INTO course_new SELECT * FROM course")
        con.execute("DROP TABLE course")
        con.execute("ALTER TABLE course_new RENAME TO course")
        print("course.knowledge_type and course.duration are optional now")
    else:
        print("course table is already up to date")

    con.commit()
    problems = con.execute("PRAGMA foreign_key_check").fetchall()
    con.close()
    if problems:
        print("WARNING: foreign key problems:", problems)
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()