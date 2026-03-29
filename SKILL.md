---
name: fitness-tracker
description: 当用户提及健身、运动相关内容时触发。包括但不限于：记录力量训练（深蹲、卧推、硬拉、引体向上等）、自重训练（悬垂举腿、平板支撑、俯卧撑等）、有氧运动（游泳、跑步、坡道走、骑行等），查看训练报告或总结，询问历史 PR，查询多日训练记录，对比两天的训练变化，删除或修改记录，修改数据存储路径。支持 kg/lbs 双单位、km/m 距离、灵活时长格式。口语化表达如"今天练了XXX"、"帮我记一下"、"看看上次卧推多少"、"这周练了啥"、"对比一下周一和周三"、"我的PR是多少"、"卧推个人记录"、"个人最好成绩"、"这个skill是什么版本"、"设置组间歇提醒"、"打开间歇计时"。
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

> **⚠️ 重要**: 每次 `record` 成功后，必须紧接着调用 `analyze "动作"` 展示该动作的训练报告。这是完整记录流程的一部分，不可省略。

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

### 9. 组间歇提醒 (Timer)

**基本命令**:
- **开启**: `python scripts/fitness_manager.py timer 2min`（支持 Xmin、Xs、XminYs 格式）
- **关闭**: `python scripts/fitness_manager.py timer off`
- **查看状态**: `python scripts/fitness_manager.py timer`
- **触发**: "设置组间歇提醒2分钟"、"打开间歇计时"、"关掉间歇提醒"、"间歇计时还开着吗"、"现在间歇提醒是什么状态"

**自动检查机制**:
每次调用 `fitness_manager.py`（无论什么命令）时，脚本启动阶段会自动执行 `check_alert()`：读取 `.timer_alert` 文件 → 输出未读提醒 → 删除文件。因此 AI 不需要轮询或等待计时器到期，下一次执行任意命令时提醒会自动出现在输出的第一行。

**计时器生命周期**（每次 `record` 后自动触发）:
1. `kill_timer()` — 杀掉已有后台计时器进程（如有）
2. `clear_alert()` — 清除残留的提醒文件（如有）
3. spawn `rest_timer.py` — 启动新的后台倒计时进程
4. 倒计时到期 → 写入 `.timer_alert` 文件 + 终端 print 提醒
5. 下一次 `record` 从步骤 1 重新开始

**提醒双输出机制**: 终端直接 print（CLI 用户可见）+ 写入 `.timer_alert` 文件（Claude Code/Claw 等工具通过自动检查机制获取）。

**已知限制**: 如果实际休息时间已超过设定间歇（如设 2min，实际过了 5min），`record` 仍会启动一个完整时长的计时器，不会因为已超时而跳过或立即提醒。

默认关闭，配置保存在 config.json 中。

### 10. 版本查询 (Version)
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

## 输出格式

脚本输出使用 emoji 前缀标识不同信息类型：
- `✅` — 记录成功
- `⏱️` — 组间歇/动作间隔时间
- `⏰` — 计时器启动/到时提醒
- `🏆` — 历史 PR
- `📝` — 今日进度
- `📅` — 日期标记
- `📊` — 统计/对比

详细输出格式示例见 `references/output_formats.md`。

## 安装与更新

### 清单驱动机制

所有需要分发的文件由 `manifest.json` 统一管理，包含每个文件的 MD5 和 size 用于完整性校验。

**`manifest.json` 结构：**
```json
{
    "version": "0.8.0",
    "files": [
        {"path": "SKILL.md", "md5": "a1b2c3...", "size": 12345},
        {"path": "VERSION", "md5": "d4e5f6...", "size": 77},
        {"path": "manifest.json", "md5": null, "size": null},
        {"path": "scripts/fitness_manager.py", "md5": "...", "size": 38152},
        ...
    ],
    "directories": ["scripts"]
}
```

