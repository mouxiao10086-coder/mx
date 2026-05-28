#!/usr/bin/env python3
"""
甲方后台定时查询工具 - 数据库操作层（多用户版）
使用 SQLite 存储用户、产品、定时任务、采集数据
"""

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "app.db"
BEIJING_TZ = timezone(timedelta(hours=8))


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """初始化数据库表"""
    conn = get_db()
    cur = conn.cursor()

    # 用户表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )
    """)

    # 产品表（每个用户独立）
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        report_type TEXT NOT NULL,
        pid TEXT NOT NULL,
        token TEXT NOT NULL,
        channels TEXT,
        timezone TEXT DEFAULT 'Etc/GMT+3',
        account TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        UNIQUE(user_id, name)
    )
    """)

    # 定时任务表（每个用户独立）
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cron_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        cron_expr TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        updated_at TEXT NOT NULL
    )
    """)

    # 采集数据表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS daily_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        channel TEXT NOT NULL,
        visit INTEGER DEFAULT 0,
        register INTEGER DEFAULT 0,
        first_recharge INTEGER DEFAULT 0,
        timestamp TEXT NOT NULL,
        UNIQUE(user_id, product_id, date, channel)
    )
    """)

    # 操作日志表
    cur.execute("""
    CREATE TABLE IF NOT EXISTS operation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        detail TEXT,
        created_at TEXT NOT NULL
    )
    """)

    # 创建默认管理员账号 (admin / admin123)
    try:
        import hashlib
        password_hash = hashlib.sha256("admin123".encode()).hexdigest()
        now = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, 1, ?)",
            ("admin", password_hash, now)
        )
        print("✅ 默认管理员账号创建成功: admin / admin123")
    except sqlite3.IntegrityError:
        print("ℹ️  管理员账号已存在")

    conn.commit()
    conn.close()
    print("✅ 数据库初始化完成")


def add_user(username, password_hash, is_admin=0):
    conn = get_db()
    cur = conn.cursor()
    now = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?)",
            (username, password_hash, is_admin, now)
        )
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        return {"ok": True, "user_id": user_id}
    except sqlite3.IntegrityError:
        conn.close()
        return {"ok": False, "error": f"用户 {username} 已存在"}
    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}


def get_user_by_username(username):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_user_by_id(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_all_users():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, is_admin, created_at FROM users ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM operation_logs WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM daily_data WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM cron_jobs WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM products WHERE user_id = ?", (user_id,))
    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


def update_user_password(user_id, password_hash):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ============ 产品操作 ============

def get_products_by_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE user_id = ? ORDER BY id", (user_id,))
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["channels"] = json.loads(d["channels"]) if d["channels"] else []
        result.append(d)
    return result


def get_all_products():
    """管理员用：获取所有用户的产品"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT p.*, u.username FROM products p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.user_id, p.id
    """)
    rows = cur.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["channels"] = json.loads(d["channels"]) if d["channels"] else []
        result.append(d)
    return result


