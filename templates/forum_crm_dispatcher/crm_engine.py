import os
import sys
import sqlite3
import time
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crm_tickets.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            category TEXT,
            subject TEXT,
            topic_id INTEGER,
            status TEXT DEFAULT 'OPEN',
            created_at REAL,
            updated_at REAL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            sender TEXT,
            text TEXT,
            timestamp REAL
        )
    """)
    conn.commit()
    conn.close()

def create_ticket(user_id: int, username: str, category: str, subject: str) -> Dict:
    now = time.time()
    # Mock topic_id generation for forums
    topic_id = int(str(user_id)[-4:]) + 1000
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO tickets (user_id, username, category, subject, topic_id, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'OPEN', ?, ?)
    """, (user_id, username or "Anonymous", category, subject, topic_id, now, now))
    tid = cur.lastrowid
    cur.execute("""
        INSERT INTO messages (ticket_id, sender, text, timestamp)
        VALUES (?, 'USER', ?, ?)
    """, (tid, subject, now))
    conn.commit()
    conn.close()
    return {
        "id": tid,
        "user_id": user_id,
        "username": username,
        "category": category,
        "subject": subject,
        "topic_id": topic_id,
        "status": "OPEN",
        "created_at": now
    }

def get_user_tickets(user_id: int) -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, category, subject, topic_id, status, created_at FROM tickets WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "category": r[1],
            "subject": r[2],
            "topic_id": r[3],
            "status": r[4],
            "created_at": r[5]
        }
        for r in rows
    ]

def add_reply(ticket_id: int, sender: str, text: str) -> bool:
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,))
    if not cur.fetchone():
        conn.close()
        return False
    cur.execute("INSERT INTO messages (ticket_id, sender, text, timestamp) VALUES (?, ?, ?, ?)", (ticket_id, sender, text, now))
    cur.execute("UPDATE tickets SET updated_at = ?, status = 'PENDING' WHERE id = ?", (now, ticket_id))
    conn.commit()
    conn.close()
    return True

def close_ticket(ticket_id: int) -> bool:
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE tickets SET status = 'RESOLVED', updated_at = ? WHERE id = ?", (now, ticket_id))
    affected = cur.rowcount
    conn.commit()
    conn.close()
    return affected > 0

def get_crm_stats() -> Dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tickets")
    total = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM tickets WHERE status = 'OPEN'")
    opened = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM tickets WHERE status = 'PENDING'")
    pending = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM tickets WHERE status = 'RESOLVED'")
    resolved = cur.fetchone()[0] or 0
    conn.close()
    return {
        "total": total,
        "open": opened,
        "pending": pending,
        "resolved": resolved,
        "agents": 3
    }

if __name__ == "__main__":
    init_db()
    t = create_ticket(1234567, "tester", "Billing", "Payment not received")
    print("Created ticket:", t)
    add_reply(t["id"], "SUPPORT", "Checking transaction hash...")
    print("Tickets for user:", get_user_tickets(1234567))
    print("CRM stats:", get_crm_stats())
