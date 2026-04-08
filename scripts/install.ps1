#Requires -Version 5.1
<#
.SYNOPSIS
    iLongRun Windows 安装脚本
.DESCRIPTION
    在 Windows 上安装 iLongRun 的本地命令、helpers 和配置文件。
    支持 PowerShell 5.1+ 和 PowerShell 7+。
.EXAMPLE
    .\scripts\install.ps1
    .\scripts\install.ps1 -Agent claude
    .\scripts\install.ps1 -Agent all -Verbose
#>

param(
    [string]$Agent = "auto",
    [string]$ILongRunHome = "",
    [string]$ClaudeDir = "",
    [switch]$SkipDoctor
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT_DIR = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ILONGRUN_HOME = if ($ILongRunHome) { $ILongRunHome } elseif ($env:ILONGRUN_HOME) { $env:ILONGRUN_HOME } else { Join-Path $HOME ".copilot-ilongrun" }
$COMMAND_BIN_DIR = Join-Path $HOME ".local\bin"
$HELPER_BIN_DIR = Join-Path $ILONGRUN_HOME "bin"
$HELPER_CONFIG_DIR = Join-Path $ILONGRUN_HOME "config"
$HELPER_REFS_DIR = Join-Path $ILONGRUN_HOME "references"
$TARGET_SKILLS_DIR = Join-Path $HOME ".copilot\skills"
$TARGET_AGENTS_DIR = Join-Path $HOME ".copilot\agents"
$CLAUDE_DIR = if ($ClaudeDir) { $ClaudeDir } elseif ($env:CLAUDE_DIR) { $env:CLAUDE_DIR } else { Join-Path $HOME ".claude\commands" }

function Write-Step($msg) { Write-Host "  $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  WARN $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "  ERR  $msg" -ForegroundColor Red }

function Backup-IfNeeded($target) {
    if (Test-Path $target -PathType Leaf) {
        $ts = (Get-Date -Format "yyyyMMdd-HHmmss")
        $backup = "$target.bak.$ts"
        Move-Item $target $backup
        Write-Warn "Backed up: $target -> $backup"
    }
    if (Test-Path $target -PathType Container) {
        $ts = (Get-Date -Format "yyyyMMdd-HHmmss")
        $backup = "$target.bak.$ts"
        Move-Item $target $backup
        Write-Warn "Backed up directory: $target -> $backup"
    }
}

function Install-CopiedDir($source, $target) {
    Backup-IfNeeded $target
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Copy-Item "$source\*" $target -Recurse -Force
}

function Install-CopiedFile($source, $target) {
    Backup-IfNeeded $target
    $parentDir = Split-Path $target -Parent
    if ($parentDir -and !(Test-Path $parentDir)) {
        New-Item -ItemType Directory -Force -Path $parentDir | Out-Null
    }
    Copy-Item $source $target -Force
}

Write-Host ""
Write-Host "  iLongRun Windows 安装向导" -ForegroundColor Yellow
Write-Host "  ─────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host ""

# Create required directories
foreach ($dir in @($ILONGRUN_HOME, $HELPER_BIN_DIR, $HELPER_CONFIG_DIR, $HELPER_REFS_DIR, $TARGET_SKILLS_DIR, $TARGET_AGENTS_DIR, $COMMAND_BIN_DIR)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

# --- Step 1: Install skills ---
Write-Step "第 1 步：安装 skills..."
$skillsSource = Join-Path $ROOT_DIR "skills"
foreach ($skillDir in Get-ChildItem $skillsSource -Directory) {
    Install-CopiedDir $skillDir.FullName (Join-Path $TARGET_SKILLS_DIR $skillDir.Name)
    Write-Ok "skill: $($skillDir.Name)"
}

# --- Step 2: Install agents ---
Write-Step "第 2 步：安装 agents..."
$agentsSource = Join-Path $ROOT_DIR "agents"
foreach ($agentFile in Get-ChildItem $agentsSource -Filter "*.md") {
    Install-CopiedFile $agentFile.FullName (Join-Path $TARGET_AGENTS_DIR $agentFile.Name)
    Write-Ok "agent: $($agentFile.Name)"
}

# --- Step 3: Install helper scripts to ILONGRUN_HOME/bin ---
Write-Step "第 3 步：安装 helper 脚本到 $HELPER_BIN_DIR..."
$scriptFiles = @(
    "hook_event.py", "_ilongrun_shared.py", "_ilongrun_lib.py",
    "_ilongrun_terminal_theme.py", "_ilongrun_report_templates.py",
    "notify_macos.py", "notify_windows.py",
    "model_policy_info.py", "probe_models.py", "probe_fleet_capability.py",
    "launch_ilongrun_supervisor.py", "prepare_ilongrun_run.py",
    "reconcile_ilongrun_run.py", "finalize_ilongrun_run.py",
    "verify_ilongrun_run.py", "write_ilongrun_scheduler.py",
    "sync_ilongrun_ledger.py", "scan_ilongrun_delivery_gaps.py",
    "_ilongrun_delivery_audit.py", "render_ilongrun_status_board.py",
    "render_ilongrun_launch_board.py", "render_ilongrun_doctor_board.py",
    "render_ilongrun_install_board.py", "selftest_ilongrun.py",
    "cleanup_legacy_workspace.py", "harvest_sources.py",
    "record_source.py", "prompt_output_packager.py"
)
foreach ($f in $scriptFiles) {
    $src = Join-Path $ROOT_DIR "scripts\$f"
    if (Test-Path $src) {
        Install-CopiedFile $src (Join-Path $HELPER_BIN_DIR $f)
        Write-Ok "helper: $f"
    }
}

# --- Step 4: Install model config ---
Write-Step "第 4 步：安装模型配置..."
$configSrc = Join-Path $ROOT_DIR "config\model-policy.jsonc"
if (Test-Path $configSrc) {
    Install-CopiedFile $configSrc (Join-Path $HELPER_CONFIG_DIR "model-policy.jsonc")
    Write-Ok "model-policy.jsonc"
}

# --- Step 5: Install references ---
Write-Step "第 5 步：安装参考文档..."
$refsSource = Join-Path $ROOT_DIR "references"
if (Test-Path $refsSource) {
    foreach ($refFile in Get-ChildItem $refsSource) {
        Install-CopiedFile $refFile.FullName (Join-Path $HELPER_REFS_DIR $refFile.Name)
        Write-Ok "ref: $($refFile.Name)"
    }
}

# --- Step 6: Install launcher .bat files to COMMAND_BIN_DIR ---
Write-Step "第 6 步：安装 Windows 命令入口..."
$launchers = @("ilongrun", "ilongrun-coding", "ilongrun-prompt", "ilongrun-resume", "ilongrun-status", "ilongrun-doctor", "copilot-ilongrun")
foreach ($launcher in $launchers) {
    $srcScript = Join-Path $ROOT_DIR "scripts\$launcher"
    $batTarget = Join-Path $COMMAND_BIN_DIR "$launcher.bat"
    Backup-IfNeeded $batTarget
    if (Test-Path $srcScript) {
        # Create a .bat wrapper that calls python or bash if available
        $batContent = "@echo off`r`n" +
            "REM iLongRun launcher: $launcher`r`n" +
            "python `"$HELPER_BIN_DIR\launch_ilongrun_supervisor.py`" --command $launcher %*`r`n"
        Set-Content -Path $batTarget -Value $batContent -Encoding ASCII
        Write-Ok "launcher: $launcher.bat"
    }
}

# --- Step 7: Install Claude Code integration (optional) ---
$shouldInstallClaude = ($Agent -eq "claude" -or $Agent -eq "all") -or
    ($Agent -eq "auto" -and (Test-Path (Join-Path $HOME ".claude")))

if ($shouldInstallClaude) {
    Write-Step "第 7 步：安装 Claude Code 命令..."
    New-Item -ItemType Directory -Force -Path $CLAUDE_DIR | Out-Null
    $integrationsDir = Join-Path $ROOT_DIR "integrations\claude-code\commands"
    if (Test-Path $integrationsDir) {
        foreach ($cmdFile in Get-ChildItem $integrationsDir -Filter "*.md") {
            Install-CopiedFile $cmdFile.FullName (Join-Path $CLAUDE_DIR $cmdFile.Name)
            Write-Ok "claude-cmd: $($cmdFile.Name)"
        }
    }
} else {
    Write-Warn "跳过 Claude Code 集成（未检测到 ~/.claude 目录）"
    Write-Warn "如需安装，请运行: .\scripts\install.ps1 -Agent claude"
}

# --- Step 8: Add to PATH if needed ---
Write-Host ""
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($currentPath -notlike "*$COMMAND_BIN_DIR*") {
    Write-Step "第 8 步：将 $COMMAND_BIN_DIR 添加到用户 PATH..."
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$COMMAND_BIN_DIR", "User")
    Write-Ok "PATH 已更新，请重新打开终端生效"
} else {
    Write-Step "PATH 已包含 $COMMAND_BIN_DIR，跳过"
}

# --- Done ---
Write-Host ""
Write-Host "  ─────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  iLongRun 安装完成！" -ForegroundColor Green
Write-Host ""
Write-Host "  常用命令（重新打开终端后生效）：" -ForegroundColor Yellow
Write-Host "    ilongrun          # 启动任务"
Write-Host "    ilongrun-status   # 查看状态"
Write-Host "    ilongrun-doctor   # 环境自检"
Write-Host "    ilongrun-resume   # 恢复任务"
Write-Host ""
