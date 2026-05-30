#!/usr/bin/env python3
"""
甲方后台定时查询工具 - Web 多用户版
完全参照原始桌面版 api.py 逻辑，新增多用户隔离。
多用户隔离方式：每个用户的数据存在 ~/甲方后台定时查询工具/users/<username>/ 下
"""

import json
import os
import hashlib
import secrets
import re
import subprocess
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError

from flask import Flask, request, jsonify, send_from_directory

# ============ 路径管理 ============
DEFAULT_ROOT = Path.home() / "甲方后台定时查询工具"
USERS_FILE = DEFAULT_ROOT / "users.json"
CRON_FILE = DEFAULT_ROOT / "cron.json"

BEIJING_TZ = timezone(timedelta(hours=8))
CRON_SECRET = os.environ.get("FETCH_CRON_TOKEN", "cron-secret-2026")

TOKENS = {}  # token -> {username, exp}
TOKENS_LOCK = threading.Lock()


def token_cleaner():
    """后台线程：每小时清理过期 token"""
    while True:
        time.sleep(3600)
        now = datetime.now(BEIJING_TZ).timestamp()
        with TOKENS_LOCK:
            expired = [k for k, v in TOKENS.items() if v.get("exp", 0) < now]
            for k in expired:
                TOKENS.pop(k, None)
app = Flask(__name__, static_folder="web", static_url_path="/static")


@app.after_request
def no_cache(response):
    """禁止浏览器和 CDN 缓存 HTML/JS，确保每次获取最新版本"""
    if request.path.endswith('.html') or request.path == '/' or '/api/' in request.path:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response
BASE_URL = "http://16.163.114.99:8990"


# ============ 用户管理 ============
def load_users():
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"users": [], "next_id": 1}


def save_users(data):
    DEFAULT_ROOT.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ============ 多用户目录 ============
def user_dir(username):
    d = DEFAULT_ROOT / "users" / username
    d.mkdir(parents=True, exist_ok=True)
    (d / "daily").mkdir(exist_ok=True)
    return d


def user_config_path(username):
    return user_dir(username) / "products_config.json"


def user_daily_dir(username):
    return user_dir(username) / "daily"


# ============ Token 认证 ============
def verify_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    with TOKENS_LOCK:
        info = TOKENS.get(token)
    if not info:
        return None
    if info["exp"] < datetime.now(BEIJING_TZ).timestamp():
        with TOKENS_LOCK:
            TOKENS.pop(token, None)
        return None
    return info["username"]


def require_auth():
    username = verify_token()
    if not username:
        return None, jsonify(ok=False, error="未登录或 Token 已过期")
    return username, None


# ============ 产品管理 ============
def load_user_products(username):
    path = user_config_path(username)
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            cfg = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    return cfg.get("products", [])


def save_user_products(username, products):
    path = user_config_path(username)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"products": products, "retention_days": 30}, f, ensure_ascii=False, indent=2)


# ============ 数据查询 ============
def get_user_dates(username):
    daily_dir = user_daily_dir(username)
    dates = []
    if daily_dir.exists():
        for f in sorted(daily_dir.iterdir(), reverse=True):
            if f.suffix == ".json":
                dates.append(f.stem)
    return dates


def get_user_data(username, date=None):
    if not date:  # None 或 "" 都走自动选最新
        dates = get_user_dates(username)
        if not dates:
            return {"date": "", "data": {}}
        date = dates[0]
    data_file = user_daily_dir(username) / f"{date}.json"
    if data_file.exists():
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {"date": date, "data": {}}
        return {"date": date, "data": data}
    return {"date": date, "data": {}}


# ============ HTML 解析 ============
def parse_html(html):
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


