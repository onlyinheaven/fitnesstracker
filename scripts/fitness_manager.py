import sqlite3
import os
import sys
import json
import re
import shutil
import io
import signal
import subprocess
import platform
from datetime import datetime
from collections import defaultdict, OrderedDict

# Windows GBK 终端下强制 UTF-8 输出，避免中文和 emoji 编码错误
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

LBS_TO_KG = 0.453592
KNOWN_FIELDS = {"weight", "reps", "sets", "distance", "duration", "incline"}

# ── 重量解析 ──────────────────────────────────────────────

def parse_weight_kg(weight_str):
    """将重量字符串统一转换为 kg 数值，用于比较。"""
    if not weight_str or weight_str == "自重":
        return 0.0
    w = weight_str.lower().strip()
    if "lbs" in w:
        return float(w.replace("lbs", "").strip()) * LBS_TO_KG
    return float(w.replace("kg", "").strip())

def parse_distance_km(distance_str):
    """将距离字符串统一转换为 km 数值，用于比较。"""
    if not distance_str:
        return 0.0
    d = distance_str.lower().strip()
    if "km" in d:
        return float(d.replace("km", "").strip())
    if "m" in d:
        return float(d.replace("m", "").strip()) / 1000.0
    return float(d)

def parse_duration_seconds(duration_str):
    """将时长字符串转换为秒数，用于比较。支持 '40min', '1h20min', '60s', '1:30:00' 等。"""
    if not duration_str:
        return 0
    d = duration_str.lower().strip()
    # 尝试 XhYminZs 格式
    total = 0
    m = re.match(r'^(?:(\d+)h)?(?:(\d+)min)?(?:(\d+)s)?$', d)
    if m and any(m.groups()):
        total += int(m.group(1) or 0) * 3600
        total += int(m.group(2) or 0) * 60
        total += int(m.group(3) or 0)
        return total
    # 纯数字视为分钟
    try:
        return int(float(d)) * 60
    except ValueError:
        return 0

# ── 配置管理 ──────────────────────────────────────────────

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(SKILL_DIR, "config.json")
DEFAULT_LOG_DIR = os.path.join(SKILL_DIR, "record")
TIMER_PID_FILE = os.path.join(SKILL_DIR, ".timer_pid")
TIMER_ALERT_FILE = os.path.join(SKILL_DIR, ".timer_alert")

DEFAULT_CONFIG = {
    "log_dir": DEFAULT_LOG_DIR,
    "rest_timer": {
        "enabled": False,
        "interval": "2min"
    }
}

def get_config():
    config = dict(DEFAULT_CONFIG)
    config["rest_timer"] = dict(DEFAULT_CONFIG["rest_timer"])
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # 合并已保存的配置，保留默认值作为兜底
            if "log_dir" in saved:
                config["log_dir"] = saved["log_dir"]
            if "rest_timer" in saved and isinstance(saved["rest_timer"], dict):
                config["rest_timer"].update(saved["rest_timer"])
        except (json.JSONDecodeError, IOError):
            pass
    return config

