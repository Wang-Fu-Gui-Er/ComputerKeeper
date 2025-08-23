<div align="center">
<img src="./icon.png" alt="icon"/>
<h1>ComputerKeeper Tool GUI</h1>
</div>


# 这是一个基于Python PyQt5 开发的摸鱼工具

企业微信、钉钉、飞书等办公软件一直会检测电脑在线状态，电脑无操作后会直接显示离开状态，这就让我们很不安心的摸鱼了，于是需要一个工具来保证电脑一直被激活。
其实网上也有很多方法，总归自己想要的功能还得自己设计，闲暇搞一个。

# 功能
0、可视化界面
1、设定一个时间段，让电脑一直保持被唤醒
2、该程序可以挂后台，最小化到托盘
3、勾选周一至周日，牛马没办法还是会加班的
- 勾选的情况：程序一直挂载后台判断是否在设定时间段内
- 不勾选情况：程序仅在当天此次设置中有效，结束时间到了则停止
4、为了不影响正常工作，只有当空闲时候程序才激活
5、通过模拟 `鼠标移动`、`滚轮滑动`、`Shift按下&松开`三种方式随机使用来激活电脑

# 前置工作
**克隆本项目**：`git clone https://github.com/GalokPeng/ComputerKeeper.git`

**安装moudle**
- `pip install PyQt5`
- `pip install pyinstaller`

# 落地

**在项目目录下启动PowerShell**
- `pyinstaller -F -w --icon=icon.ico --add-data "icon.png;." .\ComputerKeeper.py`

# 详细
![截图](https://github.com/GalokPeng/ComputerKeeper/blob/main/img.png)
# 好好工作
# 牛马程序员
