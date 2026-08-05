"""Small local store for user labels and email-related reminders."""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "mymails.db"


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS priorities (
        folder TEXT NOT NULL, email_id INTEGER NOT NULL, urgency TEXT NOT NULL,
        PRIMARY KEY (folder, email_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS todos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email_id INTEGER NOT NULL,
        folder TEXT NOT NULL, title TEXT NOT NULL, due_at TEXT,
        completed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS priority_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        sender_contains TEXT NOT NULL DEFAULT '', subject_contains TEXT NOT NULL DEFAULT '',
        urgency TEXT NOT NULL, created_at TEXT NOT NULL)""")
    return conn


def priorities_for(folder: str) -> dict[int, str]:
    with connect() as conn:
        rows = conn.execute("SELECT email_id, urgency FROM priorities WHERE folder=?", (folder,))
        return {row["email_id"]: row["urgency"] for row in rows}


def set_priority(folder: str, email_id: int, urgency: str):
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO priorities(folder,email_id,urgency) VALUES(?,?,?)", (folder, email_id, urgency))


def create_todo(email_id: int, folder: str, title: str, due_at: str | None):
    with connect() as conn:
        cur = conn.execute("INSERT INTO todos(email_id,folder,title,due_at,created_at) VALUES(?,?,?,?,?)",
                           (email_id, folder, title, due_at, datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid


def list_todos():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM todos ORDER BY completed, due_at IS NULL, due_at, created_at DESC")
        return [dict(row) for row in rows]


def update_todo(todo_id: int, completed: bool):
    with connect() as conn:
        conn.execute("UPDATE todos SET completed=? WHERE id=?", (int(completed), todo_id))


def delete_todo(todo_id: int):
    with connect() as conn:
        conn.execute("DELETE FROM todos WHERE id=?", (todo_id,))


def list_rules():
    with connect() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM priority_rules ORDER BY id DESC")]


def create_rule(name: str, sender: str, subject: str, urgency: str):
    with connect() as conn:
        cur = conn.execute("INSERT INTO priority_rules(name,sender_contains,subject_contains,urgency,created_at) VALUES(?,?,?,?,?)",
                           (name, sender, subject, urgency, datetime.now().isoformat(timespec="seconds")))
        return cur.lastrowid


def delete_rule(rule_id: int):
    with connect() as conn:
        conn.execute("DELETE FROM priority_rules WHERE id=?", (rule_id,))


def apply_rule(rules: list[dict], from_addr: str, subject: str) -> str | None:
    sender_text, subject_text = from_addr.casefold(), subject.casefold()
    for rule in rules:  # newest rule wins
        sender = rule["sender_contains"].strip().casefold()
        subject_word = rule["subject_contains"].strip().casefold()
        if sender and sender not in sender_text:
            continue
        if subject_word and subject_word not in subject_text:
            continue
        if sender or subject_word:
            return rule["urgency"]
    return None
