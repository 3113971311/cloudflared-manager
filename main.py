"""
Cloudflared 内网穿透管理工具 — pywebview + Web UI
"""
import sys
import os
import threading
import queue
import subprocess
import json
import re
import ctypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import webview

# ─── 原生弹窗 ────────────────────────────────
def native_confirm(title, message):
    """Windows 原生确认对话框，返回 True/False"""
    if os.name == "nt":
        return ctypes.windll.user32.MessageBoxW(
            0, message, title, 0x24  # MB_YESNO | MB_ICONQUESTION
        ) == 6  # IDYES
    return False

from core.cloudflared_cli import (
    is_installed, is_logged_in, get_version, login,
    list_tunnels, create_tunnel, delete_tunnel,
    route_dns, delete_dns_record, list_all_dns_routes, _find_exe,
)
from core.config_manager import (
    load_config, get_tunnel_id_from_config,
    get_ingress_rules, add_ingress_rule, remove_ingress_rule,
    set_tunnel_id,
)
from core.scheduler import (
    get_task_status, create_autostart_task, remove_autostart_task,
)

# ─── 全局状态 ────────────────────────────────
tunnel_proc = None
external_process = False  # 是否是外部启动的进程（如开机自启）
log_lines = []
log_lines_lock = threading.Lock()
running_state = "stopped"


def push_log(msg):
    """追加日志并推送到前端"""
    global log_lines
    with log_lines_lock:
        log_lines.append(msg)
    try:
        if webview.windows:
            escaped = json.dumps(msg)[1:-1]
            webview.windows[0].evaluate_js(
                f"pushLogLine('{escaped}')"
            )
    except Exception:
        pass


def push_state(state):
    """推送状态变更到前端"""
    global running_state
    running_state = state
    try:
        if webview.windows:
            webview.windows[0].evaluate_js(f"updateState('{state}')")
    except Exception:
        pass


