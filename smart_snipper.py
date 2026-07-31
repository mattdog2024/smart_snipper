import os
import time
import tkinter as tk
import threading
import queue
import subprocess
import tempfile
import sys
import winreg
import ctypes
import json

from PIL import ImageGrab, ImageOps, ImageEnhance, ImageTk, Image, ImageDraw

try:
    import mss
except ImportError:
    mss = None

try:
    import pystray
except ImportError:
    pystray = None

# 确保在任何其他系统调用之前设置 DPI 认知，避免缩放错位
try:
    ctypes.windll.user32.SetProcessDPIAware()
except:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# 配置文件路径：使用 %APPDATA% 目录，打包成 exe 后也能持久保存
# ─────────────────────────────────────────────────────────────────────────────
def get_config_path():
    """获取配置文件路径，存放在 %APPDATA%\\SmartSnipper\\ 目录下"""
    app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    config_dir = os.path.join(app_data, "SmartSnipper")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.json")

def load_config():
    config_path = get_config_path()
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {"hotkey_vk": 0x71, "hotkey_mod": 0x4000}  # 默认 F2（系统级独占注册）

def save_config(cfg):
    config_path = get_config_path()
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)
    except:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# Windows 系统级热键注册（RegisterHotKey）
# 原理：就像给自己家门装了专属门铃，只有按你家门铃才响，
#       不会影响邻居（其他软件）的门铃，也不会被邻居的门铃干扰。
# ─────────────────────────────────────────────────────────────────────────────

# 虚拟键码映射表（常用键）
VK_MAP = {
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59,
    "z": 0x5A,
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    "space": 0x20, "enter": 0x0D, "tab": 0x09,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "print": 0x2C, "scroll": 0x91, "pause": 0x13,
    "numpad0": 0x60, "numpad1": 0x61, "numpad2": 0x62, "numpad3": 0x63,
    "numpad4": 0x64, "numpad5": 0x65, "numpad6": 0x66, "numpad7": 0x67,
    "numpad8": 0x68, "numpad9": 0x69,
}

# 修饰键标志
MOD_ALT      = 0x0001
MOD_CTRL     = 0x0002
MOD_SHIFT    = 0x0004
MOD_WIN      = 0x0008
MOD_NOREPEAT = 0x4000  # 防止长按重复触发

HOTKEY_ID = 1  # 热键 ID
DEFAULT_HOTKEY_VK = 0x71  # F2
DEFAULT_HOTKEY_MOD = MOD_NOREPEAT
OLD_DEFAULT_HOTKEY_VK = 0x53  # Ctrl+Shift+S
OLD_DEFAULT_HOTKEY_MOD = MOD_CTRL | MOD_SHIFT | MOD_NOREPEAT
LEGACY_F4_VK = 0x73
LEGACY_F4_MOD = MOD_NOREPEAT

def parse_hotkey_string(hotkey_str):
    """
    将用户输入的热键字符串解析为 (modifiers, vk_code)
    例如: "f4" -> (MOD_NOREPEAT, 0x73)
          "ctrl+shift+a" -> (MOD_CTRL|MOD_SHIFT|MOD_NOREPEAT, 0x41)
    """
    parts = [p.strip().lower() for p in hotkey_str.split("+")]
    mod = MOD_NOREPEAT
    vk = 0
    for part in parts:
        if part == "ctrl":
            mod |= MOD_CTRL
        elif part == "alt":
            mod |= MOD_ALT
        elif part == "shift":
            mod |= MOD_SHIFT
        elif part == "win":
            mod |= MOD_WIN
        else:
            vk = VK_MAP.get(part, 0)
    return mod, vk

def hotkey_to_display_string(mod, vk):
    """将 (mod, vk) 转换为可读字符串，用于显示"""
    parts = []
    if mod & MOD_CTRL:
        parts.append("Ctrl")
    if mod & MOD_ALT:
        parts.append("Alt")
    if mod & MOD_SHIFT:
        parts.append("Shift")
    if mod & MOD_WIN:
        parts.append("Win")
    for name, code in VK_MAP.items():
        if code == vk:
            parts.append(name.upper())
            break
    return "+".join(parts) if parts else "未设置"


