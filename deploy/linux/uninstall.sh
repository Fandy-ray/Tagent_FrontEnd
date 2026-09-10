#!/usr/bin/env bash
# 卸载 TAgent 的 systemd 服务。
#
# 只动 /etc/systemd/system 下这三个单元，不碰代码、依赖、密钥和笔记数据。
#
#   sudo ./uninstall.sh                停止 + 禁用 + 删除单元
#   sudo ./uninstall.sh --keep-notebook  OpenNotebook 容器继续跑
#   sudo ./uninstall.sh --stop-only    只停不删（保留开机自启配置）

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

UNIT_DIR='/etc/systemd/system'
step() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    %s\n' "$1"; }
warn() { printf '    [!] %s\n' "$1"; }

command -v systemctl >/dev/null 2>&1 || { printf '\n[错误] 没有 systemctl。\n\n' >&2; exit 1; }
[ "$(id -u)" -eq 0 ] || { printf '\n[错误] 需要 root：sudo %s\n\n' "$0" >&2; exit 1; }

# 先停前端再停后端：反过来的话前端会有一小段时间对着已死的后端刷 502 日志
UNITS='tagent-frontend.service tagent-basic-agent.service'
[ "$KEEP_NOTEBOOK" = "0" ] && UNITS="$UNITS tagent-notebook.service"

step '停止服务'
for u in $UNITS; do
    if systemctl list-unit-files "$u" >/dev/null 2>&1 && [ -f "$UNIT_DIR/$u" ]; then
        systemctl stop "$u" >/dev/null 2>&1 && ok "$u : 已停止" || warn "$u : 停止失败"
    else
        warn "$u : 未安装，跳过"
    fi
done

if [ "$STOP_ONLY" = "1" ]; then
    printf '\n--stop-only：单元保留，开机仍会自启。要彻底卸载请去掉该参数重跑。\n\n'
    exit 0
fi

step '禁用并删除单元'
for u in $UNITS; do
    [ -f "$UNIT_DIR/$u" ] || continue
    systemctl disable "$u" >/dev/null 2>&1 || true
    rm -f "$UNIT_DIR/$u" && ok "已删除 $UNIT_DIR/$u"
done
systemctl daemon-reload
# 清掉已删除单元残留的失败计数等状态
systemctl reset-failed >/dev/null 2>&1 || true

printf '\n卸载完成。代码、依赖、.env.runtime 密钥、笔记数据都原样保留。\n'
printf '想手动跑：cd 交接包根目录 && bash TAgent重写版/scripts/start.sh\n\n'
