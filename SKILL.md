---
name: fitness-tracker
description: 当用户提及健身、运动相关内容时触发。包括但不限于：记录力量训练（深蹲、卧推、硬拉、引体向上等）、自重训练（悬垂举腿、平板支撑、俯卧撑等）、有氧运动（游泳、跑步、坡道走、骑行等），查看训练报告或总结，询问历史 PR，查询多日训练记录，对比两天的训练变化，删除或修改记录，修改数据存储路径。支持 kg/lbs 双单位、km/m 距离、灵活时长格式。口语化表达如"今天练了XXX"、"帮我记一下"、"看看上次卧推多少"、"这周练了啥"、"对比一下周一和周三"、"这个skill是什么版本"。
compatibility: 需要 Python 3.x 和文件系统访问权限（用于存储 SQLite 数据库）
---

# Fitness Tracker Skill

这个 Skill 旨在帮助用户精准记录各类健身与运动数据，支持力量训练、自重训练、有氧运动等多种运动类型，以及多日查询和两日对比分析。

## 依赖环境
- **Python**: 需要 Python 3.x (仅使用标准库：sqlite3, json, datetime, re, shutil 等)。
- **存储**: 默认在 Skill 目录下的 `record` 文件夹，支持用户自定义路径。
- **重量单位**: 默认使用 **kg**，如用户指定 **lbs** 则自动支持（需在输入中明确标注，如 "135lbs"）。
- **距离单位**: 支持 **km** 和 **m**（如 "1.8km"、"400m"）。
- **时长格式**: 支持 **Xh**、**Xmin**、**Xs** 及组合（如 "40min"、"1h20min"、"60s"）。

## 核心工作流

### 1. 初始化 (Initialization) - 跨会话持久化
- **触发条件**: 检测到 Skill 目录下不存在 `config.json` 时（通常是第一次使用）。
- **动作**:
    1. 询问用户："是否需要指定健身数据的存储路径？（默认路径为 Skill 目录下的 record 文件夹）"。
    2. 如果用户选择默认，调用：`python scripts/fitness_manager.py init`。
    3. 如果用户指定了路径，调用：`python scripts/fitness_manager.py init "用户指定的路径"`。

### 2. 会话首次调用提示 (Session Notification)
- **要求**: 在**每一次新的对话会话**中，当你第一次准备调用该 Skill 完成用户请求时，必须先输出提示语："**将使用 Fitness Tracker Skill 为您处理健身记录相关要求。**"

### 3. 记录功能 (Record) — 统一 key=value 格式
- **逻辑**: 分析用户的运动类型和提供的数据，映射为 key=value 参数。
- **调用**: `python scripts/fitness_manager.py record "动作" key=value ...`
- **反馈**: 记录成功后，紧接着调用 `analyze` 指令展示反馈。

**参数映射规则**:

| 运动场景 | 用户说法示例 | 调用命令 |
|---------|------------|---------|
| 力量训练 | "卧推 80kg 8个 4组" | `record "卧推" weight=80kg reps=8 sets=4` |
| 自重训练 | "悬垂举腿 12个 3组" | `record "悬垂举腿" reps=12 sets=3` |
| 距离+时长 | "游泳 1.8km 40分钟" | `record "游泳" distance=1.8km duration=40min` |
| 带坡度 | "坡道走 2km 30分钟 坡度15%" | `record "坡道走" distance=2km duration=30min incline=15%` |
| 时长+组数 | "平板支撑 60秒 3组" | `record "平板支撑" duration=60s sets=3` |
| 跑步 | "跑了5公里 用了25分钟" | `record "跑步" distance=5km duration=25min` |
| 骑行 | "骑车20km 45分钟" | `record "骑行" distance=20km duration=45min` |

**可用字段**: `weight`(重量), `reps`(次数), `sets`(组数), `distance`(距离), `duration`(时长), `incline`(坡度)

**注意事项**:
- 力量训练如果用户没说组数，**务必询问组数**。
- 自重训练（无重量的动作）不需要传 weight 字段。
- 用户说"个"、"次"、"rep"都映射为 reps。
- 用户说"公里"映射为 km，"米"映射为 m。
- 时长需转换为标准格式：分钟→Xmin，秒→Xs，小时→Xh，混合→XhYmin。