class HotkeyListener(threading.Thread):
    """
    在独立线程中运行 Windows 消息循环，监听系统级热键。
    普通组合键使用 RegisterHotKey；单键 F2 使用低级键盘钩子，
    触发截图后吞掉按键，避免当前软件同时收到 F2。
    """
    def __init__(self, on_hotkey_callback):
        super().__init__(daemon=True)
        self.on_hotkey = on_hotkey_callback
        self._hwnd = None
        self._mod = DEFAULT_HOTKEY_MOD
        self._vk = DEFAULT_HOTKEY_VK
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._keyboard_hook = None
        self._f2_down = False

    def run(self):
        WM_HOTKEY = 0x0312
        WM_KEYDOWN = 0x0100
        WM_KEYUP = 0x0101
        WM_SYSKEYDOWN = 0x0104
        WM_SYSKEYUP = 0x0105
        WH_KEYBOARD_LL = 13

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        # ctypes 默认把未声明的返回值当作 32 位 int。在 64 位 Windows 上，
        # HWND/HHOOK/HINSTANCE 会因此被截断，导致热键窗口或键盘钩子失效。
        kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        user32.CreateWindowExW.restype = ctypes.c_void_p
        user32.DefWindowProcW.restype = ctypes.c_ssize_t

        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, ctypes.c_void_p, ctypes.c_uint,
            ctypes.c_size_t, ctypes.c_ssize_t
        )
        LOWLEVELKEYBOARDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, ctypes.c_int, ctypes.c_size_t, ctypes.c_void_p
        )
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int, LOWLEVELKEYBOARDPROC, ctypes.c_void_p, ctypes.c_uint
        ]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.CallNextHookEx.restype = ctypes.c_ssize_t

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", ctypes.c_uint),
                ("scanCode", ctypes.c_uint),
                ("flags", ctypes.c_uint),
                ("time", ctypes.c_uint),
                ("dwExtraInfo", ctypes.c_size_t),
            ]

        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_HOTKEY and wparam == HOTKEY_ID:
                self.on_hotkey()
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        wnd_proc_func = WNDPROC(wnd_proc)

        def keyboard_proc(n_code, wparam, lparam):
            if n_code >= 0:
                key = ctypes.cast(
                    lparam, ctypes.POINTER(KBDLLHOOKSTRUCT)
                ).contents
                with self._lock:
                    exclusive_f2 = (
                        self._vk == DEFAULT_HOTKEY_VK
                        and self._mod == DEFAULT_HOTKEY_MOD
                    )
                if exclusive_f2 and key.vkCode == DEFAULT_HOTKEY_VK:
                    if wparam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        if not self._f2_down:
                            self._f2_down = True
                            self.on_hotkey()
                    elif wparam in (WM_KEYUP, WM_SYSKEYUP):
                        self._f2_down = False
                    return 1
            return user32.CallNextHookEx(
                self._keyboard_hook, n_code, wparam, lparam
            )

        keyboard_proc_func = LOWLEVELKEYBOARDPROC(keyboard_proc)

        class WNDCLASSEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint),
                ("style", ctypes.c_uint),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", ctypes.c_void_p),
                ("hIcon", ctypes.c_void_p),
                ("hCursor", ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p),
                ("lpszMenuName", ctypes.c_wchar_p),
                ("lpszClassName", ctypes.c_wchar_p),
                ("hIconSm", ctypes.c_void_p),
            ]

        hinstance = kernel32.GetModuleHandleW(None)
        class_name = "SmartSnipperHotkeyWnd"

        wc = WNDCLASSEX()
        wc.cbSize = ctypes.sizeof(WNDCLASSEX)
        wc.lpfnWndProc = wnd_proc_func
        wc.hInstance = hinstance
        wc.lpszClassName = class_name

        user32.RegisterClassExW(ctypes.byref(wc))

        hwnd = user32.CreateWindowExW(
            0, class_name, "SmartSnipper Hotkey Window",
            0, 0, 0, 0, 0,
            None, None, hinstance, None
        )
        self._hwnd = hwnd

        self._keyboard_hook = user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, keyboard_proc_func, hinstance, 0
        )

        # 如果独占钩子安装失败，自动回退到 RegisterHotKey。
        # 回退模式不能吞掉前台软件的 F2，但必须保证截图仍然能够触发。
        with self._lock:
            if self._vk and not (
                self._uses_exclusive_f2() and self._keyboard_hook
            ):
                user32.RegisterHotKey(hwnd, HOTKEY_ID, self._mod, self._vk)

        self._ready.set()

        MSG = ctypes.wintypes.MSG
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        user32.UnregisterHotKey(hwnd, HOTKEY_ID)
        if self._keyboard_hook:
            user32.UnhookWindowsHookEx(self._keyboard_hook)
        user32.DestroyWindow(hwnd)

    def _uses_exclusive_f2(self):
        return self._vk == DEFAULT_HOTKEY_VK and self._mod == DEFAULT_HOTKEY_MOD

    def update_hotkey(self, mod, vk):
        """更新热键，线程安全"""
        user32 = ctypes.windll.user32
        self._ready.wait(timeout=3)
        with self._lock:
            if self._hwnd:
                user32.UnregisterHotKey(self._hwnd, HOTKEY_ID)
            self._mod = mod
            self._vk = vk
            if self._hwnd and vk:
                if self._uses_exclusive_f2() and self._keyboard_hook:
                    return True
                result = user32.RegisterHotKey(self._hwnd, HOTKEY_ID, mod, vk)
                return bool(result)
        return False

    def stop(self):
        user32 = ctypes.windll.user32
        if self._hwnd:
            user32.PostMessageW(self._hwnd, 0x0012, 0, 0)  # WM_QUIT


