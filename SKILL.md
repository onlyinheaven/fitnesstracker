---
name: fitness-tracker
description: 当用户提及记录、删除、查询健身数据（如深蹲、卧推、硬拉等）或查看今日健身总结报告时触发。支持记录重量、次数、组数，并能根据用户指令删除最近一条错误记录。
---

# Fitness Tracker Skill

这个 Skill 旨在帮助用户精准记录健身数据，支持多组记录、错误记录删除、历史 PR 对比以及全天训练总结。

## 核心工作流

1. **记录功能 (Record)**:
   - 分析用户的动作、重量、次数，**务必询问组数**（如果用户没说）。
   - 调用：`python <脚本路径> record "动作" "重量" "次数" "组数"`
   - 记录成功后，紧接着调用 `analyze` 指令向用户展示该动作的反馈。

2. **今日健身报告 (Summary)**:
   - 当用户说“今天的健身报告”、“总结一下今天的训练”、“今天练了什么”或“今天的报告”时触发。
   - 调用：`python <脚本路径> summary`
   - 展示今日所有训练动作的明细，并对总动作数和总组数进行总结。

3. **删除功能 (Delete)**:
   - 用户说“删掉刚才的记录”、“记错了，删掉”时，删除对应动作的最后一条记录。
   - 调用：`python <脚本路径> delete "动作"`

4. **查询反馈 (Analyze)**:
   - 调用：`python <脚本路径> analyze "动作"`
   - 用于展示单项动作的今日进度、历史 PR 及上次对比。

5. **跨平台脚本路径**:
   - `~/.gemini/skills/fitness-tracker/scripts/fitness_manager.py` (Linux/Mac)
   - `%USERPROFILE%\.gemini\skills\fitness-tracker\scripts\fitness_manager.py` (Windows)
