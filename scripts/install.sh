#!/usr/bin/env bash
# storyrepo skill 安装器:把技能装进本机各 agent 的技能目录。
# 用法: bash scripts/install.sh [--with-engine]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
WITH_ENGINE=0
[ "${1:-}" = "--with-engine" ] && WITH_ENGINE=1

# 探测技能目录(你的工具链:pi / codex / .agents 共享 / claude / opencode)
TARGETS=()
for d in "$HOME/.pi/agent/skills" "$HOME/.codex/skills" "$HOME/.agents/skills" "$HOME/.claude/skills" "$HOME/.config/opencode/skills"; do
  [ -d "$d" ] && TARGETS+=("$d")
done
if [ "${#TARGETS[@]}" -eq 0 ]; then
  echo "✘ 未探测到任何 agent 技能目录"; exit 1
fi

for t in "${TARGETS[@]}"; do
  rm -rf "$t/storyrepo"
  mkdir -p "$t/storyrepo"
  cp -r "$HERE/SKILL.md" "$HERE/references" "$HERE/templates" "$t/storyrepo/"
  if [ "$WITH_ENGINE" = 1 ]; then
    cp -r "$HERE/engine" "$t/storyrepo/engine"
    # 尽力建 venv(无 pip 环境跳过,留提示)
    if [ -x "$t/storyrepo/engine/vendor/get-pip.py" ] && command -v python3 >/dev/null 2>&1; then
      if python3 -m venv --without-pip "$t/storyrepo/engine/.venv" 2>/dev/null \
         && "$t/storyrepo/engine/.venv/bin/python" "$t/storyrepo/engine/vendor/get-pip.py" -q 2>/dev/null \
         && "$t/storyrepo/engine/.venv/bin/pip" install -q -e "$t/storyrepo/engine" 2>/dev/null; then
        echo "   ↳ engine venv: ✔"
      else
        echo "   ↳ engine venv: ✘(手动: cd $t/storyrepo/engine && python3 -m venv --without-pip .venv && .venv/bin/python vendor/get-pip.py && .venv/bin/pip install -e .)"
      fi
    fi
  fi
  echo "✔ $t/storyrepo"
done

echo "----"
if [ "$WITH_ENGINE" = 0 ]; then
  echo "提示:未装引擎。任意 agent 里说「写小说」也能用(纯协议模式);
       要装引擎跑机检/追踪,加 --with-engine 重跑,或: pip install -e $HERE/engine"
else
  echo "引擎已随装;确认: storyrepo --help(如失败,检查对应 engine/.venv)"
fi