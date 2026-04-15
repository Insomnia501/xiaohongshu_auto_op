import sys
import os
import time
import json
import pyautogui
import pyperclip
import subprocess
from PIL import ImageChops
from pathlib import Path
import subprocess

PROJECT_ROOT = Path(__file__).parent.parent.parent
COORDS_FILE = PROJECT_ROOT / "mac_coords.json"

def record_coords():
    # 在录制坐标前，也必须先执行全屏最大化！否则录制的坐标和运行时彻底对不上！
    activate_app()

    coords = {}
    print("🌟 欢迎进入小红书 Mac 自动化标定模式 (Recorder) 🌟\n")
    print("为确保绝对精准，脚本将记录 5 个核心界面的鼠标物理坐标。")
    print("当倒计时开始时，请将鼠标移动到指定位置，并且**保持不要动**，直到倒计时结束听到提示。")
    print("--------------------------------------------------")

    locations = [
        ("search_box", "步骤 1: 请把鼠标悬停在【顶部搜索框】中心（用来输入小红书号）"),
        ("user_tab", "步骤 2: 随意搜索一个号，然后把鼠标悬停在中间栏的【用户】页签（或者能点进用户主页的位置）"),
        ("user_card", "步骤 3: 把鼠标悬停在搜索出来的【第一个用户头像/名字】上"),
        ("dm_button", "步骤 4: 点进主页，把鼠标悬停在【发私信】按钮中心"),
        ("chat_input", "步骤 5: 点进展信后，把鼠标悬停在底部的【聊天输入框】中心"),
        ("back_arrow", "步骤 6: 【扫尾工作】请把鼠标悬停在左上角的【< 返回小三角】中心（用来退出私信界面）"),
        ("bottom_home", "步骤 7: 【扫尾工作】在退回的前一个界面里，把鼠标悬停在【左下角的首页按钮】中心")
    ]

    for key, description in locations:
        input(f"\n👉 {description}\n准备好了吗？准备好请按回车键开始倒计时...")
        print("开始倒计时：")
        for i in range(10, 0, -1):
            sys.stdout.write(f"\r {i} ...")
            sys.stdout.flush()
            time.sleep(1)
        x, y = pyautogui.position()
        print(f"\n录制成功！[{key}] 坐标 -> X: {x}, Y: {y}")
        coords[key] = {"x": x, "y": y}

    with open(COORDS_FILE, "w") as f:
        json.dump(coords, f, indent=4)
    print(f"\n✅ 所有坐标已成功保存到 {COORDS_FILE}。你现在可以以 run 模式运行了！")

