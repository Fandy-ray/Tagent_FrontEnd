#!/usr/bin/env bash
# 卸载 TAgent 的 launchd 服务（macOS）。
#
# 只动 ~/Library/LaunchAgents 下这三个 job，不碰代码、依赖、密钥和笔记数据。
#
#   ./uninstall.sh                  停止 + 卸载 + 删除 plist
#   ./uninstall.sh --keep-notebook  OpenNotebook job 保留
#   ./uninstall.sh --stop-only      只停不删（保留登录自启配置）

set -uo pipefail

KEEP_NOTEBOOK=0
STOP_ONLY=0
while [ $# -gt 0 ]; do
    case "$1" in
        --keep-notebook) KEEP_NOTEBOOK=1 ;;
        --stop-only)     STOP_ONLY=1 ;;
        -h|--help)       sed -n '2,10p' "$0"; exit 0 ;;
        *) printf '未知参数: %s\n' "$1" >&2; exit 1 ;;
    esac
    shift
done

AGENT_DIR="$HOME/Library/LaunchAgents"
DOMAIN="gui/$(id -u)"

step() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    %s\n' "$1"; }
warn() { printf '    [!] %s\n' "$1"; }

[ "$(uname -s)" = "Darwin" ] || { printf '\n[错误] 本脚本只用于 macOS。\n\n' >&2; exit 1; }

# 先停前端再停后端，最后停笔记本
LABELS='com.tagent.frontend com.tagent.basic-agent'
[ "$KEEP_NOTEBOOK" = "0" ] && LABELS="$LABELS com.tagent.notebook"

step '停止并卸载 job'
for label in $LABELS; do
    if launchctl print "$DOMAIN/$label" >/dev/null 2>&1; then
        # bootout 会先 SIGTERM 再 SIGKILL，KeepAlive 也不会把它拉回来
        launchctl bootout "$DOMAIN/$label" >/dev/null 2>&1 \
            || warn "$label : bootout 失败，试 launchctl unload"
        [ -f "$AGENT_DIR/$label.plist" ] && launchctl unload -w "$AGENT_DIR/$label.plist" >/dev/null 2>&1
        # bootout 是异步的：确认真的退干净了再说"已卸载"，否则紧接着重装会失败
        waited=0
        while launchctl print "$DOMAIN/$label" >/dev/null 2>&1 && [ "$waited" -lt 20 ]; do
            sleep 1
            waited=$((waited + 1))
        done
        if launchctl print "$DOMAIN/$label" >/dev/null 2>&1; then
            warn "$label : 仍在 launchd 里，可手动 launchctl bootout ${DOMAIN}/${label}"
        else
            ok "$label : 已卸载"
        fi
    else
        warn "$label : 未加载，跳过"
    fi
done

if [ "$STOP_ONLY" = "1" ]; then
    printf '\n--stop-only：plist 保留，下次登录仍会自启。要彻底卸载请去掉该参数重跑。\n\n'
    exit 0
fi

step '删除 plist'
for label in $LABELS; do
    if [ -f "$AGENT_DIR/$label.plist" ]; then
        rm -f "$AGENT_DIR/$label.plist" && ok "已删除 $AGENT_DIR/$label.plist"
    fi
done

step '检查端口'
for p in 5001 5173; do
    if lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
        warn "端口 $p 仍被占用（可能是手动跑的 start.command）。本脚本不结束未确认的进程："
        warn "    lsof -nP -iTCP:$p -sTCP:LISTEN"
    else
        ok "端口 $p 已释放"
    fi
done

printf '\n卸载完成。代码、依赖、.env.runtime 密钥、笔记数据都原样保留。\n'
if [ "$KEEP_NOTEBOOK" = "0" ]; then
    printf 'OpenNotebook 容器没有被停（compose 里 restart: always 会让它一直在）。\n'
    printf '要停容器：docker compose -f <交接包>/opennotebook/docker-compose.yml stop\n'
fi
printf '想手动跑：双击 start.command，或 bash TAgent重写版/scripts/start.sh\n\n'
