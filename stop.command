#!/usr/bin/env bash
# TAgent - 停止服务（macOS：在访达里双击本文件即可运行）。
#
# 停 basic-agent (5001)、tagentnote (5173)，以及启动脚本拉起的
# OpenNotebook 容器（笔记数据保留）。
# 只想停前后端、容器继续跑：./stop.command --keep-notebook
#
# 双击没反应？先 chmod +x stop.command，详见 start.command 里的说明。
#
# 放在交接包根目录或 TAgent重写版 目录里都能用。

HERE="$(cd "$(dirname "$0")" && pwd)"

SH=""
if [ -f "$HERE/scripts/stop.sh" ]; then
    SH="$HERE/scripts/stop.sh"
else
    for d in "$HERE"/*/; do
        if [ -f "$d/scripts/stop.sh" ]; then
            SH="$d/scripts/stop.sh"
            break
        fi
    done
fi

if [ -z "$SH" ]; then
    printf '[错误] 在 %s 下找不到 scripts/stop.sh。\n' "$HERE"
    printf '请把本文件放在交接包根目录，或放在 scripts 文件夹的上一级。\n\n'
    printf '按回车键关闭本窗口...'
    read -r _
    exit 1
fi

bash "$SH" "$@"
RC=$?

printf '\n按回车键关闭本窗口...'
read -r _
exit $RC
