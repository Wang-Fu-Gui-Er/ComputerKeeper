import sys
import os
import time
import random
import ctypes
import datetime
import subprocess
import atexit
from ctypes import wintypes
from PyQt5 import QtWidgets, QtCore, QtGui

def resource_path(relative_path: str) -> str:
    # PyInstaller 一文件模式下的运行时临时目录在 sys._MEIPASS
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

IS_WINDOWS = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

# Windows 常量与 API
if IS_WINDOWS:
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002

    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_WHEEL = 0x0800
    KEYEVENTF_KEYUP = 0x0002
    VK_SHIFT = 0x10

    WM_INPUT = 0x00FF
    RIDEV_INPUTSINK = 0x00000100
    RIM_TYPEMOUSE = 0
    RIM_TYPEKEYBOARD = 1
    RID_HEADER = 0x10000005

    class RAWINPUTDEVICE(ctypes.Structure):
        _fields_ = [
            ("usUsagePage", wintypes.USHORT),
            ("usUsage", wintypes.USHORT),
            ("dwFlags", wintypes.DWORD),
            ("hwndTarget", wintypes.HWND),
        ]

    class RAWINPUTHEADER(ctypes.Structure):
        _fields_ = [
            ("dwType", wintypes.DWORD),
            ("dwSize", wintypes.DWORD),
            ("hDevice", wintypes.HANDLE),
            ("wParam", wintypes.WPARAM),
        ]

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", POINT),
        ]

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

mac_caffeinate_proc = None


def get_idle_seconds_mac():
    # macOS 原生空闲检测：CGEventSourceSecondsSinceLastEventType
    # 等价于 Windows 的 GetLastInputInfo
    try:
        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double
        cg.CGEventSourceSecondsSinceLastEventType.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
        # kCGEventSourceStateHidSystemState = 1, kCGAnyInputEventType = 0xFFFFFFFF
        return cg.CGEventSourceSecondsSinceLastEventType(1, 0xFFFFFFFF)
    except Exception:
        return 999999.0


def enable_keep_awake():
    global mac_caffeinate_proc
    if IS_WINDOWS:
        kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        )
    elif IS_MAC:
        # 等价于 SetThreadExecutionState：防止空闲休眠与显示器休眠
        try:
            if mac_caffeinate_proc is None or mac_caffeinate_proc.poll() is not None:
                mac_caffeinate_proc = subprocess.Popen(
                    ["caffeinate", "-i", "-d"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception:
            mac_caffeinate_proc = None


def disable_keep_awake():
    global mac_caffeinate_proc
    if IS_WINDOWS:
        kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    elif IS_MAC:
        try:
            if mac_caffeinate_proc is not None:
                mac_caffeinate_proc.kill()
        except Exception:
            pass
        mac_caffeinate_proc = None


def poke_once_mac():
    # macOS 原生模拟输入：随机 鼠标移动(50%) / 滚轮(30%) / Shift(20%)，与 Windows 版行为一致。
    # 合成事件会被系统计为有效活动，从而刷新空闲计时，保持在线状态。
    cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    cg.CGEventCreateMouseEvent.restype = ctypes.c_void_p
    cg.CGEventCreateMouseEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_double * 2, ctypes.c_uint32]
    cg.CGEventCreateScrollWheelEvent.restype = ctypes.c_void_p
    cg.CGEventCreateScrollWheelEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
    cg.CGEventCreateKeyboardEvent.restype = ctypes.c_void_p
    cg.CGEventCreateKeyboardEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_bool]
    cg.CGEventSetFlags.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    cg.CGEventPost.argtypes = [ctypes.c_uint32, ctypes.c_void_p]
    cg.CFRelease.argtypes = [ctypes.c_void_p]

    def post(ev):
        if ev:
            cg.CGEventPost(0, ev)
            cg.CFRelease(ev)

    r = random.random()
    if r < 0.5:
        # 鼠标移动：+1 再回原位（kCGEventMouseMoved=5）
        pos = QtGui.QCursor.pos()  # 真实光标位置（GUI 进程内可用）
        x, y = pos.x(), pos.y()
        for nx, ny in ((x + 1, y + 1), (x, y)):
            pt = (ctypes.c_double * 2)(nx, ny)
            post(cg.CGEventCreateMouseEvent(None, 5, pt, 0))
    elif r < 0.8:
        # 滚轮：下 1 格再上 1 格（kCGScrollEventUnitLine=0）
        for d in (1, -1):
            post(cg.CGEventCreateScrollWheelEvent(None, 0, 1, d, 0, 0))
    else:
        # Shift：按下（带修饰标志）再松开（kVK_Shift=56, kCGEventFlagMaskShift=0x20000）
        down = cg.CGEventCreateKeyboardEvent(None, 56, True)
        up = cg.CGEventCreateKeyboardEvent(None, 56, False)
        cg.CGEventSetFlags(down, 0x20000)
        post(down)
        time.sleep(0.1)
        cg.CGEventSetFlags(up, 0)
        post(up)


