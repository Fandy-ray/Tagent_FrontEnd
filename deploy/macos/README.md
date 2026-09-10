# macOS 部署（launchd）

装完是三个 launchd job，**登录后自启、崩了自动拉起**：

```text
com.tagent.basic-agent   127.0.0.1:5001   检索 / 答疑 / 出卷判卷
com.tagent.frontend      127.0.0.1:5173   前端（浏览器开这个）
com.tagent.notebook      8502 / 5055      OpenNotebook 容器（可选）
```

装的是 **LaunchAgent**（`~/Library/LaunchAgents`），不是 LaunchDaemon：不需要
`sudo`、不动系统目录、以你自己的身份运行；代价是**必须登录到桌面才会跑**。
无人值守的场景见文末「常见问题」。

`install.sh` 打出 basic-agent / 前端都「就绪」就可以关终端了。服务在后台跑，
不依赖那个窗口。笔记本页（8502）是另一件事，见下面「OpenNotebook」。

## 一、前置

```bash
brew install uv node          # 没有 Homebrew 见 https://brew.sh
# 不要只装 node@22：Homebrew 里它默认不链到 PATH，install.sh 会报「未找到 node」。
# uv 也可以：curl -LsSf https://astral.sh/uv/install.sh | sh
```

Node 需要 **20.19+ / 22.13+ / 24+**（Vite 8 的 `engine-strict`）。`node -v` 看一下。

Docker **可选**，只影响笔记本页。没有它，答疑仍用本地教材 `book1.md`。
有 Docker Desktop 也要等菜单栏鲸鱼图标停住：`docker` 命令在、引擎没起来，
`docker.sock` 照样不存在。Apple 芯片选 Apple Silicon 版；OrbStack / colima 也行。

**交接包不能放在「下载 / 桌面 / 文稿」。** 终端里你点过「允许」，手动
`./start.command` 能跑；LaunchAgent 不继承这个授权，chdir 直接 `EPERM`，
装完 `last exit code = 78`，看起来装上了其实一秒一崩。微信传来的 zip 尤其容易
落在「下载」里，先搬走：

```bash
mv ~/Downloads/TAgent交接版 ~/TAgent交接版
cd ~/TAgent交接版
chmod +x start.command stop.command deploy/macos/*.sh
```

**不要加 `--skip-prepare`。** 交接包里的 `.venv` 常常是别人机器上的符号链接
（指向 `/Users/别人/.local/share/uv/...`），在你电脑上是坏的。让 `install.sh`
自己跑 `uv sync`。

**先手动跑通一次**，确认这台机器没问题：

```bash
cd ~/TAgent交接版          # 或你搬家后的目录
./start.command --no-open
# 浏览器能打开 http://localhost:5173 就说明没问题，然后停掉：
./stop.command
```

前端若秒退、日志里是 `Cannot find native binding`：不是 npm 没装全，是微信隔离
属性拦住了 Vite 的 `.node` 文件。`start.sh` 会尝试 `xattr -cr`；仍不行就：

```bash
xattr -cr tagentnote/node_modules
# 还不行再：rm -rf tagentnote/node_modules && npm --prefix tagentnote install
```

## 二、安装

```bash
cd ~/TAgent交接版/deploy/macos
./install.sh
```

**不要加 `sudo`** —— 加了会把 job 装到 root 名下，依赖目录的属主也会变成 root。

| 参数 | 说明 |
|---|---|
| `--lan` | 监听 `0.0.0.0`，供局域网访问（明文 HTTP，仅限内网演示） |
| `--no-notebook` | 不装 OpenNotebook job（没有 Docker、或不需要笔记本页时用） |
| `--skip-prepare` | 跳过依赖安装（确认**这台机器上**已经 `uv sync` 过才用） |
| `--dry-run` | 只打印会生成的 plist，不写任何文件 |

脚本做的事：检查环境（在「下载」里会直接拒绝）→ 清隔离属性 → 跑
`start.sh --prepare` 装依赖生成密钥 → 占位符替换后写进 `~/Library/LaunchAgents/`
→ `plutil -lint` → `launchctl bootstrap` → 健康检查。可重复执行。

看到这两行就说明 TAgent 本体重好了，**可以关终端**：

