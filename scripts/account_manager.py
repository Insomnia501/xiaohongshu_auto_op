"""账号管理器 (Account Manager)

负责管理多小红书账号，每个账号有专属的 Chrome Profile 和 bridge 端口。

用法：
    uv run python scripts/account_manager.py add --account 账号A --nickname "主号"
    uv run python scripts/account_manager.py init --account 账号A
    uv run python scripts/account_manager.py list
    uv run python scripts/account_manager.py status --account 账号A
    uv run python scripts/account_manager.py start-bridge --account 账号A
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Windows 控制台默认编码不支持中文，强制 UTF-8
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.parent
ACCOUNTS_FILE = PROJECT_ROOT / "accounts.json"
PROFILES_DIR = PROJECT_ROOT / ".profiles"

# bridge 端口从 9334 开始递增（9333 保留给默认/单账号模式）
BASE_PORT = 9334


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


def get_bridge_url(account_name: str) -> str | None:
    """获取指定账号的 bridge WebSocket URL。"""
    account = get_account(account_name)
    if not account:
        return None
    return f"ws://localhost:{account['bridge_port']}"


def get_default_account() -> str | None:
    """获取默认账号名。"""
    config = load_config()
    return config.get("default") or None


def next_available_port() -> int:
    """自动分配下一个可用的 bridge 端口。"""
    config = load_config()
    used_ports = {acc["bridge_port"] for acc in config["accounts"].values()}
    port = BASE_PORT
    while port in used_ports:
        port += 1
    return port


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
    """以指定 Profile 目录启动 Chrome，并打开指定 URL。"""
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
    print(f"🚀 正在启动独立 Chrome (Profile: {abs_profile})...")
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc


# ─── Bridge 服务器操作 ──────────────────────────────────────────────────────────


def is_bridge_running(port: int) -> bool:
    """检测指定端口的 bridge_server 是否在运行。"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(("localhost", port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def start_bridge(port: int) -> subprocess.Popen:
    """在指定端口启动 bridge_server.py（后台进程）。"""
    bridge_script = Path(__file__).parent / "bridge_server.py"
    cmd = [sys.executable, str(bridge_script), "--port", str(port)]
    print(f"🔌 正在启动 bridge server (端口 {port})...")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # 等待 bridge 启动
    for _ in range(10):
        time.sleep(0.5)
        if is_bridge_running(port):
            print(f"✅ Bridge server 已启动（ws://localhost:{port}）")
            return proc
    print(f"⚠️ Bridge server 启动超时（端口 {port}）")
    return proc


def ensure_bridge_and_chrome(account_name: str) -> str:
    """
    确保指定账号的 bridge 和 Chrome 均已启动。
    返回对应的 bridge WebSocket URL。
    """
    account = get_account(account_name)
    if not account:
        print(f"❌ 未找到账号配置: {account_name}")
        print(f"   请先运行: uv run python scripts/account_manager.py add --account {account_name}")
        sys.exit(1)

    port = account["bridge_port"]
    profile_dir = PROJECT_ROOT / account["profile_dir"]

    # 启动 bridge（如未运行）
    if not is_bridge_running(port):
        start_bridge(port)
        time.sleep(1)

        # 启动 Chrome（bridge 刚启动，肯定还没 Extension 连上来，所以一起启动 Chrome）
        launch_chrome(profile_dir)
        print("⏳ 等待 Chrome 中的 XHS Bridge 扩展连接...")
        time.sleep(5)  # 给 Chrome 足够时间打开和加载扩展

    bridge_url = f"ws://localhost:{port}"
    return bridge_url


# ─── CLI 子命令 ─────────────────────────────────────────────────────────────────


def cmd_add(args: argparse.Namespace) -> None:
    """添加新账号配置（不启动，只写入 accounts.json）。"""
    config = load_config()
    if args.account in config["accounts"]:
        print(f"⚠️ 账号 '{args.account}' 已存在，如需修改请直接编辑 accounts.json")
        return

    port = args.port or next_available_port()
    profile_dir = args.profile_dir or f".profiles/{args.account}"

    config["accounts"][args.account] = {
        "nickname": args.nickname or args.account,
        "profile_dir": profile_dir,
        "bridge_port": port,
    }
    if not config.get("default"):
        config["default"] = args.account

    save_config(config)
    print(f"✅ 账号 '{args.account}' 已添加：")
    print(f"   - Profile 目录: {profile_dir}")
    print(f"   - Bridge 端口:  {port}")
    print(f"\n下一步请运行: uv run python scripts/account_manager.py init --account {args.account}")


