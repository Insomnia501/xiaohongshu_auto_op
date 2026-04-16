"""账号管理器 (Account Manager)

管理多个小红书账号，每个账号使用独立的 Chrome Profile 保持 Cookie 隔离。
并且为每个账号分配独立的 bridge server 端口和专属的扩展代码，完全并行互不干扰。

用法：
    uv run python scripts/account_manager.py add --account 账号A --nickname "主号"
    uv run python scripts/account_manager.py init --account 账号A
    uv run python scripts/account_manager.py list
    uv run python scripts/account_manager.py status --account 账号A
    uv run python scripts/account_manager.py set-default --account 账号A
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.parent
ACCOUNTS_FILE = PROJECT_ROOT / "accounts.json"
PROFILES_DIR = PROJECT_ROOT / "profiles"


# ─── 配置文件操作 ──────────────────────────────────────────────────────────────


def load_config() -> dict:
    """读取 accounts.json，不存在时返回空配置。"""
    if not ACCOUNTS_FILE.exists():
        return {"accounts": {}, "default": ""}
    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    """保存 accounts.json。"""
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_account(account_name: str) -> dict | None:
    """获取指定账号的配置，不存在则返回 None。"""
    config = load_config()
    return config["accounts"].get(account_name)


def get_default_account() -> str | None:
    """获取默认账号名。"""
    config = load_config()
    return config.get("default") or None


# ─── Chrome 操作 ───────────────────────────────────────────────────────────────


def find_chrome() -> str | None:
    """查找 macOS/Linux 上的 Chrome 可执行文件路径。"""
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def launch_chrome(profile_dir: str | Path, url: str = "https://www.xiaohongshu.com/") -> subprocess.Popen:
    """以指定 Profile 目录启动 Chrome。"""
    chrome = find_chrome()
    if not chrome:
        print("❌ 找不到 Chrome，请确认已安装 Google Chrome。")
        sys.exit(1)

    abs_profile = str(Path(profile_dir).absolute())
    cmd = [
        chrome,
        f"--user-data-dir={abs_profile}",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]
    print(f"🚀 正在启动 Chrome (Profile: {abs_profile})")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc


# ─── Bridge 服务器操作 ──────────────────────────────────────────────────────────


def is_bridge_running(port: int) -> bool:
    """检测指定端口的 bridge server 是否在运行。"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(("localhost", port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def start_bridge(port: int) -> subprocess.Popen:
    """启动 bridge_server.py（后台进程）。"""
    bridge_script = Path(__file__).parent / "bridge_server.py"
    cmd = [sys.executable, str(bridge_script), "--port", str(port)]
    print(f"🔌 正在启动 bridge server (端口 {port})...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for _ in range(10):
        time.sleep(0.5)
        if is_bridge_running(port):
            print(f"✅ Bridge server 已启动（ws://localhost:{port}）")
            return proc
    print(f"⚠️ Bridge server 启动超时")
    return proc


# ─── CLI 子命令 ─────────────────────────────────────────────────────────────────


def cmd_add(args: argparse.Namespace) -> None:
    """添加新账号配置。自动分配新的 bridge_port。"""
    config = load_config()
    if args.account in config["accounts"]:
        print(f"⚠️ 账号 '{args.account}' 已存在。")
        return

    # 分配 bridge_port
    used_ports = [acc.get("bridge_port", 9333) for acc in config["accounts"].values()]
    new_port = max(used_ports + [9333]) + 1

    profile_dir = args.profile_dir or f"profiles/{args.account}"

    config["accounts"][args.account] = {
        "nickname": args.nickname or args.account,
        "profile_dir": profile_dir,
        "bridge_port": new_port,
    }
    if not config.get("default"):
        config["default"] = args.account

    save_config(config)
    print(f"✅ 账号 '{args.account}' 已添加：")
    print(f"   - Profile 目录: {profile_dir}")
    print(f"   - Bridge 端口:  {new_port}")
    print(f"\n下一步请运行: uv run python scripts/account_manager.py init --account {args.account}")


def cmd_init(args: argparse.Namespace) -> None:
    """初始化账号：配置专属扩展、启动 Chrome 和 Bridge 让用户登录。"""
    account = get_account(args.account)
    if not account:
        print(f"❌ 未找到账号配置: {args.account}")
        sys.exit(1)

    profile_dir = PROJECT_ROOT / account["profile_dir"]
    profile_dir.mkdir(parents=True, exist_ok=True)
    port = account["bridge_port"]

    # --- 为该账号生成专属端口的扩展代码 ---
    src_ext = PROJECT_ROOT / "extension"
    dst_ext = profile_dir / "extension"
    if dst_ext.exists():
        shutil.rmtree(dst_ext)
    shutil.copytree(src_ext, dst_ext)
    
    # 替换 background.js 里的端口
    bg_js = dst_ext / "background.js"
    content = bg_js.read_text(encoding="utf-8")
    content = content.replace("ws://localhost:9333", f"ws://localhost:{port}")
    bg_js.write_text(content, encoding="utf-8")

    print(f"\n📋 正在为账号 '{args.account}' 初始化...")
    print("1. Chrome 将以独立窗口打开，只影响这个账号，不影响你的日常 Chrome。")
    print(f"2. 请在打开的 Chrome 中安装【专属 XHS Bridge 扩展】（端口已自动配置到 {port}）：")
    print(f"   - 访问 chrome://extensions/")
    print(f"   - 开启右上角「开发者模式」")
    print(f"   - 点击「加载已解压的扩展程序」")
    print(f"   - 【重要】必须选择这个新生成的专属目录：\n     {dst_ext.absolute()}")
    print("3. 请在打开的 Chrome 中登录小红书账号。")
    print("4. 完成后，回到这里按回车继续。\n")

    # 启动专属 bridge
    if not is_bridge_running(port):
        start_bridge(port)
        time.sleep(1)

    # 启动 Chrome
    launch_chrome(profile_dir)

    input("\n⏸  请在 Chrome 中完成步骤 2 和 3，然后按回车键继续...")

    # 验证
    print("\n🔍 正在验证登录状态...")
    bridge_url = f"ws://localhost:{port}"
    check_cmd = [
        sys.executable,
        str(Path(__file__).parent / "cli.py"),
        f"--bridge-url={bridge_url}",
        "check-login",
    ]
    result = subprocess.run(check_cmd, capture_output=True, text=True)
    print(result.stdout)
    if result.returncode == 0:
        print(f"🎉 账号 '{args.account}' 初始化成功！")
    else:
        print("⚠️ 登录状态检查失败，请确认已在 Chrome 中登录小红书。")


def cmd_list(args: argparse.Namespace) -> None:
    """列出所有已配置的账号及其状态。"""
    config = load_config()
    accounts = config.get("accounts", {})
    default = config.get("default", "")

    if not accounts:
        print("📭 还没有配置任何账号。")
        print(f"   快速开始: uv run python scripts/account_manager.py add --account 主号 --nickname '我的主号'")
        return

    print(f"{'账号ID':<20} {'昵称':<20} {'端口':<10} {'Bridge状态':<15} {'默认'}")
    print("-" * 75)
    for name, acc in accounts.items():
        is_default = "⭐" if name == default else ""
        nickname = acc.get("nickname", "")
        port = acc.get("bridge_port", 9333)
        bridge_st = "✅ 已启动" if is_bridge_running(port) else "⭕ 未启动"
        print(f"{name:<20} {nickname:<20} {port:<10} {bridge_st:<15} {is_default}")


def cmd_status(args: argparse.Namespace) -> None:
    """查看指定账号的详细状态。"""
    account = get_account(args.account)
    if not account:
        print(f"❌ 未找到账号: {args.account}")
        sys.exit(1)

    port = account.get("bridge_port", 9333)
    bridge_running = is_bridge_running(port)

    print(f"\n📊 账号 '{args.account}' 状态：")
    print(f"   昵称:         {account.get('nickname', '')}")
    print(f"   Profile 目录: {account['profile_dir']}")
    print(f"   专属扩展目录: {PROJECT_ROOT / account['profile_dir'] / 'extension'}")
    print(f"   Bridge 配置:  端口 {port} {'✅ 运行中' if bridge_running else '⭕ 未启动'}")

    if bridge_running:
        check_cmd = [
            sys.executable,
            str(Path(__file__).parent / "cli.py"),
            f"--bridge-url=ws://localhost:{port}",
            "check-login",
        ]
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        try:
            data = json.loads(result.stdout)
            logged_in = data.get("logged_in", False)
            print(f"   登录状态:     {'✅ 已登录' if logged_in else '❌ 未登录'}")
        except Exception:
            print(f"   登录状态:     ⚠️ 检查失败")


def cmd_set_default(args: argparse.Namespace) -> None:
    """设置默认账号。"""
    config = load_config()
    if args.account not in config["accounts"]:
        print(f"❌ 账号 '{args.account}' 不存在")
        sys.exit(1)
    config["default"] = args.account
    save_config(config)
    print(f"✅ 已将 '{args.account}' 设置为默认账号")


# ─── 入口 ──────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="account_manager",
        description="小红书多账号管理器（完全隔离的 Chrome Profile 和独立 Bridge 端口）",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    # add
    p = subs.add_parser("add", help="添加新账号配置")
    p.add_argument("--account", required=True, help="账号ID（英文，唯一标识）")
    p.add_argument("--nickname", help="账号昵称（便于识别）")
    p.add_argument("--profile-dir", help="Chrome Profile 目录（不填则默认）")
    p.set_defaults(func=cmd_add)

    # init
    p = subs.add_parser("init", help="初始化账号（启动独立 Chrome 引导安装专属扩展并登录）")
    p.add_argument("--account", required=True, help="账号ID")
    p.set_defaults(func=cmd_init)

    # list
    p = subs.add_parser("list", help="列出所有账号及状态")
    p.set_defaults(func=cmd_list)

    # status
    p = subs.add_parser("status", help="查看指定账号详细状态")
    p.add_argument("--account", required=True)
    p.set_defaults(func=cmd_status)

    # set-default
    p = subs.add_parser("set-default", help="设置默认账号")
    p.add_argument("--account", required=True)
    p.set_defaults(func=cmd_set_default)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