```text
    basic-agent 就绪（http://127.0.0.1:5001/health）
    前端 就绪（http://127.0.0.1:5173/）
```

OpenNotebook 那一行超时不要紧：Docker 没起来时脚本只会警告，前后端照样在跑。
不要再双击 `start.command`，会和后台服务抢 5001 / 5173。

## 三、验证

```bash
launchctl print gui/$(id -u)/com.tagent.basic-agent | grep -E 'state|pid|runs'
curl http://127.0.0.1:5001/health        # {"status":"ok"}
curl http://127.0.0.1:5001/knowledge     # 看 source 和 notebook_reachable
curl -I http://127.0.0.1:5173/           # 200
```

试一下自动拉起（KeepAlive）：

```bash
kill -9 $(lsof -nP -iTCP:5001 -sTCP:LISTEN -t)
sleep 15 && curl http://127.0.0.1:5001/health    # 应该又活了
```

## 四、登记模型（必做）

没登记的话前端顶栏是「选择模型」，答疑和出题都会失败。用**自己的** DeepSeek
Key，不要用别人的。完整说明见交接包根目录 `README.md` 第 3 步。

```bash
cd ~/TAgent交接版
TOKEN=$(grep '^AGENT_ADMIN_TOKEN=' TAgent重写版/.env.runtime | cut -d= -f2-)
curl -X POST http://127.0.0.1:5001/admin/model-providers \
  -H "X-Agent-Admin-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"DeepSeek","served_model_id":"deepseek",
       "base_url":"https://api.deepseek.com","upstream_model":"deepseek-chat",
       "auth_mode":"bearer","api_key":"你自己的-sk-xxx","temperature":0.1}'
```

然后刷新 http://localhost:5173 。Key 明文写在
`TAgent重写版/basic-agent/config/model_providers.json`，不要外传。

## 五、OpenNotebook（可选）

前端笔记本页用 iframe 嵌 `http://localhost:8502/notebooks`。没起容器时会显示
「未检测到 OpenNoteBook」，**前后端健康检查通过也一样**——那不是部署失败。

1. 打开 Docker Desktop，等到鲸鱼图标停住。
2. 确认引擎真的在：`docker version --format '{{.Server.Version}}'` 能打出版本号。
   只有客户端、报 `docker.sock` 不存在，等于引擎没起来（常见：界面闪退、
   `opening tray: starting electron: unexpected EOF`）。这是 Docker Desktop
   自己的问题，重装 Apple Silicon 版通常比反复 `docker desktop start` 有效。
3. 后台 job 会等最多 5 分钟再 `compose up`；也可以马上手动拉：

```bash
docker compose -f ~/TAgent交接版/opennotebook/docker-compose.yml up -d surrealdb open_notebook
```

4. 刷新 TAgent 笔记本页，或直接打开 http://localhost:8502/notebooks 。

让笔记本复用刚登记的 DeepSeek：在 8502 里 Models → OpenAI Compatible，
Base URL 填 `http://host.docker.internal:5001/v1/raw`（必须是 `/v1/raw`，
不能 `/v1`），Model 填 `deepseek`。详见根目录 README 第 4 步。

## 六、日常运维

```bash
PACK=~/TAgent交接版

# 日志（launchd 不像 journald 有统一日志，落地成文件）
tail -f "$PACK/TAgent重写版/logs/runtime/basic-agent.err.log"
tail -f "$PACK/TAgent重写版/logs/runtime/tagentnote.err.log"
tail -f "$PACK/TAgent重写版/logs/runtime/notebook.err.log"

# 重启单个服务
launchctl kickstart -k gui/$(id -u)/com.tagent.frontend

# 临时停一个（下次登录还会起）
launchctl bootout gui/$(id -u)/com.tagent.frontend

# 再装回来
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.tagent.frontend.plist
```

崩溃重启策略：`KeepAlive.SuccessfulExit=false` —— **非正常退出**才拉起，
正常退出（`launchctl bootout`、手动停）不管；`ThrottleInterval=10` 保证
起不来时最快也是 10 秒一次，不会疯狂刷日志。

## 七、卸载

