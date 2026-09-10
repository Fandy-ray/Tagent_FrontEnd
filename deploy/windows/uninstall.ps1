#Requires -Version 5.1
<#
.SYNOPSIS
    卸载 TAgent 的计划任务（Windows）。
.DESCRIPTION
    删掉 TAgent-Start 与 TAgent-Watchdog 两个任务，并停掉正在跑的服务。
    不碰代码、依赖、.env.runtime 密钥和笔记数据。

    注意顺序：必须先删看门狗再停服务，否则刚停下就被它拉回来了。
.PARAMETER KeepServices
    只删任务，让当前正在跑的服务继续跑到关机为止。
.PARAMETER KeepNotebook
    停服务时不停 OpenNotebook 容器。
#>
[CmdletBinding()]
param(
    [switch]$KeepServices,
    [switch]$KeepNotebook
)

$ErrorActionPreference = 'Stop'

$TaskPath  = '\TAgent\'
$TaskNames = @('TAgent-Watchdog', 'TAgent-Start')   # 看门狗排在前面，先删它
$Here      = $PSScriptRoot
$PackRoot  = Split-Path -Parent (Split-Path -Parent $Here)
$StopPs1   = Join-Path $PackRoot 'TAgent重写版\scripts\stop.ps1'

function Write-Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Write-Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Write-Warn2($m){ Write-Host "    $m" -ForegroundColor Yellow }

Write-Host 'TAgent 计划任务卸载脚本' -ForegroundColor White

Write-Step '删除计划任务'
if (-not (Get-Command Unregister-ScheduledTask -ErrorAction SilentlyContinue)) {
    Write-Warn2 '没有 ScheduledTasks 模块，跳过（可能本来就没装成任务）。'
} else {
    foreach ($name in $TaskNames) {
        $task = Get-ScheduledTask -TaskName $name -TaskPath $TaskPath -ErrorAction SilentlyContinue
        if ($null -eq $task) {
            Write-Warn2 "$name : 未安装，跳过"
            continue
        }
        try {
            Stop-ScheduledTask -TaskName $name -TaskPath $TaskPath -ErrorAction SilentlyContinue
            Unregister-ScheduledTask -TaskName $name -TaskPath $TaskPath -Confirm:$false
            Write-Ok "$name : 已删除"
        } catch {
            Write-Warn2 "$name : 删除失败（$($_.Exception.Message)）。权限不够的话用管理员身份重跑。"
        }
    }
}

if ($KeepServices) {
    Write-Step '按 -KeepServices 保留正在运行的服务'
    Write-Warn2 '服务仍在跑，但下次登录不会再自动启动。'
} else {
    Write-Step '停止服务'
    if (Test-Path $StopPs1) {
        $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $StopPs1)
        if ($KeepNotebook) { $args += '-KeepNotebook' }
        & powershell.exe @args
    } else {
        Write-Warn2 "找不到 $StopPs1，请手动结束 5001 / 5173 上的进程。"
    }
}

Write-Host "`n卸载完成。代码、依赖、.env.runtime 密钥、笔记数据都原样保留。" -ForegroundColor Green
Write-Host "想手动跑：双击交接包根目录的 start.bat`n"
