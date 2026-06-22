"""
Windows 开机自启动 — 通过注册表 HKCU Run 键
无需管理员权限
"""
import os
import winreg

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "CloudflareTunnel"


def create_autostart_task(tunnel_name):
    """设置开机自启（注册表 HKCU Run）"""
    from core.cloudflared_cli import _find_exe

    cloudflared_exe = _find_exe()
    if not cloudflared_exe:
        cloudflared_exe = os.path.expandvars(
            r"%USERPROFILE%\AppData\Local\Microsoft\WinGet\Links\cloudflared.exe"
        )

    config_path = os.path.expandvars(r"%USERPROFILE%\.cloudflared\config.yml")

    if not os.path.isfile(config_path):
        return False, f"配置文件不存在:\n{config_path}\n请先在域名配置页添加域名映射"

    if not os.path.isfile(cloudflared_exe):
        return False, f"cloudflared.exe 未找到:\n{cloudflared_exe}"

    # 构建启动命令行
    cmd = f'"{cloudflared_exe}" tunnel --config "{config_path}" run {tunnel_name}'

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return True, "开机自启已设置成功"
    except PermissionError:
        return False, "权限不足，请以管理员身份运行"
    except Exception as e:
        return False, f"设置失败:\n{e}"


def remove_autostart_task():
    """取消开机自启（删除注册表键值）"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, REG_NAME)
        except FileNotFoundError:
            pass  # 本来就没有
        winreg.CloseKey(key)
        return True, "开机自启已取消"
    except Exception as e:
        return True, "开机自启已取消"


def is_task_exists():
    """检查是否已设置开机自启"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, REG_NAME)
            winreg.CloseKey(key)
            return bool(value)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def get_task_status():
    """获取开机自启状态"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, REG_NAME)
            winreg.CloseKey(key)
            return True, value[:200] if value else ""
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False, "未设置开机自启"
    except Exception:
        return False, "无法获取状态"
