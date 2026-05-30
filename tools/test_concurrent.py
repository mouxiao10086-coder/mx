#!/usr/bin/env python3
"""并发采集压力测试：10 线程同时调 fetch-all，验证数据完整性"""
import sys, json, threading, time
from urllib.request import Request, urlopen
from urllib.error import URLError

SERVER = "http://127.0.0.1:8991"
TOKEN = None
RESULTS = []
LOCK = threading.Lock()

def login():
    global TOKEN
    body = json.dumps({"username": "admin", "password": "admin123"}).encode()
    req = Request(f"{SERVER}/api/login", data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=5) as r:
        TOKEN = json.loads(r.read())["token"]

def fetch_once(thread_id):
    try:
        req = Request(f"{SERVER}/api/fetch-now", method="POST")
        req.add_header("Authorization", f"Bearer {TOKEN}")
        with urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
        with LOCK:
            RESULTS.append({"thread": thread_id, "ok": data.get("ok"), "count": len(data.get("summary", []))})
    except Exception as e:
        with LOCK:
            RESULTS.append({"thread": thread_id, "error": str(e)})

if __name__ == "__main__":
    print("登录...")
    login()
    print(f"Token: {TOKEN[:10]}...")

    threads = 10
    print(f"启动 {threads} 个并发线程...")
    workers = []
    for i in range(threads):
        t = threading.Thread(target=fetch_once, args=(i,))
        t.start()
        workers.append(t)

    for t in workers:
        t.join()

    ok_count = sum(1 for r in RESULTS if r.get("ok"))
    fail_count = sum(1 for r in RESULTS if "error" in r)
    print(f"\n结果: {ok_count}/{threads} 成功, {fail_count} 失败")
    for r in RESULTS:
        status = r.get("count", r.get("error", "?"))
        print(f"  线程{r['thread']}: {status}")
    sys.exit(0 if fail_count == 0 else 1)