> `manifest.json` 自身的 md5/size 为 null（无法自引用），通过字节比对校验。
> `config.json`、`record/`、`.timer_pid`、`.timer_alert` 是运行时自动生成的，不在分发清单中。

---

### 安装/更新/修复 统一流程

安装、更新、修复共用同一套流程。

**路径定义：**
- `SOURCE`（源路径）: 本项目的 Git 仓库路径
  - **Linux / macOS / WSL**: `/mnt/e/workrepo/QClawRepo/fitness-tracker`
  - **Windows PowerShell**: `E:\workrepo\QClawRepo\fitness-tracker`
- `TARGET`（目标路径）: 用户的 Skill 安装目录，位于对应工具的 skills 目录下
  - **Claude Code (Linux / macOS / WSL)**: `~/.claude/skills/fitness-tracker/`
  - **Claude Code (Windows PowerShell)**: `%USERPROFILE%\.claude\skills\fitness-tracker\`
  - **其他工具（QClaw、Gemini CLI 等）**: 找到该工具存放 skills 的目录，在其下创建 `fitness-tracker/` 子目录作为 TARGET。通常类似 `~/.工具名/skills/fitness-tracker/`，具体路径参考对应工具的文档。

**核心原则：先拿到大脑，再拿到工具，再用工具干活。**

```
步骤 1: 从 SOURCE 复制 SKILL.md → TARGET
        → 重新加载 Skill（确保后续步骤按最新指令执行）

步骤 2: 检查 TARGET 是否具备安装所需文件
        必须文件: scripts/install.py, manifest.json
        - 文件缺失 → 从 SOURCE 直接复制（创建 scripts/ 目录如需要）
        - 文件存在但运行报错 → 从 SOURCE 重新复制覆盖
        直到必须文件就绪后继续

步骤 3: 运行安装脚本
        python <TARGET>/scripts/install.py <SOURCE> <TARGET>
        脚本自动完成：
          1. 复制源 manifest.json 为临时参考文件
          2. 比对是否需要更新（manifest MD5 比对 + 逐文件校验）
          3. 从源复制所有文件到目标
          4. 逐文件 MD5+size 校验确认完整性
          5. 输出本版本更新日志
          6. 清理临时文件

步骤 4: 完成后重新加载 Skill（使新版本的功能和指令立即生效）
```

**示例：**
```bash
python scripts/install.py /path/to/source ~/.claude/skills/fitness-tracker
```

适用于所有工具（Claude Code、Gemini CLI、QClaw 等），只需将目标路径替换为对应工具的 Skill 目录。

**触发场景：**

| 用户意图 | 示例表达 |
|---------|---------|
| 安装 | "安装 fitness tracker skill" |
| 更新 | "更新一下这个 skill"、"有新版本吗" |
| 修复 | "skill 好像坏了"、"修复一下"、"脚本报错了" |
| 强制更新 | "强制更新 skill"、"重新安装一遍"、"不管版本直接更新" |

> 安装、更新、修复均不会影响用户的 `config.json` 和 `record/` 数据。

**强制更新：** 当用户要求强制更新时，跳过版本比对，直接从步骤 1 开始执行完整流程，从源覆盖所有文件并重新校验。调用时在 install.py 后追加 `--force` 参数：

```bash
python <TARGET>/scripts/install.py <SOURCE> <TARGET> --force
```

---

### 更新日志

安装/更新完成后会自动输出本版本的更新日志。也可手动查询：

```bash
python scripts/changelog.py show [version]    # 查询指定版本或全部日志
```

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
| 实际休息时间已超过间歇设置 | 仍启动完整计时器（不会立即提醒） |
| 计时器关闭时用户询问状态 | 调用 `timer` 查看，显示"关闭" |
| 快速连续记录多组 | 每次 record 重置计时器（kill 旧 → 启新） |
| 无法识别的间歇时间格式 | 提示格式错误并显示支持的格式 |
