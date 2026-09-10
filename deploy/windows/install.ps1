#Requires -Version 5.1
<#
.SYNOPSIS
    把 TAgent 装成开机自启的计划任务（Windows）。
.DESCRIPTION
    Windows 没有 systemd / launchd 那样的现成进程守护，又不想让交接包依赖
    NSSM、WinSW 这类第三方工具，所以用系统自带的「任务计划程序」做两件事：

        TAgent-Start      登录时跑一次 scripts\start.ps1，把三个服务拉起来
        TAgent-Watchdog   每 5 分钟探一次健康，挂了就重新拉起

    Watchdog 就是这里的"健壮性"：systemd 有 Restart=on-failure、launchd 有
    KeepAlive，Windows 这边靠它补齐。健康时它什么都不做，几乎不耗资源。

    任务以当前用户身份、在登录会话里运行，所以不需要保存密码（保存密码才能
    「不登录也运行」，那要把明文凭据交给任务计划程序，本脚本不做这件事）。
    无人值守的服务器场景见 README.md 的「常见问题」。
.PARAMETER Lan
    前端监听 0.0.0.0，供局域网访问（默认仅本机 127.0.0.1）。
.PARAMETER NoWatchdog
    只装开机自启，不装 5 分钟一次的看门狗。
.PARAMETER NoNotebook
    启动时不拉 OpenNotebook 容器。
.PARAMETER SkipPrepare
    跳过依赖安装（uv sync / npm install），确认装好了才用。
.PARAMETER IntervalMinutes
    看门狗的检查间隔，默认 5 分钟。
.PARAMETER DryRun
    只打印会注册什么，不真的注册。
.EXAMPLE
    .\install.ps1
.EXAMPLE
    .\install.ps1 -Lan -IntervalMinutes 10
#>
[CmdletBinding()]
param(
    [switch]$Lan,
    [switch]$NoWatchdog,
    [switch]$NoNotebook,
    [switch]$SkipPrepare,
    [int]$IntervalMinutes = 5,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$TaskPath      = '\TAgent\'
$StartTaskName = 'TAgent-Start'
$WatchTaskName = 'TAgent-Watchdog'

# deploy\windows -> deploy -> 交接包根
$Here     = $PSScriptRoot
$PackRoot = Split-Path -Parent (Split-Path -Parent $Here)
$StartPs1 = Join-Path $PackRoot 'TAgent重写版\scripts\start.ps1'
$Watchdog = Join-Path $Here 'watchdog.ps1'
$LogDir   = Join-Path $PackRoot 'TAgent重写版\logs\runtime'

function Write-Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Write-Warn2($m){ Write-Host "    $m" -ForegroundColor Yellow }
function Stop-WithError($m) {
    Write-Host "`n[错误] $m`n" -ForegroundColor Red
    exit 1
}

Write-Host 'TAgent 计划任务安装脚本' -ForegroundColor White
Write-Host "交接包目录: $PackRoot"

# ---------------------------------------------------------------- 0. 检查
Write-Step '检查环境'

if (-not (Test-Path $StartPs1)) {
    Stop-WithError "找不到 $StartPs1。deploy\ 必须待在交接包根目录下，别单独拷出来。"
}
if (-not (Test-Path $Watchdog)) {
    Stop-WithError "找不到 $Watchdog。deploy\windows\ 的文件不全。"
}
Write-Ok '交接包结构完整'

# ScheduledTasks 模块是 Win8/2012 起随系统带的；老系统上只能用 schtasks.exe
if (-not (Get-Command Register-ScheduledTask -ErrorAction SilentlyContinue)) {
    Stop-WithError '这台机器没有 ScheduledTasks 模块（需要 Windows 8 / Server 2012 及以上）。
       退路：手动把 start.bat 的快捷方式放进「启动」文件夹
       （Win+R 输入 shell:startup）。'
}

foreach ($cmd in @('uv', 'node', 'npm')) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Stop-WithError "未找到 $cmd。先照交接包 README 的「环境要求」装好 uv 与 Node.js 22 LTS。"
    }
}
Write-Ok 'uv / node / npm 就绪'

# ---------------------------------------------------------------- 1. 前置准备
if ($SkipPrepare) {
    Write-Step '跳过依赖准备（-SkipPrepare）'
} elseif ($DryRun) {
    Write-Step '跳过依赖准备（-DryRun）'
} else {
    Write-Step '装依赖 / 生成 .env.runtime（复用 start.ps1 -Prepare）'
    Write-Warn2 '首次会装 Python 与 Node 依赖，可能要几分钟。'
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $StartPs1 -Prepare
    if ($LASTEXITCODE -ne 0) {
        Stop-WithError '依赖准备失败，上面有原因。修好再重跑本脚本。'
    }
}

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

# ---------------------------------------------------------------- 2. 注册任务
Write-Step '注册计划任务'

