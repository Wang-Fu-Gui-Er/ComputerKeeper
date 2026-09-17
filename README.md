# ComputerKeeper

> 防止电脑休眠 / 保持企业微信、钉钉等办公软件在线的工具（macOS / Windows）
>
> 本项目扩展自 [GalokPeng/ComputerKeeper](https://github.com/GalokPeng/ComputerKeeper)，在保留原版全部功能的基础上，**新增了 macOS 完整支持**（真实空闲检测、系统级防休眠、原生合成输入），并优化了默认配置与界面显示。

---

## 功能

1. 可视化 GUI 界面（PyQt5）
2. 设定时间段，在指定时间窗内让电脑保持活跃，不掉线
3. 可挂后台，最小化到托盘（右击托盘图标可退出）
4. 勾选周一至周日，只在勾选的日子生效
   - **勾选了星期**：程序长期挂后台，按设定时间窗循环判断
   - **未勾选星期**：仅在当天本次设置内有效，结束时间到即停止
5. 不影响正常工作：只有电脑**空闲达到设定阈值**时才激活
6. 通过模拟 `鼠标移动` 随机微动来刷新系统空闲计时（Windows 原版还会随机使用滚轮、Shift 键）

### macOS 新增支持

| 能力 | 实现 |
|---|---|
| 真实空闲检测 | `CGEventSourceSecondsSinceLastEventType`（等价于 Windows `GetLastInputInfo`），你操作电脑时不会打扰 |
| 系统级防休眠 | 自动启停系统自带 `caffeinate -i -d`（防止空闲休眠与显示器休眠） |
| 原生合成输入 | 用 CGEvent 发布合成鼠标移动事件（等价于 Windows `mouse_event`），被系统计为有效活动 |
| 用户活动暂停 | 你回到电脑前操作时，自动暂停激活，等待再次空闲 |
| 退出兜底 | 程序退出时自动结束 `caffeinate`，不留后台进程 |

### 默认配置

- 间隔时间：30 秒
- 生效时段：09:00 ~ 17:30
- 午休暂停：11:30 ~ 13:15
- 生效日期：周一至周五（周六、日不勾选）
- 空闲触发：3 分钟
- 窗口完全不透明；状态倒计时每秒实时刷新

---

## 环境要求

- Python 3.9+（macOS 系统自带 `/usr/bin/python3` 即 3.9）
- 依赖：`PyQt5`、`pyinstaller`

## 前置工作

**克隆本项目**

```bash
git clone https://github.com/<你的用户名>/ComputerKeeper.git
cd ComputerKeeper
```

**安装依赖（macOS）**

```bash
# 系统自带 Python 3.9，装到用户目录即可
/usr/bin/python3 -m pip install --user PyQt5 pyinstaller
```

> ⚠️ 若你的环境设置了 `PYTHONNOUSERSITE=1`（部分工具会注入该变量），会导致找不到 PyQt5 / PyInstaller。构建与运行时加上 `PYTHONNOUSERSITE=0` 即可（下文命令已带）。

---

## macOS 使用说明

### 一、应用图标

仓库已内置 `icon.icns`（macOS 应用图标），打包时直接使用，**无需自己生成**。

> 仅当你更换了图标素材、需要重新生成 `icon.icns` 时才执行下面步骤。
> 注意：仓库自带的 `icon.png` 实际是 JPEG 格式（原项目历史遗留），需先转成真正的 PNG 再生成：

```bash
sips -s format png icon.png --out icon_real.png

mkdir -p icon.iconset
for s in "16 16" "32 16" "32 32" "64 32" "128 128" "256 128" "256 256" "512 256" "512 512" "1024 512"; do
  set -- $s
  sips -z $1 $1 icon_real.png --out icon.iconset/icon_$2x$2.png >/dev/null
done
iconutil -c icns icon.iconset -o icon.icns
rm -rf icon.iconset
```

### 二、打包

```bash
PYTHONNOUSERSITE=0 pyinstaller -F -w --clean --noconfirm \
  --name ComputerKeeper --icon=icon.icns \
  --add-data "icon.png:." ComputerKeeper.py
```

产物：
- `dist/ComputerKeeper`：单文件可执行程序
- `dist/ComputerKeeper.app`：macOS 应用（推荐）

### 三、运行

```bash
# 方式一：启动应用
open dist/ComputerKeeper.app

# 方式二：直接运行源码（调试用）
PYTHONNOUSERSITE=0 /usr/bin/python3 ComputerKeeper.py
```

### 四、使用

1. 按需调整设置（间隔、起止时间、午休、星期、空闲触发分钟数）
2. 点击 **开始**，窗口可最小化，程序驻留托盘后台运行
3. 状态栏说明：
   - `待机（在时间窗内，距空闲触发还需约 X 秒）`：等待你空闲达到阈值，X 每秒递减
   - `运行中（空闲触发）`：已空闲达标，正在周期模拟活动（`caffeinate` 已启用）
   - `用户活动，已暂停`：你回到电脑前，自动暂停
   - `午休中（暂停执行）`：午休时段不动作
4. 停止：点 **停止**，或托盘图标右键 **退出**

> 说明：倒计时数值 = 空闲阈值 − 当前连续空闲秒数。你在操作电脑时它会停在阈值附近波动，停止操作后开始每秒递减到 0 触发激活，属正常行为。

---

## Windows 使用说明（原版）

**安装依赖**

```powershell
pip install PyQt5
pip install pyinstaller
```

**打包（项目目录下启动 PowerShell）**

```powershell
pyinstaller -F -w --icon=icon.ico --add-data "icon.png;." .\ComputerKeeper.py
```

运行 `dist\ComputerKeeper.exe` 即可。

---

## 常见问题

- **macOS 上动鼠标会不会打扰我工作？**
  不会。只有你空闲超过设定阈值（默认 3 分钟）后才会每 30 秒做一次 1px 微动；你在操作时完全不动。
- **为什么状态数字不递减？**
  该数字是"当前连续空闲秒数到阈值的差值"，你在用电脑时空闲秒数会反复归零，所以数字在阈值附近波动，停止操作后才会每秒递减。
- **打包时报找不到 PyQt5 / PyInstaller？**
  检查是否设置了 `PYTHONNOUSERSITE=1`，用 `PYTHONNOUSERSITE=0` 前缀重试。

---

## 致谢与许可

- 本项目扩展自 [GalokPeng/ComputerKeeper](https://github.com/GalokPeng/ComputerKeeper)，感谢原作者。
- 遵循 [MIT License](LICENSE)。