### 4. 健身报告 (Summary)
- **单日**: `python scripts/fitness_manager.py summary [YYYY-MM-DD]`（默认今天）
- **多日范围**: `python scripts/fitness_manager.py summary 开始日期 结束日期`
- **触发**: "今天的健身报告"、"这周训练总结"、"看看最近几天练了啥"

### 5. 两日对比 (Compare)
- **调用**: `python scripts/fitness_manager.py compare 日期1 日期2`
- **触发**: "对比一下周一和周三的训练"、"上次和这次卧推有什么变化"
- **功能**: 自动找出共同训练项目并逐项对比变化，列出仅某日有的项目。两天练的项目不需要完全相同。

### 6. 查询分析 (Analyze)
- **调用**: `python scripts/fitness_manager.py analyze "动作"`
- **功能**: 根据运动类型智能选择 PR 标准：
  - 力量训练 → 最大重量 PR
  - 自重训练 → 最多次数 PR
  - 距离类运动 → 最长距离 PR + 最快配速

### 7. 删除与修改 (Maintenance)
- **删除**: `python scripts/fitness_manager.py delete [动作]`
- **修改**: `python scripts/fitness_manager.py update "动作" key=value ...`（只需传要改的字段）

### 8. 修改存储路径 (Set Path)
- **从头开始**: `python scripts/fitness_manager.py setpath "新路径"`
- **迁移数据**: `python scripts/fitness_manager.py setpath "新路径" --migrate`

### 9. 版本查询 (Version)
- **调用**: `python scripts/fitness_manager.py version`
- **触发**: "这个skill是什么版本"、"fitness tracker版本号"、"当前版本"
- **功能**: 输出当前版本号、对应的 commit 哈希、发布日期和更新说明。

## 脚本路径引用
脚本位于 SKILL.md 同级目录下的 `scripts/fitness_manager.py`。

调用脚本时，需要确保使用正确的路径。推荐方式：
- 获取 SKILL.md 所在目录的绝对路径（即 Skill 根目录），拼接 `scripts/fitness_manager.py`
- 示例：若 Skill 安装在 `/home/user/.claude/skills/fitness-tracker/`，则调用：
  `python /home/user/.claude/skills/fitness-tracker/scripts/fitness_manager.py <command> [args]`

可通过 `python scripts/fitness_manager.py help` 查看完整用法说明。

## 输出格式示例

### 力量训练记录
```
✅ 成功记录: 2024-03-24 | 卧推 | 80kg | 8次 | 4组
⏱️ 距离上一组间歇时间: 3分15秒
```

### 自重训练记录
```
✅ 成功记录: 2024-03-24 | 悬垂举腿 | 自重 | 12次 | 3组
```

### 距离+时长记录
```
✅ 成功记录: 2024-03-24 | 游泳 | 1.8km | 40min
✅ 成功记录: 2024-03-24 | 坡道走 | 2km | 30min | 坡度15%
```

### 动作分析报告（力量）
```
--- 卧推 训练报告 ---
📝 今日进度:
   - 60kg | 12次 | 3组
   - 80kg | 8次 | 4组 [间歇 3分15秒]
🏆 历史 PR (最大重量): 85kg | 6次 | 3组 于 2024-03-20
📅 上次训练 (2024-03-20):
   - 80kg | 8次 | 3组
----------------------
```

### 动作分析报告（距离类）
```
--- 游泳 训练报告 ---
📝 今日进度:
   - 1.8km | 40min
🏆 历史 PR (最长距离): 2.0km | 38min 于 2024-03-15
⚡ 最快配速: 19'00"/km 于 2024-03-15
📅 上次训练 (2024-03-22):
   - 1.5km | 35min
----------------------
```

### 多日训练报告
```
======= 🏋️ 训练报告 (2024-03-20 ~ 2024-03-24) =======
📅 2024-03-20:
  🔹 卧推: 共 10 组
     - 80kg | 8次 | 4组
  🔹 深蹲: 共 9 组
     - 100kg | 8次 | 3组
📅 2024-03-22:
  🔹 游泳:
     - 1.8km | 40min
📅 2024-03-24:
  🔹 悬垂举腿: 共 6 组
     - 自重 | 12次 | 3组
==========================================
📊 总结: 3 天内共完成了 4 个动作。
坚持就是胜利！💪
```

