#!/usr/bin/env bash
# TAgent - 一键启动（macOS：在访达里双击本文件即可运行）。
#
#   basic-agent   127.0.0.1:5001
#   tagentnote    127.0.0.1:5173   <- 浏览器开这个
#
# OpenNotebook（页面 8502 / 接口 5055）由本脚本用 Docker 一起拉起；
# Docker 没在跑时会说明原因并继续启动另外两个 —— 那种情况下答疑只用本地教材。
#
# 首次运行会装 Python 与 Node 依赖，比较慢，属正常。
#
# 双击没反应？多半是丢了可执行权限（从 Windows 打包的 zip 解压常会这样）。
# 在本文件所在目录开一个终端，跑一次：
#     chmod +x start.command stop.command
# 若提示「无法打开，因为它来自身份不明的开发者」：右键 -> 打开 -> 打开。
#
# 放在交接包根目录或 TAgent重写版 目录里都能用 —— 两个位置都会去找 scripts/start.sh。
# 命令行参数原样透传，例如：./start.command --lan --skip-notebook

HERE="$(cd "$(dirname "$0")" && pwd)"

SH=""
if [ -f "$HERE/scripts/start.sh" ]; then
    SH="$HERE/scripts/start.sh"
else
    for d in "$HERE"/*/; do
        if [ -f "$d/scripts/start.sh" ]; then
            SH="$d/scripts/start.sh"
            break
        fi
    done
fi

if [ -z "$SH" ]; then
    printf '[错误] 在 %s 下找不到 scripts/start.sh。\n' "$HERE"
    printf '请把本文件放在交接包根目录，或放在 scripts 文件夹的上一级。\n\n'
    printf '按回车键关闭本窗口...'
    read -r _
    exit 1
fi

# 用 bash 调用而不是直接执行：这样 .sh 丢了可执行权限也照样能跑。
bash "$SH" "$@"
RC=$?

printf '\n按回车键关闭本窗口...'
read -r _
exit $RC
