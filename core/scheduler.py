"""
Windows 计划任务管理 — 开机自启动隧道
"""
import os
import subprocess

TASK_NAME = "CloudflareTunnel_AutoStart"
if os.name == "nt":
    _NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    _NO_WINDOW = 0


def _run_ps(script):
    """执行 PowerShell 脚本"""
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            startupinfo=startupinfo,
            creationflags=_NO_WINDOW,
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)


def is_task_exists():
    """检查计划任务是否存在"""
    code, stdout, stderr = _run_ps(f"Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue")
    return code == 0 and stdout.strip()


def create_autostart_task(tunnel_name):
    """创建开机自启计划任务"""
    from core.cloudflared_cli import _find_exe

    cloudflared_exe = _find_exe()
    if not cloudflared_exe:
        cloudflared_exe = os.path.expandvars(
            r"%USERPROFILE%\AppData\Local\Microsoft\WinGet\Links\cloudflared.exe"
        )

    config_path = os.path.expandvars(r"%USERPROFILE%\.cloudflared\config.yml")

    if not os.path.isfile(config_path):
        return False, f"配置文件不存在: {config_path}\n请先在【域名配置】页添加域名映射"

    if not os.path.isfile(cloudflared_exe):
        return False, f"cloudflared.exe 未找到: {cloudflared_exe}"

    # 使用单行命令注册计划任务，避免多行字符串在 PowerShell 中的问题
    # 去掉 -RunLevel Highest 避免需要管理员权限
    ps_script = (
        f"$action = New-ScheduledTaskAction -Execute '{cloudflared_exe}'"
        f" -Argument 'tunnel --config {config_path} run {tunnel_name}';"
        f" $trigger = New-ScheduledTaskTrigger -AtLogon -RandomDelay (New-TimeSpan -Seconds 30);"
        f" $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME;"
        f" $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries"
        f" -DontStopIfGoingOnBatteries -StartWhenAvailable"
        f" -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1);"
        f" Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action"
        f" -Trigger $trigger -Principal $principal -Settings $settings -Force"
    )
    code, stdout, stderr = _run_ps(ps_script)
    if code == 0:
        return True, "开机自启已设置成功"
    err_msg = stderr.strip() if stderr else stdout.strip() if stdout else "未知错误"
    return False, f"设置失败:\n{err_msg}"


def remove_autostart_task():
    """删除开机自启计划任务"""
    code, stdout, stderr = _run_ps(
        f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false -ErrorAction SilentlyContinue"
    )
    if code == 0:
        return True, "开机自启已取消"
    # 如果任务不存在也算成功
    return True, "开机自启已取消"


def get_task_status():
    """获取计划任务状态"""
    if not is_task_exists():
        return False, "未设置开机自启"

    ps_script = f"""
$task = Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue
if ($task) {{
    $info = Get-ScheduledTaskInfo -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue
    Write-Output "State: $($task.State)"
    if ($info.LastRunTime) {{ Write-Output "LastRun: $($info.LastRunTime)" }}
    if ($info.NextRunTime) {{ Write-Output "NextRun: $($info.NextRunTime)" }}
}}
"""
    code, stdout, stderr = _run_ps(ps_script)
    if code == 0 and stdout.strip():
        return True, stdout.strip()
    return False, "无法获取任务状态"
