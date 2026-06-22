"""
config.yml 配置文件读写管理
"""
import os
import yaml
from core.cloudflared_cli import get_config_path, get_cloudflared_dir


def load_config():
    """加载 config.yml，返回 dict"""
    path = get_config_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return None


def save_config(config_dict):
    """保存 config.yml"""
    path = get_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def get_tunnel_id_from_config():
    """从配置中读取 tunnel UUID"""
    config = load_config()
    if config:
        return config.get("tunnel", None)
    return None


def get_ingress_rules():
    """获取所有 ingress 规则，返回 [{"hostname": str, "service": str}, ...]"""
    config = load_config()
    if not config or "ingress" not in config:
        return []

    rules = []
    for item in config["ingress"]:
        if "hostname" in item and "service" in item:
            rules.append({
                "hostname": item["hostname"],
                "service": item["service"],
            })
    return rules


def add_ingress_rule(hostname, service):
    """添加一条 ingress 规则"""
    config = load_config()
    if config is None:
        config = {}

    if "ingress" not in config:
        config["ingress"] = []

    # 检查是否已存在该 hostname
    for item in config["ingress"]:
        if item.get("hostname") == hostname:
            item["service"] = service
            save_config(config)
            return True, "已更新现有规则"

    # 在 catch-all 规则前插入
    catch_all = None
    for i, item in enumerate(config["ingress"]):
        if "service" in item and "hostname" not in item:
            catch_all = config["ingress"].pop(i)
            break

    config["ingress"].append({"hostname": hostname, "service": service})

    if catch_all:
        config["ingress"].append(catch_all)
    else:
        config["ingress"].append({"service": "http_status:404"})

    save_config(config)
    return True, "规则已添加"


def remove_ingress_rule(hostname):
    """删除一条 ingress 规则"""
    config = load_config()
    if not config or "ingress" not in config:
        return False, "配置文件为空"

    config["ingress"] = [
        item
        for item in config["ingress"]
        if item.get("hostname") != hostname
    ]
    save_config(config)
    return True, "规则已删除"


def set_tunnel_id(tunnel_id):
    """设置配置文件中的 tunnel UUID"""
    config = load_config()
    if config is None:
        config = {}

    config["tunnel"] = tunnel_id

    # 自动设置 credentials-file
    cloudflared_dir = get_cloudflared_dir()
    cred_file = os.path.join(cloudflared_dir, f"{tunnel_id}.json")
    config["credentials-file"] = cred_file.replace("\\", "/")

    if "ingress" not in config:
        config["ingress"] = [{"service": "http_status:404"}]

    save_config(config)
    return True


def generate_config(tunnel_id, ingress_rules):
    """根据隧道 ID 和 ingress 规则生成完整配置"""
    cloudflared_dir = get_cloudflared_dir()
    cred_file = os.path.join(cloudflared_dir, f"{tunnel_id}.json")

    config = {
        "tunnel": tunnel_id,
        "credentials-file": cred_file.replace("\\", "/"),
        "ingress": [],
    }

    for rule in ingress_rules:
        config["ingress"].append({
            "hostname": rule["hostname"],
            "service": rule["service"],
        })

    # catch-all 规则
    config["ingress"].append({"service": "http_status:404"})

    save_config(config)
    return True
