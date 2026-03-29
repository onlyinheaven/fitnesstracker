#!/usr/bin/env python3
"""fitness-tracker 安装/更新脚本

根据 manifest.json 清单安装 skill 文件，使用 MD5+size 校验完整性。
安装流程：复制源 manifest 为临时文件 → 判断是否需要更新 → 安装 → 校验 → 输出更新日志。

用法:
    python scripts/install.py <源路径> <目标路径> [--force]
    python scripts/install.py /path/to/repo ~/.claude/skills/fitness-tracker
    python scripts/install.py /path/to/repo ~/.claude/skills/fitness-tracker --force
"""

import hashlib
import io
import json
import os
import shutil
import sys

# Windows GBK 终端下强制 UTF-8 输出
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

MANIFEST_TMP = ".manifest_tmp"


def file_md5(filepath):
    """计算文件 MD5"""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path):
    """读取 manifest.json，返回解析后的 dict"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_file_paths(manifest):
    """从 manifest 提取文件路径列表（兼容新旧格式）"""
    paths = []
    for item in manifest.get("files", []):
        if isinstance(item, dict):
            paths.append(item["path"])
        else:
            paths.append(item)
    return paths


def verify_files(target_dir, manifest):
    """逐文件校验 MD5 + size，返回 (ok_count, errors)"""
    ok = 0
    errors = []
    for item in manifest.get("files", []):
        if isinstance(item, dict):
            path, expected_md5, expected_size = item["path"], item.get("md5"), item.get("size")
        else:
            path, expected_md5, expected_size = item, None, None

        # manifest.json 自身跳过 MD5 校验（无法自引用）
        if path == "manifest.json":
            if os.path.exists(os.path.join(target_dir, path)):
                ok += 1
            else:
                errors.append(f"缺失: {path}")
            continue

        dst = os.path.join(target_dir, path)
        if not os.path.exists(dst):
            errors.append(f"缺失: {path}")
            continue

        if expected_size is not None and os.path.getsize(dst) != expected_size:
            errors.append(f"大小不匹配: {path} (期望 {expected_size}, 实际 {os.path.getsize(dst)})")
            continue

        if expected_md5 is not None and file_md5(dst) != expected_md5:
            errors.append(f"MD5 不匹配: {path}")
            continue

        ok += 1

    return ok, errors


def show_changelog(target_dir, version):
    """输出指定版本的更新日志"""
    changelog_file = os.path.join(target_dir, "changelog.json")
    if not os.path.exists(changelog_file):
        return

    with open(changelog_file, "r", encoding="utf-8") as f:
        entries = json.load(f)

    for entry in entries:
        if entry["version"] == version:
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
            return


def install(source_dir, target_dir, force=False):
    source_dir = os.path.abspath(source_dir)
    target_dir = os.path.abspath(target_dir)

    src_manifest = os.path.join(source_dir, "manifest.json")
    if not os.path.exists(src_manifest):
        print("错误: 源目录找不到 manifest.json")
        sys.exit(1)

    # 步骤 1: 复制源 manifest 到目标目录作为临时参考文件
    os.makedirs(target_dir, exist_ok=True)
    tmp_manifest = os.path.join(target_dir, MANIFEST_TMP)
    shutil.copy2(src_manifest, tmp_manifest)

    try:
        manifest = load_manifest(tmp_manifest)
        src_ver = manifest.get("version", "")

        # 记录安装前的目标状态（用于判断是安装/更新/修复）
        dst_manifest = os.path.join(target_dir, "manifest.json")
        dst_ver_file = os.path.join(target_dir, "VERSION")
        had_manifest = os.path.exists(dst_manifest)
        old_ver = ""
        if os.path.exists(dst_ver_file):
            with open(dst_ver_file, "r", encoding="utf-8") as f:
                old_ver = f.readline().strip()

        # 步骤 2: 判断是否需要安装
        if force:
            print(f"强制更新模式，覆盖所有文件...")
        elif os.path.exists(dst_manifest):
            if file_md5(dst_manifest) == file_md5(tmp_manifest):
                # manifest 完全一致，逐文件校验
                _, errors = verify_files(target_dir, manifest)
                if not errors:
                    print(f"当前已是最新版本 v{src_ver}，无需更新")
                    return
                print(f"版本一致 (v{src_ver}) 但文件不完整，重新安装...")
            # else: manifest 不同，需要更新

        # 步骤 3: 创建子目录
        for d in manifest.get("directories", []):
            os.makedirs(os.path.join(target_dir, d), exist_ok=True)

        # 步骤 4: 从源逐文件复制
        file_paths = get_file_paths(manifest)
        copied = 0
        for fp in file_paths:
            src = os.path.join(source_dir, fp)
            dst = os.path.join(target_dir, fp)
            os.makedirs(os.path.dirname(dst) or target_dir, exist_ok=True)
            if not os.path.exists(src):
                print(f"⚠️  源文件不存在，跳过: {fp}")
                continue
            shutil.copy2(src, dst)
            copied += 1

        # 步骤 5: 安装后校验
        ok, errors = verify_files(target_dir, manifest)

        # manifest.json 特殊校验：与临时参考副本字节比对
        if os.path.exists(dst_manifest):
            if file_md5(dst_manifest) != file_md5(tmp_manifest):
                errors.append("manifest.json 校验不一致")

        if errors:
            for e in errors:
                print(f"❌ {e}")
            print("安装不完整，请检查源文件")
            sys.exit(1)

        # 判断安装/更新/修复/强制更新（基于安装前记录的状态）
        if force:
            action = "强制更新"
        elif not old_ver:
            action = "安装"
        elif old_ver == src_ver:
            action = "修复"
        else:
            action = "更新"

        print(f"✅ {action}完成: v{src_ver} ({copied} 个文件，校验通过)")

        # 步骤 6: 输出本版本更新日志
        show_changelog(target_dir, src_ver)

    finally:
        # 清理临时文件
        if os.path.exists(tmp_manifest):
            os.remove(tmp_manifest)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv

    if len(args) < 2:
        print("用法: python scripts/install.py <源路径> <目标路径> [--force]")
        print("示例: python scripts/install.py /path/to/repo ~/.claude/skills/fitness-tracker")
        print("      python scripts/install.py /path/to/repo ~/.claude/skills/fitness-tracker --force")
        sys.exit(1)

    install(args[0], args[1], force=force)
