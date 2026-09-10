#!/usr/bin/env bash
# 把 TAgent 装成 systemd 服务（Linux），开机自启、挂了自动拉起。
#
#   tagent-basic-agent.service   127.0.0.1:5001
#   tagent-frontend.service      127.0.0.1:5173
#   tagent-notebook.service      OpenNotebook 容器（可选，要 Docker）
#
# 做的事：
#   1. 检查依赖（systemd / uv / node，可选 docker）
#   2. 跑 scripts/start.sh --prepare 装依赖、生成 .env.runtime（幂等，密钥不会被改写）
#   3. 把 *.service 里的占位符替换成本机实际路径，装到 /etc/systemd/system/
#   4. daemon-reload + enable + start，最后做一次健康检查
#
# 用法（需要 root 写 /etc/systemd/system）：
#   sudo ./install.sh                     仅本机访问（127.0.0.1）
#   sudo ./install.sh --lan               监听 0.0.0.0，供局域网访问
#   sudo ./install.sh --user tagent       指定跑服务的用户（默认调用 sudo 的那个人）
#   sudo ./install.sh --no-notebook       不装 OpenNotebook 单元
#   sudo ./install.sh --skip-prepare      跳过第 2 步（依赖已经装好了）
#   sudo ./install.sh --dry-run           只打印会生成什么，不写任何文件
#
# 卸载：sudo ./uninstall.sh

set -uo pipefail

BIND_HOST='127.0.0.1'
RUN_USER=''
WITH_NOTEBOOK=1
SKIP_PREPARE=0
DRY_RUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --lan)          BIND_HOST='0.0.0.0' ;;
        --user)         shift; RUN_USER="${1:-}" ;;
        --no-notebook)  WITH_NOTEBOOK=0 ;;
        --skip-prepare) SKIP_PREPARE=1 ;;
        --dry-run)      DRY_RUN=1 ;;
        -h|--help)      sed -n '2,26p' "$0"; exit 0 ;;
        *) printf '未知参数: %s\n（--help 看用法）\n' "$1" >&2; exit 1 ;;
    esac
    shift
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# deploy/linux -> deploy -> 交接包根
PACK_ROOT="$(cd "$HERE/../.." && pwd)"
UNIT_DIR='/etc/systemd/system'

step() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    %s\n' "$1"; }
warn() { printf '    [!] %s\n' "$1"; }
die()  { printf '\n[错误] %s\n\n' "$1" >&2; exit 1; }

have() { command -v "$1" >/dev/null 2>&1; }

printf 'TAgent systemd 安装脚本\n'
printf '交接包目录: %s\n' "$PACK_ROOT"

# ---------------------------------------------------------------- 0. 检查
step '检查环境'

[ "$(uname -s)" = "Linux" ] || die "本脚本只用于 Linux。macOS 请用 ../macos/install.sh，Windows 用 ..\\windows\\install.ps1。"
have systemctl || die '没有 systemctl —— 这台机器不是 systemd 系统。请改用 scripts/start.sh 前台运行，或自行写 init 脚本。'

if [ "$DRY_RUN" = "0" ] && [ "$(id -u)" -ne 0 ]; then
    die "需要 root 才能写 ${UNIT_DIR}。请用：sudo $0 $*"
fi

# 默认用调用 sudo 的那个人跑服务，而不是 root —— 服务要写 basic-agent/config、
# node_modules/.vite 这些目录，用 root 跑会把文件属主搞成 root，之后普通用户
# 再手动跑 start.sh 就会 Permission denied。
if [ -z "$RUN_USER" ]; then
    RUN_USER="${SUDO_USER:-$(id -un)}"
fi
if [ "$RUN_USER" = "root" ]; then
    warn '将以 root 运行服务。建议改用普通用户：--user <用户名>'
fi
id "$RUN_USER" >/dev/null 2>&1 || die "用户 $RUN_USER 不存在。"
RUN_GROUP="$(id -gn "$RUN_USER")"
ok "运行用户: ${RUN_USER}:${RUN_GROUP}"

# 关键路径先确认存在，别等 systemd 起不来才发现装错了目录
for p in "$PACK_ROOT/TAgent重写版/scripts/start.sh" \
         "$PACK_ROOT/TAgent重写版/basic-agent/main.py" \
         "$PACK_ROOT/tagentnote/package.json"; do
    [ -e "$p" ] || die "找不到 ${p}。deploy/ 必须待在交接包根目录下，别单独拷出来。"
done
ok '交接包结构完整'

# systemd 单元里 ExecStart 必须写绝对路径，PATH 那一套在这里不生效
NODE_BIN="$(command -v node || true)"
[ -n "$NODE_BIN" ] || die '未找到 node。请先装 Node.js 18+（推荐 22 LTS）。'
have uv || die '未找到 uv。安装：curl -LsSf https://astral.sh/uv/install.sh | sh'
ok "node: $NODE_BIN"

DOCKER_BIN="$(command -v docker || true)"
if [ "$WITH_NOTEBOOK" = "1" ]; then
    if [ -z "$DOCKER_BIN" ]; then
        warn '未找到 docker，跳过 OpenNotebook 单元（答疑将只用本地教材 book1.md）。'
        WITH_NOTEBOOK=0
    elif ! docker compose version >/dev/null 2>&1; then
        warn 'docker 没有 compose 子命令（需要 Docker Compose v2），跳过 OpenNotebook 单元。'
        WITH_NOTEBOOK=0
    else
        ok "docker: $DOCKER_BIN"
    fi
fi

# ---------------------------------------------------------------- 1. 前置准备
if [ "$SKIP_PREPARE" = "1" ]; then
    step '跳过依赖准备（--skip-prepare）'
elif [ "$DRY_RUN" = "1" ]; then
    step '跳过依赖准备（--dry-run）'
