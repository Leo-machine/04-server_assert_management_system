#!/bin/bash
# 一次性注册：让后端服务开机自启 + 崩溃自动拉起（launchd 用户代理）
# 只需双击运行一次。之后即使重启电脑，后端也会自动运行。
set -e
PLIST="$HOME/Library/LaunchAgents/com.parts.backend.plist"

if launchctl print "gui/$(id -u)/com.parts.backend" >/dev/null 2>&1; then
  echo "已注册过，重新加载..."
  launchctl kickstart -k "gui/$(id -u)/com.parts.backend"
else
  launchctl bootstrap "gui/$(id -u)" "$PLIST"
fi

sleep 2
echo "==> 健康检查："
curl -s -m 3 http://127.0.0.1:8000/api/health && echo "  后端已常驻运行 ✅" || {
  echo "注册失败，请把本窗口信息截图反馈"; exit 1;
}
echo ""
echo "完成。以后后端会：开机自动启动 / 崩溃自动重启 / 改代码自动热加载。"
echo "如需卸载自启：launchctl bootout gui/\$(id -u) $PLIST"
