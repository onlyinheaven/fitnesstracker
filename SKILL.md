---
name: fitness-tracker
description: 当用户提及健身、力量训练相关内容时触发。包括但不限于：记录、删除、修改、查询健身数据（如深蹲、卧推、硬拉、引体向上等），查看训练报告或健身总结，询问历史 PR，修改数据存储路径，或使用口语化表达如"今天练了XXX"、"帮我记一下"、"看看上次卧推多少"、"把数据换个地方存"。支持 kg/lbs 双单位，自动分析间歇时间和历史 PR。
compatibility: 需要 Python 3.x 和文件系统访问权限（用于存储 SQLite 数据库）
---

# Fitness Tracker Skill

这个 Skill 旨在帮助用户精准记录健身数据，支持多组记录、错误记录删除、历史 PR 对比以及全天训练总结。

## 依赖环境
- **Python**: 需要 Python 3.x (仅使用标准库：sqlite3, json, datetime 等)。
- **存储**: 默认在 Skill 目录下的 `record` 文件夹，支持用户自定义路径。
- **重量单位**: 默认使用 **kg**，如用户指定 **lbs** 则自动支持（需在输入中明确标注，如 "135lbs"）。

## 核心工作流

### 1. 初始化 (Initialization) - 跨会话持久化
- **触发条件**: 检测到 Skill 目录下不存在 `config.json` 时（通常是第一次使用）。
- **动作**:
    1. 询问用户："是否需要指定健身数据的存储路径？（默认路径为 Skill 目录下的 record 文件夹）"。
    2. 如果用户选择默认，调用：`python scripts/fitness_manager.py init`（无需传路径，脚本自动使用默认路径）。
    3. 如果用户指定了路径，调用：`python scripts/fitness_manager.py init "用户指定的路径"`。
    4. 脚本会将路径保存到 `config.json`（位于 Skill 目录）中，后续所有对话将自动读取该配置，不再重复询问。

### 2. 会话首次调用提示 (Session Notification)
- **要求**: 在**每一次新的对话会话**中，当你第一次准备调用该 Skill 完成用户请求时，必须先输出提示语："**将使用 Fitness Tracker Skill 为您处理健身记录相关要求。**"

### 3. 记录功能 (Record)
- **逻辑**: 分析用户的动作、重量、次数，**务必询问组数**（如果用户没说）。
- **调用**: `python scripts/fitness_manager.py record "动作" "重量" "次数" "组数"`
- **反馈**: 记录成功后，紧接着调用 `analyze` 指令向用户展示该动作的反馈（含间歇时间分析）。

### 4. 健身报告 (Summary)
- **触发**: "今天的健身报告"、"总结一下训练"或查询特定日期。
- **调用**: `python scripts/fitness_manager.py summary [可选日期：YYYY-MM-DD]`

### 5. 删除与修改 (Maintenance)
- **删除**: `python scripts/fitness_manager.py delete [可选动作]` (删除该动作或全局最后一条记录)
- **修改**: `python scripts/fitness_manager.py update "动作" "重量" "次数" "组数"` (修改该动作最后一条记录)

### 6. 查询分析 (Analyze)
- **调用**: `python scripts/fitness_manager.py analyze "动作"`

### 7. 修改存储路径 (Set Path)
- **触发**: 用户想要更改健身数据的存储位置，如"把数据换个地方存"、"修改存储路径"。
- **逻辑**: 先询问用户："是要在新路径下从头开始记录，还是把已有数据迁移过去继续记录？"
  - **从头开始（默认）**: `python scripts/fitness_manager.py setpath "新路径"` — 旧数据保留在原路径不受影响。
  - **迁移数据**: `python scripts/fitness_manager.py setpath "新路径" --migrate` — 将旧数据搬到新路径。
- **反馈**: 显示旧路径、新路径，以及操作结果。

## 脚本路径引用
脚本位于 SKILL.md 同级目录下的 `scripts/fitness_manager.py`。

调用脚本时，需要确保使用正确的路径。推荐方式：
- 获取 SKILL.md 所在目录的绝对路径（即 Skill 根目录），拼接 `scripts/fitness_manager.py`
- 示例：若 Skill 安装在 `/home/user/.claude/skills/fitness-tracker/`，则调用：
  `python /home/user/.claude/skills/fitness-tracker/scripts/fitness_manager.py <command> [args]`