# ============ 采集逻辑 ============
def fetch_report(product):
    report_type = product.get("report_type", "niunai")
    channels = product.get("channels", [])
    tz = product.get("timezone", "Etc/GMT+3")

    # 晴天产品 (ads27b): POST JSON 到 /realtime_search
    if report_type == "ads27b":
        merchant = product.get("merchant_id") or product.get("id", "")
        results = []
        for ch in channels:
            try:
                body = json.dumps({
                    "keyword": ch,
                    "timezone": tz,
                    "realtime_today": True,
                    "day_shift": 0,
                    "force_refresh": False,
                }).encode()
                req = Request(
                    f"https://ads27b.com/{merchant}/realtime_search",
                    data=body,
                    headers={"Content-Type": "application/json"},
                )
                with urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="replace"))
                items = (data.get("result") or {}).get("items", [])
                for item in items:
                    results.append({
                        "channel": item.get("keyword", ch),
                        "visit": item.get("visit", 0),
                        "register": item.get("direct_register", 0),
                        "first_recharge": item.get("direct_first", 0),
                    })
            except (URLError, OSError, Exception):
                continue
        return results

    # 普通产品 (niunai/zhugan): GET 带参数
    pid = product.get("pid") or product.get("id")
    token = product.get("token", "")

    base = f"{BASE_URL}/report{report_type}.php"
    params = f"id={pid}&token={token}&timezone={quote(tz)}"
    for ch in channels:
        params += f"&channels={quote(ch)}"
    url = f"{base}?{params}"

    try:
        req = Request(url)
        with urlopen(req, timeout=10) as resp:
            result = resp.read().decode("utf-8", errors="replace")
    except (URLError, OSError):
        return []

    return parse_html(result)


def save_daily_record(username, product_name, records):
    date_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
    data_file = user_daily_dir(username) / f"{date_str}.json"

    existing_data = {}
    if data_file.exists():
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing_data = {}

    if product_name not in existing_data:
        existing_data[product_name] = []

    timestamp = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
    for rec in records:
        record_with_time = {**rec, "timestamp": timestamp}
        existing_data[product_name].append(record_with_time)

    data_file.parent.mkdir(parents=True, exist_ok=True)
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)


# ============ 静态文件 ============
@app.route("/")
def index():
    return send_from_directory("web", "index.html")


@app.route("/login.html")
def login_page():
    return send_from_directory("web", "login.html")


# ============ 认证接口 ============
@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify(ok=False, error="请输入用户名和密码")
    if len(password) < 4:
        return jsonify(ok=False, error="密码至少4位")

    users = load_users()
    if any(u["username"] == username for u in users["users"]):
        return jsonify(ok=False, error="用户名已存在")

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    uid = users["next_id"]
    users["users"].append({
        "id": uid,
        "username": username,
        "password_hash": pw_hash,
        "is_admin": 1 if username == "admin" else 0,
    })
    users["next_id"] = uid + 1
    save_users(users)

    token = secrets.token_hex(32)
    with TOKENS_LOCK:
        TOKENS[token] = {
            "username": username,
        "exp": datetime.now(BEIJING_TZ).timestamp() + 86400 * 7,
    }
    return jsonify(ok=True, token=token, user={"username": username, "is_admin": username == "admin"})


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify(ok=False, error="请输入用户名和密码")

    users = load_users()
    user = next((u for u in users["users"] if u["username"] == username), None)
    if not user:
        return jsonify(ok=False, error="用户不存在")
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    if user["password_hash"] != pw_hash:
        return jsonify(ok=False, error="密码错误")

    token = secrets.token_hex(32)
    with TOKENS_LOCK:
        TOKENS[token] = {
            "username": username,
        "exp": datetime.now(BEIJING_TZ).timestamp() + 86400 * 7,
    }
    return jsonify(ok=True, token=token, user={
        "id": user["id"],
        "username": user["username"],
        "is_admin": user["is_admin"],
    })


@app.route("/api/user")
def api_get_user():
    username = verify_token()
    if not username:
        return jsonify(ok=False)
    users = load_users()
    user = next((u for u in users["users"] if u["username"] == username), None)
    if not user:
        return jsonify(ok=False)
    return jsonify(ok=True, user={
        "id": user["id"],
        "username": user["username"],
        "is_admin": user["is_admin"],
    })


