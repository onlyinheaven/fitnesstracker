# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Claude AI Skill (defined in SKILL.md) for recording and analyzing fitness/exercise data. Python CLI backed by SQLite, zero external dependencies. Supports strength training, bodyweight exercises, cardio/distance activities, and more.

## Commands

```bash
# Run the CLI
python scripts/fitness_manager.py <action> [args...]

# Record (key=value format, all fields optional except exercise name)
python scripts/fitness_manager.py record "卧推" weight=80kg reps=8 sets=4       # 力量训练
python scripts/fitness_manager.py record "悬垂举腿" reps=12 sets=3              # 自重训练
python scripts/fitness_manager.py record "游泳" distance=1.8km duration=40min   # 距离+时长
python scripts/fitness_manager.py record "坡道走" distance=2km duration=30min incline=15%
python scripts/fitness_manager.py record "平板支撑" duration=60s sets=3         # 时长+组数

# Other actions
python scripts/fitness_manager.py init [路径]                    # Initialize
python scripts/fitness_manager.py analyze "动作"                 # Analyze exercise
python scripts/fitness_manager.py summary                        # Today's summary
python scripts/fitness_manager.py summary 2024-03-20 2024-03-24  # Multi-day range
python scripts/fitness_manager.py compare 2024-03-20 2024-03-24  # Compare two dates
python scripts/fitness_manager.py delete [动作]                  # Delete last record
python scripts/fitness_manager.py update "动作" weight=85kg      # Update last record (partial)
python scripts/fitness_manager.py setpath /new/path --migrate    # Move data
python scripts/fitness_manager.py version                       # Version + commit info
python scripts/fitness_manager.py help

# Install/update (source + target)
python scripts/install.py <源路径> <目标路径>
python scripts/install.py . ~/.claude/skills/fitness-tracker

# Changelog management
python scripts/changelog.py add <version> "变更1" "变更2" ...   # Add entry
python scripts/changelog.py show [version]                       # Query log
python scripts/changelog.py generate                             # Regenerate CHANGELOG.md
```

Available fields: `weight`, `reps`, `sets`, `distance`, `duration`, `incline`.

There is no linter, build step, or automated test runner. Evaluation cases are in `evals/evals.json` (7 manual test scenarios).

## Architecture

- **`scripts/fitness_manager.py`** — the entire application. CLI dispatcher at the bottom routes actions to handler functions.
- **`SKILL.md`** — skill definition with trigger conditions, workflow, parameter mapping rules, and output format. This is the interface contract for how Claude invokes the tool.
- **`config.json`** (git-ignored) — stores `log_dir` path. Created on `init`.
- **`record/fitness_log.db`** (git-ignored) — SQLite database. Schema: `workouts(id, date, timestamp, exercise, weight, reps, sets, distance, duration, incline)`. All fields except id/date/timestamp/exercise are nullable.

## Key Design Decisions

- **Flexible key=value parameters**: `record` and `update` accept arbitrary field combinations. Different exercise types use different fields — no fixed positional arguments.
- **Weight is stored as-is** (with unit suffix like "80kg" or "176lbs"). PR comparison converts to kg internally via `parse_weight_kg()`.
- **Distance stored as-is** ("1.8km", "400m"). Comparison converts to km via `parse_distance_km()`.
- **Duration stored as-is** ("40min", "1h20min", "60s"). Comparison converts to seconds via `parse_duration_seconds()`.
- **PR logic is type-aware**: strength → max weight, bodyweight → max reps, distance → max distance + best pace.
- **Rest time** is calculated from explicit local timestamps stored per record.
- **Auto-migration**: detects legacy CSV files and imports into SQLite; also ALTERs old tables to add new columns.
- **Compare** handles non-identical exercise sets: shows common exercises with diffs, plus exercises unique to each date.
- Documentation and output strings are in **Chinese**.

## 提交规范

每次 `git commit` 之前，必须先运行 `bash scripts/bump_version.sh` 更新 VERSION 和 manifest.json 中的版本信息（commit hash、日期、message）。如果是功能性变更，传入新版本号（如 `bash scripts/bump_version.sh 0.7.0`）；如果只是小修改，不传参数保留当前版本号。然后将 `VERSION` 和 `manifest.json` 一并加入本次提交。

## Manifest 维护

`manifest.json` 记录所有需要分发给用户的文件清单。**以下操作必须同步更新 `manifest.json`：**

- 新增需要分发的文件 → 加入 `files` 列表
- 删除或重命名已分发文件 → 从 `files` 中移除/修改路径
- 新增需要分发的子目录 → 加入 `directories` 列表
- `scripts/bump_version.sh` 会自动同步 manifest 中的 `version` 字段

不需要分发的文件（如 `CLAUDE.md`、`evals/`、`scripts/bump_version.sh`、`.gitignore`）列在 `exclude_from_dist` 中仅供参考，不影响安装流程。

## 测试规范

**禁止在用户真实数据库上做测试。** 所有测试临时文件统一放在项目路径下的 `tmp/` 目录中（已在 `.gitignore` 中排除）。

具体做法：
1. 测试前：`python scripts/fitness_manager.py init tmp/test`
2. 执行测试操作
3. 测试后：`python scripts/fitness_manager.py init record` 恢复配置，并 `rm -rf tmp/`