else
    step '装依赖 / 生成 .env.runtime（复用 scripts/start.sh --prepare）'
    warn '首次会装 Python 与 Node 依赖，可能要几分钟。'
    # 必须用目标用户跑：root 跑出来的 .venv / node_modules 属主是 root，
    # 服务用普通用户启动时读得到但写不了，vite 缓存和向量库都会失败。
    if [ "$(id -un)" = "$RUN_USER" ]; then
        bash "$PACK_ROOT/TAgent重写版/scripts/start.sh" --prepare
    else
        sudo -u "$RUN_USER" -H bash "$PACK_ROOT/TAgent重写版/scripts/start.sh" --prepare
    fi
    [ $? -eq 0 ] || die '依赖准备失败，上面有原因。修好再重跑本脚本。'
fi

# 日志目录：systemd 的 ReadWritePaths 容忍缺失，但 basic-agent 自己会往这里写
install -d -o "$RUN_USER" -g "$RUN_GROUP" "$PACK_ROOT/TAgent重写版/logs/runtime" 2>/dev/null || true

# ---------------------------------------------------------------- 2. 生成单元
step '生成 systemd 单元'

UNITS='tagent-basic-agent.service tagent-frontend.service'
[ "$WITH_NOTEBOOK" = "1" ] && UNITS="$UNITS tagent-notebook.service"

render_unit() {
    # 占位符替换。路径里可能有中文和空格，但不会有 | ，所以用 | 当 sed 分隔符。
    sed -e "s|@TAGENT_ROOT@|$PACK_ROOT|g" \
        -e "s|@RUN_USER@|$RUN_USER|g" \
        -e "s|@RUN_GROUP@|$RUN_GROUP|g" \
        -e "s|@BIND_HOST@|$BIND_HOST|g" \
        -e "s|@NODE_BIN@|$NODE_BIN|g" \
        -e "s|@DOCKER_BIN@|$DOCKER_BIN|g" \
        "$HERE/$1"
}

for u in $UNITS; do
    if [ "$DRY_RUN" = "1" ]; then
        printf '\n----- %s -----\n' "$u"
        render_unit "$u"
        continue
    fi
    render_unit "$u" > "$UNIT_DIR/$u" || die "写入 $UNIT_DIR/$u 失败。"
    chmod 644 "$UNIT_DIR/$u"
    ok "$UNIT_DIR/$u"
done

if [ "$DRY_RUN" = "1" ]; then
    printf '\n--dry-run：以上内容没有写入磁盘。\n\n'
    exit 0
fi

# 替换完再自检一次：漏掉的占位符会让 systemd 起不来，且报错信息很难懂
for u in $UNITS; do
    if grep -q '@[A-Z_]*@' "$UNIT_DIR/$u"; then
        die "$UNIT_DIR/$u 里还有没替换的占位符：$(grep -o '@[A-Z_]*@' "$UNIT_DIR/$u" | sort -u | tr '\n' ' ')"
    fi
done

# ---------------------------------------------------------------- 3. 启用
step '启用并启动'
systemctl daemon-reload || die 'systemctl daemon-reload 失败。'

for u in $UNITS; do
    systemctl enable "$u" >/dev/null 2>&1 || warn "$u : enable 失败"
done
# 顺序：笔记本 -> 后端 -> 前端。前端起早了只是暂时 502，不致命。
for u in $UNITS; do
    systemctl restart "$u" || warn "$u : 启动失败，看 journalctl -u $u -n 50"
done

# ---------------------------------------------------------------- 4. 自检
step '健康检查'
check_url() {
    local url="$1" name="$2" timeout="$3" waited=0
    while [ "$waited" -lt "$timeout" ]; do
        if curl -fsS -m 5 -o /dev/null "$url" 2>/dev/null; then
            ok "$name 就绪（${url}）"
            return 0
        fi
        sleep 3
        waited=$((waited + 3))
    done
    warn "$name 在 ${timeout} 秒内没起来（${url}）"
    return 1
}
warn 'basic-agent 首次启动要加载嵌入模型并建向量索引，最长等 600 秒...'
check_url "http://127.0.0.1:5001/health"  'basic-agent' 600 || warn '看日志：journalctl -u tagent-basic-agent -n 80'
check_url "http://127.0.0.1:5173/"        '前端'         180 || warn '看日志：journalctl -u tagent-frontend -n 80'
if [ "$WITH_NOTEBOOK" = "1" ]; then
    check_url "http://localhost:5055/api/notebooks" 'OpenNotebook' 300 \
        || warn '看日志：journalctl -u tagent-notebook -n 50；首次拉镜像很慢，可稍后再看。'
fi

printf '\n安装完成。\n'
printf '  浏览器访问:   http://%s:5173\n' "$([ "$BIND_HOST" = "0.0.0.0" ] && hostname -I 2>/dev/null | awk '{print $1}' || echo localhost)"
printf '  查看状态:     systemctl status tagent-basic-agent tagent-frontend\n'
printf '  实时日志:     journalctl -u tagent-basic-agent -f\n'
printf '  停止/启动:    systemctl stop|start tagent-frontend tagent-basic-agent\n'
printf '  卸载:         sudo %s/uninstall.sh\n\n' "$HERE"
if [ "$BIND_HOST" = "0.0.0.0" ]; then
    printf '注意：--lan 是明文 HTTP，登录态与答疑内容都不加密，只适合内网短期演示。\n'
    printf '对外提供服务请在前面加 Nginx/Caddy 反代并配 HTTPS，同时放行防火墙 5173。\n\n'
fi
printf '还没登记模型的话，先用自己的 DeepSeek Key 登记一个，否则答疑和出题都会失败：\n'
printf '  见交接包根目录 README.md 第 3 步。\n\n'
