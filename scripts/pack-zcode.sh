#!/usr/bin/env bash
# 打包 zcode 插件技能目录:skills/storyrepo/ ← 仓库根(单一事实源)。
# 用法: bash scripts/pack-zcode.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$HERE/skills/storyrepo"
rm -rf "$DEST" && mkdir -p "$DEST"
cp "$HERE/SKILL.md" "$DEST/"
cp -r "$HERE/references" "$DEST/references"
cp -r "$HERE/templates" "$DEST/templates"
echo "✔ skills/storyrepo 已打包($(find "$DEST" -type f | wc -l) 个文件)"
