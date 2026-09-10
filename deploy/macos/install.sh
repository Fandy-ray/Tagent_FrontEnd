#!/usr/bin/env bash
# 把 TAgent 装成 launchd 服务（macOS），登录后自启、挂了自动拉起。
#
#   com.tagent.basic-agent   127.0.0.1:5001
#   com.tagent.frontend      127.0.0.1:5173
#   com.tagent.notebook      OpenNotebook 容器（可选，要 Docker）
#
# 装的是 LaunchAgent（~/Library/LaunchAgents），不是 LaunchDaemon：
#   * 不需要 sudo，不动系统目录；
#   * 以你自己的身份运行，文件属主不会变成 root；
#   * 代价是必须登录到桌面才会跑。做无人值守服务器见 README「常见问题」。
#
# 做的事：
#   1. 检查依赖（uv / node，可选 docker）
#   2. 跑 scripts/start.sh --prepare 装依赖、生成 .env.runtime（幂等，密钥不改写）
#   3. 占位符替换后写进 ~/Library/LaunchAgents/
#   4. launchctl bootstrap + kickstart，最后做一次健康检查
#
# 用法：
#   ./install.sh                  仅本机访问（127.0.0.1）
#   ./install.sh --lan            监听 0.0.0.0，供局域网访问
#   ./install.sh --no-notebook    不装 OpenNotebook job
#   ./install.sh --skip-prepare   跳过第 2 步（依赖已经装好了）
#   ./install.sh --dry-run        只打印会生成什么，不写任何文件
#
# 卸载：./uninstall.sh

set -uo pipefail

BIND_HOST='127.0.0.1'
WITH_NOTEBOOK=1
SKIP_PREPARE=0
DRY_RUN=0

while [ $# -gt 0 ]; do
    case "$1" in
        --lan)          BIND_HOST='0.0.0.0' ;;
        --no-notebook)  WITH_NOTEBOOK=0 ;;
        --skip-prepare) SKIP_PREPARE=1 ;;
        --dry-run)      DRY_RUN=1 ;;
        -h|--help)      sed -n '2,29p' "$0"; exit 0 ;;
        *) printf '未知参数: %s\n（--help 看用法）\n' "$1" >&2; exit 1 ;;
    esac
    shift
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACK_ROOT="$(cd "$HERE/../.." && pwd)"
AGENT_DIR="$HOME/Library/LaunchAgents"
# launchctl 的新接口要用 gui/<uid> 这种域名，bootstrap/bootout/kickstart 都认它
DOMAIN="gui/$(id -u)"
LABELS='com.tagent.basic-agent com.tagent.frontend'

step() { printf '\n==> %s\n' "$1"; }
ok()   { printf '    %s\n' "$1"; }
warn() { printf '    [!] %s\n' "$1"; }
die()  { printf '\n[错误] %s\n\n' "$1" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

for extra in /opt/homebrew/bin /usr/local/bin "$HOME/.local/bin"; do
    case ":$PATH:" in *":$extra:"*) ;; *) [ -d "$extra" ] && PATH="$PATH:$extra" ;; esac
done
export PATH

printf 'TAgent launchd 安装脚本\n'
printf '交接包目录: %s\n' "$PACK_ROOT"

# ---------------------------------------------------------------- 0. 检查
step '检查环境'
[ "$(uname -s)" = "Darwin" ] || die '本脚本只用于 macOS。Linux 请用 ../linux/install.sh。'
[ "$(id -u)" -ne 0 ] || die '不要用 sudo 跑这个脚本 —— LaunchAgent 装在你自己的 ~/Library 下，
       用 root 跑会把 job 装到 root 名下，且依赖目录属主会变成 root。'

for p in "$PACK_ROOT/TAgent重写版/scripts/start.sh" \
         "$PACK_ROOT/TAgent重写版/basic-agent/main.py" \
         "$PACK_ROOT/tagentnote/package.json"; do
    [ -e "$p" ] || die "找不到 ${p}。deploy/ 必须待在交接包根目录下，别单独拷出来。"
done
ok '交接包结构完整'

