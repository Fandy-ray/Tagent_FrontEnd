#!/usr/bin/env bash
# 等 Docker 引擎就绪后拉起 OpenNotebook 容器。
#
# 单独成一个脚本而不是塞进 plist 的 <string>：shell 里的 2>&1、&& 在 XML 里
# 都要转义（&amp;），写在 plist 里既难读又容易写错（plutil 只会告诉你
# "unknown ampersand-escape sequence"，不会说是哪个 &）。
#
# 用法：notebook-up.sh <docker 可执行路径> <docker-compose.yml 路径>
# 由 com.tagent.notebook.plist 调用，也可以手动跑。

set -uo pipefail

DOCKER_BIN="${1:?用法: notebook-up.sh <docker路径> <compose文件路径>}"
COMPOSE_FILE="${2:?用法: notebook-up.sh <docker路径> <compose文件路径>}"

# 登录后 launchd 起得比 Docker Desktop 快，直接 compose up 必然失败。
# 最多等 5 分钟。探测用 `version --format {{.Server.Version}}` 而不是
# `docker info`：Docker 29 即使连不上引擎，info 照样打印客户端信息并退出码 0。
i=0
until "$DOCKER_BIN" version --format '{{.Server.Version}}' >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -ge 60 ]; then
        echo "[notebook-up] 等了 5 分钟 Docker 引擎仍不可用，放弃本轮（launchd 会稍后重试）。" >&2
        exit 1
    fi
    sleep 5
done

echo "[notebook-up] Docker 就绪，拉起 OpenNotebook..."
# 只起这两个：aliyun-tts-bridge 要 DashScope Key 且要现场 build，默认不带。
exec "$DOCKER_BIN" compose -f "$COMPOSE_FILE" up -d surrealdb open_notebook