```bash
cd ~/TAgent交接版/deploy/macos
./uninstall.sh                  # 停止 + 卸载 + 删 plist
./uninstall.sh --stop-only      # 只停，保留登录自启配置
./uninstall.sh --keep-notebook  # 笔记本 job 保留
```

代码、依赖、密钥、笔记数据都不动。OpenNotebook 的**容器**不会被停
（compose 里 `restart: always`），要停容器：

```bash
docker compose -f ~/TAgent交接版/opennotebook/docker-compose.yml stop
```

## 八、常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `bootstrap failed: 5: Input/output error` | plist 有问题或路径不存在。`plutil -lint ~/Library/LaunchAgents/com.tagent.*.plist` |
| `Bootstrap failed: 37: Operation already in progress` | 上一次 bootout 还没退干净。等几秒重试；`install.sh` 已经自己处理了这个竞态 |
| job 装上了但没跑 | `launchctl print gui/$(id -u)/com.tagent.basic-agent` 看 `last exit code`。日志目录不存在是最常见原因（launchd 不会替你建目录） |
| `last exit code = 78` / 健康检查 600 秒超时 | 交接包在「下载 / 桌面 / 文稿」里。移到 `~/TAgent交接版` 后重新 `./install.sh`（脚本现在会直接拒绝装在隐私目录） |
| 笔记本 job `exit 126` / `Operation not permitted` | 同上，或微信隔离属性。`install.sh` 会 `xattr -cr`；仍不行就移出「下载」 |
| 前端秒退，`Cannot find native binding` | 微信隔离拦住了 rolldown 的 `.node`。`xattr -cr tagentnote/node_modules` |
| basic-agent 日志里 python 指向 `/Users/别人/` | 交接包拷来的 `.venv` 不能用。去掉 `--skip-prepare` 重装 |
| 端口 5001 被 `ControlCenter` 占 | 「隔空播放接收器」：系统设置 → 通用 → 隔空播放与接力，关掉 |
| 弹「是否允许接受传入连接」 | 用了 `--lan` 时会弹，选「允许」 |
| 重启电脑后没起来 | LaunchAgent 要**登录**才跑。开了自动登录的话就没问题 |
| 页面「未检测到 OpenNoteBook」 | 8502 没起来。`docker version --format '{{.Server.Version}}'` 打不出版本 = 引擎没好。前后端可以照常用 |
| `docker.sock: no such file` | Docker Desktop 没起来或界面崩了。修 Docker，不是重装 TAgent。国内访问 docker.com 超时只影响拉镜像/更新 |
| 笔记本 job 一直重启 | Docker 没起来。`notebook-up.sh` 最多等 5 分钟，超时后 launchd 隔 30 秒再试 |
| 想停服务却被拉回来 | 不要只用 `stop.command`（下次登录 launchd 还会起）。彻底停：`./uninstall.sh` |
| 想不登录也跑 | 要改成 LaunchDaemon（`/Library/LaunchDaemons`，需要 sudo，且要在 plist 里指定 `UserName`）。但 Docker Desktop 本身也要登录才起，笔记本功能仍然用不了 —— 真要无人值守建议上 Linux |

## 九、plist 说明

`*.plist` 是模板，占位符由 `install.sh` 替换：

| 占位符 | 含义 |
|---|---|
| `@TAGENT_ROOT@` | 交接包根目录绝对路径 |
| `@BIND_HOST@` | `127.0.0.1` 或 `0.0.0.0` |
| `@NODE_BIN@` / `@NODE_DIR@` | node 的绝对路径 / 所在目录（launchd 的 PATH 很干净，找不到 nvm、Homebrew 里的 node） |
| `@DOCKER_BIN@` | docker 的绝对路径 |

密钥**不写进 plist**（plist 是明文且会被 Time Machine 备份）——
`main.py` 自己会用 python-dotenv 读 `.env.runtime`。plist 里只钉死监听地址和端口。

`notebook-up.sh` 是给笔记本 job 用的小包装：登录后 launchd 起得比 Docker Desktop
快，它先等引擎就绪（最多 5 分钟）再 `compose up`。单独成一个脚本是因为 shell 里的
`2>&1`、`&&` 写进 plist 的 XML 要转义成 `&amp;`，既难读又容易写错。
