#!/bin/bash
# 更新 VERSION 文件中的 commit、date 和 message 信息
# 用法: ./scripts/bump_version.sh [新版本号]
#   不传版本号时只更新 commit/date/message，保留当前版本号

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION_FILE="$SCRIPT_DIR/../VERSION"

# 读取当前版本号
CURRENT_VERSION=$(head -1 "$VERSION_FILE" 2>/dev/null || echo "0.1.0")

# 如果传了新版本号则使用新版本号
NEW_VERSION="${1:-$CURRENT_VERSION}"

# 获取 git 信息
COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
DATE=$(date +%Y-%m-%d)
MESSAGE=$(git log -1 --format=%s 2>/dev/null || echo "")

cat > "$VERSION_FILE" <<EOF
${NEW_VERSION}
commit: ${COMMIT}
date: ${DATE}
message: ${MESSAGE}
EOF

echo "VERSION updated: v${NEW_VERSION} (${COMMIT}, ${DATE})"
echo "  message: ${MESSAGE}"
