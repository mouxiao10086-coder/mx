#!/usr/bin/env python3
"""
甲方后台定时查询工具 - 数据采集脚本（多用户版）
- 从 SQLite 数据库读取所有用户的产品配置
- 通过 urllib 抓取报表 HTML，解析数据
- 存储到 daily_data 表（按用户隔离）
- 支持按 user_id 采集（手动触发时用）
"""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from urllib.request import urlopen, Request
from urllib.error import URLError

# 添加当前目录到路径，以便导入 db 模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db

BASE_URL = "http://16.163.114.99:8990"

BRAZIL_TZ = timezone(timedelta(hours=3))
BEIJING_TZ = timezone(timedelta(hours=8))


def get_today_str():
    """返回北京日期字符串 YYYY-MM-DD（按北京时间归档）"""
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d")


def get_now_str():
    """返回当前北京时间戳"""
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


def fetch_report(product):
    """
    抓取单个产品的报表数据
    product: dict with keys: report_type, pid, token, channels, timezone
    """
    report_type = product["report_type"]
    pid = product["pid"]
    token = product["token"]
    channels = product.get("channels", [])
    tz = product.get("timezone", "Etc/GMT+3")

    base = f"{BASE_URL}/report{report_type}.php"
    params = f"id={pid}&token={token}&timezone={quote(tz)}"
    for ch in channels:
        params += f"&channels={quote(ch)}"
    url = f"{base}?{params}"

    try:
        req = Request(url)
        with urlopen(req, timeout=10) as resp:
            result = resp.read().decode("utf-8", errors="replace")
    except (URLError, OSError, Exception) as e:
        print(f"  ❌ 请求失败: {e}")
        return []

    return parse_html(result)


def parse_html(html):
    """从 HTML 中解析出所有渠道的数据行"""
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


def fetch_for_user(user_id):
    """
    为指定用户采集所有产品数据
    返回: {"ok": True, "summary": [...]}
    """
    products = db.get_products_by_user(user_id)
    if not products:
        return {"ok": False, "error": "该用户没有配置产品"}

    date_str = get_today_str()
    summary_rows = []
    errors = []

    print(f"\n{'='*60}")
    print(f"  采集任务 | 用户ID: {user_id} | 北京日期: {date_str}")
    print(f"  北京时间: {get_now_str()}")
    print(f"{'='*60}\n")

    for product in products:
        name = product["name"]
        product_id = product["id"]
        try:
            records = fetch_report(product)
            if not records:
                errors.append((name, "未获取到数据（可能维护时段）"))
                continue

            # 保存到数据库
            db.save_daily_data(user_id, product_id, date_str, records)

            for rec in records:
                summary_rows.append(
                    [name, rec["channel"], rec["visit"], rec["register"], rec["first_recharge"]]
                )
        except Exception as e:
            errors.append((name, str(e)))

    # 输出摘要
    if summary_rows:
        print(f"{'产品':<6} {'渠道':<24} {'访问':>6} {'注册':>6} {'首充':>6}")
        print("-" * 56)
        for row in summary_rows:
            print(f"{row[0]:<6} {row[1]:<24} {row[2]:>6,} {row[3]:>6,} {row[4]:>6,}")

    if errors:
        print(f"\n⚠️ 异常:")
        for name, err in errors:
            print(f"   {name}: {err}")

    return {
        "ok": True,
        "date": date_str,
        "products_count": len(products),
        "data_count": len(summary_rows),
        "errors": [{"product": n, "error": e} for n, e in errors],
    }


def fetch_all_users():
    """
    采集所有启用了定时任务的用户的数据
    由 APScheduler 定时调用
    """
    # 获取所有启用的定时任务
    jobs = db.get_all_cron_jobs()
    if not jobs:
        print(f"[{get_now_str()}] 没有启用的定时任务")
        return

    for job in jobs:
        user_id = job["user_id"]
        print(f"\n▶ 开始采集用户 {user_id} 的数据...")
        try:
            result = fetch_for_user(user_id)
            print(f"  ✅ 完成: {result.get('data_count', 0)} 条数据")
        except Exception as e:
            print(f"  ❌ 失败: {e}")


def main():
    """命令行模式：采集所有启用了定时任务的用户"""
    print(f"\n{'='*60}")
    print(f"  甲方后台定时查询工具 | 多用户版")
    print(f"  北京时间: {get_now_str()}")
    print(f"{'='*60}\n")

    fetch_all_users()


if __name__ == "__main__":
    main()
