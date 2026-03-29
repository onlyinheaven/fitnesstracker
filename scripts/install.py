#!/usr/bin/env python3
"""fitness-tracker 安装/更新脚本

根据 manifest.json 清单，将 skill 文件从源目录安装到目标目录。
自动比较版本号，版本一致时跳过。

用法:
    python scripts/install.py <目标路径>
    python scripts/install.py ~/.claude/skills/fitness-tracker
"""

import json
import os
import shutil
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DIR = os.path.dirname(SCRIPT_DIR)  # 项目根目录


def read_version(path):
    """读取 VERSION 文件第一行"""
    version_file = os.path.join(path, "VERSION")
    if os.path.exists(version_file):
        with open(version_file, "r", encoding="utf-8") as f:
            return f.readline().strip()
    return ""


def install(target_dir):
    manifest_file = os.path.join(SOURCE_DIR, "manifest.json")
    if not os.path.exists(manifest_file):
        print("错误: 找不到 manifest.json")
        sys.exit(1)

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    src_ver = read_version(SOURCE_DIR)
    dst_ver = read_version(target_dir)

    if src_ver and src_ver == dst_ver:
        print(f"当前已是最新版本 v{src_ver}，无需更新")
        return

    # 创建目标根目录
    os.makedirs(target_dir, exist_ok=True)

    # 创建子目录
    for d in manifest.get("directories", []):
        os.makedirs(os.path.join(target_dir, d), exist_ok=True)

    # 复制文件
    copied = 0
    for f in manifest["files"]:
        src = os.path.join(SOURCE_DIR, f)
        dst = os.path.join(target_dir, f)
        os.makedirs(os.path.dirname(dst) or target_dir, exist_ok=True)
        if not os.path.exists(src):
            print(f"警告: 源文件不存在，跳过: {f}")
            continue
        shutil.copy2(src, dst)
        copied += 1

    action = "更新" if dst_ver else "安装"
    print(f"{action}完成: v{src_ver} ({copied} 个文件)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scripts/install.py <目标路径>")
        print("示例: python scripts/install.py ~/.claude/skills/fitness-tracker")
        sys.exit(1)

    install(sys.argv[1])