# ─────────────────────────────────────────────────────────────────────────────
# 截图界面
# ─────────────────────────────────────────────────────────────────────────────

class SmartSnipper:
    def __init__(self, root, screen_img):
        self.root = root
        
        user32 = ctypes.windll.user32
        vx = user32.GetSystemMetrics(76)
        vy = user32.GetSystemMetrics(77)
        vw = user32.GetSystemMetrics(78)
        vh = user32.GetSystemMetrics(79)

        self.root.overrideredirect(True)
        self.root.geometry(f"{vw}x{vh}+{vx}+{vy}")
        self.root.attributes("-topmost", True)
        self.root.configure(cursor="cross")
        
        self.canvas = tk.Canvas(root, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.start_x = None
        self.start_y = None
        self.rect = None
        self.rect_image_id = None
        self.x1, self.y1, self.x2, self.y2 = 0, 0, 0, 0

        self.mode = "select"
        self.current_tool = None
        self.last_x = None
        self.last_y = None

        self.pil_image = None
        self.pil_draw = None
        self.active_entry = None
        self.active_entry_pos = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        self.root.bind("<Escape>", self.exit_snip)
        self.root.bind("<Button-3>", self.on_right_click)

        self.original_screen = screen_img
        
        self.enhanced_screen = self.enhance_image(self.original_screen)
        self.dimmed_screen = ImageEnhance.Brightness(self.enhanced_screen).enhance(0.6)
        
        self.bg_image = ImageTk.PhotoImage(self.dimmed_screen)
        self.canvas.create_image(0, 0, image=self.bg_image, anchor="nw")

        self.instruction_text = self.canvas.create_text(
            vw // 2, 50,
            text="拖动鼠标框选截图区域，松开鼠标即可出现工具栏\n(按 ESC 或右键取消)",
            fill="#FF5555", font=("Microsoft YaHei", 20, "bold"), justify="center"
        )
        self.toolbar_frame = None

    def enhance_image(self, img):
        enh = ImageOps.autocontrast(img, cutoff=1)
        enh = ImageEnhance.Brightness(enh).enhance(1.2)
        enh = ImageEnhance.Contrast(enh).enhance(1.1)
        return enh

    def on_button_press(self, event):
        if self.mode == "select":
            self.canvas.delete(self.instruction_text)
            self.start_x = self.canvas.canvasx(event.x)
            self.start_y = self.canvas.canvasy(event.y)
            if not self.rect:
                self.rect = self.canvas.create_rectangle(
                    self.start_x, self.start_y, self.start_x, self.start_y, 
                    outline='#FF3333', width=2, dash=(4, 4)
                )
        elif self.mode == "edit":
            if self.current_tool == "draw":
                self.last_x = self.canvas.canvasx(event.x)
                self.last_y = self.canvas.canvasy(event.y)
            elif self.current_tool == "text":
                cx = self.canvas.canvasx(event.x)
                cy = self.canvas.canvasy(event.y)
                if self.x1 <= cx <= self.x2 and self.y1 <= cy <= self.y2:
                    self.finalize_current_text()
                    self.active_entry = tk.Entry(self.root, font=("Microsoft YaHei", 14), fg="red", bg="white", borderwidth=0)
                    self.active_entry_pos = (cx, cy)
                    window_id = self.canvas.create_window(cx, cy, anchor="nw", window=self.active_entry)
                    self.active_entry.focus_set()
                    self.active_entry.bind("<Return>", lambda e: self.finalize_current_text())
                    self.active_entry.bind("<FocusOut>", lambda e: self.finalize_current_text())

    def finalize_current_text(self):
        if hasattr(self, 'active_entry') and self.active_entry:
            try:
                val = self.active_entry.get()
                cx, cy = self.active_entry_pos
                self.active_entry.destroy()
                self.active_entry = None
                if val:
                    self.canvas.create_text(cx, cy, text=val, fill="red", font=("Microsoft YaHei", 14), anchor="nw")
                    try:
                        from PIL import ImageFont
                        fnt = ImageFont.truetype("msyh.ttc", 18)
                    except:
                        fnt = None
                    self.pil_draw.text((cx - self.x1, cy - self.y1), val, fill="red", font=fnt)
            except tk.TclError:
                self.active_entry = None

    def on_right_click(self, event):
        if self.mode == "select":
            self.exit_snip(event)
        elif self.mode == "edit":
            if hasattr(self, 'active_entry') and self.active_entry:
                try:
                    self.active_entry.destroy()
                except tk.TclError:
                    pass
                self.active_entry = None
            self.set_tool(None)
            self.canvas.config(cursor="arrow")

    def on_move_press(self, event):
        if self.mode == "select" and self.rect:
            cur_x = self.canvas.canvasx(event.x)
            cur_y = self.canvas.canvasy(event.y)
            self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)
            x1, y1 = min(self.start_x, cur_x), min(self.start_y, cur_y)
            x2, y2 = max(self.start_x, cur_x), max(self.start_y, cur_y)
            if x2 - x1 > 0 and y2 - y1 > 0:
                bright_part = self.enhanced_screen.crop((x1, y1, x2, y2))
                self.selection_photo = ImageTk.PhotoImage(bright_part)
                if self.rect_image_id is None:
                    self.rect_image_id = self.canvas.create_image(x1, y1, image=self.selection_photo, anchor="nw")
                else:
                    self.canvas.itemconfig(self.rect_image_id, image=self.selection_photo)
                    self.canvas.coords(self.rect_image_id, x1, y1)
                self.canvas.tag_raise(self.rect)
        elif self.mode == "edit":
            if self.current_tool == "draw" and self.last_x is not None and self.last_y is not None:
                cx = self.canvas.canvasx(event.x)
                cy = self.canvas.canvasy(event.y)
                self.canvas.create_line(self.last_x, self.last_y, cx, cy, fill="red", width=3, capstyle=tk.ROUND, joinstyle=tk.ROUND, smooth=True)
                self.pil_draw.line([(self.last_x - self.x1, self.last_y - self.y1), 
                                    (cx - self.x1, cy - self.y1)], fill="red", width=3, joint="curve")
                self.last_x, self.last_y = cx, cy

    def on_button_release(self, event):
        if self.mode == "select":
            end_x = self.canvas.canvasx(event.x)
            end_y = self.canvas.canvasy(event.y)
            self.x1 = min(self.start_x, end_x)
            self.y1 = min(self.start_y, end_y)
            self.x2 = max(self.start_x, end_x)
            self.y2 = max(self.start_y, end_y)
            if self.x2 - self.x1 > 10 and self.y2 - self.y1 > 10:
                self.mode = "edit"
                self.canvas.config(cursor="arrow")
                self.pil_image = self.enhanced_screen.crop((self.x1, self.y1, self.x2, self.y2))
                self.pil_draw = ImageDraw.Draw(self.pil_image)
                self.toolbar_frame = tk.Frame(self.canvas, bg="#EEEEEE", padx=2, pady=2)
                btn_copy = tk.Button(self.toolbar_frame, text="复制", command=self.do_copy, font=("Microsoft YaHei", 10))
                btn_draw = tk.Button(self.toolbar_frame, text="画笔", command=lambda: self.set_tool('draw'), font=("Microsoft YaHei", 10))
                btn_txt  = tk.Button(self.toolbar_frame, text="文字", command=lambda: self.set_tool('text'), font=("Microsoft YaHei", 10))
                btn_save = tk.Button(self.toolbar_frame, text="保存", command=self.do_save, font=("Microsoft YaHei", 10))
                btn_cncl = tk.Button(self.toolbar_frame, text="取消", command=lambda: self.exit_snip(None), font=("Microsoft YaHei", 10))
                for btn in [btn_copy, btn_draw, btn_txt, btn_save, btn_cncl]:
                    btn.pack(side="left", padx=2)
                self.toolbar_frame.update_idletasks()
                tw = self.toolbar_frame.winfo_reqwidth()
                th = self.toolbar_frame.winfo_reqheight()
                user32 = ctypes.windll.user32
                vw = user32.GetSystemMetrics(78)
                vh = user32.GetSystemMetrics(79)
                place_x = self.x2
                place_y = self.y2 + 5
                if place_x > vw - 5:
                    place_x = vw - 5
                if place_x - tw < 5:
                    place_x = tw + 5
                if place_y + th > vh - 40:
                    place_y = self.y1 - th - 5
                    if place_y < 0:
                        place_y = 5
                self.canvas.create_window(place_x, place_y, anchor="ne", window=self.toolbar_frame)
            else:
                self.canvas.delete(self.rect)
                if self.rect_image_id:
                    self.canvas.delete(self.rect_image_id)
                self.rect = None
                self.rect_image_id = None
                self.start_x, self.start_y = None, None
        elif self.mode == "edit":
            if self.current_tool == "draw":
                self.last_x, self.last_y = None, None

    def set_tool(self, tool_name):
        self.current_tool = tool_name
        if tool_name == "draw":
            self.canvas.config(cursor="crosshair")
        elif tool_name == "text":
            self.canvas.config(cursor="xterm")

    def do_copy(self):
        self.finalize_current_text()
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as f:
            bmp_path = f.name
        self.pil_image.convert("RGB").save(bmp_path, "BMP")
        ps_script = f"Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('{bmp_path}'))"
        subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
        time.sleep(0.3)
        try: os.remove(bmp_path)
        except: pass
        self.exit_snip(None)

    def do_save(self):
        self.finalize_current_text()
        # 保存到桌面，方便找到
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop):
            desktop = os.path.expanduser("~")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"截图_{timestamp}.png"
        filepath = os.path.join(desktop, filename)
        self.pil_image.save(filepath)
        self.exit_snip(None)

    def exit_snip(self, event):
        self.root.destroy()