@app.route("/api/change-password", methods=["POST"])
def api_change_password():
    username, err = require_auth()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    old_pwd = data.get("old_password", "")
    new_pwd = data.get("new_password", "")
    if not old_pwd or not new_pwd:
        return jsonify(ok=False, error="请填写旧密码和新密码")
    if len(new_pwd) < 4:
        return jsonify(ok=False, error="新密码至少4位")

    users = load_users()
    user = next((u for u in users["users"] if u["username"] == username), None)
    if not user:
        return jsonify(ok=False, error="用户不存在")
    old_hash = hashlib.sha256(old_pwd.encode()).hexdigest()
    if user["password_hash"] != old_hash:
        return jsonify(ok=False, error="旧密码错误")

    user["password_hash"] = hashlib.sha256(new_pwd.encode()).hexdigest()
    save_users(users)
    return jsonify(ok=True)


# ============ 产品管理接口 ============
@app.route("/api/products", methods=["GET"])
def api_get_products():
    username, err = require_auth()
    if err:
        return err
    products = load_user_products(username)
    return jsonify(ok=True, products=products)


@app.route("/api/products", methods=["POST"])
def api_add_product():
    username, err = require_auth()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(ok=False, error="产品名称不能为空")

    products = load_user_products(username)
    if any(p["name"] == name for p in products):
        return jsonify(ok=False, error=f"产品 {name} 已存在")

    new_product = {
        "name": name,
        "account": data.get("account", ""),
        "report_type": data.get("report_type", "niunai"),
        "id": data.get("pid") or data.get("id"),
        "token": data.get("token", ""),
        "channels": data.get("channels", []),
        "timezone": data.get("timezone", "Etc/GMT+3"),
    }
    if data.get("merchant_id"):
        new_product["merchant_id"] = data["merchant_id"]
    products.append(new_product)
    save_user_products(username, products)
    return jsonify(ok=True)


@app.route("/api/products/<name>", methods=["PUT"])
def api_update_product(name):
    username, err = require_auth()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    # 兼容两种格式：扁平 {name,pid,...} 或嵌套 {product:{name,pid,...}}
    if "product" in data:
        data = data["product"]
    products = load_user_products(username)
    for i, p in enumerate(products):
        if p["name"] == name:
            new_name = (data.get("name") or "").strip()
            if not new_name:
                return jsonify(ok=False, error="产品名称不能为空")
            if new_name != name and any(pp["name"] == new_name for pp in products):
                return jsonify(ok=False, error=f"产品 {new_name} 已存在")
            products[i] = {
                "name": new_name,
                "account": data.get("account", p.get("account", "")),
                "report_type": data.get("report_type", p.get("report_type", "niunai")),
                "id": data.get("pid", data.get("id", p.get("id"))),
                "token": data.get("token", p.get("token", "")),
                "channels": data.get("channels", p.get("channels", [])),
                "timezone": data.get("timezone", p.get("timezone", "Etc/GMT+3")),
            }
            if data.get("merchant_id") or p.get("merchant_id"):
                products[i]["merchant_id"] = data.get("merchant_id", p.get("merchant_id", ""))
            save_user_products(username, products)
            return jsonify(ok=True)
    return jsonify(ok=False, error=f"产品 {name} 不存在")


@app.route("/api/products/<name>", methods=["DELETE"])
def api_delete_product(name):
    username, err = require_auth()
    if err:
        return err
    products = load_user_products(username)
    new_products = [p for p in products if p["name"] != name]
    if len(new_products) == len(products):
        return jsonify(ok=False, error=f"产品 {name} 不存在")
    save_user_products(username, new_products)
    return jsonify(ok=True)


@app.route("/api/test-connection", methods=["POST"])
def api_test_connection():
    username, err = require_auth()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    result = test_product(data)
    return jsonify(result)


