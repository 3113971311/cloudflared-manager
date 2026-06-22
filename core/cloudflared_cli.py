"""
cloudflared CLI 命令封装
所有与 cloudflared.exe 的交互都通过此模块
"""
import os
import re
import subprocess
import uuid as uuid_module


CLOUDFLARED_PATHS = [
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\Microsoft\WinGet\Links\cloudflared.exe"),
    os.path.expandvars(r"%USERPROFILE%\scoop\shims\cloudflared.exe"),
    "cloudflared.exe",
]

USER_HOME = os.path.expanduser("~")
CLOUDFLARED_DIR = os.path.join(USER_HOME, ".cloudflared")
CERT_PATH = os.path.join(CLOUDFLARED_DIR, "cert.pem")
CONFIG_PATH = os.path.join(CLOUDFLARED_DIR, "config.yml")


def _find_exe():
    """查找 cloudflared.exe 路径"""
    for p in CLOUDFLARED_PATHS:
        if os.path.isfile(p):
            return p
    # 尝试 where 命令（Windows 系统命令，用系统默认编码）
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            ["where", "cloudflared"],
            capture_output=True, text=True, timeout=10,
            creationflags=creationflags,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass
    return None


def _run(args, timeout=60, show_progress=False):
    """执行 cloudflared 命令，返回 (returncode, stdout, stderr)"""
    exe = _find_exe()
    if not exe:
        return -1, "", "cloudflared.exe 未找到，请先安装 cloudflared"
    cmd = [exe] + args
    try:
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8", errors="replace",
            timeout=timeout,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", "cloudflared.exe 未找到"
    except subprocess.TimeoutExpired:
        return -1, "", "命令执行超时"
    except Exception as e:
        return -1, "", str(e)


def is_installed():
    """检查 cloudflared 是否已安装"""
    return _find_exe() is not None


def get_version():
    """获取 cloudflared 版本"""
    code, stdout, stderr = _run(["--version"], timeout=10)
    if code == 0:
        match = re.search(r"cloudflared version (\S+)", stdout)
        if match:
            return match.group(1)
        return stdout.strip()
    return None


def is_logged_in():
    """检查是否已登录（cert.pem 是否存在）"""
    return os.path.isfile(CERT_PATH)


def login():
    """执行 cloudflared login，打开浏览器认证"""
    exe = _find_exe()
    if not exe:
        return False, "cloudflared.exe 未找到"
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        subprocess.run(
            [exe, "login"], timeout=120,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )
        return is_logged_in(), "登录完成" if is_logged_in() else "登录可能未完成，请重试"
    except subprocess.TimeoutExpired:
        return is_logged_in(), "登录超时，请重试"
    except Exception as e:
        return False, str(e)


def list_tunnels():
    """列出所有隧道，返回 [{"id": str, "name": str, "created": str, "connections": int}]"""
    code, stdout, stderr = _run(["tunnel", "list"], timeout=15)
    if code != 0:
        return [], stderr

    tunnels = []
    lines = stdout.strip().split("\n")
    # 跳过表头行和分隔线
    in_data = False
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("ID") or line.startswith("--"):
            in_data = True
            continue
        if in_data:
            # 格式: UUID  NAME  CREATED  CONNECTIONS
            parts = line.split()
            if len(parts) >= 2:
                # 检查第一个是否是 UUID
                try:
                    uuid_module.UUID(parts[0])
                    tunnel_id = parts[0]
                    name = parts[1] if len(parts) > 1 else ""
                    connections = 0
                    # 最后一个是 connections 数字
                    if parts[-1].isdigit():
                        connections = int(parts[-1])
                    tunnels.append({
                        "id": tunnel_id,
                        "name": name,
                        "connections": connections,
                    })
                except ValueError:
                    pass
    return tunnels, None


def create_tunnel(name):
    """创建隧道，返回 (success, message, tunnel_id)"""
    code, stdout, stderr = _run(["tunnel", "create", name], timeout=30)
    if code != 0:
        return False, stderr, None

    # 从输出中提取 UUID
    match = re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        stdout,
        re.IGNORECASE,
    )
    tunnel_id = match.group(0) if match else None
    return True, stdout.strip(), tunnel_id


def delete_tunnel(name_or_id):
    """删除隧道"""
    code, stdout, stderr = _run(["tunnel", "delete", "-f", name_or_id], timeout=30)
    if code != 0:
        return False, stderr
    return True, stdout.strip()


def get_tunnel_info(name_or_id):
    """获取隧道详细信息"""
    code, stdout, stderr = _run(["tunnel", "info", name_or_id], timeout=15)
    if code != 0:
        return None, stderr
    return stdout.strip(), None


def route_dns(tunnel_name, hostname):
    """绑定 DNS 记录"""
    code, stdout, stderr = _run(
        ["tunnel", "route", "dns", tunnel_name, hostname], timeout=30
    )
    if code != 0:
        return False, stderr
    return True, stdout.strip()


def list_routes():
    """列出所有已绑定的 DNS 路由"""
    code, stdout, stderr = _run(["tunnel", "route", "dns"], timeout=15)
    if code != 0:
        return [], stderr

    routes = []
    lines = stdout.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line or line.startswith("ID") or line.startswith("--"):
            continue
        # 尝试匹配 UUID hostname 格式
        parts = line.split()
        if len(parts) >= 2:
            routes.append(parts)
    return routes, None


def unroute_dns(tunnel_id, hostname=""):
    """解绑 DNS 记录"""
    args = ["tunnel", "route", "dns", "delete", tunnel_id]
    if hostname:
        args.append(hostname)
    code, stdout, stderr = _run(args, timeout=30)
    if code != 0:
        return False, stderr
    return True, stdout.strip()


def cleanup_connections(tunnel_id):
    """清理隧道连接"""
    code, stdout, stderr = _run(
        ["tunnel", "cleanup", "connections", tunnel_id], timeout=15
    )
    if code != 0:
        return False, stderr
    return True, stdout.strip()


def get_config_path():
    """获取配置文件路径"""
    return CONFIG_PATH


def get_cert_path():
    """获取证书路径"""
    return CERT_PATH


def get_cloudflared_dir():
    """获取 cloudflared 配置目录"""
    return CLOUDFLARED_DIR
