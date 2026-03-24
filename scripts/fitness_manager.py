import sqlite3
import os
import sys
import json
from datetime import datetime
from collections import defaultdict

LBS_TO_KG = 0.453592

def parse_weight_kg(weight_str):
    """将重量字符串统一转换为 kg 数值，用于比较。"""
    w = weight_str.lower().strip()
    if "lbs" in w:
        return float(w.replace("lbs", "").strip()) * LBS_TO_KG
    return float(w.replace("kg", "").strip())

# 基础配置路径
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(SKILL_DIR, "config.json")
DEFAULT_LOG_DIR = os.path.join(SKILL_DIR, "record")

def get_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"log_dir": DEFAULT_LOG_DIR}

def save_config(log_dir):
    # 配置文件保存在 Skill 根目录，不需要创建目录（假设 Skill 目录已存在）
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"log_dir": log_dir}, f, ensure_ascii=False, indent=4)

def get_db_paths():
    config = get_config()
    log_dir = os.path.expanduser(config["log_dir"])
    return log_dir, os.path.join(log_dir, "fitness_log.db"), os.path.join(log_dir, "fitness_log.csv")

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
            weight TEXT NOT NULL,
            reps INTEGER NOT NULL,
            sets INTEGER NOT NULL
        )
    ''')
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
                INSERT INTO workouts (date, exercise, weight, reps, sets)
                VALUES (?, ?, ?, ?, ?)
            ''', (row["Date"], row["Exercise"], row["Weight"], row["Reps"], row["Sets"]))
    conn.commit()
    conn.close()
    print("✅ 旧数据迁移完成！")

