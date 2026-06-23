"""
Windows 开机自启动 — 通过注册表 HKCU Run 键 + VBS 静默启动
无需管理员权限，不显示终端窗口
"""
import os
import re
import winreg

REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_NAME = "CloudflareTunnel"

CLOUDFLARED_DIR = os.path.expandvars(r"%USERPROFILE%\.cloudflared")
VBS_PATH = os.path.join(CLOUDFLARED_DIR, "autostart_launcher.vbs")


def create_autostart_task(tunnel_name):
    """设置开机自启（注册表 HKCU Run → VBS → cloudflared，不弹窗）"""
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

    # 写入 VBS 静默启动脚本（第 2 个参数 0 = 隐藏窗口）
    os.makedirs(CLOUDFLARED_DIR, exist_ok=True)
    vbs_content = (
        f'Set WshShell = CreateObject("WScript.Shell")\r\n'
        f'WshShell.Run """{cloudflared_exe}"" tunnel --config ""{config_path}"" run {tunnel_name}", 0, False\r\n'
        f'Set WshShell = Nothing\r\n'
    )
    with open(VBS_PATH, 'w') as f:
        f.write(vbs_content)

    # 注册表指向 wscript.exe 执行 VBS，//B 禁止脚本错误弹窗
    cmd = f'wscript.exe "{VBS_PATH}" //B'

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, REG_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return True, f"开机自启已设置 (隧道: {tunnel_name})"
    except PermissionError:
        return False, "权限不足，请以管理员身份运行"
    except Exception as e:
        return False, f"设置失败:\n{e}"


def remove_autostart_task():
    """取消开机自启（删除注册表键值 + VBS 文件）"""
    # 清理 VBS 文件
    if os.path.isfile(VBS_PATH):
        try:
            os.remove(VBS_PATH)
        except Exception:
            pass

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, REG_NAME)
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
        return True, "开机自启已取消"
    except Exception:
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
    """获取开机自启状态与隧道名"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, REG_NAME)
            winreg.CloseKey(key)
            if not value:
                return False, "未设置开机自启"

            # 从 VBS 脚本中解析隧道名
            tunnel_name = ""
            if os.path.isfile(VBS_PATH):
                try:
                    with open(VBS_PATH, 'r') as f:
                        content = f.read()
                    m = re.search(r'run\s+(\S+)', content)
                    if m:
                        tunnel_name = m.group(1)
                except Exception:
                    pass

            if tunnel_name:
                return True, f"已开启 (隧道: {tunnel_name})"
            return True, "已开启"
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False, "未设置开机自启"
    except Exception:
        return False, "无法获取状态"