atexit.register(disable_keep_awake)

def get_idle_seconds_win32():
    if not IS_WINDOWS:
        return 0.0
    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(lii)
    if not user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0
    tick_now = kernel32.GetTickCount()
    diff = (tick_now - lii.dwTime) & 0xFFFFFFFF
    return diff / 1000.0

class MouseMover(QtWidgets.QWidget):
    def __init__(self):
        super(MouseMover, self).__init__()

        self.setWindowTitle("ComputerKeeper")
        self.setGeometry(100, 100, 520, 440)
        self.setWindowOpacity(1.0)  # 不透明，避免叠窗时看不清文字

        # 设置窗口图标
        app_icon_path = resource_path("icon.png")
        self.setWindowIcon(QtGui.QIcon(app_icon_path))

        row_y = 20
        # 间隔时间
        self.intervalLabel = QtWidgets.QLabel('间隔时间（秒）：', self)
        self.intervalLabel.move(20, row_y)
        self.intervalLineEdit = QtWidgets.QLineEdit(self)
        self.intervalLineEdit.setGeometry(150, row_y - 4, 120, 28)
        self.intervalLineEdit.setPlaceholderText("建议 >= 20")
        self.intervalLineEdit.setText("30")
        self.intervalLineEdit.setValidator(QtGui.QIntValidator(1, 86400, self))

        row_y += 40
        # 开始时间
        self.startLabel = QtWidgets.QLabel('开始时间（HH:MM）：', self)
        self.startLabel.move(20, row_y)
        self.startTimeEdit = QtWidgets.QTimeEdit(self)
        self.startTimeEdit.setGeometry(150, row_y - 4, 120, 28)
        self.startTimeEdit.setDisplayFormat("HH:mm")
        self.startTimeEdit.setTime(QtCore.QTime(9, 0))

        row_y += 40
        # 结束时间
        self.endLabel = QtWidgets.QLabel('结束时间（HH:MM）：', self)
        self.endLabel.move(20, row_y)
        self.endTimeEdit = QtWidgets.QTimeEdit(self)
        self.endTimeEdit.setGeometry(150, row_y - 4, 120, 28)
        self.endTimeEdit.setDisplayFormat("HH:mm")
        self.endTimeEdit.setTime(QtCore.QTime(17, 30))

        row_y += 40
        # 午休时间段
        self.lunchLabel = QtWidgets.QLabel('午休（HH:MM~HH:MM）：', self)
        self.lunchLabel.move(20, row_y)
        self.lunchStartEdit = QtWidgets.QTimeEdit(self)
        self.lunchStartEdit.setGeometry(170, row_y - 4, 90, 28)
        self.lunchStartEdit.setDisplayFormat("HH:mm")
        self.lunchStartEdit.setTime(QtCore.QTime(11, 30))
        self.lunchSepLabel = QtWidgets.QLabel('~', self)
        self.lunchSepLabel.setGeometry(265, row_y, 10, 24)
        self.lunchEndEdit = QtWidgets.QTimeEdit(self)
        self.lunchEndEdit.setGeometry(280, row_y - 4, 90, 28)
        self.lunchEndEdit.setDisplayFormat("HH:mm")
        self.lunchEndEdit.setTime(QtCore.QTime(13, 15))

        row_y += 40
        # 一周 7 天选择（全不选=当天有效）
        self.dayChecks = []
        day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        x_positions_row1 = [20, 90, 160, 230]
        x_positions_row2 = [20, 90, 160]
        for i in range(4):
            cb = QtWidgets.QCheckBox(day_names[i], self)
            cb.setGeometry(x_positions_row1[i], row_y, 60, 24)
            cb.setChecked(True)
            self.dayChecks.append(cb)
        row_y += 30
        for i in range(3):
            cb = QtWidgets.QCheckBox(day_names[4 + i], self)
            cb.setGeometry(x_positions_row2[i], row_y, 60, 24)
            cb.setChecked(True if i == 0 else False)
            self.dayChecks.append(cb)

        row_y += 40
        # 空闲触发
        self.idleLabel = QtWidgets.QLabel('空闲触发（分钟）：', self)
        self.idleLabel.move(20, row_y)
        self.idleMinutesSpin = QtWidgets.QSpinBox(self)
        self.idleMinutesSpin.setGeometry(150, row_y - 4, 120, 28)
        self.idleMinutesSpin.setRange(1, 240)
        self.idleMinutesSpin.setValue(3)

        row_y += 40
        self.startButton = QtWidgets.QPushButton('开始', self)
        self.startButton.setGeometry(20, row_y, 160, 32)
        self.startButton.clicked.connect(self.start_moving)

        self.stopButton = QtWidgets.QPushButton('停止', self)
        self.stopButton.setGeometry(200, row_y, 160, 32)
        self.stopButton.clicked.connect(self.stop_moving)
        self.stopButton.setEnabled(False)

        row_y += 40
        self.statusLabel = QtWidgets.QLabel('状态：待机', self)
        self.statusLabel.setGeometry(20, row_y, 500, 22)

        # 定时器
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._on_timer)

        # 运行状态
        self.running = False
        self.active_mode = False
        self.last_poke_ts = 0.0        # macOS：上次合成微动的时间（区分真实输入用）
        self._next_poke_at = 0.0       # macOS：下次允许微动的时刻（随机间隔）
        self.interval_seconds = 30
        self.start_time = self.startTimeEdit.time()
        self.end_time = self.endTimeEdit.time()
        self.lunch_start = self.lunchStartEdit.time()
        self.lunch_end = self.lunchEndEdit.time()
        self.idle_minutes_threshold = self.idleMinutesSpin.value()

        # “当天有效”模式
        self.no_day_selected = False
        self.anchor_date = None

        # Raw Input
        self.raw_input_registered = False
        self.use_raw_input = False
        self.last_user_input_ts = time.monotonic()

        # 托盘
        self.tray_icon = QtWidgets.QSystemTrayIcon(self)
        self.tray_icon.setIcon(QtGui.QIcon(resource_path("icon.png")))
        self.tray_icon.setVisible(True)

        self.tray_menu = QtWidgets.QMenu(self)
        self.show_action = self.tray_menu.addAction("显示")
        self.show_action.triggered.connect(self.show_window)
        self.exit_action = self.tray_menu.addAction("退出")
        self.exit_action.triggered.connect(self.exit_application)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)

        self._tray_tip_shown = False

        # macOS：点 Dock 图标 / Cmd+Tab 切回时恢复窗口（关闭只是隐藏到托盘，非退出）
        QtWidgets.QApplication.instance().installEventFilter(self)

    # ------------------ UI 控制 ------------------
    def start_moving(self):
        text = self.intervalLineEdit.text().strip()
        if not text:
            QtWidgets.QMessageBox.warning(self, '输入错误', '请输入间隔秒数（数字）')
            return
        try:
            interval = int(text)
            if interval <= 0:
                raise ValueError
        except ValueError:
            QtWidgets.QMessageBox.warning(self, '输入错误', '间隔时间仅可填写数字（> 0）')
            return

        # 读取设置
        self.start_time = self.startTimeEdit.time()
        self.end_time = self.endTimeEdit.time()
        self.lunch_start = self.lunchStartEdit.time()
        self.lunch_end = self.lunchEndEdit.time()
        self.idle_minutes_threshold = max(1, int(self.idleMinutesSpin.value()))
        self.interval_seconds = interval

        # 校验1：开始时间不能大于结束时间（不支持跨午夜）
        if self.start_time > self.end_time:
            QtWidgets.QMessageBox.warning(self, '时间设置错误', '开始时间不能大于结束时间（不支持跨午夜）。')
            return

        # 校验2：开始-结束时长 ≥ 10 分钟 且 ≥ 空闲触发时间
        duration_secs = self.start_time.secsTo(self.end_time)  # 已保证非负
        if duration_secs < 600:
            QtWidgets.QMessageBox.warning(self, '时间设置错误', '开始时间到结束时间的时长不能小于 10 分钟。')
            return
        if duration_secs < self.idle_minutes_threshold * 60:
            QtWidgets.QMessageBox.warning(self, '时间设置错误', '开始-结束时长不能小于空闲触发时间。')
            return

        # 记录“当天有效”模式
        self.no_day_selected = not any(cb.isChecked() for cb in self.dayChecks)
        self.anchor_date = datetime.date.today() if self.no_day_selected else None

        # 若“当天有效”且当前已过结束时间，则不启动
        if self.no_day_selected and self._is_session_finished_for_no_day_selected():
            self.running = False
            self.active_mode = False
            self.statusLabel.setText("状态：当天结束时间已到，未开始（请明天或重新设置后再开始）")
            return

        # 进入运行：时间窗内立即启动防休眠（不等空闲达标，防止系统先睡眠/锁屏）
        self.running = True
        self.active_mode = False
        if IS_MAC and self._is_in_time_window_now():
            enable_keep_awake()

        # UI 状态
        self.startButton.setEnabled(False)
        self.stopButton.setEnabled(True)
        self.intervalLineEdit.setEnabled(False)
        self.startTimeEdit.setEnabled(False)
        self.endTimeEdit.setEnabled(False)
        self.lunchStartEdit.setEnabled(False)
        self.lunchEndEdit.setEnabled(False)
        for cb in self.dayChecks:
            cb.setEnabled(False)
        self.idleMinutesSpin.setEnabled(False)
        self.statusLabel.setText(self._waiting_status_text())

        if not self._tray_tip_shown:
            try:
                self.tray_icon.showMessage(
                    "ComputerKeeper",
                    "程序已在后台运行：达到设置的时间窗与（若选择）日期，并在空闲达阈值后自动执行。\n午休时段暂停执行（非结束）。\n未选择星期时：当天结束时间到后自动停止，需要手动重新开始。",
                    QtWidgets.QSystemTrayIcon.Information,
                    6000
                )
                self._tray_tip_shown = True
            except Exception:
                pass

        self._schedule_next()

    def stop_moving(self):
        if not self.running and not self.active_mode:
            return
        self.running = False
        self.active_mode = False
        self.timer.stop()
        disable_keep_awake()

        self.startButton.setEnabled(True)
        self.stopButton.setEnabled(False)
        self.intervalLineEdit.setEnabled(True)
        self.startTimeEdit.setEnabled(True)
        self.endTimeEdit.setEnabled(True)
        self.lunchStartEdit.setEnabled(True)
        self.lunchEndEdit.setEnabled(True)
        for cb in self.dayChecks:
            cb.setEnabled(True)
        self.idleMinutesSpin.setEnabled(True)
        self.statusLabel.setText("状态：已停止")

    # ------------------ 时间/日期判断 ------------------
    def _is_day_allowed(self, dt: datetime.datetime) -> bool:
        if self.no_day_selected:
            return dt.date() == self.anchor_date
        wd = dt.weekday()  # 周一=0, 周日=6
        return self.dayChecks[wd].isChecked()

    def _is_in_time_window_now(self) -> bool:
        # 不支持跨午夜：开始 <= 结束
        now = datetime.datetime.now()
        now_time = QtCore.QTime.currentTime()
        start_t = self.start_time
        end_t = self.end_time
        in_window = (now_time >= start_t and now_time < end_t)
        return in_window and self._is_day_allowed(now)

    def _is_in_lunch_break_now(self) -> bool:
        s = self.lunch_start
        e = self.lunch_end
        if s == e:
            return False
        now_t = QtCore.QTime.currentTime()
        if s <= e:
            return s <= now_t < e
        else:
            # 允许设置跨午夜午休，但一般不需要
            return (now_t >= s) or (now_t < e)

    def _is_session_finished_for_no_day_selected(self) -> bool:
        # 当天有效：当天到点即结束；不考虑跨午夜（已禁止）
        if not self.no_day_selected or self.anchor_date is None:
            return False
        now = datetime.datetime.now()
        today = now.date()
        now_t = QtCore.QTime.currentTime()
        if today > self.anchor_date:
            return True
        if today == self.anchor_date and now_t >= self.end_time:
            return True
        return False

    # ------------------ 定时与逻辑 ------------------
    def _schedule_next(self):
        if not self.running:
            return
        if self.no_day_selected and self._is_session_finished_for_no_day_selected():
            self.timer.stop()
            return
        if not self._is_in_time_window_now():
            delay_ms = 60000
        elif self._is_in_lunch_break_now():
            delay_ms = 60000
        elif not self.active_mode:
            delay_ms = 1000
        else:
            if IS_MAC:
                delay_ms = 1000  # macOS：每秒检查活动，到点才微动
            else:
                base = max(self.interval_seconds, 3)
                factor = random.uniform(0.7, 1.3)
                delay_ms = int(base * factor * 1000)
        self.timer.start(delay_ms)

    def _on_timer(self):
        if not self.running:
            return

        if IS_MAC:
            # 时间窗内全程防休眠（含午休）：空闲达标前就阻止系统睡眠/锁屏
            if self._is_in_time_window_now():
                enable_keep_awake()
            else:
                disable_keep_awake()

        if self.no_day_selected and self._is_session_finished_for_no_day_selected():
            self.stop_moving()
            self.statusLabel.setText("状态：当天结束时间已到，已停止（请重新开始）")
            return

        if not self._is_in_time_window_now():
            if self.active_mode:
                self.active_mode = False
            self.statusLabel.setText(self._waiting_status_text())
            self._schedule_next()
            return

        if self._is_in_lunch_break_now():
            if self.active_mode:
                self.active_mode = False
            self.statusLabel.setText("状态：午休中（暂停执行）")
            self._schedule_next()
            return

        if not self.active_mode:
            idle_secs = self._get_idle_seconds()
            if idle_secs >= self.idle_minutes_threshold * 60:
                self.active_mode = True
                enable_keep_awake()
                self.statusLabel.setText("状态：运行中（空闲触发）")
                self._poke_once()
            else:
                left = max(0, self.idle_minutes_threshold * 60 - int(idle_secs))
                self.statusLabel.setText(f"状态：待机（在时间窗内，距空闲触发还需约 {left} 秒）")
        else:
            if IS_MAC:
                now = time.monotonic()
                # 自己的合成事件也会清零空闲计时，需与真实输入区分：
                # 距上次微动已超 5 秒时空闲仍 < 5 秒，说明是真实用户活动
                if self._get_idle_seconds() < 5 and now - self.last_poke_ts > 5:
                    self._on_user_activity()
                    return
                if now >= self._next_poke_at:
                    self._poke_once()
            else:
                self._poke_once()

        self._schedule_next()

    def _waiting_status_text(self) -> str:
        start_str = self.start_time.toString("HH:mm")
        end_str = self.end_time.toString("HH:mm")
        lunch_str = f"{self.lunch_start.toString('HH:mm')}~{self.lunch_end.toString('HH:mm')}"
        day_names = ["周一","周二","周三","周四","周五","周六","周日"]
        selected = [name for i, name in enumerate(day_names) if self.dayChecks[i].isChecked()]
        if self.no_day_selected:
            day_str = "当天"
        else:
            day_str = "、".join(selected) if selected else "未选择日期"
        return f"状态：待机（等待 {day_str} 的 {start_str}~{end_str} 时间窗，午休 {lunch_str} 暂停）"

    def _poke_once(self):
        r = random.random()
        try:
            if IS_WINDOWS:
                if r < 0.5:
                    user32.mouse_event(MOUSEEVENTF_MOVE, 1, 1, 0, 0)
                    user32.mouse_event(MOUSEEVENTF_MOVE, -1, -1, 0, 0)
                elif r < 0.8:
                    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, 120, 0)
                    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, -120, 0)
                else:
                    user32.keybd_event(VK_SHIFT, 0, 0, 0)
                    user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
            elif IS_MAC:
                poke_once_mac()
            else:
                pos = QtGui.QCursor.pos()
                QtGui.QCursor.setPos(pos.x() + 1, pos.y() + 1)
                QtGui.QCursor.setPos(pos)
        except Exception:
            pos = QtGui.QCursor.pos()
            QtGui.QCursor.setPos(pos.x() + 1, pos.y() + 1)
            QtGui.QCursor.setPos(pos)
        self.last_poke_ts = time.monotonic()
        self._next_poke_at = self.last_poke_ts + max(self.interval_seconds, 3) * random.uniform(0.7, 1.3)

    # ------------------ 空闲检测 ------------------
    def _get_idle_seconds(self):
        if IS_WINDOWS and self.use_raw_input:
            return max(0.0, time.monotonic() - self.last_user_input_ts)
        elif IS_WINDOWS:
            return get_idle_seconds_win32()
        elif IS_MAC:
            return get_idle_seconds_mac()
        else:
            return 999999.0

    def _on_user_activity(self):
        self.last_user_input_ts = time.monotonic()
        if self.running and self.active_mode:
            self.active_mode = False
            self.statusLabel.setText("状态：用户活动，已暂停（等待再次空闲）")
            self.timer.stop()
            self.timer.start(5000)

    # ------------------ Raw Input ------------------
    def _register_raw_input(self):
        if not IS_WINDOWS:
            return False
        try:
            hwnd = int(self.winId())
            devices = (RAWINPUTDEVICE * 2)()
            devices[0].usUsagePage = 0x01
            devices[0].usUsage = 0x02
            devices[0].dwFlags = RIDEV_INPUTSINK
            devices[0].hwndTarget = hwnd
            devices[1].usUsagePage = 0x01
            devices[1].usUsage = 0x06
            devices[1].dwFlags = RIDEV_INPUTSINK
            devices[1].hwndTarget = hwnd
            if not user32.RegisterRawInputDevices(ctypes.byref(devices), 2, ctypes.sizeof(RAWINPUTDEVICE)):
                return False
            return True
        except Exception:
            return False

    def nativeEvent(self, eventType, message):
        if IS_WINDOWS and eventType == "windows_generic_MSG":
            msg = MSG.from_address(int(message))
            if msg.message == WM_INPUT:
                size = wintypes.UINT(0)
                user32.GetRawInputData(msg.lParam, RID_HEADER, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                if size.value:
                    buf = ctypes.create_string_buffer(size.value)
                    if user32.GetRawInputData(msg.lParam, RID_HEADER, buf, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER)) == size.value:
                        header = RAWINPUTHEADER.from_buffer_copy(buf)
                        if header.dwType in (RIM_TYPEMOUSE, RIM_TYPEKEYBOARD):
                            self._on_user_activity()
        return False, 0

    # ------------------ 窗口与托盘 ------------------
    def closeEvent(self, event):
        event.ignore()
        self.hide()
        if not self._tray_tip_shown:
            try:
                self.tray_icon.showMessage(
                    "ComputerKeeper",
                    "程序已最小化到托盘，仍会在后台按设置运行（午休时间暂停）。\n右击托盘图标可退出。",
                    QtWidgets.QSystemTrayIcon.Information,
                    6000
                )
                self._tray_tip_shown = True
            except Exception:
                pass

    def showEvent(self, event):
        if IS_WINDOWS and not self.raw_input_registered:
            self.raw_input_registered = True
            ok = self._register_raw_input()
            self.use_raw_input = ok
            self.last_user_input_ts = time.monotonic()
        self.tray_icon.setVisible(True)
        event.accept()

    def hideEvent(self, event):
        self.tray_icon.setVisible(True)
        event.accept()

    def tray_icon_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show()

    def eventFilter(self, obj, event):
        if IS_MAC and event.type() == QtCore.QEvent.ApplicationActivate:
            if self.isHidden():
                self.show()
                self.raise_()
                self.activateWindow()
        return super(MouseMover, self).eventFilter(obj, event)

    def show_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def exit_application(self):
        self.stop_moving()
        QtWidgets.QApplication.quit()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    # 设置应用图标（任务栏等处）
    app.setWindowIcon(QtGui.QIcon(resource_path("icon.png")))
    window = MouseMover()
    window.show()
    sys.exit(app.exec_())