def activate_app():
    print("正在唤起小红书 Mac 客户端 (rednote) 并强行触发原生全屏...")
    script = '''
    tell application "rednote" to activate
    delay 1
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        tell frontApp
            tell window 1
                if (value of attribute "AXFullScreen") is false then
                    set value of attribute "AXFullScreen" to true
                end if
            end tell
        end tell
    end tell
    '''
    p = subprocess.Popen(['osascript', '-'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(script.encode('utf-8'))
    if p.returncode != 0:
        print(f"⚠️ AppleScript 警告: {err.decode('utf-8').strip()}")
        
    print("✅ 已发送原生全屏指令！等待动画完成...")
    time.sleep(2) # 等待 Mac 系统的平滑全屏动画

def click_and_type(coord, text=None, delay=1.0):
    x, y = coord["x"], coord["y"]
    # 瞬间移动并点击
    pyautogui.moveTo(x, y, duration=0.2)
    pyautogui.click()
    time.sleep(0.5)

    if text:
        # 复制文本到剪贴板然后粘贴（避免中文输入法和特殊字符问题）
        pyperclip.copy(text)
        # MacOS 下复制粘贴是 Command + v
        pyautogui.hotkey('command', 'v')
        time.sleep(0.5)
        # 按下回车
        pyautogui.press('enter')

    time.sleep(delay)

def get_screen_diff_ratio(img1, img2):
    """
    Calculate the percentage of pixels that have changed between two screenshots.
    Returns a float between 0.0 and 1.0
    """
    diff = ImageChops.difference(img1, img2)
    diff_img = diff.convert("L")
    
    # Avoid Pillow 14 deprecation warning
    try:
        diff_data = diff_img.get_flattened_data()
    except AttributeError:
        diff_data = diff_img.getdata()
        
    changed_pixels = sum(1 for p in diff_data if p > 30)
    return changed_pixels / len(diff_data)

def vertical_sweep_click(coord, chat_input_coord=None, text=None, delay=2.0, max_attempts=10, step_y=40):
    """
    Smart click feature: Bi-directional vertical sweep to find floating responsive buttons.
    Clicks sequentially around the anchor coord. Evaluates success by comparing screen diff.
    """
    base_x, base_y = coord["x"], coord["y"]
    
    offsets = [0]
    for i in range(1, (max_attempts // 2) + 1):
        offsets.append(i * step_y)
        offsets.append(-i * step_y)
        
    for attempt, offset in enumerate(offsets[:max_attempts]):
        current_y = base_y + offset
        print(f"[{attempt+1}/{max_attempts}] 智能探针：尝试点击私信位置 (X:{base_x}, Y:{current_y})")
        
        img_before = pyautogui.screenshot()
        
        pyautogui.moveTo(base_x, current_y, duration=0.2)
        pyautogui.click()
        time.sleep(delay)  # Wait for page transition
        
        img_after = pyautogui.screenshot()
        
        diff_ratio = get_screen_diff_ratio(img_before, img_after)
        print(f" -> 探测结果：界面像素变化率: {diff_ratio:.2%}")
        
        if diff_ratio > 0.05:
            print("✅ 探测成功！检测到巨大界面变更，极大概率已跨入私信内！")
            if text and chat_input_coord:
                print(" -> 正在点击输入框激活光标...")
                pyautogui.moveTo(chat_input_coord["x"], chat_input_coord["y"], duration=0.2)
                pyautogui.click()
                time.sleep(0.5)
                print(" -> 键入消息内容并发送...")
                pyperclip.copy(text)
                pyautogui.hotkey('command', 'v')
                time.sleep(0.5)
                pyautogui.press('enter')
                time.sleep(1.0)
            return True
        else:
            print(" -> 无效击中（差异率太低）。继续垂直浮动扫描...")
            
    print("❌ 极限扫描结束：未在锚点附近找到任何可交互的入口！")
    return False

def run_dm(target_account, message):
    if not os.path.exists(COORDS_FILE):
        return {"success": False, "error": f"找不到坐标标定文件 {COORDS_FILE}，请先运行: python cli.py dm-record"}

    with open(COORDS_FILE, "r") as f:
        coords = json.load(f)

    # 1. 唤起小红书
    activate_app()

    # 2. 点击搜索框，输入账号并回车
    print(f"正在搜索账号: {target_account}")
    click_and_type(coords["search_box"], text=target_account, delay=2.0)

    # 3. 点击“用户”页签
    print("点击用户页签...")
    click_and_type(coords["user_tab"], delay=1.0)

    # 4. 点击第一个搜索结果卡片
    print("点击第一个用户卡片...")
    click_and_type(coords["user_card"], delay=3.0)

    # 5 & 6. 浮动扫描点击“发私信”按钮，并在成功命中后自动发送文本
    print("启动动态视觉雷达扫描【发私信】按钮...")
    success = vertical_sweep_click(
        coords["dm_button"], 
        chat_input_coord=coords["chat_input"],
        text=message, 
        delay=2.0, 
        max_attempts=12, 
        step_y=35
    )
    
    if success:
        # ================= 状态重置扫尾工作 =================
        print("正在清理页面层级返回首页...")
        if "back_arrow" in coords and "bottom_home" in coords:
            print(" -> 连续点击左上角小三角 5 次返回（确保退出层层叠叠的界面）...")
            for _ in range(5):
                click_and_type(coords["back_arrow"], delay=3.0)

            print(" -> 点击左下角首页按钮重置状态...")
            click_and_type(coords["bottom_home"], delay=1.5)
        else:
            print("⚠️ 未发现完整的重置坐标，为了防丢建议务必重新用 dm-record 将退出的两步录入。")
        # =================================================

        return {"success": True, "message": f"🎉 成功向 {target_account} 发送了自动化私信并且已重置页面！"}
    else:
        return {"success": False, "error": f"⚠️ 送达失败：未能在 {target_account} 主页找到有效的私信按钮入口。"}

def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  标定坐标: python xhs_mac_dm.py record")
        print("  发送私信: python xhs_mac_dm.py run <小红书号> <一段消息>")
        sys.exit(1)

    mode = sys.argv[1]
    if mode == "record":
        record_coords()
    elif mode == "run":
        if len(sys.argv) < 4:
            print("❌ 缺少参数！正确的格式为: python xhs_mac_dm.py run <小红书号> <长消息>")
            sys.exit(1)
        target_account = sys.argv[2]
        message = sys.argv[3]
        run_dm(target_account, message)
    else:
        print("未知的模式！")

if __name__ == "__main__":
    main()