def cmd_init(args: argparse.Namespace) -> None:
    """初始化账号：启动独立 Chrome 让用户登录小红书，保存 session。"""
    account = get_account(args.account)
    if not account:
        print(f"❌ 未找到账号配置: {args.account}")
        print(f"   请先运行: uv run python scripts/account_manager.py add --account {args.account}")
        sys.exit(1)

    profile_dir = PROJECT_ROOT / account["profile_dir"]
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📋 正在为账号 '{args.account}' 初始化...")
    print("1. Chrome 将以独立窗口打开，只影响这个账号，不影响你的日常 Chrome。")
    print("2. 请在打开的 Chrome 中安装 XHS Bridge 扩展（如尚未安装）。")
    print("3. 请在打开的 Chrome 中登录小红书账号。")
    print("4. 登录完成后，回到这里按回车继续。\n")

    # 先启动 Bridge
    port = account["bridge_port"]
    if not is_bridge_running(port):
        start_bridge(port)
        time.sleep(1)

    # 启动 Chrome
    launch_chrome(profile_dir, url="https://www.xiaohongshu.com/")
    print(f"✅ Chrome 已启动（Profile: {profile_dir}）")

    input("\n⏸  请在 Chrome 中完成登录，然后按回车键继续...")

    # 验证登录状态
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

    print(f"{'账号ID':<16} {'昵称':<16} {'端口':<8} {'Bridge状态':<12} {'默认'}")
    print("-" * 62)
    for name, acc in accounts.items():
        port = acc["bridge_port"]
        running = "✅ 运行中" if is_bridge_running(port) else "⭕ 未启动"
        is_default = "⭐" if name == default else ""
        nickname = acc.get("nickname", "")
        print(f"{name:<16} {nickname:<16} {port:<8} {running:<12} {is_default}")


def cmd_status(args: argparse.Namespace) -> None:
    """查看指定账号的详细状态。"""
    account = get_account(args.account)
    if not account:
        print(f"❌ 未找到账号: {args.account}")
        sys.exit(1)

    port = account["bridge_port"]
    bridge_running = is_bridge_running(port)

    print(f"\n📊 账号 '{args.account}' 状态：")
    print(f"   昵称:         {account.get('nickname', '')}")
    print(f"   Profile 目录: {account['profile_dir']}")
    print(f"   Bridge 端口:  {port}")
    print(f"   Bridge 状态:  {'✅ 运行中' if bridge_running else '⭕ 未启动'}")

    if bridge_running:
        bridge_url = f"ws://localhost:{port}"
        check_cmd = [
            sys.executable,
            str(Path(__file__).parent / "cli.py"),
            f"--bridge-url={bridge_url}",
            "check-login",
        ]
        result = subprocess.run(check_cmd, capture_output=True, text=True)
        try:
            data = json.loads(result.stdout)
            logged_in = data.get("logged_in", False)
            print(f"   登录状态:     {'✅ 已登录' if logged_in else '❌ 未登录'}")
        except Exception:
            print(f"   登录状态:     ⚠️ 检查失败")


def cmd_start_bridge(args: argparse.Namespace) -> None:
    """为指定账号启动 bridge server（前台运行，用于调试）。"""
    account = get_account(args.account)
    if not account:
        print(f"❌ 未找到账号: {args.account}")
        sys.exit(1)

    port = account["bridge_port"]
    if is_bridge_running(port):
        print(f"✅ Bridge server 已在运行（端口 {port}）")
        return

    bridge_script = Path(__file__).parent / "bridge_server.py"
    print(f"🔌 启动 bridge server（端口 {port}）...")
    # 前台运行
    subprocess.run([sys.executable, str(bridge_script), "--port", str(port)])


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
        description="小红书多账号管理器",
    )
    subs = parser.add_subparsers(dest="command", required=True)

    # add
    p = subs.add_parser("add", help="添加新账号配置")
    p.add_argument("--account", required=True, help="账号ID（英文，唯一标识）")
    p.add_argument("--nickname", help="账号昵称（便于识别）")
    p.add_argument("--port", type=int, help="指定 bridge 端口（不填则自动分配）")
    p.add_argument("--profile-dir", help="Chrome Profile 目录（不填则使用 .profiles/<account>）")
    p.set_defaults(func=cmd_add)

    # init
    p = subs.add_parser("init", help="初始化账号（启动 Chrome 引导登录）")
    p.add_argument("--account", required=True, help="账号ID")
    p.set_defaults(func=cmd_init)

    # list
    p = subs.add_parser("list", help="列出所有账号及状态")
    p.set_defaults(func=cmd_list)

    # status
    p = subs.add_parser("status", help="查看指定账号详细状态")
    p.add_argument("--account", required=True)
    p.set_defaults(func=cmd_status)

    # start-bridge
    p = subs.add_parser("start-bridge", help="为指定账号启动 bridge server（前台）")
    p.add_argument("--account", required=True)
    p.set_defaults(func=cmd_start_bridge)

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
