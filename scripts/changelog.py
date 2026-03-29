#!/usr/bin/env python3
"""更新日志管理脚本

用法:
    python scripts/changelog.py add <version> "变更1" "变更2" ...
    python scripts/changelog.py show [version]
    python scripts/changelog.py generate
"""

import io
import json
import os
import sys
from datetime import date

# Windows GBK 终端下强制 UTF-8 输出，避免中文和 emoji 编码错误
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
CHANGELOG_JSON = os.path.join(PROJECT_DIR, "changelog.json")
CHANGELOG_MD = os.path.join(PROJECT_DIR, "CHANGELOG.md")
MANIFEST_JSON = os.path.join(PROJECT_DIR, "manifest.json")


def load_changelog():
    if os.path.exists(CHANGELOG_JSON):
        with open(CHANGELOG_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_changelog(entries):
    with open(CHANGELOG_JSON, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=4)
        f.write("\n")


def build_tree():
    """根据 manifest.json 生成目录结构树"""
    if not os.path.exists(MANIFEST_JSON):
        return "（manifest.json 不存在，无法生成目录树）"

    with open(MANIFEST_JSON, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 收集所有路径
    files = manifest.get("files", [])
    paths = []
    for item in files:
        if isinstance(item, dict):
            paths.append(item["path"])
        else:
            paths.append(item)

    # 构建树结构
    tree = {}
    for p in sorted(paths):
        parts = p.split("/")
        node = tree
        for part in parts:
            if part not in node:
                node[part] = {}
            node = node[part]

    # 渲染树
    lines = ["fitness-tracker/"]

    def render(node, prefix=""):
        items = sorted(node.items(), key=lambda x: (len(x[1]) == 0, x[0]))
        for i, (name, children) in enumerate(items):
            is_last = i == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(f"{prefix}{connector}{name}")
            if children:
                extension = "    " if is_last else "│   "
                render(children, prefix + extension)

    render(tree)
    return "\n".join(lines)


def cmd_add(version, changes):
    entries = load_changelog()

    # 检查版本是否已存在，已存在则追加 changes
    existing = None
    for entry in entries:
        if entry["version"] == version:
            existing = entry
            break

    tree = build_tree()

    if existing:
        existing["changes"].extend(changes)
        existing["date"] = date.today().isoformat()
        existing["tree"] = tree
    else:
        entries.insert(0, {
            "version": version,
            "date": date.today().isoformat(),
            "changes": changes,
            "tree": tree,
        })

    save_changelog(entries)
    cmd_generate()
    print(f"✅ 已{'追加' if existing else '添加'} v{version} 更新日志 ({len(changes)} 条变更)")


def cmd_show(version=None):
    entries = load_changelog()
    if not entries:
        print("暂无更新日志")
        return

    if version:
        version = version.lstrip("v")
        found = [e for e in entries if e["version"] == version]
        if not found:
            print(f"未找到 v{version} 的更新日志")
            return
        entries = found

    for entry in entries:
        print(f"\n{'=' * 50}")
        print(f"📦 v{entry['version']} ({entry['date']})")
        print(f"{'=' * 50}")
        for change in entry.get("changes", []):
            print(f"  - {change}")
        if entry.get("tree"):
            print(f"\n📁 目录结构:")
            for line in entry["tree"].split("\n"):
                print(f"  {line}")
        print()


def cmd_generate():
    entries = load_changelog()
    lines = ["# Changelog\n"]

    for entry in entries:
        lines.append(f"## v{entry['version']} ({entry['date']})\n")
        for change in entry.get("changes", []):
            lines.append(f"- {change}")
        if entry.get("tree"):
            lines.append(f"\n<details><summary>目录结构</summary>\n")
            lines.append("```")
            lines.append(entry["tree"])
            lines.append("```\n")
            lines.append("</details>")
        lines.append("")

    with open(CHANGELOG_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ 已生成 CHANGELOG.md")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python scripts/changelog.py add <version> \"变更1\" \"变更2\" ...")
        print("  python scripts/changelog.py show [version]")
        print("  python scripts/changelog.py generate")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "add":
        if len(sys.argv) < 4:
            print("用法: python scripts/changelog.py add <version> \"变更1\" [\"变更2\" ...]")
            sys.exit(1)
        cmd_add(sys.argv[2], sys.argv[3:])

    elif cmd == "show":
        version = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_show(version)

    elif cmd == "generate":
        cmd_generate()

    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