def capture_screen():
    """优先使用 mss 快速抓取全部显示器，失败时回退到 Pillow。"""
    if mss is not None:
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                shot = sct.grab(monitor)
                return Image.frombytes(
                    "RGB", shot.size, shot.bgra, "raw", "BGRX"
                )
        except Exception:
            pass
    return ImageGrab.grab(all_screens=True)


def take_snip():
    # 不再人为等待；按下快捷键后立即抓屏。
    screen_img = capture_screen()
    root = tk.Tk()
    app = SmartSnipper(root, screen_img)
    root.focus_force()
    root.mainloop()


mutex = None

def check_single_instance():
    global mutex
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "SmartSnipper_Global_Mutex_v1")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

def apply_startup_config():
    try:
        startup_dir = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup")
        vbs_path = os.path.join(startup_dir, "SmartSnipper.vbs")
        if os.path.exists(vbs_path): os.remove(vbs_path)
    except: pass

    if getattr(sys, 'frozen', False):
        startup_cmd = f'"{sys.executable}"'
    else:
        script_path = os.path.abspath(__file__)
        pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
        startup_cmd = f'"{pythonw_path}" "{script_path}"'
        
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "SmartSnipper", 0, winreg.REG_SZ, startup_cmd)
        winreg.CloseKey(key)
    except: pass