def save_config_full(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def update_config(**updates):
    """读取当前配置，合并更新项，写回。"""
    config = get_config()
    for k, v in updates.items():
        if k == "rest_timer" and isinstance(v, dict) and isinstance(config.get("rest_timer"), dict):
            config["rest_timer"].update(v)
        else:
            config[k] = v
    save_config_full(config)
    return config

def get_db_paths():
    config = get_config()
    log_dir = os.path.expanduser(config["log_dir"])
    return log_dir, os.path.join(log_dir, "fitness_log.db"), os.path.join(log_dir, "fitness_log.csv")

# ── 组间歇计时器 ─────────────────────────────────────────────

TIMER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rest_timer.py")

def parse_interval_seconds(interval_str):
    """将间隔字符串转换为秒数。支持 '2min', '90s', '1min30s' 等。"""
    s = interval_str.lower().strip()
    m = re.match(r'^(?:(\d+)min)?(?:(\d+)s)?$', s)
    if m and any(m.groups()):
        total = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
        return total if total > 0 else None
    try:
        return int(float(s)) * 60  # 纯数字视为分钟
    except ValueError:
        return None

def kill_timer():
    """杀掉正在运行的计时器后台进程。"""
    if not os.path.exists(TIMER_PID_FILE):
        return
    try:
        with open(TIMER_PID_FILE, "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, ValueError, OSError):
        pass  # 进程已结束或 PID 无效
    try:
        os.remove(TIMER_PID_FILE)
    except OSError:
        pass

def clear_alert():
    """清除已有的提醒文件。"""
    try:
        os.remove(TIMER_ALERT_FILE)
    except OSError:
        pass

def check_alert():
    """检查并读取提醒文件，返回提醒消息（如有），同时清除文件。"""
    if not os.path.exists(TIMER_ALERT_FILE):
        return None
    try:
        with open(TIMER_ALERT_FILE, "r", encoding="utf-8") as f:
            alert = json.load(f)
        os.remove(TIMER_ALERT_FILE)
        return alert.get("message")
    except (json.JSONDecodeError, IOError, OSError):
        return None

def start_timer(exercise, interval_seconds):
    """启动后台计时器进程。"""
    kill_timer()
    clear_alert()
    kwargs = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        [sys.executable, TIMER_SCRIPT, str(interval_seconds), exercise, TIMER_ALERT_FILE],
        **kwargs
    )
    with open(TIMER_PID_FILE, "w") as f:
        f.write(str(proc.pid))

def handle_timer_command(args):
    """处理 timer 命令：查看/设置/关闭。"""
    config = get_config()
    timer_cfg = config["rest_timer"]

    if not args:
        # 查看当前状态
        if timer_cfg["enabled"]:
            print(f"⏰ 组间歇提醒: 开启（间隔 {timer_cfg['interval']}）")
        else:
            print("⏰ 组间歇提醒: 关闭")
        return

    arg = args[0].lower()
    if arg == "off":
        kill_timer()
        update_config(rest_timer={"enabled": False})
        print("⏰ 组间歇提醒已关闭。")
    else:
        seconds = parse_interval_seconds(arg)
        if seconds is None:
            print(f"❌ 无法识别的时间格式: {arg}")
            print("   支持格式: 2min, 90s, 1min30s")
            return
        update_config(rest_timer={"enabled": True, "interval": arg})
        print(f"⏰ 组间歇提醒已开启，间隔 {arg}。记录训练后将自动计时。")

# ── 数据库 ────────────────────────────────────────────────

def get_connection():
    log_dir, db_file, _ = get_db_paths()
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            exercise TEXT NOT NULL,
            weight TEXT,
            reps INTEGER,
            sets INTEGER,
            distance TEXT,
            duration TEXT,
            incline TEXT
        )
    ''')
    conn.commit()
    # 迁移：为旧表添加新列
    cursor.execute("PRAGMA table_info(workouts)")
    existing_cols = {row["name"] for row in cursor.fetchall()}
    for col, col_type in [("distance", "TEXT"), ("duration", "TEXT"), ("incline", "TEXT")]:
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE workouts ADD COLUMN {col} {col_type}")
    conn.commit()
    return conn

def auto_migrate():
    log_dir, db_file, csv_file = get_db_paths()
    if not os.path.exists(csv_file):
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM workouts")
    if cursor.fetchone()["count"] > 0:
        conn.close()
        return
    print(f"🔄 检测到路径 {log_dir} 下有旧版 CSV 数据，正在自动迁移...")
    import csv
    with open(csv_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute('''
                INSERT INTO workouts (date, timestamp, exercise, weight, reps, sets)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (row["Date"], row.get("Timestamp", row["Date"]), row["Exercise"],
                  row["Weight"], row["Reps"], row["Sets"]))
    conn.commit()
    conn.close()
    print("✅ 旧数据迁移完成！")

# ── CLI 参数解析 ──────────────────────────────────────────

def parse_kv_args(args):
    """解析 key=value 参数列表，返回 dict。"""
    fields = {}
    for arg in args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            k = k.strip().lower()
            if k in KNOWN_FIELDS:
                fields[k] = v.strip()
            else:
                print(f"⚠️ 未知字段 '{k}'，已忽略。已知字段: {', '.join(sorted(KNOWN_FIELDS))}")
        else:
            print(f"⚠️ 无法解析参数 '{arg}'，请使用 key=value 格式。")
    return fields

# ── 格式化输出辅助 ────────────────────────────────────────

