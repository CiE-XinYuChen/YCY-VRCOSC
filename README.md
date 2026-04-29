# YCY-VRCOSC

通过 VRChat OSC 接口控制 **YokoNex 飞机杯**（YSKJ_TOY_BLE V1.1）的 A / B / C 三路电机。  
本项目基于 [YokoNex-OpenCLI](https://github.com/CiE-XinYuChen/YokoNex-OpenCLI) 提供的 WebSocket 桥接服务与设备通信，无需任何第三方 App 中转。

---

## 支持设备

| 设备 | 型号 | 电机 |
|------|------|------|
| 飞机杯 | YSKJ_TOY_BLE V1.1 | A / B / C（速度 0-20） |

---

## 架构

```
VRChat ──OSC UDP:9001──► YCY-VRCOSC
                               │
                         WebSocket :8765
                               │
                        YokoNex-OpenCLI server
                               │
                            BLE (直连)
                               │
                          飞机杯设备
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 YokoNex BLE 服务器

在 **YokoNex-OpenCLI** 项目目录下：

```bash
yokonex server
# 或
python main.py server
```

服务器默认监听 `ws://127.0.0.1:8765`。

### 3. 启动本程序

```bash
python src/app.py
```

### 4. 连接流程

1. **网络配置** 标签页 → 填写 YokoNex 服务器地址（默认 `127.0.0.1:8765`）→ 点击 **连接**
2. 点击 **扫描设备** → 从下拉列表选择飞机杯
3. 点击 **连接设备**
4. 在 VRChat 中打开 SoundPad 面板，开始控制

---

## OSC 接口说明

### SoundPad 面板控制

| 参数 | 值 | 说明 |
|------|----|------|
| `SoundPad/Page` | 0 | 控制电机 **A** |
| `SoundPad/Page` | 1 | 控制电机 **B** |
| `SoundPad/Page` | 2 | 控制电机 **C** |
| `SoundPad/Button/1` | 按下 | 循环切换模式（1→2→3→4→1） |
| `SoundPad/Button/2` | 按下 | 当前电机停止（速度 = 0） |
| `SoundPad/Button/3` | 按下 | 速度 − 步进 |
| `SoundPad/Button/4` | 按下 | 速度 + 步进 |
| `SoundPad/Button/5` | 长按/松开 | 一键开火（松手恢复原速度） |
| `SoundPad/Button/6` | 按下 | 切换 ChatBox 状态显示 |
| `SoundPad/Button/7~10` | 按下 | 直接设置模式 1~4 |
| `SoundPad/Volume` | 0.0~1.0 | 设置开火步进值 |

### 交互参数（PhysBone / Contact）

在 **OSC 参数** 标签页自定义地址，将 VRChat Avatar 的物理骨骼值（0.0~1.0）映射到指定电机速度范围。  
每条地址可独立绑定 A / B / C 任意电机，并设置各自的速度映射区间（%）。

---

## ChatBox 格式

```
[A] A:10 B:5 C:0 M:2
```

- `[A]` — 当前 SoundPad 选中的电机
- `A/B/C:数字` — 各电机当前速度（0-20）
- `M:数字` — 当前选中电机的模式（1-4）

---

## 项目结构

```
src/
├── app.py                  主窗口入口
├── toy_controller.py       飞机杯控制器（命令队列、OSC 处理）
├── yokonex_client.py       YokoNex WS 客户端
├── command_types.py        命令优先级定义
├── config.py               配置读写
├── i18n.py                 国际化
├── gui/
│   ├── network_config_tab.py     网络 & 设备连接
│   ├── controller_settings_tab.py 电机控制 UI
│   ├── osc_parameters.py          OSC 地址映射配置
│   ├── log_viewer_tab.py          日志 & 调试
│   └── about_tab.py               关于
└── locales/
    ├── zh.yml
    ├── en.yml
    └── ja.yml
```

---

## 命令优先级

| 来源 | 优先级 | 冷却 |
|------|--------|------|
| GUI 滑块 | 最高 | 无 |
| SoundPad 按钮 | 中 | 100ms |
| PhysBone 交互 | 低 | 50ms |

---

## 依赖

| 包 | 用途 |
|----|------|
| PySide6 | GUI |
| qasync | Qt + asyncio 集成 |
| websockets | YokoNex WS 通信 |
| python-osc | 接收 VRChat OSC |
| pyyaml | 配置文件 |
| psutil | 网卡枚举 |

---

## 免责声明

本项目仅供个人研究与娱乐使用。请确保在安全、合理的前提下使用设备，作者不对任何使用造成的后果负责。