# 启动参数：装成服务时不该再自动开浏览器，也不必每次都查依赖
$startArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$StartPs1`"")
if ($Lan)        { $startArgs += '-Lan' }
if ($NoNotebook) { $startArgs += '-SkipNotebook' }

$watchArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$Watchdog`"")
if ($Lan)        { $watchArgs += '-Lan' }
if ($NoNotebook) { $watchArgs += '-NoNotebook' }

if ($DryRun) {
    Write-Host "`n----- $StartTaskName -----"
    Write-Host "  触发: 登录时"
    Write-Host "  执行: powershell.exe $($startArgs -join ' ')"
    if (-not $NoWatchdog) {
        Write-Host "`n----- $WatchTaskName -----"
        Write-Host "  触发: 登录时起，每 $IntervalMinutes 分钟一次"
        Write-Host "  执行: powershell.exe $($watchArgs -join ' ')"
    }
    Write-Host "`n-DryRun：没有注册任何任务。`n"
    exit 0
}

# 以当前用户身份、只在登录会话里跑：这样不用保存密码。
# RunLevel Limited = 不提权；服务本身不需要管理员权限。
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

# MultipleInstances IgnoreNew 很关键：看门狗上一轮还在重启服务时，
# 下一轮不该并发再来一遍，否则两个 start.ps1 会互相抢 5001 端口。
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

function Register-TagentTask {
    param([string]$Name, [string[]]$Arguments, $Trigger, [string]$Description)

    $action = New-ScheduledTaskAction -Execute 'powershell.exe' `
        -Argument ($Arguments -join ' ') -WorkingDirectory $PackRoot
    try {
        Register-ScheduledTask -TaskName $Name -TaskPath $TaskPath `
            -Action $action -Trigger $Trigger -Principal $principal `
            -Settings $settings -Description $Description -Force | Out-Null
        Write-Ok "$TaskPath$Name : 已注册"
    } catch {
        Stop-WithError "注册 $Name 失败：$($_.Exception.Message)
       多半是权限不够 —— 用「以管理员身份运行」打开 PowerShell 再跑一次。"
    }
}

Register-TagentTask -Name $StartTaskName -Arguments $startArgs `
    -Trigger (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME") `
    -Description 'TAgent: 登录时启动 basic-agent(5001) 与前端(5173)'

if ($NoWatchdog) {
    Write-Warn2 '按 -NoWatchdog 跳过看门狗：服务崩了不会自动恢复。'
} else {
    # 登录后 2 分钟开始，之后每 N 分钟一次。RepetitionDuration 给一个足够长的
    # 时间跨度当"永远"——某些 PowerShell 版本上 [TimeSpan]::MaxValue 会报错。
    $watchTrigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
    $watchTrigger.Delay = 'PT2M'
    $watchTrigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) `
        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
        -RepetitionDuration (New-TimeSpan -Days 3650)).Repetition

    Register-TagentTask -Name $WatchTaskName -Arguments $watchArgs -Trigger $watchTrigger `
        -Description "TAgent: 每 $IntervalMinutes 分钟探一次健康，挂了自动拉起"
}

# ---------------------------------------------------------------- 3. 立即启动
Write-Step '立即启动一次'
try {
    Start-ScheduledTask -TaskName $StartTaskName -TaskPath $TaskPath
    Write-Ok '已触发 TAgent-Start（后台运行，首次要装模型可能要几分钟）'
} catch {
    Write-Warn2 "触发失败：$($_.Exception.Message)"
}

# ---------------------------------------------------------------- 4. 自检
Write-Step '健康检查'
function Wait-Url($Url, $Name, $TimeoutSec) {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) { Write-Ok "$Name 就绪（$Url）"; return $true }
        } catch { }
        Start-Sleep -Seconds 3
    }
    Write-Warn2 "$Name 在 $TimeoutSec 秒内没起来（$Url）"
    return $false
}
Write-Warn2 'basic-agent 首次启动要加载嵌入模型并建向量索引，最长等 600 秒...'
if (-not (Wait-Url 'http://127.0.0.1:5001/health' 'basic-agent' 600)) {
    Write-Warn2 "看日志：$LogDir\basic-agent.err.log"
}
if (-not (Wait-Url 'http://127.0.0.1:5173/' '前端' 180)) {
    Write-Warn2 "看日志：$LogDir\tagentnote.err.log"
}

Write-Host "`n安装完成。" -ForegroundColor Green
Write-Host "  浏览器访问:   http://localhost:5173"
Write-Host "  查看任务:     Get-ScheduledTask -TaskPath '$TaskPath'"
Write-Host "  看门狗日志:   $LogDir\watchdog.log"
Write-Host "  运行日志:     $LogDir\"
Write-Host "  手动停止:     stop.bat（看门狗会在 $IntervalMinutes 分钟内把它拉回来，"
Write-Host "                要彻底停请先跑 .\uninstall.ps1）"
Write-Host "  卸载:         .\uninstall.ps1`n"
Write-Host '还没登记模型的话，先用自己的 DeepSeek Key 登记一个，否则答疑和出题都会失败：' -ForegroundColor Yellow
Write-Host '  见交接包根目录 README.md 第 3 步。' -ForegroundColor Yellow
