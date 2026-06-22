# 寒彬 Cloudflared 内网穿透管理工具

傻瓜式操作的 Cloudflare Tunnel 管理工具，无需命令行，图形化界面完成隧道创建、域名映射、DNS 绑定、启动停止和开机自启。

基于 Python + pywebview，使用 Edge WebView2 渲染现代 Web UI，原生 Windows 窗口运行，无端口、无浏览器地址栏。

## 功能

- **环境检测** — 自动检查 cloudflared 安装状态和 Cloudflare 登录状态，一键安装/登录
- **隧道管理** — 创建、删除隧道，设为当前使用
- **域名映射** — 可视化编辑 ingress 规则，一键绑定 DNS 记录
- **隧道控制** — 启动 / 停止 / 停止所有隧道，实时日志输出
- **开机自启** — 一键创建/删除 Windows 计划任务，登录自动启动隧道
- **引导向导** — 首次使用逐步引导完成全部配置

## 截图
<img width="1004" height="661" alt="image" src="https://github.com/user-attachments/assets/3cc893a0-bb07-4519-8fa9-594e2b5062c7" />
> 运行效果见下方（请替换为实际截图）

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | HTML5 + CSS3 + JavaScript (Vanilla) |
| 渲染 | pywebview (Edge WebView2) |
| 后端 | Python 3 |
| 隧道交互 | cloudflared CLI (subprocess) |
| 打包 | PyInstaller (单文件 EXE) |

## 快速开始

### 前提条件

- Windows 10/11（自带 Edge WebView2）
- Python 3.10+
- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)（或在程序内一键安装）
- 一个托管到 Cloudflare 的域名

### 运行

```bash
pip install pyyaml pywebview
python main.py
```

### 打包为 EXE

```bash
pip install pyyaml pyinstaller pywebview
pyinstaller --onefile --windowed --icon logo.ico --name "寒彬Cloudflared管理工具" --add-data "web;web" --add-data "core;core" --hidden-import yaml main.py
```

## 项目结构

```
├── main.py                  # 入口 (pywebview + API)
├── logo.ico                 # 程序图标
├── requirements.txt         # 依赖
├── core/
│   ├── cloudflared_cli.py   # cloudflared 命令封装
│   ├── config_manager.py    # config.yml 读写
│   └── scheduler.py         # 计划任务管理
├── web/
│   ├── index.html           # 页面结构
│   ├── logo.png             # 侧边栏 Logo
│   ├── css/style.css        # 暗色主题样式
│   └── js/app.js            # 前端交互逻辑
└── dist/
    └── 寒彬Cloudflared管理工具.exe
```

## 参考

- [Cloudflare Tunnel 文档](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [pywebview](https://pywebview.flowrl.com/)