def format_record_fields(row):
    """根据记录中实际有值的字段生成显示字符串。"""
    parts = []
    weight = row["weight"] if row["weight"] else None
    reps = row["reps"] if row["reps"] else None
    sets_ = row["sets"] if row["sets"] else None
    distance = row["distance"] if row["distance"] else None
    duration = row["duration"] if row["duration"] else None
    incline = row["incline"] if row["incline"] else None

    if weight:
        parts.append(weight)
    elif reps and not distance:
        parts.append("自重")

    if distance:
        parts.append(distance)
    if duration:
        parts.append(duration)
    if incline:
        parts.append(f"坡度{incline}")
    if reps:
        parts.append(f"{reps}次")
    if sets_:
        parts.append(f"{sets_}组")
    return " | ".join(parts) if parts else "（无详细数据）"

def format_rest_time(seconds):
    """将秒数格式化为 X分Y秒。"""
    mins = int(seconds // 60)
    secs = int(seconds % 60)
    if mins > 0:
        return f"{mins}分{secs}秒"
    return f"{secs}秒"

# ── 核心功能 ──────────────────────────────────────────────

def record(exercise, fields):
    conn = get_connection()
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d")

    # 间歇时间：先查同动作，再查任意动作（换动作场景）
    cursor.execute('''
        SELECT exercise, timestamp FROM workouts
        WHERE exercise = ? AND date = ?
        ORDER BY timestamp DESC LIMIT 1
    ''', (exercise, date_str))
    last_same = cursor.fetchone()

    last_any = None
    if not last_same:
        cursor.execute('''
            SELECT exercise, timestamp FROM workouts
            WHERE date = ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (date_str,))
        last_any = cursor.fetchone()

    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

    weight = fields.get("weight")
    reps = int(fields["reps"]) if "reps" in fields else None
    sets_ = int(fields["sets"]) if "sets" in fields else None
    distance = fields.get("distance")
    duration = fields.get("duration")
    incline = fields.get("incline")

    cursor.execute('''
        INSERT INTO workouts (date, timestamp, exercise, weight, reps, sets, distance, duration, incline)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (date_str, timestamp_str, exercise, weight, reps, sets_, distance, duration, incline))
    conn.commit()

    # 构建输出
    display_parts = [date_str, exercise]
    if weight:
        display_parts.append(weight)
    elif reps and not distance:
        display_parts.append("自重")
    if distance:
        display_parts.append(distance)
    if duration:
        display_parts.append(duration)
    if incline:
        display_parts.append(f"坡度{incline}")
    if reps:
        display_parts.append(f"{reps}次")
    if sets_:
        display_parts.append(f"{sets_}组")

    print(f"✅ 成功记录: {' | '.join(display_parts)}")

    if last_same:
        try:
            last_dt = datetime.strptime(last_same["timestamp"], "%Y-%m-%d %H:%M:%S")
            diff_seconds = (now - last_dt).total_seconds()
            if diff_seconds > 0:
                print(f"⏱️ 距离上一组间歇时间: {format_rest_time(diff_seconds)}")
        except (ValueError, TypeError):
            pass
    elif last_any:
        try:
            last_dt = datetime.strptime(last_any["timestamp"], "%Y-%m-%d %H:%M:%S")
            diff_seconds = (now - last_dt).total_seconds()
            if diff_seconds > 0:
                prev_name = last_any["exercise"]
                print(f"⏱️ 距离上一个动作（{prev_name}）间隔时间: {format_rest_time(diff_seconds)}")
        except (ValueError, TypeError):
            pass

    conn.close()

    # 组间歇计时器：记录后自动启动
    timer_cfg = get_config().get("rest_timer", {})
    if timer_cfg.get("enabled"):
        interval_str = timer_cfg.get("interval", "2min")
        interval_s = parse_interval_seconds(interval_str)
        if interval_s:
            start_timer(exercise, interval_s)
            print(f"⏰ 组间歇计时 {interval_str} 已启动")

def delete_last(exercise=None):
    conn = get_connection()
    cursor = conn.cursor()
    if exercise:
        cursor.execute("SELECT * FROM workouts WHERE exercise = ? ORDER BY timestamp DESC LIMIT 1", (exercise,))
    else:
        cursor.execute("SELECT * FROM workouts ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        print("❌ 未找到记录，无法删除。")
        conn.close()
        return
    cursor.execute("DELETE FROM workouts WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    print(f"🗑️ 已成功删除记录: {row['date']} | {row['exercise']} | {format_record_fields(row)}")

def update_last(exercise, fields):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workouts WHERE exercise = ? ORDER BY timestamp DESC LIMIT 1", (exercise,))
    row = cursor.fetchone()
    if not row:
        print(f"❌ 未找到关于 {exercise} 的记录。")
        conn.close()
        return

    # 只更新传入的字段
    update_cols = []
    update_vals = []
    for k, v in fields.items():
        if k == "reps" or k == "sets":
            update_cols.append(f"{k} = ?")
            update_vals.append(int(v))
        else:
            update_cols.append(f"{k} = ?")
            update_vals.append(v)

    if not update_cols:
        print("❌ 未指定要修改的字段。")
        conn.close()
        return

    update_vals.append(row["id"])
    cursor.execute(f"UPDATE workouts SET {', '.join(update_cols)} WHERE id = ?", update_vals)
    conn.commit()

    # 重新查询显示更新后的记录
    cursor.execute("SELECT * FROM workouts WHERE id = ?", (row["id"],))
    updated = cursor.fetchone()
    conn.close()
    print(f"✏️ 已成功修改记录: {updated['date']} | {exercise} | {format_record_fields(updated)}")

def analyze(exercise):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workouts WHERE exercise = ? ORDER BY timestamp ASC", (exercise,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print(f"尚无 {exercise} 的历史记录。")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_records = []
    last_date = None
    last_records = []

    # 判断运动类型：优先看距离，再看重量，最后看次数
    has_distance = any(r["distance"] for r in rows)
    has_weight = any(r["weight"] and r["weight"] != "自重" for r in rows) and not has_distance
    has_reps = any(r["reps"] for r in rows)

    # PR 计算
    pr_record = None
    pr_label = ""

    if has_distance:
        pr_val = -1.0
        for r in rows:
            if not r["distance"]:
                continue
            try:
                d_km = parse_distance_km(r["distance"])
                if d_km > pr_val:
                    pr_val = d_km
                    pr_record = r
            except (ValueError, AttributeError):
                pass
        pr_label = "最长距离"
    elif has_weight:
        pr_val = -1.0
        for r in rows:
            try:
                w_kg = parse_weight_kg(r["weight"])
                if w_kg > pr_val:
                    pr_val = w_kg
                    pr_record = r
            except (ValueError, AttributeError):
                pass
        pr_label = "最大重量"
    elif has_reps:
        pr_val = -1
        for r in rows:
            if r["reps"] and r["reps"] > pr_val:
                pr_val = r["reps"]
                pr_record = r
        pr_label = "最多次数"

    for row in rows:
        r_date = row["date"]
        if r_date == today_str:
            today_records.append(row)
        elif r_date < today_str:
            if last_date is None or r_date > last_date:
                last_date = r_date
                last_records = [row]
            elif r_date == last_date:
                last_records.append(row)

    print(f"--- {exercise} 训练报告 ---")
    if today_records:
        print("📝 今日进度:")
        for i, r in enumerate(today_records):
            time_info = ""
            if i > 0:
                try:
                    t1 = datetime.strptime(today_records[i-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
                    t2 = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
                    diff = (t2 - t1).total_seconds()
                    time_info = f" [间歇 {format_rest_time(diff)}]"
                except (ValueError, TypeError):
                    pass
            print(f"   - {format_record_fields(r)}{time_info}")

    if pr_record:
        print(f"🏆 历史 PR ({pr_label}): {format_record_fields(pr_record)} 于 {pr_record['date']}")

    # 如果有距离+时长的记录，显示最快配速
    if has_distance:
        best_pace = None
        best_pace_record = None
        for r in rows:
            d_km = parse_distance_km(r["distance"])
            dur_s = parse_duration_seconds(r["duration"])
            if d_km > 0 and dur_s > 0:
                pace = dur_s / d_km  # 秒/km
                if best_pace is None or pace < best_pace:
                    best_pace = pace
                    best_pace_record = r
        if best_pace_record:
            pace_min = int(best_pace // 60)
            pace_sec = int(best_pace % 60)
            print(f"⚡ 最快配速: {pace_min}'{pace_sec:02d}\"/km 于 {best_pace_record['date']}")

    if last_records:
        print(f"📅 上次训练 ({last_date}):")
        for r in last_records:
            print(f"   - {format_record_fields(r)}")
    print("----------------------")

def summary(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workouts WHERE date = ? ORDER BY timestamp ASC", (date_str,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print(f"📅 {date_str} 暂无训练记录。")
        return
    _print_day_summary(date_str, rows, show_header=True)

def summary_range(start_date, end_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workouts WHERE date BETWEEN ? AND ? ORDER BY date ASC, timestamp ASC",
                   (start_date, end_date))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print(f"📅 {start_date} ~ {end_date} 暂无训练记录。")
        return

    # 按日期分组
    days = OrderedDict()
    for r in rows:
        days.setdefault(r["date"], []).append(r)

    print(f"======= 🏋️ 训练报告 ({start_date} ~ {end_date}) =======")
    total_exercises = set()
    for date_str, day_rows in days.items():
        exercises = defaultdict(list)
        for r in day_rows:
            exercises[r["exercise"]].append(r)
            total_exercises.add(r["exercise"])
        print(f"📅 {date_str}:")
        for exercise, records in exercises.items():
            total_sets = sum(r["sets"] for r in records if r["sets"])
            if total_sets > 0:
                print(f"  🔹 {exercise}: 共 {total_sets} 组")
            else:
                print(f"  🔹 {exercise}:")
            for i, r in enumerate(records):
                time_info = ""
                if i > 0:
                    try:
                        t1 = datetime.strptime(records[i-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
                        t2 = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
                        diff = (t2 - t1).total_seconds()
                        time_info = f" [间歇 {format_rest_time(diff)}]"
                    except (ValueError, TypeError):
                        pass
                print(f"     - {format_record_fields(r)}{time_info}")
    print("==========================================")
    print(f"📊 总结: {len(days)} 天内共完成了 {len(total_exercises)} 个动作。")
    print("坚持就是胜利！💪")

def _print_day_summary(date_str, rows, show_header=True):
    """打印单日训练总结。"""
    exercises = defaultdict(list)
    for r in rows:
        exercises[r["exercise"]].append(r)

    if show_header:
        print(f"======= 🏋️ 健身报告 ({date_str}) =======")

    total_exercises = len(exercises)
    total_sets = 0
    for exercise, records in exercises.items():
        exercise_sets = sum(r["sets"] for r in records if r["sets"])
        total_sets += exercise_sets
        if exercise_sets > 0:
            print(f"🔹 {exercise}: 共 {exercise_sets} 组")
        else:
            print(f"🔹 {exercise}:")
        for i, r in enumerate(records):
            time_info = ""
            if i > 0:
                try:
                    t1 = datetime.strptime(records[i-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
                    t2 = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
                    diff = (t2 - t1).total_seconds()
                    time_info = f" [间歇 {format_rest_time(diff)}]"
                except (ValueError, TypeError):
                    pass
            print(f"   - {format_record_fields(r)}{time_info}")

    if show_header:
        print("==========================================")
        print(f"📊 总结: 共完成了 {total_exercises} 个动作，累计训练 {total_sets} 组。")
        print("坚持就是胜利！💪")

def _aggregate_exercise(records):
    """聚合同一 exercise 的多条记录，返回摘要 dict。"""
    agg = {
        "max_weight": None, "max_weight_kg": 0,
        "total_sets": 0, "max_reps": 0,
        "max_distance": None, "max_distance_km": 0,
        "best_duration": None, "best_duration_s": None,
        "incline": None,
        "has_weight": False, "has_distance": False, "has_reps": False,
    }
    for r in records:
        if r["sets"]:
            agg["total_sets"] += r["sets"]
        if r["reps"] and r["reps"] > agg["max_reps"]:
            agg["max_reps"] = r["reps"]
            agg["has_reps"] = True
        if r["weight"] and r["weight"] != "自重":
            agg["has_weight"] = True
            try:
                w_kg = parse_weight_kg(r["weight"])
                if w_kg > agg["max_weight_kg"]:
                    agg["max_weight_kg"] = w_kg
                    agg["max_weight"] = r["weight"]
            except (ValueError, AttributeError):
                pass
        if r["distance"]:
            agg["has_distance"] = True
            try:
                d_km = parse_distance_km(r["distance"])
                if d_km > agg["max_distance_km"]:
                    agg["max_distance_km"] = d_km
                    agg["max_distance"] = r["distance"]
            except (ValueError, AttributeError):
                pass
        if r["duration"]:
            dur_s = parse_duration_seconds(r["duration"])
            if agg["best_duration_s"] is None or dur_s < agg["best_duration_s"]:
                agg["best_duration_s"] = dur_s
                agg["best_duration"] = r["duration"]
        if r["incline"]:
            agg["incline"] = r["incline"]
    return agg

def _format_agg(agg):
    """将聚合数据格式化为显示字符串。"""
    parts = []
    if agg["has_weight"]:
        parts.append(f"最大 {agg['max_weight']}")
    elif agg["has_reps"] and not agg["has_distance"]:
        parts.append("自重")
    if agg["has_distance"] and agg["max_distance"]:
        parts.append(agg["max_distance"])
    if agg["best_duration"]:
        parts.append(agg["best_duration"])
    if agg["incline"]:
        parts.append(f"坡度{agg['incline']}")
    if agg["total_sets"] > 0:
        parts.append(f"共 {agg['total_sets']} 组")
    if agg["has_reps"] and agg["max_reps"] > 0:
        parts.append(f"最多 {agg['max_reps']} 次/组")
    return ", ".join(parts) if parts else "（无详细数据）"

def compare(date1, date2):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workouts WHERE date = ? ORDER BY timestamp ASC", (date1,))
    rows1 = cursor.fetchall()
    cursor.execute("SELECT * FROM workouts WHERE date = ? ORDER BY timestamp ASC", (date2,))
    rows2 = cursor.fetchall()
    conn.close()

    if not rows1 and not rows2:
        print(f"📅 {date1} 和 {date2} 均无训练记录。")
        return
    if not rows1:
        print(f"📅 {date1} 无训练记录。")
        return
    if not rows2:
        print(f"📅 {date2} 无训练记录。")
        return

    # 按 exercise 聚合
    ex1 = defaultdict(list)
    ex2 = defaultdict(list)
    for r in rows1:
        ex1[r["exercise"]].append(r)
    for r in rows2:
        ex2[r["exercise"]].append(r)

    common = set(ex1.keys()) & set(ex2.keys())
    only1 = set(ex1.keys()) - common
    only2 = set(ex2.keys()) - common

    d1_short = date1[5:]  # MM-DD
    d2_short = date2[5:]

    print(f"======= 📊 训练对比 ({d1_short} vs {d2_short}) =======")

    if common:
        print("🔄 共同训练项目:")
        for ex in sorted(common):
            agg1 = _aggregate_exercise(ex1[ex])
            agg2 = _aggregate_exercise(ex2[ex])
            print(f"  🔹 {ex}:")
            print(f"     {d1_short}: {_format_agg(agg1)}")
            print(f"     {d2_short}: {_format_agg(agg2)}")
            # 计算变化
            changes = []
            if agg1["has_weight"] and agg2["has_weight"]:
                diff = agg2["max_weight_kg"] - agg1["max_weight_kg"]
                if abs(diff) > 0.01:
                    sign = "↑" if diff > 0 else "↓"
                    changes.append(f"重量 {sign}{abs(diff):.1f}kg")
            if agg1["has_reps"] and agg2["has_reps"]:
                diff = agg2["max_reps"] - agg1["max_reps"]
                if diff != 0:
                    sign = "↑" if diff > 0 else "↓"
                    changes.append(f"次数 {sign}{abs(diff)}")
            if agg1["total_sets"] > 0 and agg2["total_sets"] > 0:
                diff = agg2["total_sets"] - agg1["total_sets"]
                if diff != 0:
                    sign = "↑" if diff > 0 else "↓"
                    changes.append(f"组数 {sign}{abs(diff)}")
            if agg1["has_distance"] and agg2["has_distance"]:
                diff = agg2["max_distance_km"] - agg1["max_distance_km"]
                if abs(diff) > 0.001:
                    sign = "↑" if diff > 0 else "↓"
                    changes.append(f"距离 {sign}{abs(diff):.1f}km")
            if agg1["best_duration_s"] and agg2["best_duration_s"]:
                diff = agg2["best_duration_s"] - agg1["best_duration_s"]
                if abs(diff) > 0:
                    # 时长：减少是进步
                    sign = "↓" if diff < 0 else "↑"
                    diff_min = abs(diff) / 60
                    if diff_min >= 1:
                        changes.append(f"时长 {sign}{diff_min:.0f}min")
                    else:
                        changes.append(f"时长 {sign}{abs(diff):.0f}s")
            if changes:
                print(f"     变化: {', '.join(changes)}")
            print()

    if only1:
        print(f"⬅️ 仅 {date1} 训练:")
        for ex in sorted(only1):
            agg = _aggregate_exercise(ex1[ex])
            print(f"  🔹 {ex}: {_format_agg(agg)}")

    if only2:
        print(f"➡️ 仅 {date2} 训练:")
        for ex in sorted(only2):
            agg = _aggregate_exercise(ex2[ex])
            print(f"  🔹 {ex}: {_format_agg(agg)}")

    print("=============================================")

# ── 路径管理 ──────────────────────────────────────────────

def set_path(new_path, migrate=False):
    new_path = os.path.expanduser(new_path)
    new_path = os.path.abspath(new_path)
    old_config = get_config()
    old_path = os.path.expanduser(old_config["log_dir"])
    old_path = os.path.abspath(old_path)

    if old_path == new_path:
        print(f"ℹ️ 新路径与当前路径相同: {new_path}，无需修改。")
        return

    print(f"📂 当前存储路径: {old_path}")
    print(f"📂 新存储路径:   {new_path}")

    if not os.path.exists(new_path):
        os.makedirs(new_path, exist_ok=True)

    old_db = os.path.join(old_path, "fitness_log.db")
    new_db = os.path.join(new_path, "fitness_log.db")

    if migrate and os.path.exists(old_db):
        if os.path.exists(new_db):
            print("⚠️ 目标路径已存在数据库文件，旧数据库将被覆盖。")
        shutil.copy2(old_db, new_db)
        os.remove(old_db)
        old_csv = os.path.join(old_path, "fitness_log.csv")
        if os.path.exists(old_csv):
            shutil.copy2(old_csv, os.path.join(new_path, "fitness_log.csv"))
            os.remove(old_csv)
        print("✅ 已有数据已迁移至新路径。")
    elif migrate:
        print("ℹ️ 旧路径下无数据文件，跳过迁移。")
    else:
        print("ℹ️ 将在新路径下从头开始记录（旧数据保留在原路径不受影响）。")

    update_config(log_dir=new_path)
    print(f"✅ 存储路径已更新为: {new_path}")

# ── 版本信息 ──────────────────────────────────────────────

def load_version_info():
    """从 VERSION 文件读取版本号、commit、日期。格式:
    0.3.0
    commit: abc1234
    date: 2026-03-29
    """
    version_file = os.path.join(SKILL_DIR, "VERSION")
    info = {"version": "unknown", "commit": None, "date": None, "message": None}
    if not os.path.exists(version_file):
        return info
    with open(version_file, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    if lines:
        info["version"] = lines[0]
    for line in lines[1:]:
        if line.startswith("commit:"):
            info["commit"] = line.split(":", 1)[1].strip()
        elif line.startswith("date:"):
            info["date"] = line.split(":", 1)[1].strip()
        elif line.startswith("message:"):
            info["message"] = line.split(":", 1)[1].strip()
    return info

def print_version():
    """输出版本号、commit、日期和说明（全部来自 VERSION 文件，无需 git）。"""
    info = load_version_info()
    print(f"Fitness Tracker v{info['version']}")
    if info["commit"]:
        print(f"  commit:  {info['commit']}")
    if info["date"]:
        print(f"  date:    {info['date']}")
    if info["message"]:
        print(f"  message: {info['message']}")

# ── 用法说明 ──────────────────────────────────────────────

def print_usage():
    print("""用法: python fitness_manager.py <command> [args]

命令:
  init [路径]                              初始化配置
  record "动作" key=value ...              记录训练数据
  analyze "动作"                           查看某动作的训练报告
  delete [动作]                            删除最后一条记录
  update "动作" key=value ...              修改某动作最后一条记录
  summary [日期]                           查看每日训练总结（默认今天）
  summary 开始日期 结束日期                查看多日训练总结
  compare 日期1 日期2                      对比两日训练变化
  setpath "新路径" [--migrate]             修改存储路径
  timer [间隔|off]                         组间歇提醒（如 timer 2min / timer off）
  version                                  查看版本号和 commit 信息

可用字段 (key=value):
  weight=80kg    重量（支持 kg/lbs）
  reps=8         次数
  sets=4         组数
  distance=1.8km 距离（支持 km/m）
  duration=40min 时长（支持 Xh/Xmin/Xs）
  incline=15%    坡度

示例:
  python fitness_manager.py record "卧推" weight=80kg reps=8 sets=4
  python fitness_manager.py record "悬垂举腿" reps=12 sets=3
  python fitness_manager.py record "游泳" distance=1.8km duration=40min
  python fitness_manager.py record "坡道走" distance=2km duration=30min incline=15%
  python fitness_manager.py record "平板支撑" duration=60s sets=3
  python fitness_manager.py analyze "卧推"
  python fitness_manager.py summary 2024-03-20 2024-03-24
  python fitness_manager.py compare 2024-03-20 2024-03-24""")

# ── CLI 入口 ──────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    action = sys.argv[1]

    # 每次调用时检查未读的间歇提醒
    pending_alert = check_alert()
    if pending_alert:
        print(pending_alert)

    if action in ("-h", "--help", "help"):
        print_usage()
        sys.exit(0)
    elif action in ("version", "--version", "-v"):
        print_version()
        sys.exit(0)
    elif action == "init":
        log_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_LOG_DIR
        if os.path.exists(CONFIG_FILE):
            print(f"⚠️ 已存在配置文件，原路径: {get_config()['log_dir']}，将更新为: {log_dir}")
        update_config(log_dir=log_dir)
        auto_migrate()
        print(f"🚀 初始化完成，数据将存储在: {log_dir}")
    elif action == "record":
        if len(sys.argv) < 4:
            print("❌ 参数不足。用法: record \"动作\" key=value ...")
            print("   示例: record \"卧推\" weight=80kg reps=8 sets=4")
            sys.exit(1)
        auto_migrate()
        exercise = sys.argv[2]
        fields = parse_kv_args(sys.argv[3:])
        if not fields:
            print("❌ 至少需要一个有效的 key=value 参数。")
            sys.exit(1)
        record(exercise, fields)
    elif action == "analyze":
        if len(sys.argv) < 3:
            print("❌ 参数不足。用法: analyze \"动作\"")
            sys.exit(1)
        analyze(sys.argv[2])
    elif action == "delete":
        exercise = sys.argv[2] if len(sys.argv) > 2 else None
        delete_last(exercise)
    elif action == "update":
        if len(sys.argv) < 4:
            print("❌ 参数不足。用法: update \"动作\" key=value ...")
            sys.exit(1)
        exercise = sys.argv[2]
        fields = parse_kv_args(sys.argv[3:])
        if not fields:
            print("❌ 至少需要一个有效的 key=value 参数。")
            sys.exit(1)
        update_last(exercise, fields)
    elif action == "summary":
        if len(sys.argv) >= 4:
            summary_range(sys.argv[2], sys.argv[3])
        elif len(sys.argv) == 3:
            summary(sys.argv[2])
        else:
            summary()
    elif action == "compare":
        if len(sys.argv) < 4:
            print("❌ 参数不足。用法: compare 日期1 日期2")
            print("   示例: compare 2024-03-20 2024-03-24")
            sys.exit(1)
        compare(sys.argv[2], sys.argv[3])
    elif action == "setpath":
        if len(sys.argv) < 3:
            print("❌ 参数不足。用法: setpath \"新路径\" [--migrate]")
            sys.exit(1)
        migrate = "--migrate" in sys.argv
        set_path(sys.argv[2], migrate=migrate)
    elif action == "timer":
        handle_timer_command(sys.argv[2:])
    else:
        print(f"❌ 未知命令: {action}")
        print_usage()
        sys.exit(1)
