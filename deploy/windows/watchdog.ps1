#Requires -Version 5.1
<#
.SYNOPSIS
    TAgent 看门狗：探一次健康，挂了就重新拉起（Windows）。
.DESCRIPTION
    由 TAgent-Watchdog 计划任务每几分钟调用一次。健康时立刻退出，什么都不做。

    Windows 没有 systemd 的 Restart=on-failure、也没有 launchd 的 KeepAlive，
    这个脚本就是那两者的替代品。判据是 HTTP 健康检查而不是"进程还在不在"：
    进程活着但端口不响应（比如卡死、或者 venv 被删了半个）同样算挂。

    重启前先跑 stop.ps1：半死不活的残留进程会占着 5001/5173，
    不清干净的话 start.ps1 会因为端口被占直接失败。
.PARAMETER Lan
    重启时让前端监听 0.0.0.0（要和 install.ps1 装的时候保持一致）。
.PARAMETER NoNotebook
    重启时不拉 OpenNotebook 容器。
.PARAMETER Force
    不做健康检查，直接重启一遍。
#>
[CmdletBinding()]
param(
    [switch]$Lan,
    [switch]$NoNotebook,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$Here     = $PSScriptRoot
$PackRoot = Split-Path -Parent (Split-Path -Parent $Here)
$ScriptDir = Join-Path $PackRoot 'TAgent重写版\scripts'
$LogDir   = Join-Path $PackRoot 'TAgent重写版\logs\runtime'
$LogFile  = Join-Path $LogDir 'watchdog.log'

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
}

function Write-Log($Message) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Message
    Write-Host $line
    try {
        # 日志超过 1 MB 就滚一次，别让它无限长下去：
        # 这个脚本每 5 分钟跑一次，一年下来行数很可观。
        if ((Test-Path $LogFile) -and ((Get-Item $LogFile).Length -gt 1MB)) {
            Move-Item $LogFile "$LogFile.1" -Force
        }
        Add-Content -Path $LogFile -Value $line -Encoding UTF8
    } catch {
        # 日志写不进去不该影响看门狗本身干活
    }
}

function Test-Endpoint($Url) {
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

$agentOk = Test-Endpoint 'http://127.0.0.1:5001/health'
$frontOk = Test-Endpoint 'http://127.0.0.1:5173/'

if ($agentOk -and $frontOk -and -not $Force) {
    # 正常情况下每次都走到这里。不写日志，否则一天 288 行全是"一切正常"。
    exit 0
}

if ($Force) {
    Write-Log '[watchdog] -Force：直接重启。'
} else {
    Write-Log ("[watchdog] 健康检查未通过（basic-agent={0} 前端={1}），准备重启。" -f $agentOk, $frontOk)
}

# 先停干净：残留进程占着端口的话 start.ps1 会直接失败退出。
try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $ScriptDir 'stop.ps1') -KeepNotebook 2>&1 | Out-Null
} catch {
    Write-Log "[watchdog] stop.ps1 出错（继续）：$($_.Exception.Message)"
}

$startArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass',
               '-File', (Join-Path $ScriptDir 'start.ps1'), '-SkipInstall')
if ($Lan)        { $startArgs += '-Lan' }
if ($NoNotebook) { $startArgs += '-SkipNotebook' }

try {
    & powershell.exe @startArgs 2>&1 | Out-Null
    $code = $LASTEXITCODE
} catch {
    Write-Log "[watchdog] start.ps1 抛异常：$($_.Exception.Message)"
    exit 1
}

if ($code -eq 0) {
    Write-Log '[watchdog] 已重新拉起。'
    exit 0
}

# 起不来时别把 -SkipInstall 的锅算在网络上：依赖可能真的坏了，
# 这里退一步做一次完整安装（uv sync / npm install 都是幂等的）。
Write-Log "[watchdog] start.ps1 退出码 $code，改用完整模式再试一次（会重查依赖）。"
$fullArgs = $startArgs | Where-Object { $_ -ne '-SkipInstall' }
& powershell.exe @fullArgs 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Log '[watchdog] 完整模式拉起成功。'
    exit 0
}
Write-Log "[watchdog] 仍然失败（退出码 $LASTEXITCODE）。看 basic-agent.err.log / tagentnote.err.log。"
exit 1
