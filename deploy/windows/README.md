# Windows 部署（任务计划程序）

Windows 没有 systemd / launchd 那样现成的进程守护，又不想让交接包依赖 NSSM、
WinSW 这类第三方工具，所以用系统自带的**任务计划程序**，两个任务配合：

```text
\TAgent\TAgent-Start      登录时跑一次 scripts\start.ps1，把服务拉起来
\TAgent\TAgent-Watchdog   每 5 分钟探一次健康，挂了就重新拉起
```

看门狗就是这里的"崩溃自愈"：Linux 靠 `Restart=on-failure`、macOS 靠 `KeepAlive`，
Windows 靠它。健康时它立刻退出、不写日志，几乎不占资源。

判据是 **HTTP 健康检查**而不是"进程还在不在"——进程活着但端口不响应
（卡死、依赖被删掉一半）同样算挂，这种情况只看进程列表是发现不了的。

## 一、前置

```powershell
# uv（会自动带 Python 3.12，不用预装 Python）
python -m pip install uv

# Node.js 22 LTS：https://nodejs.org 下载安装包，或
winget install OpenJS.NodeJS.LTS
```

Docker Desktop 可选（只影响笔记本功能）。装不上、或报「未检测到虚拟化支持」，
见交接包根目录 `README.md` 第 1 步。

**先手动跑通一次**，确认这台机器没问题：双击 `start.bat`，浏览器能打开
<http://localhost:5173> 就行，然后双击 `stop.bat`。

## 二、安装

在交接包的 `deploy\windows` 目录里开 PowerShell：

```powershell
.\install.ps1
```

如果提示执行策略限制：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

| 参数 | 说明 |
|---|---|
| `-Lan` | 前端监听 `0.0.0.0`，供局域网访问（明文 HTTP，仅限内网演示） |
| `-NoWatchdog` | 只装开机自启，不装看门狗 |
| `-NoNotebook` | 启动时不拉 OpenNotebook 容器 |
| `-SkipPrepare` | 跳过依赖安装（确认装好了才用） |
| `-IntervalMinutes <N>` | 看门狗间隔，默认 5 分钟 |
| `-DryRun` | 只打印会注册什么，不真的注册 |

脚本做的事：检查环境 → 跑 `start.ps1 -Prepare` 装依赖生成密钥 → 注册两个任务
→ 立刻触发一次 → 健康检查。可重复执行（`Register-ScheduledTask -Force`）。

> **任务以当前用户身份、在登录会话里运行**，所以不需要保存密码。
> 要「不登录也运行」必须把账户密码交给任务计划程序保存，本脚本不做这件事
> —— 需要无人值守请见文末。

## 三、验证

```powershell
Get-ScheduledTask -TaskPath '\TAgent\' | Format-Table TaskName, State
Invoke-RestMethod http://127.0.0.1:5001/health      # status = ok
Invoke-RestMethod http://127.0.0.1:5001/knowledge   # 看 source / notebook_reachable
```

试一下看门狗（手动停掉服务，等一个间隔看它拉不拉得回来）：

```powershell
..\..\stop.bat
# 等 5 分钟，或者直接手动跑一次看门狗：
powershell -NoProfile -ExecutionPolicy Bypass -File .\watchdog.ps1
Invoke-RestMethod http://127.0.0.1:5001/health
```

## 四、日常运维

```powershell
$PACK = Resolve-Path ..\..

# 日志
Get-Content "$PACK\TAgent重写版\logs\runtime\basic-agent.err.log" -Tail 50 -Wait
Get-Content "$PACK\TAgent重写版\logs\runtime\watchdog.log" -Tail 30

# 手动触发一次启动
Start-ScheduledTask -TaskName 'TAgent-Start' -TaskPath '\TAgent\'

# 暂时关掉看门狗（比如要停服务做维护）
Disable-ScheduledTask -TaskName 'TAgent-Watchdog' -TaskPath '\TAgent\'
Enable-ScheduledTask  -TaskName 'TAgent-Watchdog' -TaskPath '\TAgent\'
```

> **想停服务时记得先关看门狗**，否则双击 `stop.bat` 停掉之后，5 分钟内它又会
> 把服务拉回来。彻底停请跑 `.\uninstall.ps1`。

看门狗日志超过 1 MB 会自动滚成 `watchdog.log.1`，不会无限长下去。

## 五、卸载

```powershell
.\uninstall.ps1                  # 删任务 + 停服务
.\uninstall.ps1 -KeepServices    # 只删任务，当前服务继续跑到关机
.\uninstall.ps1 -KeepNotebook    # 停服务时不停容器
```

删任务的顺序是**先看门狗后启动任务**，否则刚停下就被拉回来了。
代码、依赖、密钥、笔记数据都不动。

## 六、常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 注册任务报「拒绝访问」 | 用「以管理员身份运行」打开 PowerShell 再跑 |
| 任务状态是 Ready 但服务没起来 | 看 `logs\runtime\basic-agent.err.log`；也在任务计划程序里看「上次运行结果」 |
| 登录后要等很久才能用 | 首次启动要下嵌入模型、建向量索引，属正常；看门狗的 2 分钟延迟也是为了避开这段 |
| 停不掉服务，总被拉回来 | 看门狗还开着。先 `Disable-ScheduledTask -TaskName 'TAgent-Watchdog' -TaskPath '\TAgent\'` |
| 页面全 502 | basic-agent 没起来，或端口不是 5001（`vite.config.ts` 的代理写死了 5001） |
| `uv sync` 卡住超时 | `--frozen` 无视镜像设置，见根目录 README 的「国内网络」一节；`start.ps1` 会自动换镜像重试 |
| 想不登录也运行 | 两条路：① 在任务计划程序里把任务改成「不管用户是否登录都要运行」并输入密码；② 用 NSSM 把 `start.ps1` 包成真正的 Windows 服务。两者都要自己保管凭据，本脚本不代劳 |
| 没有 ScheduledTasks 模块（Win7） | 退路：把 `start.bat` 的快捷方式丢进「启动」文件夹（`Win+R` → `shell:startup`），没有看门狗 |

## 七、文件说明

| 文件 | 作用 |
|---|---|
| `install.ps1` | 注册两个计划任务，装之前先跑依赖准备 |
| `uninstall.ps1` | 删任务 + 停服务 |
| `watchdog.ps1` | 健康检查 + 自愈；由 `TAgent-Watchdog` 每 N 分钟调用，也可手动跑 |

`watchdog.ps1` 重启前会先跑 `stop.ps1`：半死不活的残留进程占着 5001/5173 的话，
`start.ps1` 会因为端口被占直接失败。若 `-SkipInstall` 模式仍起不来，它会退一步
做一次完整安装（`uv sync` / `npm install` 都是幂等的）再试。