def get_product_by_id(product_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["channels"] = json.loads(d["channels"]) if d["channels"] else []
        return d
    return None


def add_product(user_id, product):
    conn = get_db()
    cur = conn.cursor()
    now = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    channels_json = json.dumps(product.get("channels", []), ensure_ascii=False)
    try:
        cur.execute(
            """INSERT INTO products
               (user_id, name, report_type, pid, token, channels, timezone, account, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, product["name"], product["report_type"],
             str(product["id"]), product["token"],
             channels_json, product.get("timezone", "Etc/GMT+3"),
             product.get("account", ""), now)
        )
        conn.commit()
        product_id = cur.lastrowid
        conn.close()
        return {"ok": True, "id": product_id}
    except sqlite3.IntegrityError:
        conn.close()
        return {"ok": False, "error": f"产品 {product['name']} 已存在"}
    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}


def update_product(user_id, product_id, product):
    conn = get_db()
    cur = conn.cursor()
    # 验证产品属于该用户
    cur.execute("SELECT id FROM products WHERE user_id = ? AND id = ?", (user_id, product_id))
    if not cur.fetchone():
        conn.close()
        return {"ok": False, "error": f"产品不存在或无权修改"}
    channels_json = json.dumps(product.get("channels", []), ensure_ascii=False)
    cur.execute(
        """UPDATE products SET name=?, report_type=?, pid=?, token=?,
           channels=?, timezone=?, account=? WHERE user_id=? AND id=?""",
        (product["name"], product["report_type"], str(product["id"]),
         product["token"], channels_json,
         product.get("timezone", "Etc/GMT+3"),
         product.get("account", ""),
         user_id, product_id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}


def delete_product(user_id, product_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM products WHERE user_id = ? AND id = ?", (user_id, product_id))
    conn.commit()
    conn.close()
    return {"ok": True}


# ============ 定时任务操作 ============

def get_cron_job(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cron_jobs WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def set_cron_job(user_id, cron_expr):
    conn = get_db()
    cur = conn.cursor()
    now = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    existing = get_cron_job(user_id)
    if existing:
        cur.execute(
            "UPDATE cron_jobs SET cron_expr = ?, updated_at = ? WHERE user_id = ?",
            (cron_expr, now, user_id)
        )
    else:
        cur.execute(
            "INSERT INTO cron_jobs (user_id, cron_expr, enabled, updated_at) VALUES (?, ?, 1, ?)",
            (user_id, cron_expr, now)
        )
    conn.commit()
    conn.close()
    return {"ok": True}


def remove_cron_job(user_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM cron_jobs WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


def get_all_cron_jobs():
    """获取所有启用的定时任务（调度器用）"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM cron_jobs WHERE enabled = 1")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============ 数据操作 ============

def save_daily_data(user_id, product_id, date_str, records):
    """保存采集数据（upsert）"""
    conn = get_db()
    cur = conn.cursor()
    for rec in records:
        timestamp = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """INSERT INTO daily_data
               (user_id, product_id, date, channel, visit, register, first_recharge, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, product_id, date, channel)
            DO UPDATE SET visit=excluded.visit, register=excluded.register,
               first_recharge=excluded.first_recharge, timestamp=excluded.timestamp""",
            (user_id, product_id, date_str, rec["channel"],
             rec["visit"], rec["register"], rec["first_recharge"], timestamp)
        )
    conn.commit()
    conn.close()


def get_dates_by_user(user_id):
    """获取某用户所有有数据的日期"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT DISTINCT date FROM daily_data WHERE user_id = ? ORDER BY date DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return [r["date"] for r in rows]


def get_data_by_user_and_date(user_id, date_str):
    """获取某用户某日的所有产品数据"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT d.*, p.name as product_name FROM daily_data d
           JOIN products p ON d.product_id = p.id
           WHERE d.user_id = ? AND d.date = ?
           ORDER BY d.id DESC""",
        (user_id, date_str)
    )
    rows = cur.fetchall()
    conn.close()
    result = {}
    for r in rows:
        name = r["product_name"]
        if name not in result:
            result[name] = []
        result[name].append({
            "channel": r["channel"],
            "visit": r["visit"],
            "register": r["register"],
            "first_recharge": r["first_recharge"],
            "timestamp": r["timestamp"]
        })
    return result


def get_all_dates():
    """管理员用：获取所有有数据的日期"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT date FROM daily_data ORDER BY date DESC")
    rows = cur.fetchall()
    conn.close()
    return [r["date"] for r in rows]


def get_all_data_by_date(date_str):
    """管理员用：获取某日所有用户的数据"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT d.*, p.name as product_name, u.username FROM daily_data d
           JOIN products p ON d.product_id = p.id
           JOIN users u ON d.user_id = u.id
           WHERE d.date = ?
           ORDER BY d.user_id, d.id DESC""",
        (date_str,)
    )
    rows = cur.fetchall()
    conn.close()
    result = {}
    for r in rows:
        key = f"{r['username']}/{r['product_name']}"
        if key not in result:
            result[key] = []
        result[key].append({
            "channel": r["channel"],
            "visit": r["visit"],
            "register": r["register"],
            "first_recharge": r["first_recharge"],
            "timestamp": r["timestamp"]
        })
    return result


def cleanup_old_data_by_user(user_id, days):
    """清理某用户的旧数据"""
    cutoff = (datetime.now(BEIJING_TZ) - __import__('datetime').timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM daily_data WHERE user_id = ? AND date < ?",
        (user_id, cutoff)
    )
    removed = cur.rowcount
    conn.commit()
    conn.close()
    return removed


# ============ 日志操作 ============

def add_log(user_id, action, detail=""):
    """添加操作日志"""
    conn = get_db()
    cur = conn.cursor()
    now = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO operation_logs (user_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
        (user_id, action, detail, now)
    )
    conn.commit()
    conn.close()


def get_logs(limit=100):
    """获取操作日志（管理员用）"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.*, u.username FROM operation_logs l
        JOIN users u ON l.user_id = u.id
        ORDER BY l.id DESC LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