# ─── API 类 ──────────────────────────────────
class Api:

    def get_status(self):
        return {
            "installed": is_installed(),
            "logged_in": is_logged_in(),
            "version": get_version() or "",
        }

    def install(self):
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            result = subprocess.run(
                ["winget", "install", "--id", "Cloudflare.cloudflared", "--accept-source-agreements"],
                capture_output=True, text=True, timeout=120,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return {"success": result.returncode == 0, "message": "安装完成" if result.returncode == 0 else result.stderr}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def login(self):
        success, msg = login()
        return {"success": success, "message": msg}

    def list_tunnels(self):
        tunnels, err = list_tunnels()
        config_tid = get_tunnel_id_from_config()
        return {"tunnels": tunnels, "current_id": config_tid, "error": err or ""}

    def create_tunnel(self, name):
        success, msg, tid = create_tunnel(name)
        if success and tid:
            set_tunnel_id(tid)
        return {"success": success, "message": msg, "tunnel_id": tid or ""}

    def delete_tunnel(self, tid):
        success, msg = delete_tunnel(tid)
        return {"success": success, "message": msg}

    def set_current_tunnel(self, tid):
        set_tunnel_id(tid)
        return {"success": True}

    def get_config(self):
        config = load_config()
        tid = get_tunnel_id_from_config()
        rules = get_ingress_rules()
        # 查找当前隧道名
        tunnel_name = ""
        if tid:
            tunnels, _ = list_tunnels()
            for t in tunnels:
                if t["id"] == tid:
                    tunnel_name = t["name"]
                    break

        return {
            "current_tunnel": tid or "",
            "current_tunnel_name": tunnel_name,
            "has_config": config is not None,
            "rules": rules,
        }

    def add_rule(self, hostname, service):
        success, msg = add_ingress_rule(hostname, service)
        return {"success": success, "message": msg}

    def delete_rule(self, hostname, also_delete_dns=False):
        if also_delete_dns:
            self._try_delete_dns(hostname)
        success, msg = remove_ingress_rule(hostname)
        return {"success": success, "message": msg}

    def delete_dns(self, hostname):
        """单独删除 DNS 解析记录"""
        result = self._try_delete_dns(hostname)
        return result

    def _try_delete_dns(self, hostname):
        """尝试删除 DNS 解析，优先精确查找所属隧道"""
        tunnels, _ = list_tunnels()
        if not tunnels:
            return {"success": False, "message": "没有可用的隧道"}

        # 先用 list_all_dns_routes 精确定位 DNS 所属隧道
        dns_map = list_all_dns_routes([t["name"] for t in tunnels])
        exact_tunnel = dns_map.get(hostname, "")

        if exact_tunnel:
            success, msg = delete_dns_record(exact_tunnel, hostname)
            if success:
                return {"success": True, "message": f"已删除 {hostname} 的 DNS 解析（隧道: {exact_tunnel}）"}

        # 精确查找失败，遍历所有隧道尝试
        for t in tunnels:
            if t["name"] == exact_tunnel:
                continue
            success, msg = delete_dns_record(t["name"], hostname)
            if success:
                return {"success": True, "message": f"已删除 {hostname} 的 DNS 解析（隧道: {t['name']}）"}

        return {"success": False, "message": "未找到该域名的 DNS 解析记录，可能已被删除或需手动清理"}

    def bind_dns(self, hostname):
        tunnels, _ = list_tunnels()
        if not tunnels:
            return {"success": False, "message": "请先创建隧道"}
        config_tid = get_tunnel_id_from_config()
        tunnel_name = None
        for t in tunnels:
            if t["id"] == config_tid:
                tunnel_name = t["name"]
                break
        if not tunnel_name:
            tunnel_name = tunnels[0]["name"]
        success, msg = route_dns(tunnel_name, hostname)
        if success and not msg:
            msg = f"DNS 绑定成功：{hostname} → {tunnel_name}"
        return {"success": success, "message": msg}

    def bind_dns_bulk(self, hostnames):
        """批量绑定 DNS"""
        tunnels, _ = list_tunnels()
        if not tunnels:
            return {"success": False, "message": "请先创建隧道"}
        config_tid = get_tunnel_id_from_config()
        tunnel_name = None
        for t in tunnels:
            if t["id"] == config_tid:
                tunnel_name = t["name"]
                break
        if not tunnel_name:
            tunnel_name = tunnels[0]["name"]

        ok, fail = [], []
        for h in hostnames:
            success, msg = route_dns(tunnel_name, h)
            if success:
                ok.append(h)
            else:
                fail.append(f"{h}: {msg[:60]}")
        parts = []
        if ok:
            parts.append(f"成功绑定 {len(ok)} 个：{', '.join(ok)}")
        if fail:
            parts.append(f"失败 {len(fail)} 个：{' | '.join(fail)}")
        return {"success": len(fail) == 0, "message": '\n'.join(parts)}

    def get_autostart(self):
        exists, status = get_task_status()
        return {"enabled": exists, "status": status}

    def enable_autostart(self):
        tunnels, _ = list_tunnels()
        if not tunnels:
            return {"success": False, "message": "请先创建隧道"}
        config_tid = get_tunnel_id_from_config()
        tunnel_name = None
        for t in tunnels:
            if t["id"] == config_tid:
                tunnel_name = t["name"]
                break
        if not tunnel_name:
            tunnel_name = tunnels[0]["name"]
        success, msg = create_autostart_task(tunnel_name)
        return {"success": success, "message": msg}

    def disable_autostart(self):
        success, msg = remove_autostart_task()
        return {"success": success, "message": msg}

    def start_tunnel(self, tunnel_name):
        global tunnel_proc, running_state
        if running_state in ("starting", "running"):
            return {"success": False, "message": "隧道已在运行中"}

        config_path = os.path.expandvars(r"%USERPROFILE%\.cloudflared\config.yml")
        if not os.path.isfile(config_path):
            return {"success": False, "message": "配置文件不存在，请先添加域名映射"}

        running_state = "starting"
        push_state("starting")
        push_log(f"========== 启动隧道: {tunnel_name} ==========")

        def run():
            global tunnel_proc, running_state
            exe = _find_exe()
            if not exe:
                running_state = "stopped"
                push_state("stopped")
                push_log("[ERROR] 找不到 cloudflared.exe")
                return
            try:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                tunnel_proc = subprocess.Popen(
                    [exe, "tunnel", "--config", config_path, "run", tunnel_name],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    encoding="utf-8", errors="replace", bufsize=1,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                for line in iter(tunnel_proc.stdout.readline, ""):
                    line = line.rstrip()
                    push_log(line)
                    if running_state == "starting" and "INF" in line:
                        running_state = "running"
                        push_state("running")
                    if running_state == "stopping":
                        break
                tunnel_proc.stdout.close()
                code = tunnel_proc.wait()
                if running_state != "stopping":
                    push_log(f"--- 隧道进程已退出，返回码: {code} ---")
            except Exception as e:
                push_log(f"[ERROR] 启动异常: {e}")
            finally:
                tunnel_proc = None
                external_process = False
                running_state = "stopped"
                push_state("stopped")

        threading.Thread(target=run, daemon=True).start()
        return {"success": True, "message": "启动中..."}

    def stop_tunnel(self):
        global tunnel_proc, running_state, external_process
        if running_state not in ("starting", "running"):
            return {"success": True}
        running_state = "stopping"
        push_state("stopping")
        push_log("--- 正在停止隧道... ---")

        # 外部进程（如开机自启启动的），用 taskkill
        if external_process and (not tunnel_proc or tunnel_proc.poll() is not None):
            self._taskkill_cloudflared()
            external_process = False
            running_state = "stopped"
            push_state("stopped")
            return {"success": True}

        if tunnel_proc and tunnel_proc.poll() is None:
            try:
                tunnel_proc.terminate()
            except Exception:
                pass
        # 3秒后强杀
        def force_kill():
            global tunnel_proc, running_state, external_process
            if tunnel_proc and tunnel_proc.poll() is None:
                try:
                    tunnel_proc.kill()
                    push_log("--- 强制终止隧道进程 ---")
                except Exception:
                    pass
            running_state = "stopped"
            external_process = False
            push_state("stopped")
        threading.Timer(3, force_kill).start()
        return {"success": True}

    def _taskkill_cloudflared(self):
        """使用 taskkill 终止 cloudflared 进程"""
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            subprocess.run(
                ["taskkill", "/F", "/IM", "cloudflared.exe"],
                capture_output=True, text=True, timeout=15,
                startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW,
            )
            push_log("--- 已终止外部 cloudflared 进程 ---")
        except Exception:
            pass

    def confirm_kill(self):
        """弹出原生确认对话框"""
        return native_confirm("停止所有隧道", "确定要停止所有 cloudflared 隧道进程吗？")

    def kill_all(self):
        global tunnel_proc, running_state, external_process
        push_log("========== 停止所有隧道 ==========")
        if tunnel_proc and tunnel_proc.poll() is None:
            try:
                tunnel_proc.terminate()
            except Exception:
                pass
        self._taskkill_cloudflared()
        tunnel_proc = None
        external_process = False
        running_state = "stopped"
        push_state("stopped")
        return {"success": True}

    def get_logs(self):
        """获取历史日志"""
        with log_lines_lock:
            lines = list(log_lines)
            log_lines.clear()
        return {"lines": lines, "state": running_state}

    def get_state(self):
        return {"state": running_state}

    def check_running_processes(self):
        """启动时检测是否有外部 tunnel 进程在运行（如开机自启启动的）"""
        global running_state
        if running_state != "stopped":
            return {"running": True, "state": running_state}
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = subprocess.SW_HIDE
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq cloudflared.exe', '/NH'],
                capture_output=True, text=True, timeout=5,
                startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW
            )
            if 'cloudflared.exe' in result.stdout:
                # 尝试从进程命令行解析隧道名
                tunnel_name = ""
                try:
                    ps = subprocess.run(
                        ['powershell', '-NoProfile', '-Command',
                         '(Get-CimInstance Win32_Process -Filter "Name=\'cloudflared.exe\'").CommandLine'],
                        capture_output=True, text=True, timeout=8,
                        startupinfo=si, creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    m = re.search(r'run\s+(\S+)', ps.stdout)
                    if m:
                        tunnel_name = m.group(1)
                except Exception:
                    pass

                running_state = "running"
                external_process = True
                push_state("running")
                push_log(f"[检测] 发现已在运行的 cloudflared 隧道进程"
                         + (f" ({tunnel_name})" if tunnel_name else ""))
                return {"running": True, "state": "running",
                        "external": True, "tunnel_name": tunnel_name}
        except Exception:
            pass
        return {"running": False, "state": "stopped"}


# ─── HTML 文件查找（兼容 PyInstaller） ────────────
def get_web_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'web')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'web')


# ─── 入口 ────────────────────────────────────
def main():
    # 指定 WebView2 用户数据目录（避免临时目录被清理导致无法启动）
    webview_data = os.path.join(os.environ['LOCALAPPDATA'], '寒彬Cloudflared管理', 'WebView2')
    os.makedirs(webview_data, exist_ok=True)
    os.environ['WEBVIEW2_USER_DATA_FOLDER'] = webview_data

    api = Api()
    web_path = get_web_path()
    html_path = os.path.join(web_path, 'index.html')
    icon_path = os.path.join(web_path, 'logo.png')
    webview.create_window(
        "寒彬 Cloudflared 内网穿透管理",
        html_path,
        js_api=api,
        width=1020,
        height=700,
        min_size=(860, 560),
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
