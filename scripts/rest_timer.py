"""后台组间歇计时器 — 由 fitness_manager.py 自动 spawn，到时间后输出提醒。

双输出机制：
  1. 终端 print（CLI 直接使用时用户可见）
  2. 写入 .timer_alert 文件（Claude Code/Claw 等工具通过读文件获取提醒）
"""
import sys
import os
import time
import io
import json
from datetime import datetime

# Windows GBK 终端兼容
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def format_interval(seconds):
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins > 0 and secs > 0:
        return f"{mins}分{secs}秒"
    if mins > 0:
        return f"{mins}分"
    return f"{secs}秒"

if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(1)
    interval_seconds = int(sys.argv[1])
    exercise = sys.argv[2]
    alert_file = sys.argv[3]  # .timer_alert 文件路径

    time.sleep(interval_seconds)

    interval_str = format_interval(interval_seconds)
    message = f"⏰ 组间歇 {interval_str} 已到！（动作: {exercise}）"

    # 输出 1: 终端 print（CLI 用户直接可见）
    print(f"\n{message}")

    # 输出 2: 写入提醒文件（Claude Code/Claw 通过读文件获取）
    alert = {
        "message": message,
        "exercise": exercise,
        "interval": interval_str,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(alert_file, "w", encoding="utf-8") as f:
            json.dump(alert, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
