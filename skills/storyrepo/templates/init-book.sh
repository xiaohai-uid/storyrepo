#!/usr/bin/env bash
# 用法: bash init-book.sh <书名目录> <总章数> <每章字数> [目标字数]
# storyrepo v2 建仓:骨架 + book.yaml + storyrepo 引擎初始化。
# 前置:storyrepo CLI 已安装(见 engine/README.md)。
set -euo pipefail
NAME="${1:?用法: bash init-book.sh 书名 总章数 每章字数 [目标字数]}"
CHS="${2:-330}"; WPC="${3:-3000}"; TARGET="$((CHS*WPC))"; [ -n "${4:-}" ] && TARGET="$4"
ROOT="$(pwd)/$NAME"
mkdir -p "$ROOT"/{大纲/{承诺,信息差,卷纲},定稿/{正文,设定/{角色,信息差},记忆/{章摘要,卷摘要}},文风/金句库,工作区/评审报告}

cat > "$ROOT/book.yaml" <<EOF
---
name: $NAME
status: planning
total_chapters: $CHS
min_words_per_chapter: $WPC
max_words_per_chapter: $((WPC+800))
target_words: $TARGET
createdAt: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
---
EOF
printf '%s\n' '工作区/' '.cache/' > "$ROOT/.gitignore"

# 骨架文档(开书流填充)
cat > "$ROOT/大纲/总纲.md" <<'EOF'
# 总纲
## 一句话
## 金手指(规则与代价)
## 主线目标 / 阻力
## 核心暗线 / 回收点
## 卷划分
| 卷 | 章范围 | 核心冲突 | 卷末高潮 |
EOF
cat > "$ROOT/大纲/细纲蓝图.md" <<'EOF'
| 章 | 标题 | 要发生什么 | 硬约束 | 禁区 | 下一章悬念 |
EOF
cat > "$ROOT/文风/风格宪法.md" <<'EOF'
# 风格宪法
## 语调/节奏/视角
## 禁词(去AI味,见 skill references/anti-ai-flavor.md)
## 比喻偏好
EOF
cat > "$ROOT/偏好记忆.md" <<'EOF'
# 偏好记忆(favoriteGenres / protagonist / 平台 / 篇幅)
EOF

# 引擎初始化
git -C "$ROOT" init -q && git -C "$ROOT" config core.quotepath false
if command -v storyrepo >/dev/null 2>&1; then SR=storyrepo
else SR="$(dirname "$0")/../engine/.venv/bin/storyrepo"; fi
$SR init --root "$ROOT"
echo "✅ 书仓已建: $ROOT (目标 $TARGET 字 / $CHS 章)"
echo "下一步: storyrepo 开书流填 总纲/人物档案/细纲蓝图 → 二次确认 → 写第 1 章"
echo "命令: $SR contract/context/brief/doctor/review/commit/check --root $ROOT --chapter 1"