配置文件 `config.json` 在首次运行 `init` 命令时生成，位于 Skill 根目录。

可通过 `python scripts/fitness_manager.py help` 查看完整用法说明。

## 输出格式示例

### 记录成功
```
✅ 成功记录: 2024-03-24 | 卧推 | 80kg | 8次 | 4组
⏱️ 距离上一组间歇时间: 3分15秒
```

### 动作分析报告
```
--- 卧推 训练报告 ---
📝 今日进度:
   - 60kg (12次 x 3组)
   - 70kg (10次 x 3组) [间歇 2分30秒]
   - 80kg (8次 x 4组) [间歇 3分15秒]
🏆 历史 PR: 85kg (6次 x 3组) 于 2024-03-20
📅 上次训练 (2024-03-20):
   - 80kg (8次 x 3组)
   - 85kg (6次 x 3组)
----------------------
```

### 每日总结
```
======= 🏋️ 健身报告 (2024-03-24) =======
🔹 卧推: 共 10 组
   - 60kg | 12次 | 3组
   - 70kg | 10次 | 3组
   - 80kg | 8次 | 4组
🔹 深蹲: 共 9 组
   - 100kg | 8次 | 3组
   - 120kg | 5次 | 3组
   - 130kg | 3次 | 3组
==========================================
📊 总结: 共完成了 2 个动作，累计训练 19 组。
坚持就是胜利！💪
```

## 安装与更新

### 必须文件

从本仓库安装此 Skill，需要拷贝以下文件（保持目录结构）：

```
fitness-tracker/
├── SKILL.md                        # Skill 定义文件（必须）
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
cp /mnt/e/workrepo/QClawRepo/fitness-tracker/scripts/fitness_manager.py ~/.claude/skills/fitness-tracker/scripts/
```

**安装（Windows CMD）：**
```cmd
mkdir %USERPROFILE%\.claude\skills\fitness-tracker\scripts
copy /Y E:\workrepo\QClawRepo\fitness-tracker\SKILL.md %USERPROFILE%\.claude\skills\fitness-tracker\
copy /Y E:\workrepo\QClawRepo\fitness-tracker\scripts\fitness_manager.py %USERPROFILE%\.claude\skills\fitness-tracker\scripts\
```

**安装（Windows PowerShell）：**
```powershell
New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude\skills\fitness-tracker\scripts"
Copy-Item "E:\workrepo\QClawRepo\fitness-tracker\SKILL.md" "$env:USERPROFILE\.claude\skills\fitness-tracker\" -Force
Copy-Item "E:\workrepo\QClawRepo\fitness-tracker\scripts\fitness_manager.py" "$env:USERPROFILE\.claude\skills\fitness-tracker\scripts\" -Force
```

**更新**：重新执行上述拷贝命令即可覆盖旧文件。已有的 `config.json` 和 `record/` 数据不受影响。

---

### 其他工具（Gemini CLI、QClaw 等）

对于其他支持 Skill / 插件机制的 AI 工具，安装方式相同——将上述两个必须文件拷贝至该工具的 Skill 目录中，保持 `fitness-tracker/` 的目录结构：

```
<工具的Skill目录>/fitness-tracker/
├── SKILL.md
└── scripts/
    └── fitness_manager.py
```

请参考对应工具的文档确认其 Skill 目录位置，然后将文件从本仓库拷贝过去。更新时同样覆盖拷贝即可。

---

## 边缘情况处理

| 情况 | 处理方式 |
|------|----------|
| 用户未指定单位 | 默认使用 kg |
| 用户指定 lbs | 支持，如 "135lbs"、"45 lbs" |
| 用户未说组数 | 必须主动询问 |
| 删除不存在的记录 | 提示"未找到记录，无法删除" |
| 查询不存在的动作 | 提示"尚无 XXX 的历史记录" |
| 指定日期无训练记录 | 提示"YYYY-MM-DD 暂无训练记录" |
| 修改路径未指定新路径 | 提示参数不足，显示用法 |
| 新路径与当前路径相同 | 提示无需修改 |
| 迁移时目标路径已有数据库 | 提示将被覆盖，继续执行 |