# ============ 数据查询接口 ============
@app.route("/api/dates")
def api_get_dates():
    username, err = require_auth()
    if err:
        return err
    dates = get_user_dates(username)
    return jsonify(dates=dates)


@app.route("/api/data")
def api_get_data():
    username, err = require_auth()
    if err:
        return err
    date = request.args.get("date", "")
    result = get_user_data(username, date)
    return jsonify(result)


@app.route("/api/dashboard")
def api_dashboard():
    """合并接口：一次请求返回日期列表+最新数据+产品列表，减少网络往返"""
    username, err = require_auth()
    if err:
        return err
    dates = get_user_dates(username)
    date = request.args.get("date", dates[0] if dates else "")
    data_result = get_user_data(username, date) if date else {"date": "", "data": {}}
    products = load_user_products(username)

    # 读取该用户的定时采集状态
    cron_info = {}
    cron_data = load_cron()
    for task in cron_data.get("tasks", []):
        if task.get("username") == username:
            cron_info = {
                "last_run": task.get("last_run", ""),
                "last_status": task.get("last_status", ""),
                "has_cron": True,
            }
            break

    return jsonify(
        ok=True,
        dates=dates,
        date=date,
        data=data_result.get("data", {}),
        products=products,
        last_cron=cron_info,
    )


