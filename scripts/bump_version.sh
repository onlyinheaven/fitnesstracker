#!/bin/bash
# 更新 VERSION 文件和 manifest.json 中的版本信息
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

# 同步更新 manifest.json 中的 version 字段
if [ -f "$MANIFEST_FILE" ]; then
    if command -v python3 &>/dev/null; then
        python3 -c "
import json
with open('$MANIFEST_FILE', 'r') as f:
    m = json.load(f)
m['version'] = '$NEW_VERSION'
with open('$MANIFEST_FILE', 'w') as f:
    json.dump(m, f, ensure_ascii=False, indent=4)
    f.write('\n')
"
        echo "manifest.json version synced: ${NEW_VERSION}"
    fi
fi

echo "VERSION updated: v${NEW_VERSION} (${COMMIT}, ${DATE})"
echo "  message: ${MESSAGE}"
