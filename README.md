# **YCY-VRCOSC**
这是与 **VRChat** 游戏联动的役次元 (YCY/YOKONEX) 设备控制程序，通过 VRChat 游戏内的 avatars 互动和其他事件来控制设备的输出。

> 基于 [PyDGLab-WS-for-YCY](https://github.com/CiE-XinYuChen/PyDGLab-WS-for-YCY) 实现电击器功能， [YokoNex-OpenCLI](https://github.com/CiE-XinYuChen/YokoNex-OpenCLI) 实现飞机杯功能，后续电击器将迁移到该协议
> main分支支持电击器一代，DJJ-2.0分支支持电击器2代，ZJJPRO支持榨精机PRO设备，理论支持所有Yokonex的跳蛋/飞机杯设备，使用可能略有差异。

- **VRChat Avatar 联动功能** ( **OSC**)：
  - **面板控制模式**：通过 VRSuya 的 [SoundPad](https://booth.pm/zh-cn/items/5950846) 进行控制，映射按键到设备功能。同时也支持**远程控制**，你可以通过自己 avatar 上的面板控制其他安装相同面板玩家的设备。
  - **交互控制模式**：支持通过 VRChat 的 Contact 或 Physbones 参数进行控制，让 avatar 之间的交互可以控制设备输出（ 例如触碰或是拉伸动骨）。
  - **ChatBox 显示**：可以通过 VRChat 的 ChatBox 显示当前设备信息。

**补充说明：**
- 面板控制功能需要在 Booth 购买 [声音面板](https://booth.pm/zh-cn/items/5950846) 后将资源导入工程，再导入本项目提供的修改包，将修改包内提供的 prefab 安装到您的 avatar 中。


## 快速开始

1. 下载 Release 中的对应版本，（若无自行版本请自行布置环境）
2. 扫描设备，连接成功后即可开始使用

> 注意：你需要修改你使用的模型，才能让此程序与游戏中的 avatar 联动。

## 注意事项

 1. 本程序及开发者不对使用该本程序产生的**任何后果**负责，使用程序则视为同意本条款。
 2. 请以安全的方式使用设备，使用此程序前请根据个人情况设置合理的强度上限。
 3. 本程序大部分代码使用 LLM 生成，未经过充分的测试！使用时请注意风险！

## 界面说明

> 以下是 v0.1 版本程序的界面

程序界面：
![DG-LAB-VRCOSC-MainUI-CN.png](docs%2Fassets%2FDG-LAB-VRCOSC-MainUI-CN.png)

SoundPad 控制面板界面：
![DG-LAB-VRCOSC-SoundPad-CN.png](docs%2Fassets%2FDG-LAB-VRCOSC-SoundPad-CN.png)

VRChat 游戏内轮盘菜单：
![DG-LAB-VRCOSC-VRChatMenu-CN.png](docs%2Fassets%2FDG-LAB-VRCOSC-VRChatMenu-CN.png)

## About

这个程序一开始只是为了做下面图片中的事情（画的好棒），后来想更完善些就加上了 UI 和 ToN 游戏的支持。

<div style="display: flex; align-items: center;">
    <img src="docs/images/dg-lab-start.png" alt="dg-lab-start" style="height: 450px; margin-right: 10px;">
    <img src="docs/images/misaka-h.png" alt="misaka-h" style="height: 450px;">
</div>
Artworks by Wanlin


## 相关项目

- [PyDGLab-WS-for-YCY](https://github.com/CiE-XinYuChen/PyDGLab-WS-for-YCY) - 役次元设备蓝牙直连 Python 库
- [DG-LAB-VRCOSC](https://github.com/ccvrc/DG-LAB-VRCOSC) - 原版 DG-Lab 控制程序

## 许可证

本项目使用 GPL-3.0 许可证。
