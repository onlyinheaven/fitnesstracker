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

每次 `git commit` 之前，必须先运行 `bash scripts/bump_version.sh` 更新 VERSION 和 manifest.json 中的版本信息（commit hash、日期、message）。然后将 `VERSION` 和 `manifest.json` 一并加入本次提交。

**版本号规则（语义化版本 X.Y.Z）：**

| 变更类型 | 版本位 | 示例 | bump 命令 |
|---------|--------|------|-----------|
| 新功能、新脚本、新命令 | minor (Y) | 0.9.0 → 0.10.0 | `bash scripts/bump_version.sh 0.10.0` |
| bug 修复、编码修复 | patch (Z) | 0.9.0 → 0.9.1 | `bash scripts/bump_version.sh 0.9.1` |
| 文档、注释、格式调整 | 不升版本 | 0.9.0 不变 | `bash scripts/bump_version.sh` |

- **功能性变更**（feat）：必须升 minor 版本
- **修复性变更**（fix）：必须升 patch 版本
- **非功能性变更**（docs、chore、refactor）：不传版本号，仅更新 commit/date/message

## Manifest 维护

`manifest.json` 记录所有需要分发给用户的文件清单。**以下操作必须同步更新 `manifest.json`：**

- 新增需要分发的文件 → 加入 `files` 列表
- 删除或重命名已分发文件 → 从 `files` 中移除/修改路径
- 新增需要分发的子目录 → 加入 `directories` 列表
- `scripts/bump_version.sh` 会自动同步 manifest 中的 `version` 字段

不需要分发的文件（如 `CLAUDE.md`、`evals/`、`scripts/bump_version.sh`、`.gitignore`）列在 `exclude_from_dist` 中仅供参考，不影响安装流程。

## Windows GBK 编码规范

Windows 终端默认使用 GBK 编码，无法输出中文和 emoji，会导致 `UnicodeEncodeError`。**所有 Python 脚本必须在模块顶部（import 之后、业务代码之前）添加以下编码修复：**

```python
import io
import sys

# Windows GBK 终端下强制 UTF-8 输出，避免中文和 emoji 编码错误
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
```

新增或修改 Python 脚本时必须确认包含此修复，stdout 和 stderr 都要处理。

## 测试规范

**禁止在用户真实数据库上做测试。** 所有测试临时文件统一放在项目路径下的 `tmp/` 目录中（已在 `.gitignore` 中排除）。

具体做法：
1. 测试前：`python scripts/fitness_manager.py init tmp/test`
2. 执行测试操作
3. 测试后：`python scripts/fitness_manager.py init record` 恢复配置，并 `rm -rf tmp/`
