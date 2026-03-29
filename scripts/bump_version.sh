#!/bin/bash
# 更新 VERSION 文件和 manifest.json 中的版本信息（含 MD5+size）
# 用法: ./scripts/bump_version.sh [新版本号]
#   不传版本号时只更新 commit/date/message，保留当前版本号

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."
VERSION_FILE="$PROJECT_DIR/VERSION"
MANIFEST_FILE="$PROJECT_DIR/manifest.json"

# 读取当前版本号
CURRENT_VERSION=$(head -1 "$VERSION_FILE" 2>/dev/null || echo "0.1.0")

# 如果传了新版本号则使用新版本号
NEW_VERSION="${1:-$CURRENT_VERSION}"

# 获取 git 信息
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
DATE=$(date +%Y-%m-%d)
MESSAGE=$(git log -1 --format=%s 2>/dev/null || echo "")

# 更新 VERSION 文件
cat > "$VERSION_FILE" <<EOF
${NEW_VERSION}
commit: ${COMMIT}
date: ${DATE}
message: ${MESSAGE}
EOF

echo "VERSION updated: v${NEW_VERSION} (${COMMIT}, ${DATE})"
echo "  message: ${MESSAGE}"

# 同步更新 manifest.json：版本号 + 文件 MD5+size
if [ -f "$MANIFEST_FILE" ]; then
    if command -v python3 &>/dev/null; then
        python3 -c "
import json, hashlib, os

project_dir = '$PROJECT_DIR'
manifest_file = '$MANIFEST_FILE'
new_version = '$NEW_VERSION'

with open(manifest_file, 'r') as f:
    m = json.load(f)

m['version'] = new_version

# 计算每个文件的 MD5 和 size
new_files = []
old_files = m.get('files', [])
for item in old_files:
    # 兼容旧格式（纯字符串）和新格式（dict）
    if isinstance(item, dict):
        path = item['path']
    else:
        path = item

    filepath = os.path.join(project_dir, path)

    # manifest.json 自身无法自引用
    if path == 'manifest.json':
        new_files.append({'path': path, 'md5': None, 'size': None})
        continue

    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        h = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        md5 = h.hexdigest()
        new_files.append({'path': path, 'md5': md5, 'size': size})
    else:
        new_files.append({'path': path, 'md5': None, 'size': None})
        print(f'  warning: {path} not found, skipping checksum')

m['files'] = new_files

with open(manifest_file, 'w') as f:
    json.dump(m, f, ensure_ascii=False, indent=4)
    f.write('\n')

print(f'manifest.json synced: v{new_version} ({len(new_files)} files with checksums)')
"
    fi
fi