@app.route("/api/data/<product_name>/clear", methods=["DELETE"])
def api_clear_product_data(product_name):
    """清除当前用户某个产品今天的全部数据"""
    username, err = require_auth()
    if err:
        return err
    date_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
    data_file = user_daily_dir(username) / f"{date_str}.json"
    if data_file.exists():
        with open(data_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if product_name in data:
            del data[product_name]
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify(ok=True)


@app.route("/api/fetch-one/<product_name>", methods=["POST"])
def api_fetch_one(product_name):
    """只采集一个产品"""
    username, err = require_auth()
    if err:
        return err
    products = load_user_products(username)
    product = next((p for p in products if p["name"] == product_name), None)
    if not product:
        return jsonify(ok=False, error=f"产品 {product_name} 不存在")
    records = fetch_report(product)
    if records:
        save_daily_record(username, product_name, records)
    return jsonify(ok=True, count=len(records))


# ============ 测试采集 ============
def test_product(product):
    report_type = product.get("report_type", "niunai")
    channels = product.get("channels", [])
    tz = product.get("timezone", "Etc/GMT+3")

    if report_type == "ads27b":
        merchant = product.get("merchant_id") or product.get("id", "")
        ch = channels[0] if channels else ""
        body = json.dumps({"keyword": ch, "timezone": tz, "realtime_today": True, "day_shift": 0, "force_refresh": False}).encode()
        try:
            url = f"https://ads27b.com/{merchant}/realtime_search"
            req = Request(url, data=body, headers={"Content-Type": "application/json"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            items = (data.get("result") or {}).get("items", [])
            rows = [{"channel": it.get("keyword",""), "visit": it.get("visit",0), "register": it.get("direct_register",0), "first_recharge": it.get("direct_first",0)} for it in items]
            if not rows:
                return {"ok": False, "error": "未获取到数据", "url": url}
            return {"ok": True, "data": rows, "url": url}
        except (URLError, OSError) as e:
            return {"ok": False, "error": f"请求失败: {e}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    pid = product.get("pid") or product.get("id")
    token = product.get("token", "")

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


# ============ 手动采集 ============
@app.route("/api/fetch-now", methods=["POST"])
def api_fetch_now():
    # cron 脚本用 X-Cron-Token 免密调用
    cron_token = request.headers.get("X-Cron-Token", "")
    data = request.get_json(force=True, silent=True) or {}
    if cron_token == CRON_SECRET:
        username = data.get("username", "admin")
    else:
        username, err = require_auth()
        if err:
            return err
    result = fetch_for_user(username)
    return jsonify(result)


def fetch_for_user(username):
    products = load_user_products(username)
    if not products:
        return {"ok": False, "error": "该用户没有配置产品"}

    date_str = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")
    summary = []
    errors = []

    for product in products:
        name = product["name"]
        try:
            records = fetch_report(product)
            if not records:
                errors.append({"product": name, "error": "未获取到数据（可能维护时段）"})
                continue
            save_daily_record(username, name, records)
            for rec in records:
                summary.append({
                    "product": name,
                    "channel": rec["channel"],
                    "visit": rec["visit"],
                    "register": rec["register"],
                    "first_recharge": rec["first_recharge"],
                })
        except Exception as e:
            errors.append({"product": name, "error": str(e)})

    return {
        "ok": True,
        "date": date_str,
        "summary": summary,
    }


def record_cron_log(username, cron_expr, status, detail=""):
    """记录定时任务执行日志到 cron.json"""
    all_cron = load_cron()
    for task in all_cron.get("tasks", []):
        if task.get("username") == username:
            task["last_run"] = datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
            task["last_status"] = status
            task["last_detail"] = detail[:100] if detail else ""
    save_cron(all_cron)



# ============ 定时任务 API ============
@app.route("/api/cron", methods=["GET"])
def api_get_cron():
    username, err = require_auth()
    if err:
        return err
    data = load_cron()
    user_task = None
    for t in data.get("tasks", []):
        if t.get("username") == username:
            user_task = t
            break
    if user_task:
        return jsonify(ok=True, active=True, config=user_task)
    return jsonify(ok=True, active=False)


@app.route("/api/cron", methods=["POST"])
def api_save_cron():
    username, err = require_auth()
    if err:
        return err
    data = request.get_json(force=True, silent=True) or {}
    cron_expr = data.get("cron_expr", "")
    if not cron_expr:
        return jsonify(ok=False, error="cron 表达式不能为空")

    all_cron = load_cron()
    tasks = all_cron.get("tasks", [])
    found = False
    for i, t in enumerate(tasks):
        if t.get("username") == username:
            tasks[i] = {"username": username, "cron_expr": cron_expr, "enabled": True}
            found = True
            break
    if not found:
        tasks.append({"username": username, "cron_expr": cron_expr, "enabled": True})
    all_cron["tasks"] = tasks
    save_cron(all_cron)
    schedule_user_cron(username, cron_expr)
    return jsonify(ok=True)


@app.route("/api/cron", methods=["DELETE"])
def api_delete_cron():
    username, err = require_auth()
    if err:
        return err
    all_cron = load_cron()
    tasks = all_cron.get("tasks", [])
    tasks = [t for t in tasks if t.get("username") != username]
    all_cron["tasks"] = tasks
    save_cron(all_cron)
    cancel_user_cron(username)
    return jsonify(ok=True)


def load_cron():
    if CRON_FILE.exists():
        try:
            with open(CRON_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"tasks": []}


def save_cron(data):
    DEFAULT_ROOT.mkdir(parents=True, exist_ok=True)
    with open(CRON_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_system_cron():
    """根据 cron.json 重建系统 crontab（超时保护，避免阻塞）"""
    all_cron = load_cron()
    tasks = all_cron.get("tasks", [])
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5)
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    except Exception:
        lines = []

    # 移除旧的工具相关行
    lines = [l for l in lines if "report-tool-fetch" not in l]

    # 为每个用户的任务添加一行
    script_path = str(DEFAULT_ROOT / "fetch_all.sh")
    for t in tasks:
        if t.get("enabled"):
            line = f"{t['cron_expr']} /bin/bash {script_path} {t['username']}"
            lines.append(line)

    content = "\n".join(lines) + "\n"
    try:
        proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        proc.communicate(input=content, timeout=5)
    except Exception:
        pass  # crontab 更新失败不影响主流程


# ============ 独立 Timer 调度器（每用户一个 Timer，精确触发）============
USER_TIMERS = {}  # username -> threading.Timer
TIMER_LOCK = threading.Lock()


def next_cron_minute(cron_expr, from_dt=None):
    """计算 cron 表达式下一次匹配的时间（精度到分钟），从 from_dt 之后开始找"""
    if from_dt is None:
        from_dt = datetime.now(BEIJING_TZ)
    # 从下一秒开始找，避免重复触发当前分钟
    dt = from_dt.replace(second=0, microsecond=0) + timedelta(minutes=1)
    # 最多往后找 7 天，防止死循环
    for _ in range(7 * 24 * 60):
        if cron_matches(cron_expr, dt):
            return dt
        dt += timedelta(minutes=1)
    return None


def schedule_user_cron(username, cron_expr):
    """为该用户创建/更新 Timer，在下次 cron 匹配时触发"""
    cancel_user_cron(username)
    next_time = next_cron_minute(cron_expr)
    if not next_time:
        return
    delay = (next_time - datetime.now(BEIJING_TZ)).total_seconds()
    if delay <= 0:
        delay = 1

    def trigger():
        try:
            result = fetch_for_user(username)
            errs = result.get("errors", [])
            if errs:
                record_cron_log(username, cron_expr, "error", ", ".join(e["error"] for e in errs))
            else:
                record_cron_log(username, cron_expr, "ok", f"采集 {len(result.get('summary',[]))} 条")
        except Exception as e:
            record_cron_log(username, cron_expr, "error", str(e))
        # 重新调度下一次
        schedule_user_cron(username, cron_expr)

    with TIMER_LOCK:
        t = threading.Timer(delay, trigger)
        t.daemon = True
        t.start()
        USER_TIMERS[username] = t


def cancel_user_cron(username):
    """取消该用户的 Timer"""
    with TIMER_LOCK:
        t = USER_TIMERS.pop(username, None)
        if t:
            t.cancel()


def start_all_cron_timers():
    """启动时加载所有用户的 cron 并启动 Timer"""
    all_cron = load_cron()
    for task in all_cron.get("tasks", []):
        if task.get("enabled") and task.get("cron_expr"):
            schedule_user_cron(task["username"], task["cron_expr"])


def parse_cron_field(field, min_val, max_val):
    """解析单个 cron 字段为允许值集合。如 '0-9,18-23' -> {0,1,...,9,18,...,23}，'*' -> 全集合"""
    result = set()
    parts = field.split(",")
    for part in parts:
        part = part.strip()
        if part == "*":
            return set(range(min_val, max_val + 1))
        if "/" in part:
            base, step = part.split("/")
            step = int(step)
            if base == "*":
                base = f"{min_val}-{max_val}"
            if "-" in base:
                lo, hi = base.split("-")
                for v in range(int(lo), int(hi) + 1, step):
                    result.add(v)
            else:
                for v in range(int(base), max_val + 1, step):
                    result.add(v)
        elif "-" in part:
            lo, hi = part.split("-")
            for v in range(int(lo), int(hi) + 1):
                result.add(v)
        else:
            result.add(int(part))
    return result


def cron_matches(cron_expr, dt):
    """检查 cron 表达式是否匹配当前时间（北京时间）"""
    try:
        parts = cron_expr.strip().split()
        if len(parts) < 5:
            return False
        minutes = parse_cron_field(parts[0], 0, 59)
        hours = parse_cron_field(parts[1], 0, 23)
        days = parse_cron_field(parts[2], 0, 6)
        return dt.minute in minutes and dt.hour in hours and dt.weekday() in days
    except Exception:
        return False


def cron_runner():
    """后台线程：每秒检查，分钟变化时扫描 cron 并触发（绝无重复）"""
    last_minute = -1
    while True:
        try:
            now = datetime.now(BEIJING_TZ)
            if now.minute != last_minute:
                last_minute = now.minute
                all_cron = load_cron()
                for task in all_cron.get("tasks", []):
                    if task.get("enabled") and cron_matches(task["cron_expr"], now):
                        try:
                            fetch_for_user(task["username"])
                        except Exception:
                            pass
        except Exception:
            pass
        time.sleep(1)


# ============ 管理员接口 ============
@app.route("/api/admin/users", methods=["GET"])
def api_admin_get_users():
    username, err = require_auth()
    if err:
        return err
    users = load_users()
    current = next((u for u in users["users"] if u["username"] == username), None)
    if not current or not current["is_admin"]:
        return jsonify(ok=False, error="需要管理员权限")
    return jsonify(ok=True, users=users["users"])


@app.route("/api/admin/users", methods=["POST"])
def api_admin_add_user():
    username, err = require_auth()
    if err:
        return err
    users = load_users()
    current = next((u for u in users["users"] if u["username"] == username), None)
    if not current or not current["is_admin"]:
        return jsonify(ok=False, error="需要管理员权限")

    data = request.get_json(force=True, silent=True) or {}
    new_username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    is_admin = data.get("is_admin", 0)

    if not new_username or not password:
        return jsonify(ok=False, error="请输入用户名和密码")
    if len(password) < 4:
        return jsonify(ok=False, error="密码至少4位")
    if any(u["username"] == new_username for u in users["users"]):
        return jsonify(ok=False, error="用户名已存在")

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    uid = users["next_id"]
    users["users"].append({
        "id": uid,
        "username": new_username,
        "password_hash": pw_hash,
        "is_admin": is_admin,
    })
    users["next_id"] = uid + 1
    save_users(users)
    return jsonify(ok=True)


@app.route("/api/admin/users/<username>", methods=["DELETE"])
def api_admin_delete_user(username):
    current_user, err = require_auth()
    if err:
        return err
    users = load_users()
    current = next((u for u in users["users"] if u["username"] == current_user), None)
    if not current or not current["is_admin"]:
        return jsonify(ok=False, error="需要管理员权限")
    if username == "admin":
        return jsonify(ok=False, error="不能删除默认管理员")
    users["users"] = [u for u in users["users"] if u["username"] != username]
    save_users(users)
    return jsonify(ok=True)


# ============ 启动 ============
if __name__ == "__main__":
    # 确保默认管理员存在
    users = load_users()
    if not any(u["username"] == "admin" for u in users["users"]):
        pw_hash = hashlib.sha256("admin123".encode()).hexdigest()
        uid = users["next_id"]
        users["users"].append({
            "id": uid,
            "username": "admin",
            "password_hash": pw_hash,
            "is_admin": 1,
        })
        users["next_id"] = uid + 1
        save_users(users)
        print("已创建默认管理员: admin / admin123")

    # 确保 fetch_all.sh 存在
    script_path = DEFAULT_ROOT / "fetch_all.sh"
    if not script_path.exists():
        DEFAULT_ROOT.mkdir(parents=True, exist_ok=True)
        with open(script_path, "w") as f:
            f.write("""#!/bin/bash
# 甲方后台定时查询工具 - 定时采集脚本（兼容系统 crontab）
USERNAME="${1:-admin}"
curl -s -X POST "http://localhost:8991/api/fetch-now" \\
    -H "Content-Type: application/json" \\
    -H "X-Cron-Token: cron-secret-2026" \\
    -d "{\\"username\\":\\"$USERNAME\\"}" 2>&1
""")
        script_path.chmod(0o755)
        print(f"已创建采集脚本: {script_path}")

    print(f"服务器启动: http://0.0.0.0:8991")
    # 启动所有用户的独立 cron Timer
    start_all_cron_timers()
    # 启动 token 清理线程（每小时一次）
    threading.Thread(target=token_cleaner, daemon=True).start()

    # 优先使用 waitress（多线程生产服务器），回退到 Flask 开发服务器
    try:
        from waitress import serve
        print("使用 waitress 多线程服务器")
        serve(app, host="0.0.0.0", port=8991, threads=4)
    except ImportError:
        print("未安装 waitress，使用 Flask 开发服务器（单线程，仅适合本地调试）")
        app.run(host="0.0.0.0", port=8991, debug=False)