def record(exercise, weight, reps, sets):
    conn = get_connection()
    cursor = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    cursor.execute('''
        SELECT timestamp FROM workouts 
        WHERE exercise = ? AND date = ?
        ORDER BY timestamp DESC LIMIT 1
    ''', (exercise, date_str))
    last_row = cursor.fetchone()
    
    now = datetime.now()
    timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO workouts (date, timestamp, exercise, weight, reps, sets)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (date_str, timestamp_str, exercise, weight, reps, sets))
    conn.commit()
    
    rest_time_str = "首组"
    if last_row:
        try:
            last_dt = datetime.strptime(last_row["timestamp"], "%Y-%m-%d %H:%M:%S")
            diff_seconds = (now - last_dt).total_seconds()
            if diff_seconds > 0:
                mins = int(diff_seconds // 60)
                secs = int(diff_seconds % 60)
                rest_time_str = f"{mins}分{secs}秒" if mins > 0 else f"{secs}秒"
        except (ValueError, TypeError):
            pass

    conn.close()
    print(f"✅ 成功记录: {date_str} | {exercise} | {weight} | {reps}次 | {sets}组")
    if rest_time_str != "首组":
         print(f"⏱️ 距离上一组间歇时间: {rest_time_str}")

def delete_last(exercise=None):
    conn = get_connection()
    cursor = conn.cursor()
    if exercise:
        cursor.execute("SELECT id, date, exercise, weight, reps, sets FROM workouts WHERE exercise = ? ORDER BY timestamp DESC LIMIT 1", (exercise,))
    else:
        cursor.execute("SELECT id, date, exercise, weight, reps, sets FROM workouts ORDER BY timestamp DESC LIMIT 1")
    row = cursor.fetchone()
    if not row:
        print(f"❌ 未找到记录，无法删除。")
        conn.close()
        return
    cursor.execute("DELETE FROM workouts WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    print(f"🗑️ 已成功删除记录: {row['date']} | {row['exercise']} | {row['weight']} | {row['reps']}次 | {row['sets']}组")

def update_last(exercise, weight, reps, sets):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, date FROM workouts WHERE exercise = ? ORDER BY timestamp DESC LIMIT 1", (exercise,))
    row = cursor.fetchone()
    if not row:
        print(f"❌ 未找到关于 {exercise} 的记录。")
        conn.close()
        return
    cursor.execute("UPDATE workouts SET weight = ?, reps = ?, sets = ? WHERE id = ?", (weight, reps, sets, row["id"]))
    conn.commit()
    conn.close()
    print(f"✏️ 已成功修改记录: {row['date']} | {exercise} | {weight} | {reps}次 | {sets}组")

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
    pr_weight_kg = -1.0
    pr_record = None
    for row in rows:
        try:
            w_kg = parse_weight_kg(row["weight"])
            if w_kg > pr_weight_kg:
                pr_weight_kg = w_kg
                pr_record = row
        except (ValueError, AttributeError):
            pass
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
        print(f"📝 今日进度:")
        for i, r in enumerate(today_records):
            time_info = ""
            if i > 0:
                try:
                    t1 = datetime.strptime(today_records[i-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
                    t2 = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
                    diff = (t2 - t1).total_seconds()
                    mins = int(diff // 60)
                    secs = int(diff % 60)
                    time_info = f"[间歇 {mins}分{secs}秒]" if mins > 0 else f"[间歇 {secs}秒]"
                except (ValueError, TypeError):
                    pass
            print(f"   - {r['weight']} ({r['reps']}次 x {r['sets']}组) {time_info}")
    if pr_record:
        print(f"🏆 历史 PR: {pr_record['weight']} ({pr_record['reps']}次 x {pr_record['sets']}组) 于 {pr_record['date']}")
    if last_records:
        print(f"📅 上次训练 ({last_date}):")
        for r in last_records:
            print(f"   - {r['weight']} ({r['reps']}次 x {r['sets']}组)")
    print("----------------------")

def summary(date_str=None):
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT exercise, weight, reps, sets, timestamp FROM workouts WHERE date = ? ORDER BY timestamp ASC", (date_str,))
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        print(f"📅 {date_str} 暂无训练记录。")
        return
    today_data = defaultdict(list)
    for r in rows:
        today_data[r["exercise"]].append(r)
    print(f"======= 🏋️ 健身报告 ({date_str}) =======")
    total_exercises = len(today_data)
    total_sets = 0
    for exercise, records in today_data.items():
        exercise_sets = sum(int(r["sets"]) for r in records)
        total_sets += exercise_sets
        print(f"🔹 {exercise}: 共 {exercise_sets} 组")
        for i, r in enumerate(records):
            time_info = ""
            if i > 0:
                try:
                    t1 = datetime.strptime(records[i-1]["timestamp"], "%Y-%m-%d %H:%M:%S")
                    t2 = datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S")
                    diff = (t2 - t1).total_seconds()
                    mins = int(diff // 60)
                    secs = int(diff % 60)
                    time_info = f"[间歇 {mins}分{secs}秒]" if mins > 0 else f"[间歇 {secs}秒]"
                except (ValueError, TypeError):
                    pass
            print(f"   - {r['weight']} | {r['reps']}次 | {r['sets']}组 {time_info}")
    print("==========================================")
    print(f"📊 总结: 共完成了 {total_exercises} 个动作，累计训练 {total_sets} 组。")
    print("坚持就是胜利！💪")

import shutil

def set_path(new_path, migrate=False):
    """修改数据存储路径。默认从新路径重新开始记录，--migrate 可迁移旧数据。"""
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
            print(f"⚠️ 目标路径已存在数据库文件，旧数据库将被覆盖。")
        shutil.copy2(old_db, new_db)
        os.remove(old_db)
        old_csv = os.path.join(old_path, "fitness_log.csv")
        if os.path.exists(old_csv):
            shutil.copy2(old_csv, os.path.join(new_path, "fitness_log.csv"))
            os.remove(old_csv)
        print(f"✅ 已有数据已迁移至新路径。")
    elif migrate:
        print(f"ℹ️ 旧路径下无数据文件，跳过迁移。")
    else:
        print(f"ℹ️ 将在新路径下从头开始记录（旧数据保留在原路径不受影响）。")

    save_config(new_path)
    print(f"✅ 存储路径已更新为: {new_path}")

def print_usage():
    print("""用法: python fitness_manager.py <command> [args]

命令:
  init [路径]                          初始化配置（不传路径则使用默认 record/ 目录）
  record "动作" "重量" "次数" "组数"   记录一条健身数据
  analyze "动作"                       查看某动作的训练报告
  delete [动作]                        删除最后一条记录（可指定动作）
  update "动作" "重量" "次数" "组数"   修改某动作最后一条记录
  summary [YYYY-MM-DD]                 查看每日训练总结（默认今天）
  setpath "新路径" [--migrate]          修改存储路径（默认从新路径重新开始，--migrate 迁移旧数据）

示例:
  python fitness_manager.py record "卧推" "80kg" "8" "4"
  python fitness_manager.py analyze "卧推"
  python fitness_manager.py summary 2024-03-24
  python fitness_manager.py setpath "/data/fitness"
  python fitness_manager.py setpath "/data/fitness" --migrate""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    action = sys.argv[1]
    if action in ("-h", "--help", "help"):
        print_usage()
        sys.exit(0)
    elif action == "init":
        log_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_LOG_DIR
        if os.path.exists(CONFIG_FILE):
            print(f"⚠️ 已存在配置文件，原路径: {get_config()['log_dir']}，将更新为: {log_dir}")
        save_config(log_dir)
        auto_migrate()
        print(f"🚀 初始化完成，数据将存储在: {log_dir}")
    elif action == "record":
        if len(sys.argv) < 6:
            print("❌ 参数不足。用法: record \"动作\" \"重量\" \"次数\" \"组数\"")
            sys.exit(1)
        auto_migrate()
        record(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif action == "analyze":
        if len(sys.argv) < 3:
            print("❌ 参数不足。用法: analyze \"动作\"")
            sys.exit(1)
        analyze(sys.argv[2])
    elif action == "delete":
        exercise = sys.argv[2] if len(sys.argv) > 2 else None
        delete_last(exercise)
    elif action == "update":
        if len(sys.argv) < 6:
            print("❌ 参数不足。用法: update \"动作\" \"重量\" \"次数\" \"组数\"")
            sys.exit(1)
        update_last(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif action == "summary":
        date_str = sys.argv[2] if len(sys.argv) > 2 else None
        summary(date_str)
    elif action == "setpath":
        if len(sys.argv) < 3:
            print("❌ 参数不足。用法: setpath \"新路径\" [--migrate]")
            sys.exit(1)
        migrate = "--migrate" in sys.argv
        set_path(sys.argv[2], migrate=migrate)
    else:
        print(f"❌ 未知命令: {action}")
        print_usage()
        sys.exit(1)
