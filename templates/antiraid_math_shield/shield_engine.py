import os
import sys
import random
import time
import sqlite3
from typing import Tuple, List, Dict

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shield_data.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS verification_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            solved INTEGER,
            response_time REAL,
            timestamp REAL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS active_challenges (
            user_id INTEGER PRIMARY KEY,
            equation TEXT,
            correct_answer INTEGER,
            options TEXT,
            created_at REAL,
            timeout INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rate_limits (
            user_id INTEGER,
            timestamp REAL
        )
    """)
    conn.commit()
    conn.close()

def generate_math_challenge() -> Tuple[str, int, List[int]]:
    ops = ["+", "-", "*"]
    op = random.choice(ops)
    if op == "+":
        a = random.randint(11, 89)
        b = random.randint(11, 89)
        ans = a + b
    elif op == "-":
        a = random.randint(30, 99)
        b = random.randint(11, a - 1)
        ans = a - b
    else:  # multiplication
        a = random.randint(3, 12)
        b = random.randint(3, 12)
        ans = a * b
    
    eq_str = f"{a} {op} {b}"
    
    # Generate 3 plausible decoys
    decoys = set()
    offsets = [-10, 10, -2, 2, -1, 1, -5, 5, -3, 3]
    random.shuffle(offsets)
    for off in offsets:
        val = ans + off
        if val > 0 and val != ans:
            decoys.add(val)
        if len(decoys) == 3:
            break
    
    options = list(decoys) + [ans]
    random.shuffle(options)
    return eq_str, ans, options

def create_challenge_for_user(user_id: int, timeout: int = 60) -> Dict:
    eq, ans, opts = generate_math_challenge()
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO active_challenges (user_id, equation, correct_answer, options, created_at, timeout)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, eq, ans, ",".join(map(str, opts)), now, timeout))
    conn.commit()
    conn.close()
    return {
        "equation": eq,
        "correct_answer": ans,
        "options": opts,
        "timeout": timeout
    }

def verify_user_answer(user_id: int, submitted_val: int) -> Tuple[bool, str]:
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT equation, correct_answer, created_at, timeout FROM active_challenges WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "no_challenge"
    
    eq, correct, created_at, timeout = row
    cur.execute("DELETE FROM active_challenges WHERE user_id = ?", (user_id,))
    
    elapsed = now - created_at
    if elapsed > timeout:
        cur.execute("INSERT INTO verification_stats (user_id, solved, response_time, timestamp) VALUES (?, 0, ?, ?)", (user_id, elapsed, now))
        conn.commit()
        conn.close()
        return False, "timeout"
    
    if submitted_val == correct:
        cur.execute("INSERT INTO verification_stats (user_id, solved, response_time, timestamp) VALUES (?, 1, ?, ?)", (user_id, elapsed, now))
        conn.commit()
        conn.close()
        return True, "success"
    else:
        cur.execute("INSERT INTO verification_stats (user_id, solved, response_time, timestamp) VALUES (?, 0, ?, ?)", (user_id, elapsed, now))
        conn.commit()
        conn.close()
        return False, "wrong_answer"

def check_rate_limit(user_id: int, window: float = 5.0, max_msgs: int = 5) -> bool:
    now = time.time()
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM rate_limits WHERE timestamp < ?", (now - window,))
    cur.execute("SELECT COUNT(*) FROM rate_limits WHERE user_id = ?", (user_id,))
    cnt = cur.fetchone()[0]
    if cnt >= max_msgs:
        conn.close()
        return False
    cur.execute("INSERT INTO rate_limits (user_id, timestamp) VALUES (?, ?)", (user_id, now))
    conn.commit()
    conn.close()
    return True

def get_shield_statistics() -> Dict:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(solved), AVG(response_time) FROM verification_stats")
    row = cur.fetchone()
    total = row[0] or 0
    solved = row[1] or 0
    avg_t = row[2] or 0.0
    blocked = total - solved
    conn.close()
    return {
        "total_checks": total,
        "verified": solved,
        "blocked": blocked,
        "avg_time": avg_t,
        "raid_mode": "ACTIVE 🛡"
    }

if __name__ == "__main__":
    init_db()
    c = create_challenge_for_user(999)
    print("Generated challenge:", c)
    ans = c["correct_answer"]
    res, reason = verify_user_answer(999, ans)
    print(f"Verified {ans}:", res, reason)
    stats = get_shield_statistics()
    print("Shield stats:", stats)
