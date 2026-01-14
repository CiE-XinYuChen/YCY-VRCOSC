# **YCY-VRCOSC**

这是与 **VRChat** 游戏联动的役次元 (YCY/YOKONEX) 设备控制程序，通过 VRChat 游戏内的 avatars 互动和其他事件来控制设备的输出。

> **本项目已适配役次元 (YCY) 设备蓝牙直连，无需通过 DG-Lab App 中转。**
>
> 基于 [PyDGLab-WS-for-YCY](https://github.com/CiE-XinYuChen/PyDGLab-WS-for-YCY) 实现蓝牙直连功能。

- **兼容设备**：役次元 (YCY/YOKONEX) 设备，通过蓝牙直连控制。

- **VRChat Avatar 联动功能** ( **OSC**)：

  - **面板控制模式**：通过 VRSuya 的 [SoundPad](https://booth.pm/zh-cn/items/5950846) 进行控制，映射按键到设备功能。同时也支持**远程控制**，你可以通过自己 avatar 上的面板控制其他安装相同面板玩家的设备。

  - **交互控制模式**：支持通过 VRChat 的 Contact 或 Physbones 参数进行控制，让 avatar 之间的交互可以控制设备输出（ 例如触碰或是拉伸动骨）。

  - **ChatBox 显示**：可以通过 VRChat 的 ChatBox 显示当前设备信息。

- [**Terrors of Nowhere**](https://terror.moe/) 游戏联动功能：

  - 游戏内受到伤害会增加设备输出，游戏内死亡会触发死亡惩罚。
  - 通过 [ToNSaveManager](https://github.com/ChrisFeline/ToNSaveManager) 的 WebSocket API 监控游戏事件，需要在游玩 ToN 时运行这个存档软件，并打开设置中的 WebSocket API 服务器。

**补充说明：**

- 面板控制功能需要在 Booth 购买 [声音面板](https://booth.pm/zh-cn/items/5950846) 后将资源导入工程，再导入本项目提供的修改包，将修改包内提供的 prefab 安装到您的 avatar 中。此处的修改包发布已获取 [ VRサウンドパッド ] 原作者授权。
- 如果需要缩短对 ToN 游戏状态的响应时间，可以调整 ToNSaveManager 设置中的 **常规-设置更新速率**，将更新速率设置为 100ms（默认为 1000ms，根据实际情况调整）。


## 快速开始

1. 下载 [release](https://github.com/CiE-XinYuChen/YCY-VRCOSC/releases) 中最新版本的 `YCY-VRCOSC.zip`，解压后运行
2. 打开役次元设备电源，程序会自动扫描并连接附近的设备
3. 连接成功后即可开始使用

> 注意：你需要修改你使用的模型，才能让此程序与游戏中的 avatar 联动。
> ToN 游戏支持不需要修改模型，只需按上面的说明启用 ToNSaveManager 的 WebSocket API 接口即可。

## 与原版 DG-LAB-VRCOSC 的区别

| 特性 | YCY-VRCOSC | DG-LAB-VRCOSC |
|------|-----------|---------------|
| 连接方式 | 蓝牙直连 | 需要 DG-Lab App 中转 |
| 支持设备 | 役次元 (YCY/YOKONEX) | DG-LAB 3.0 |
| 连接步骤 | 开机即连 | 需要扫码连接 App |

## 问题反馈

如果在使用过程中遇到问题，欢迎在 [Issues](https://github.com/CiE-XinYuChen/YCY-VRCOSC/issues) 中提出。

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
