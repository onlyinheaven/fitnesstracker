# Changelog

## v0.8.0 (2026-03-29)

- feat: manifest.json 增加 MD5+size 完整性校验
- feat: 安装脚本临时 manifest 机制，不依赖源路径持续可读
- feat: 自举更新流程，兼容只有 SKILL.md 的旧版本
- feat: 增量更新日志系统 (changelog.json + CHANGELOG.md)
- feat: 安装/更新后自动输出本版本更新日志

<details><summary>目录结构</summary>

```
fitness-tracker/
├── scripts
│   ├── changelog.py
│   ├── fitness_manager.py
│   ├── install.py
│   └── rest_timer.py
├── CHANGELOG.md
├── SKILL.md
├── VERSION
├── changelog.json
└── manifest.json
```

</details>

## v0.7.0 (2026-03-29)

- feat: 安装/更新逻辑迁移到独立 Python 脚本 (install.py)
- refactor: SKILL.md 安装章节从内联命令精简为脚本调用

## v0.6.0 (2026-03-29)

- feat: 清单驱动的安装/更新机制 (manifest.json)
- docs: 添加提交规范和测试规范到 CLAUDE.md

## v0.5.0 (2026-03-29)

- feat: 新增组间歇计时提醒功能 (timer 命令)
- feat: 双输出机制 — 终端 print + .timer_alert 文件

## v0.4.0 (2026-03-29)

- fix: 修复 Windows GBK 终端下中文和 emoji 输出编码错误
- fix: 记录新动作时显示距上一个动作的间隔时间

## v0.3.0 (2026-03-29)

- feat: 添加版本查询功能 (version 命令)

## v0.2.0 (2026-03-29)

- feat: 扩展支持多运动类型、key=value 参数格式
- feat: 多日查询和两日对比分析

## v0.1.0 (2026-03-29)

- feat: 初始版本 — 基础健身记录和查询功能
