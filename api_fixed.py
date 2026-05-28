"""
甲方后台定时查询工具 - 后端 API（多用户版）
提供登录、产品管理、数据查询、定时任务管理等接口
使用 SQLite 存储，Token 认证
"""

import json
import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError

import db

# ============ 路径管理 ============
DEFAULT_DATA_ROOT = Path.home() / "甲方后台定时查询工具"
DATA_ROOT = DEFAULT_DATA_ROOT
APP_DIR = Path(__file__).parent

# 应用配置路径
APP_CONFIG_PATH = Path.home() / "甲方后台定时查询工具" / "app_config.json"

BEIJING_TZ = timezone(timedelta(hours=8))

# Token 存储（内存，服务重启需重新登录）
TOKENS = {}  # token -> {user_id, username, is_admin, exp}


def _init_db():
    db.init_db()
    # 创建默认管理员账号 admin / admin123
    if not db.get_user_by_username("admin"):
        pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
        db.add_user("admin", pw_hash, is_admin=1)


_init_db()

# ============ Token 工具 ============


def make_token(user):
    token = secrets.token_hex(32)
    TOKENS[token] = {
        "user_id": user["id"],
        "username": user["username"],
        "is_admin": user["is_admin"],
        "exp": datetime.now(BEIJING_TZ).timestamp() + 86400 * 7  # 7天
    }
    return token


def verify_token(handler):
    """从请求头提取并验证 Token，返回用户信息或 None"""
    auth = handler.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    info = TOKENS.get(token)
    if not info:
        return None
    if info["exp"] < datetime.now(BEIJING_TZ).timestamp():
        TOKENS.pop(token, None)
        return None
    return info


# ============ 应用配置 ============

def get_data_root():
    return {"data_root": str(DATA_ROOT)}


def update_data_root(new_path):
    if not new_path or not new_path.strip():
        new_path = str(DEFAULT_DATA_ROOT)
    global DATA_ROOT
    DATA_ROOT = Path(new_path)
    cfg = {}
    APP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if APP_CONFIG_PATH.exists():
        with open(APP_CONFIG_PATH, "r") as f:
            cfg = json.load(f)
    cfg["data_root"] = new_path
    with open(APP_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return {"ok": True, "data_root": new_path}


# ============ 认证接口 ============

def login(username, password):
    user = db.get_user_by_username(username)
    if not user:
        return {"ok": False, "error": "用户不存在"}
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if user["password_hash"] != pw_hash:
        return {"ok": False, "error": "密码错误"}
    token = make_token(user)
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "is_admin": user["is_admin"]
        }
    }


def get_current_user(handler):
    return verify_token(handler)


# ============ 用户管理（管理员） ============

def add_user_api(username, password, is_admin=0):
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    return db.add_user(username, pw_hash, is_admin)


def update_password_api(user_id, new_password):
    pw_hash = hashlib.sha256(new_password.encode()).hexdigest()
    return db.update_user_password(user_id, pw_hash)


def delete_user_api(user_id):
    return db.delete_user(user_id)


def list_users():
    return {"ok": True, "users": db.get_all_users()}


# ============ 产品配置（按 user_id 过滤） ============

def get_products(handler):
    user = verify_token(handler)
    if not user:
        return []
    return db.get_products_by_user(user["user_id"])


def add_product(data, handler):
    user = verify_token(handler)
    if not user:
        return {"ok": False, "error": "未登录"}
    for p in db.get_products_by_user(user["user_id"]):
        if p["name"] == data["name"]:
            return {"ok": False, "error": f"产品 {data['name']} 已存在"}
    return db.add_product(user["user_id"], data)


def update_product(old_name, product, handler):
    user = verify_token(handler)
    if not user:
        return {"ok": False, "error": "未登录"}
    return db.update_product(user["user_id"], old_name, product)


def delete_product(name, handler):
    user = verify_token(handler)
    if not user:
        return {"ok": False, "error": "未登录"}
    return db.delete_product(user["user_id"], name)


# ============ 数据查询 ============

def get_dates(handler):
    user = verify_token(handler)
    if not user:
        return []
    if user["is_admin"]:
        return db.get_all_dates()
    return db.get_dates_by_user(user["user_id"])