### 两日对比
```
======= 📊 训练对比 (03-20 vs 03-24) =======
🔄 共同训练项目:
  🔹 卧推:
     03-20: 最大 80kg, 共 10 组
     03-24: 最大 85kg, 共 10 组
     变化: 重量 ↑5.0kg

⬅️ 仅 2024-03-20 训练:
  🔹 深蹲: 最大 100kg, 共 9 组

➡️ 仅 2024-03-24 训练:
  🔹 悬垂举腿: 自重, 共 6 组
=============================================
```

## 安装与更新

### 必须文件

```
fitness-tracker/
├── SKILL.md                        # Skill 定义文件（必须）
├── VERSION                         # 版本信息文件（必须）
└── scripts/
    └── fitness_manager.py          # 核心脚本（必须）
```

源路径（本仓库）：`/mnt/e/workrepo/QClawRepo/fitness-tracker/`

> `config.json` 和 `record/` 目录是运行时自动生成的，无需拷贝。

---

### Claude Code

Claude Code 的 Skill 目录：
- **Linux / macOS**: `~/.claude/skills/`
- **Windows**: `%USERPROFILE%\.claude\skills\`

**安装（Linux / macOS）：**
```bash
mkdir -p ~/.claude/skills/fitness-tracker/scripts
cp /mnt/e/workrepo/QClawRepo/fitness-tracker/SKILL.md ~/.claude/skills/fitness-tracker/
cp /mnt/e/workrepo/QClawRepo/fitness-tracker/VERSION ~/.claude/skills/fitness-tracker/
cp /mnt/e/workrepo/QClawRepo/fitness-tracker/scripts/fitness_manager.py ~/.claude/skills/fitness-tracker/scripts/
```

**安装（Windows CMD）：**
```cmd
mkdir %USERPROFILE%\.claude\skills\fitness-tracker\scripts
copy /Y E:\workrepo\QClawRepo\fitness-tracker\SKILL.md %USERPROFILE%\.claude\skills\fitness-tracker\
copy /Y E:\workrepo\QClawRepo\fitness-tracker\VERSION %USERPROFILE%\.claude\skills\fitness-tracker\
copy /Y E:\workrepo\QClawRepo\fitness-tracker\scripts\fitness_manager.py %USERPROFILE%\.claude\skills\fitness-tracker\scripts\
```

**安装（Windows PowerShell）：**
```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills\fitness-tracker\scripts"
Copy-Item "E:\workrepo\QClawRepo\fitness-tracker\SKILL.md" "$env:USERPROFILE\.claude\skills\fitness-tracker\" -Force
Copy-Item "E:\workrepo\QClawRepo\fitness-tracker\VERSION" "$env:USERPROFILE\.claude\skills\fitness-tracker\" -Force
Copy-Item "E:\workrepo\QClawRepo\fitness-tracker\scripts\fitness_manager.py" "$env:USERPROFILE\.claude\skills\fitness-tracker\scripts\" -Force
```

**更新**：重新执行上述拷贝命令即可覆盖旧文件。已有的 `config.json` 和 `record/` 数据不受影响。

---

### 其他工具（Gemini CLI、QClaw 等）

将上述两个必须文件拷贝至该工具的 Skill 目录中，保持 `fitness-tracker/` 的目录结构。请参考对应工具的文档确认其 Skill 目录位置。

---

## 边缘情况处理

| 情况 | 处理方式 |
|------|----------|
| 用户未指定单位 | 重量默认 kg，距离默认 km |
| 用户指定 lbs | 支持，如 "135lbs"、"45 lbs" |
| 用户指定 m（米）| 支持，如 "400m"，内部转换为 km 比较 |
| 力量训练未说组数 | 必须主动询问 |
| 自重训练无重量 | 不传 weight 字段，输出显示"自重" |
| 有氧运动无次数/组数 | 只传 distance/duration，不传 reps/sets |
| 带坡度的运动 | 额外传 incline 字段 |
| 删除不存在的记录 | 提示"未找到记录，无法删除" |
| 查询不存在的动作 | 提示"尚无 XXX 的历史记录" |
| 指定日期无训练记录 | 提示"YYYY-MM-DD 暂无训练记录" |
| 多日范围无记录 | 提示"开始 ~ 结束 暂无训练记录" |
| 对比时两天项目不同 | 分别列出共同项目和仅某日项目 |
| 新路径与当前路径相同 | 提示无需修改 |
| 迁移时目标已有数据库 | 提示将被覆盖，继续执行 |
