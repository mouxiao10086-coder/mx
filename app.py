#!/usr/bin/env python3
"""
甲方后台定时查询工具 - 桌面应用
启动内嵌 HTTP 服务器 + pywebview 原生窗口
支持命令行参数：
  无参数  → 启动 GUI 模式（服务器+浏览器）
  --fetch → 执行一次数据采集后退出（供定时任务调用）
跨平台兼容：macOS (.app) / Windows (.exe)
"""

import sys
import os
import json
import threading
import time
import platform
from http.server import HTTPServer
from pathlib import Path

# 确保 api 模块可导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from server import ReportHandler, PORT
import api

IS_WINDOWS = platform.system() == "Windows"


class ApiBridge:
    """pywebview JS→Python 桥接，用于原生操作"""

    def chooseDirectory(self):
        """弹出系统目录选择框"""
        import webview
        result = webview.windows[0].create_file_dialog(
            webview.FOLDER_DIALOG
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def getAppInfo(self):
        """返回应用信息"""
        return {
            "data_root": str(api.DATA_ROOT),
            "version": "1.0.0",
        }


def check_data_root():
    """检查是否已设置数据目录"""
    app_config_path = Path.home() / "甲方后台定时查询工具" / "app_config.json"
    if app_config_path.exists():
        with open(app_config_path, "r") as f:
            cfg = json.load(f)
            if cfg.get("data_root"):
                api.set_data_root(cfg["data_root"])
                return True
    return False


def save_data_root(path):
    """保存数据目录选择"""
    config_dir = Path.home() / "甲方后台定时查询工具"
    config_dir.mkdir(parents=True, exist_ok=True)
    app_config_path = config_dir / "app_config.json"
    cfg = {}
    if app_config_path.exists():
        with open(app_config_path, "r") as f:
            cfg = json.load(f)
    cfg["data_root"] = path
    with open(app_config_path, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    api.set_data_root(path)


def get_fetch_args():
    """获取 --fetch 模式的命令行参数"""
    if getattr(sys, 'frozen', False):
        return [sys.executable, "--fetch"]
    else:
        return [sys.executable, os.path.abspath(__file__), "--fetch"]


def write_cron_script():
    """在数据目录生成调度脚本（macOS: .sh, Windows: .bat）"""
    args = get_fetch_args()

    api.DATA_ROOT.mkdir(parents=True, exist_ok=True)
    (api.DATA_ROOT / "daily").mkdir(parents=True, exist_ok=True)

    if IS_WINDOWS:
        return _write_bat_script(args)
    else:
        return _write_sh_script(args)


def _write_sh_script(args):
    """生成 macOS bash 调度脚本"""
    cmd = " ".join(f'"{a}"' if " " in a else a for a in args)

    script_content = f"""#!/bin/bash
# 甲方后台定时查询工具 - 自动生成，请勿手动编辑
# 由 甲方后台定时查询工具.app 自动创建，crontab 调用此脚本
# 删除 .app 后此脚本将失效

{cmd} >> "{api.DATA_ROOT}/daily/fetch.log" 2>&1
"""
    script_path = api.DATA_ROOT / "fetch_cron.sh"
    with open(script_path, "w") as f:
        f.write(script_content)
    os.chmod(script_path, 0o755)
    return script_path


def _write_bat_script(args):
    """生成 Windows batch 调度脚本"""
    cmd = " ".join(f'"{a}"' if " " in a else a for a in args)
    log_path = api.DATA_ROOT / "daily" / "fetch.log"

    script_content = f"""@echo off
REM 甲方后台定时查询工具 - 自动生成，请勿手动编辑
REM 由 甲方后台定时查询工具.exe 自动创建，schtasks 调用此脚本
REM 删除 .exe 后此脚本将失效

{cmd} >> "{log_path}" 2>&1
"""
    script_path = api.DATA_ROOT / "fetch_cron.bat"
    with open(script_path, "w", encoding="gbk", errors="replace") as f:
        f.write(script_content)
    return script_path


def run_fetch_mode():
    """命令行模式：执行一次采集后退出"""
    # 确保 api 模块知道用户设置的数据路径
    check_data_root()
    # 确保数据目录
    api.ensure_dirs()
    import fetch_reports
    fetch_reports.main()


def run_gui_mode():
    """GUI 模式：启动服务器 + 打开浏览器"""
    # 检查数据目录
    has_data_root = check_data_root()

    # 启动内嵌 HTTP 服务器
    api.ensure_dirs()
    server = HTTPServer(("127.0.0.1", PORT), ReportHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    # 自动生成调度脚本（指向当前可执行文件）
    cron_script = write_cron_script()
    print(f"调度脚本已更新: {cron_script}")

    # 创建 pywebview 窗口
    import webview

    bridge = ApiBridge()
    window = webview.create_window(
        title="甲方后台定时查询工具",
        url=f"http://127.0.0.1:{PORT}",
        width=1000,
        height=700,
        min_size=(800, 500),
        js_api=bridge,
    )

    # 如果首次启动，注入提示
    if not has_data_root:
        def on_shown():
            time.sleep(0.5)
            window.evaluate_js('showWelcomeModal && showWelcomeModal()')
        window.events.shown += on_shown

    # 启动事件循环（阻塞）
    webview.start(debug=False)

    # 窗口关闭后
    server.shutdown()


def main():
    if "--fetch" in sys.argv:
        run_fetch_mode()
    else:
        run_gui_mode()


if __name__ == "__main__":
    main()