# macOS 10.15 起把「下载 / 桌面 / 文稿」列为隐私目录。
# 你在终端里点过「允许」，所以手动 ./start.command 能跑；
# LaunchAgent 不继承这个授权，chdir 和读文件会得到 EPERM，
# launchd 记成 last exit code 78 (EX_CONFIG)，KeepAlive 狂重启。
# 微信传来的 zip 还会打上 quarantine，后台执行脚本变成 exit 126。
if xattr -p com.apple.quarantine "$PACK_ROOT" >/dev/null 2>&1 \
    || xattr -p com.apple.quarantine "$PACK_ROOT/TAgent重写版" >/dev/null 2>&1; then
    warn '检测到隔离属性（微信/浏览器下载常见），正在清除…'
    xattr -cr "$PACK_ROOT" 2>/dev/null || true
fi
case "$PACK_ROOT" in
    "$HOME/Downloads"|"$HOME/Downloads"/*|"$HOME/Desktop"|"$HOME/Desktop"/*|"$HOME/Documents"|"$HOME/Documents"/*)
        die "交接包现在位于：
       ${PACK_ROOT}

       这个位置属于 macOS 隐私目录，后台服务（LaunchAgent）无权访问，
       装上去会立刻失败：basic-agent / 前端 last exit code = 78。

       请先把整个文件夹移到家目录（或任意非「下载/桌面/文稿」路径），再重跑安装：
         mv \"$PACK_ROOT\" \"$HOME/TAgent交接版\"
         cd \"$HOME/TAgent交接版/deploy/macos\" && ./install.sh

       Cursor 里把工作区也改到新路径。"
        ;;
esac

# plist 里 ProgramArguments 必须写绝对路径，launchd 不认 PATH 里的相对查找
NODE_BIN="$(command -v node || true)"
[ -n "$NODE_BIN" ] || die '未找到 node。装一个：brew install node@22'
NODE_DIR="$(dirname "$NODE_BIN")"
have uv || die '未找到 uv。装一个：brew install uv'
ok "node: $NODE_BIN"

DOCKER_BIN="$(command -v docker || true)"
if [ "$WITH_NOTEBOOK" = "1" ]; then
    if [ -z "$DOCKER_BIN" ]; then
        warn '未找到 docker，跳过 OpenNotebook job（答疑将只用本地教材 book1.md）。'
        WITH_NOTEBOOK=0
    else
        ok "docker: $DOCKER_BIN"
        LABELS="$LABELS com.tagent.notebook"
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
    bash "$PACK_ROOT/TAgent重写版/scripts/start.sh" --prepare \
        || die '依赖准备失败，上面有原因。修好再重跑本脚本。'
fi

# launchd 不会替你建目录：StandardOutPath 的父目录不存在时 job 直接起不来
mkdir -p "$PACK_ROOT/TAgent重写版/logs/runtime" || die '无法创建日志目录。'

# ---------------------------------------------------------------- 2. 生成 plist
step '生成 LaunchAgent'
mkdir -p "$AGENT_DIR" || die "无法创建 ${AGENT_DIR}。"

render_plist() {
    sed -e "s|@TAGENT_ROOT@|$PACK_ROOT|g" \
        -e "s|@BIND_HOST@|$BIND_HOST|g" \
        -e "s|@NODE_BIN@|$NODE_BIN|g" \
        -e "s|@NODE_DIR@|$NODE_DIR|g" \
        -e "s|@DOCKER_BIN@|$DOCKER_BIN|g" \
        "$HERE/$1.plist"
}

for label in $LABELS; do
    if [ "$DRY_RUN" = "1" ]; then
        printf '\n----- %s.plist -----\n' "$label"
        render_plist "$label"
        continue
    fi
    render_plist "$label" > "$AGENT_DIR/$label.plist" || die "写入 $AGENT_DIR/$label.plist 失败。"
    # 语法坏掉的 plist 会被 launchd 静默忽略，装之前先自己验一遍
    plutil -lint "$AGENT_DIR/$label.plist" >/dev/null \
        || die "$AGENT_DIR/$label.plist 不是合法 plist。"
    if grep -q '@[A-Z_]*@' "$AGENT_DIR/$label.plist"; then
        die "$label.plist 里还有没替换的占位符：$(grep -o '@[A-Z_]*@' "$AGENT_DIR/$label.plist" | sort -u | tr '\n' ' ')"
    fi
    ok "$AGENT_DIR/$label.plist"
done

if [ "$DRY_RUN" = "1" ]; then
    printf '\n--dry-run：以上内容没有写入磁盘。\n\n'
    exit 0
fi

# ---------------------------------------------------------------- 3. 加载
step '加载并启动'
# bootout 是异步的：进程还在退的时候立刻 bootstrap，launchd 会回
# "Bootstrap failed: 37: Operation already in progress"。所以卸完必须等它真的
# 从 launchd 里消失再装 —— 重复执行 install.sh 时这一步决定成败。
unload_and_wait() {
    local label="$1" waited=0
    launchctl print "$DOMAIN/$label" >/dev/null 2>&1 || return 0
    launchctl bootout "$DOMAIN/$label" >/dev/null 2>&1 || true
    while launchctl print "$DOMAIN/$label" >/dev/null 2>&1; do
        if [ "$waited" -ge 20 ]; then
            warn "$label : 卸载超时，仍在 launchd 里"
            return 1
        fi
        sleep 1
        waited=$((waited + 1))
    done
    return 0
}

for label in $LABELS; do
    unload_and_wait "$label"
    if err="$(launchctl bootstrap "$DOMAIN" "$AGENT_DIR/$label.plist" 2>&1)"; then
        ok "$label : 已加载"
    else
        warn "$label : bootstrap 失败（${err}），改用老接口 launchctl load"
        if launchctl load -w "$AGENT_DIR/$label.plist" 2>/dev/null; then
            ok "$label : 已加载（load）"
        else
            warn "$label : 加载失败。查原因：launchctl print ${DOMAIN}/${label}"
        fi
    fi
    # RunAtLoad 已经会拉起一次；kickstart 兜住"已加载但没在跑"的情况
    launchctl kickstart "$DOMAIN/$label" >/dev/null 2>&1 || true
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
check_url 'http://127.0.0.1:5001/health' 'basic-agent' 600 \
    || warn "看日志：tail -50 '$PACK_ROOT/TAgent重写版/logs/runtime/basic-agent.err.log'"
check_url 'http://127.0.0.1:5173/' '前端' 180 \
    || warn "看日志：tail -50 '$PACK_ROOT/TAgent重写版/logs/runtime/tagentnote.err.log'"
if [ "$WITH_NOTEBOOK" = "1" ]; then
    check_url 'http://localhost:5055/api/notebooks' 'OpenNotebook' 300 \
        || warn '首次拉镜像很慢，可稍后再看；也确认一下 Docker Desktop 已经在跑。'
fi

printf '\n安装完成。\n'
if [ "$BIND_HOST" = "0.0.0.0" ]; then
    printf '  浏览器访问:   http://%s:5173\n' "$(ipconfig getifaddr en0 2>/dev/null || echo '<本机IP>')"
else
    printf '  浏览器访问:   http://localhost:5173\n'
fi
printf '  查看状态:     launchctl print %s/com.tagent.basic-agent | head -20\n' "$DOMAIN"
printf '  实时日志:     tail -f "%s/TAgent重写版/logs/runtime/basic-agent.err.log"\n' "$PACK_ROOT"
printf '  重启单个:     launchctl kickstart -k %s/com.tagent.frontend\n' "$DOMAIN"
printf '  卸载:         %s/uninstall.sh\n\n' "$HERE"
if [ "$BIND_HOST" = "0.0.0.0" ]; then
    printf '注意：--lan 是明文 HTTP，只适合内网短期演示；首次可能弹「是否允许接受传入连接」，选允许。\n\n'
fi
printf '还没登记模型的话，先用自己的 DeepSeek Key 登记一个，否则答疑和出题都会失败：\n'
printf '  见交接包根目录 README.md 第 3 步。\n\n'