def get_data(date, handler, view_user_id=None):
    user = verify_token(handler)
    if not user:
        return {"date": "", "data": {}}

    if view_user_id and user["is_admin"]:
        # 管理员查看指定用户数据
        target_user_id = int(view_user_id)
    else:
        target_user_id = user["user_id"]

    if not date:
        dates = db.get_dates_by_user(target_user_id)
        if not dates:
            return {"date": "", "data": {}}
        date = dates[0]

    return {"date": date, "data": db.get_data_by_user_and_date(target_user_id, date)}


# ============ 测试采集 ============

BASE_URL = "http://16.163.114.99:8990"


def test_product(data):
    report_type = data.get("report_type", "niunai")
    pid = data.get("id")
    token = data.get("token", "")
    channels = data.get("channels", [])
    tz = data.get("timezone", "Etc/GMT+3")

    base = f"{BASE_URL}/report{report_type}.php"
    params = f"id={pid}&token={token}&timezone={quote(tz)}"
    for ch in channels:
        params += f"&channels={quote(ch)}"
    url = f"{base}?{params}"

    try:
        req = Request(url)
        with urlopen(req, timeout=10) as resp:
            result = resp.read().decode("utf-8", errors="replace")
    except (URLError, OSError) as e:
        return {"ok": False, "error": f"请求失败: {e}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    rows = parse_html(result)
    if not rows:
        return {"ok": False, "error": "未获取到数据（可能维护时段或配置错误）", "url": url}

    return {"ok": True, "data": rows, "url": url}


def parse_html(html):
    import re
    rows = []
    pattern = re.compile(
        r'<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>([\d,]+)</td>\s*<td[^>]*>([\d,]+)</td>\s*<td[^>]*>([\d,]+)</td>\s*</tr>',
        re.DOTALL,
    )
    matches = pattern.findall(html)
    for channel, visit, reg, recharge in matches:
        if "合计" in channel.strip():
            continue
        rows.append({
            "channel": channel.strip(),
            "visit": int(visit.replace(",", "")),
            "register": int(reg.replace(",", "")),
            "first_recharge": int(recharge.replace(",", "")),
        })
    return rows


# ============ 定时任务管理（按 user_id） ============

def get_crontab(handler):
    user = verify_token(handler)
    if not user:
        return {"active": False}
    job = db.get_cron_job(user["user_id"])
    if job:
        return {"active": True, "cron_expr": job["cron_expr"], "enabled": job["enabled"]}
    return {"active": False}


def set_crontab(schedule_str, handler):
    user = verify_token(handler)
    if not user:
        return {"ok": False, "error": "未登录"}
    result = db.set_cron_job(user["user_id"], schedule_str)
    return result


def remove_crontab(handler):
    user = verify_token(handler)
    if not user:
        return {"ok": False, "error": "未登录"}
    return db.remove_cron_job(user["user_id"])


# ============ 数据保留 ============

def get_retention_days(handler):
    # 全局设置，存 SQLite
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS app_config (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("SELECT value FROM app_config WHERE key = 'retention_days'")
    row = cur.fetchone()
    conn.close()
    return int(row[0]) if row else 30


def set_retention_days(days, handler):
    user = verify_token(handler)
    if not user or not user["is_admin"]:
        return {"ok": False, "error": "需要管理员权限"}
    conn = db.get_db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS app_config (key TEXT PRIMARY KEY, value TEXT)")
    cur.execute("INSERT OR REPLACE INTO app_config (key, value) VALUES ('retention_days', ?)", (str(days),))
    conn.commit()
    conn.close()
    return {"ok": True, "retention_days": days}


def cleanup_old_data(handler):
    user = verify_token(handler)
    if not user:
        return {"ok": False, "error": "未登录"}
    days = get_retention_days(handler)
    removed = db.cleanup_old_data_by_user(user["user_id"], days)
    return {"ok": True, "removed": removed}


# ============ 手动触发采集 ============

def run_fetch(handler):
    user = verify_token(handler)
    if not user:
        return {"ok": False, "error": "未登录"}
    # 采集该用户的所有产品
    from fetch_reports import fetch_for_user
    result = fetch_for_user(user["user_id"])
    return result
