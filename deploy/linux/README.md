# Linux 部署（systemd）

装完是三个 systemd 服务，开机自启、崩了自动拉起：

```text
tagent-basic-agent.service   127.0.0.1:5001   检索 / 答疑 / 出卷判卷
tagent-frontend.service      127.0.0.1:5173   前端（浏览器开这个）
tagent-notebook.service      8502 / 5055      OpenNotebook 容器（可选）
```

## 一、前置

```bash
# uv（会自动带 Python 3.12，不用预装 Python）
curl -LsSf https://astral.sh/uv/install.sh | sh

# Node.js 22 LTS（以 Debian/Ubuntu 为例）
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Docker（可选，只影响笔记本功能）
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER    # 加完要重新登录才生效
```

**先手动跑通一次**，确认这台机器没问题：

```bash
cd <交接包目录>
bash TAgent重写版/scripts/start.sh --no-open
# 浏览器能打开 http://localhost:5173 就说明没问题，然后停掉：
bash TAgent重写版/scripts/stop.sh
```

## 二、安装

```bash
cd <交接包目录>/deploy/linux
sudo ./install.sh
```

想让局域网也能访问（明文 HTTP，仅限内网演示）：

```bash
sudo ./install.sh --lan
```

| 参数 | 说明 |
|---|---|
| `--lan` | 监听 `0.0.0.0`，供局域网访问 |
| `--user <名字>` | 指定跑服务的用户，默认是调用 `sudo` 的那个人 |
| `--no-notebook` | 不装 OpenNotebook 单元 |
| `--skip-prepare` | 跳过依赖安装（确认装好了才用） |
| `--dry-run` | 只打印会生成的单元内容，不写任何文件 |

脚本做的事：检查环境 → 用目标用户跑 `start.sh --prepare` 装依赖生成密钥 →
把 `*.service` 里的占位符换成本机实际路径写进 `/etc/systemd/system/` →
`daemon-reload` + `enable` + `start` → 健康检查。可重复执行。

> **为什么不用 root 跑服务**：服务要写 `basic-agent/config/`、`text_db/`、
> `node_modules/.vite`。用 root 跑会把这些文件的属主变成 root，之后普通用户
> 再手动执行 `start.sh` 就会 Permission denied。所以 `install.sh` 默认用
> `$SUDO_USER` 的身份装依赖、也用它跑服务。

## 三、验证

```bash
systemctl status tagent-basic-agent tagent-frontend
curl http://127.0.0.1:5001/health        # {"status":"ok"}
curl http://127.0.0.1:5001/knowledge     # 看 source 和 notebook_reachable
curl -I http://127.0.0.1:5173/           # 200
```

## 四、日常运维

```bash
# 实时日志（systemd 走 journald，不落地成文件）
journalctl -u tagent-basic-agent -f
journalctl -u tagent-frontend -n 100 --no-pager

# 重启 / 停止
sudo systemctl restart tagent-basic-agent
sudo systemctl stop tagent-frontend tagent-basic-agent

# 开机自启开关
sudo systemctl disable tagent-frontend
sudo systemctl enable  tagent-frontend

# 改完 .service 文件后必须 reload
sudo systemctl daemon-reload && sudo systemctl restart tagent-basic-agent
```

崩溃重启策略：`Restart=on-failure`、间隔 5 秒，但 300 秒内连起 5 次仍失败就停下
等人处理（`StartLimitBurst`），不会无限重启刷日志。想手动解除：

```bash
sudo systemctl reset-failed tagent-basic-agent
sudo systemctl start tagent-basic-agent
```

## 五、卸载

```bash
sudo ./uninstall.sh                  # 停止 + 禁用 + 删除单元
sudo ./uninstall.sh --stop-only      # 只停，保留开机自启配置
sudo ./uninstall.sh --keep-notebook  # 容器继续跑
```

代码、依赖、密钥、笔记数据都不动。

## 六、常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `Failed to start ... status=203/EXEC` | `ExecStart` 的路径不对。多半是依赖没装（`.venv` 不存在），去掉 `--skip-prepare` 重装 |
| `status=1/FAILURE`，日志里 `Address already in use` | 5001/5173 被别的进程占着。`ss -ltnp \| grep -E '5001\|5173'` 看是谁 |
| 服务起来了但页面 502 | 后端没就绪。`journalctl -u tagent-basic-agent -n 50`；首次要下嵌入模型，慢是正常的 |
| `notebook_reachable` 一直 false | 8502 是页面端口、5055 才是接口。确认容器起来了：`docker compose -f ../../opennotebook/docker-compose.yml ps` |
| 改了 `.env.runtime` 不生效 | 单元里的 `Environment=BASIC_AGENT_PORT=5001` 优先级更高（python-dotenv 不覆盖已存在的环境变量），这是故意的 |
| 局域网访问不了 | 除了 `--lan`，还要放行防火墙：`sudo ufw allow 5173/tcp` |
| 机器重启后容器没回来 | `sudo systemctl enable docker`，容器自身的 `restart: always` 才有意义 |

## 七、单元文件说明

`*.service` 是模板，里面的 `@TAGENT_ROOT@` 等占位符由 `install.sh` 替换。
想手工装也行：把占位符换成实际值，复制进 `/etc/systemd/system/`，再 `daemon-reload`。

| 占位符 | 含义 |
|---|---|
| `@TAGENT_ROOT@` | 交接包根目录绝对路径 |
| `@RUN_USER@` / `@RUN_GROUP@` | 跑服务的用户 / 组 |
| `@BIND_HOST@` | `127.0.0.1` 或 `0.0.0.0` |
| `@NODE_BIN@` / `@DOCKER_BIN@` | node / docker 的绝对路径（systemd 不认 PATH） |