def main():
    check_single_instance()
    apply_startup_config()

    config = load_config()
    current_mod = config.get("hotkey_mod", DEFAULT_HOTKEY_MOD)
    current_vk  = config.get("hotkey_vk", DEFAULT_HOTKEY_VK)

    # 确保 MOD_NOREPEAT 标志始终存在（防止长按重复截图）
    current_mod = (current_mod & ~MOD_NOREPEAT) | MOD_NOREPEAT
    needs_f2_migration = (
        (current_vk == LEGACY_F4_VK and current_mod == LEGACY_F4_MOD)
        or
        (current_vk == OLD_DEFAULT_HOTKEY_VK and current_mod == OLD_DEFAULT_HOTKEY_MOD)
    )
    if needs_f2_migration:
        current_mod = DEFAULT_HOTKEY_MOD
        current_vk = DEFAULT_HOTKEY_VK
        config["hotkey_mod"] = current_mod
        config["hotkey_vk"] = current_vk
        save_config(config)

    cmd_queue = queue.Queue()

    # 启动系统级热键监听线程
    hotkey_listener = HotkeyListener(lambda: cmd_queue.put('snip'))
    hotkey_listener.start()
    hotkey_listener._ready.wait(timeout=3)
    hotkey_listener.update_hotkey(current_mod, current_vk)

    def quit_app(icon, item):
        hotkey_listener.stop()
        icon.stop()
        os._exit(0)

    def show_settings(icon, item):
        cmd_queue.put('settings')

    icon = None

    if pystray:
        display_hk = hotkey_to_display_string(current_mod, current_vk)
        icon_img = Image.new('RGB', (64, 64), color=(0, 128, 255))
        d = ImageDraw.Draw(icon_img)
        d.text((12, 10), "Snip", fill=(255, 255, 255))
        icon = pystray.Icon(
            "SmartSnipper",
            icon_img,
            f"智能截图 ({display_hk})",
            menu=pystray.Menu(
                pystray.MenuItem('设置快捷键', show_settings),
                pystray.MenuItem('关闭并退出', quit_app)
            )
        )
        threading.Thread(target=icon.run, daemon=True).start()

    def open_settings_window():
        nonlocal current_mod, current_vk

        settings_root = tk.Tk()
        settings_root.title("设置截图快捷键")
        
        user32 = ctypes.windll.user32
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        w, h = 380, 200
        settings_root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
        settings_root.resizable(False, False)

        tk.Label(
            settings_root,
            text="请输入新的快捷键\n(默认: f2；也支持 ctrl+shift+s / ctrl+alt+a)",
            font=("Microsoft YaHei", 10), justify="center"
        ).pack(pady=12)

        current_display = hotkey_to_display_string(current_mod, current_vk)
        entry = tk.Entry(settings_root, font=("Microsoft YaHei", 13), justify='center')
        entry.pack(pady=5, padx=20, fill='x')
        entry.insert(0, current_display.lower())

        status_label = tk.Label(settings_root, text="", font=("Microsoft YaHei", 9), fg="gray")
        status_label.pack()

        def save():
            nonlocal current_mod, current_vk
            new_str = entry.get().strip()
            if not new_str:
                return
            new_mod, new_vk = parse_hotkey_string(new_str)
            if new_vk == 0:
                status_label.config(text="无法识别按键，请检查输入格式", fg="red")
                return
            if hotkey_listener.update_hotkey(new_mod, new_vk):
                current_mod = new_mod
                current_vk  = new_vk
                config["hotkey_mod"] = current_mod
                config["hotkey_vk"]  = current_vk
                save_config(config)
                if icon:
                    try:
                        icon.title = f"智能截图 ({hotkey_to_display_string(current_mod, current_vk)})"
                    except:
                        pass
                settings_root.destroy()
            else:
                status_label.config(text="注册失败，该快捷键可能已被其他程序占用", fg="red")
                hotkey_listener.update_hotkey(current_mod, current_vk)

        tk.Button(
            settings_root, text="保存设置", command=save,
            font=("Microsoft YaHei", 10), width=15
        ).pack(pady=10)

        settings_root.attributes('-topmost', True)
        settings_root.focus_force()
        settings_root.mainloop()

    while True:
        try:
            msg = cmd_queue.get()
            if msg == 'snip':
                for _ in range(cmd_queue.qsize()):
                    try: cmd_queue.get_nowait()
                    except: pass
                take_snip()
                for _ in range(cmd_queue.qsize()):
                    try: cmd_queue.get_nowait()
                    except: pass
            elif msg == 'settings':
                open_settings_window()
        except KeyboardInterrupt:
            break


if __name__ == '__main__':
    main()
