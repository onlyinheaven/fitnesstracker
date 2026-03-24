import csv
import os
import sys
from datetime import datetime
from collections import defaultdict

LOG_DIR = os.path.join(os.getcwd(), "record")
LOG_FILE = os.path.join(LOG_DIR, "fitness_log.csv")

def ensure_file_exists():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Date", "Exercise", "Weight", "Reps", "Sets"])

def record(exercise, weight, reps, sets):
    ensure_file_exists()
    date_str = datetime.now().strftime("%Y-%m-%d")
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([date_str, exercise, weight, reps, sets])
    print(f"✅ 成功记录: {date_str} | {exercise} | {weight} | {reps}次 | {sets}组")

def delete_last(exercise):
    if not os.path.exists(LOG_FILE):
        print("❌ 尚无历史记录，无法删除。")
        return

    rows = []
    with open(LOG_FILE, mode="r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("❌ 记录文件为空。")
        return

    last_index = -1
    for i in range(len(rows) - 1, -1, -1):
        if rows[i]["Exercise"] == exercise:
            last_index = i
            break

    if last_index != -1:
        deleted = rows.pop(last_index)
        with open(LOG_FILE, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Date", "Exercise", "Weight", "Reps", "Sets"])
            writer.writeheader()
            writer.writerows(rows)
        print(f"🗑️ 已成功删除最新的 {exercise} 记录: {deleted[\"Date\"]} | {deleted[\"Weight\"]} | {deleted[\"Reps\"]}次 | {deleted[\"Sets\"]}组")
    else:
        print(f"❓ 未找到关于 {exercise} 的任何记录。")

def analyze(exercise):
    if not os.path.exists(LOG_FILE):
        print("尚无历史记录。")
        return

    pr_weight = -1.0
    pr_record = None
    last_records = []
    last_date = None
    today_records = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    with open(LOG_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Exercise"] == exercise:
                try:
                    w_str = row["Weight"].lower().replace("kg", "").replace("lbs", "").strip()
                    w = float(w_str)
                    if w > pr_weight:
                        pr_weight = w
                        pr_record = row
                except ValueError:
                    pass
                
                r_date = row["Date"]
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
        for r in today_records:
            print(f"   - {r[\"Weight\"]} ({r[\"Reps\"]}次 x {r[\"Sets\"]}组)")
    
    if pr_record:
        print(f"🏆 历史 PR: {pr_record[\"Weight\"]} ({pr_record[\"Reps\"]}次 x {pr_record[\"Sets\"]}组) 于 {pr_record[\"Date"]}")
    
    if last_records:
        print(f"📅 上次训练 ({last_date}):")
        for r in last_records:
            print(f"   - {r[\"Weight\"]} ({r[\"Reps\"]}次 x {r[\"Sets\"]}组)")
    print("----------------------")

def summary_today():
    if not os.path.exists(LOG_FILE):
        print("❌ 尚无记录，快去开始今天的训练吧！")
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_data = defaultdict(list)
    
    with open(LOG_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Date"] == today_str:
                today_data[row["Exercise"]].append(row)

    if not today_data:
        print(f"📅 {today_str} 暂无训练记录。")
        return

    print(f"======= 🏋️ 今日健身报告 ({today_str}) =======")
    total_exercises = len(today_data)
    total_sets = 0
    
    for exercise, records in today_data.items():
        exercise_sets = sum(int(r["Sets"]) for r in records)
        total_sets += exercise_sets
        print(f"🔹 {exercise}: 共 {exercise_sets} 组")
        for r in records:
            print(f"   - {r[\"Weight\"]} | {r[\"Reps\"]}次 | {r[\"Sets\"]}组")
    
    print("==========================================")
    print(f"📊 总结: 今天共完成了 {total_exercises} 个动作，累计训练 {total_sets} 组。")
    print("坚持就是胜利！💪")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
        
    action = sys.argv[1]
    if action == "record":
        record(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    elif action == "analyze":
        analyze(sys.argv[2])
    elif action == "delete":
        delete_last(sys.argv[2])
    elif action == "summary":
        summary_today()
