# YCY-VRCOSC — YokoNex Fusion Controller for VRChat

![Version](https://img.shields.io/badge/version-v1.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![VRChat](https://img.shields.io/badge/VRChat-OSC-blueviolet)
![Python](https://img.shields.io/badge/Python-3.10%2B-yellow)

**版本**: v1.0.0 · **开发者**: 可乐Shayne · **协议**: MIT  
**源仓库**: [DG-LAB-VRCOSC](https://github.com/ccvrc/DG-LAB-VRCOSC)（改造基础）  
**WebSocket 桥接**: [YokoNex-OpenCLI](https://github.com/CiE-XinYuChen/YokoNex-OpenCLI)

通过 VRChat OSC 接口同时控制多台 **YokoNex YSKJ_TOY_BLE协议设备**（跳蛋、飞机杯、炮机）与 **YokoNex YSKJ_EMS_BLEV2协议设备**（第二代电击器）。无需第三方 App 中转，直接通过 BLE 桥接服务器通信。支持自定义Chatbox消息，深度自定义SoundPad指向功能事件，自定义强度上限等。

---

## 已被验证的支持设备

| 设备型号 | 协议 | 控制量 |
|------|------|--------|
| YCY-FJB-03 榨精机PRO  | YSKJ_TOY_BLE V1.1 | 电机 A / B / C，速度 0–20，模式 1–4 |
| YCY-DJ-V2 电击器2.0 | YSKJ_EMS_BLE V2 | 通道 A / B，强度 0–276，波形 1–17 |

**理论同一协议设备均可支持，如YSKJ_TOY_BLE V1.1协议同样支持 其他版本飞机杯/跳蛋/炮机，但可能电机用途并不同**
多台设备可同时连接，无数量限制。单个按键动作可一次性对多台设备发送指令。

---
## 

## 项目截图
<img width="1072" height="792" alt="148f489e27ca0ff94c2354486a4edf06" src="https://github.com/user-attachments/assets/261c51a1-2d6a-4b0a-95e0-7ed8a85468e4" />
<img width="1072" height="792" alt="d65dedec0478c45be10c83e3a2c4e210" src="https://github.com/user-attachments/assets/0e526070-a3e1-41e9-b816-e28caf2d59fd" />
<img width="1072" height="792" alt="f24018d858cb5bc15ad5ae8edb40aec9" src="https://github.com/user-attachments/assets/9ffa6c63-343a-4824-b762-a5971cc6d39f" />
<img width="492" height="605" alt="c3c9bda4a8ec9d19561cf70d8a5c0d4c" src="https://github.com/user-attachments/assets/2e7b28df-f74e-4c83-be46-8c01f5c20782" />

<img width="1072" height="792" alt="9ab135cd16e0e0b62df9d0d8cf91fc27" src="https://github.com/user-attachments/assets/41f904f0-069e-4e3d-adf3-104d100fca2f" />

```
VRChat ──OSC UDP:9001──► YCY-VRCOSC (本程序)
                               │
                         WebSocket :8765
                               │
                        YokoNex-OpenCLI server
                               │
                       BLE (直连，可多设备)
                          ┌────┴────┐
                        飞机杯   电击器
```

---

## 快速开始
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

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 YokoNex BLE 服务器

```bash
yokonex server
# 或
python main.py server
```

默认监听 `ws://127.0.0.1:8765`。

### 3. 启动本程序

```bash
python src/app.py
```

### 4. 连接流程
1. 下载 Release 中的对应版本，（若无自行版本请自行布置环境）
2. 扫描设备，连接成功后即可开始使用

> 注意：你需要修改你使用的模型，才能让此程序与游戏中的 avatar 联动。

1. **网络配置** 标签页 → 填写服务器地址（默认 `127.0.0.1:8765`）→ 点击 **连接**
2. 点击 **扫描设备** → 下拉选择发现的设备 → 选择类型（toy / estim）→ 点击 **+ 连接**
3. 重复步骤 2 可添加更多设备（toy 和 estim 均可共存）
4. 进入 **面板** 标签页配置按键，或直接点击 **应用预设** 快速填充

---

## 标签页功能总览

### 网络配置

- 填写 YokoNex-OpenCLI WebSocket 服务器地址与端口
- 填写 VRChat OSC 接收端口（默认 9001）
- **扫描设备**：列出附近 BLE 设备，选择后选类型并连接
- **已连接设备列表**：显示所有已连接设备（名称、地址、类型），支持选中后断开
- **云端中继**：勾选后填写 Client Token 与 Agent ID，可通过 YokoNex-Cloud 中继连接远程 BLE 服务器（无需本地直连）
- 语言切换（中文 / English / 日本語）

---

### 面板编辑器

#### 结构

- 3 个页面（页面 1 / 2 / 3），每页 15 个按键（3 行 × 5 列）
- 每个按键可绑定任意数量的**动作**，按住 VRChat SoundPad 按钮时并发执行

#### OSC 映射

| OSC 参数 | 值 | 说明 |
|----------|----|------|
| `/avatar/parameters/SoundPad/Page` | 0 / 1 / 2 | 切换当前页面 |
| `/avatar/parameters/SoundPad/Button/N` | True（按下） | 启动第 N 个按键（Hold 模式） |
| `/avatar/parameters/SoundPad/Button/N` | False（松开） | 停止第 N 个按键 |

**Hold 模式**：按住期间每 ~100ms 执行一次所有循环动作；松开时自动恢复（`fire_channel` 会还原强度到按下前的值）。

#### 按键配置

点击任意按键打开编辑对话框：
- **按键标签**：自定义显示文字
- **动作列表**：添加/删除动作，每条动作包含目标设备、动作类型、参数
- **只执行一次（once）**：勾选后该动作仅在按下瞬间触发一次，不随 Hold 循环重复

#### 支持的动作类型

**飞机杯（toy）**

| 动作 | 参数 | 说明 |
|------|------|------|
| `adjust_speed` | `motor`, `delta` | 相对调速，delta 可为负 |
| `set_speed` | `motor_a`, `motor_b`, `motor_c` | 直接设定各电机速度（0–20） |
| `set_mode` | `motors`, `mode` | 设置模式（1–4） |
| `stop` | — | 所有电机停止 |

**电击器（estim）**

| 动作 | 参数 | 说明 |
|------|------|------|
| `adjust_channel` | `channel`, `delta` | 相对调整强度（受通道上限约束） |
| `fire_channel` | `channel`, `fire_intensity` | 短暂提升强度，松开后自动还原 |
| `set_channel_mode` | `channel`, `mode` | 切换波形（1–17），once |
| `toggle_channel` | `channel` | 开/关指定通道，once |
| `set_channel` | `channel`, `enabled`, `intensity`, `mode`, `freq`, `pulse_us` | 直接设定全部参数 |
| `stop` | — | 停止所有通道 |

**全局**

| 动作 | 说明 |
|------|------|
| `toggle_chatbox` | 开/关 VRChat ChatBox 状态显示，once |

#### 预设功能

顶部预设栏一键填充当前页面：

1. 选择 **预设类型**：DG-LAB 电击 / 飞机杯
2. 选择 **目标**：
   - 电击：通道 A / 通道 B / 通道 AB
   - 飞机杯：马达 A / B / C / AB / AC / BC / ABC
3. 选择 **设备**（留空 = 自动按类型路由）
4. 点击 **应用到此页** — 仅替换当前页面，其余页面不受影响

**飞机杯预设布局（每页）**

| 位置 | 功能 |
|------|------|
| R1C1 | 停止所有电机 |
| R1C2 | 归零（速度 → 0） |
| R1C3 | −2（速度 −2） |
| R1C4 | +2（速度 +2） |
| R1C5 | 全速（速度 → 最大） |
| R2C1 | ChatBox 开/关 |
| R2C2–R2C5 | 模式 1 / 2 / 3 / 4 |

**电击器预设布局（每页）**

| 位置 | 功能 |
|------|------|
| R1C1 | 开/关通道（once） |
| R1C2 | 归零（强度 → 0） |
| R1C3 | −5（强度 −5） |
| R1C4 | +5（强度 +5） |
| R1C5 | +30🔥 急火（松开还原） |
| R2C1 | ChatBox 开/关 |
| R2C2–R2C5 | 波形 1 / 2 / 3 / 4 |
| R3C1–R3C5 | 波形 5 / 6 / 7 / 8 / 9 |

#### 导入 / 导出

- **导出预设**：将当前 3 个页面的全部按键配置保存为 YAML 文件
- **导入预设**：从 YAML 文件加载并覆盖当前面板配置

---

### 控制器

直接通过 GUI 实时控制已连接设备，无需 VRChat OSC。

**飞机杯（每台设备）**

- 电机 A / B / C 各一个速度滑块（0–20）及当前模式显示
- 模式下拉选择（1–4）
- 一键停止

**电击器（每台设备）**

- 通道 A / B 各自：
  - **启用** 复选框
  - **强度滑块**（0 至上限），滑块旁显示当前值
  - **上限（Cap）** 数字框：设置该通道的最大强度（1–276），动态调整滑块范围；`adjust_channel` / `fire_channel` 动作同样受此上限约束
  - **波形** 下拉选择（1–17）
- 一键停止（所有通道）
- 滑块操作带 80ms 防抖，避免快速拖动时向设备发送过多指令

---

### OSC 参数（PhysBone / Contact 映射）

将 Avatar 物理骨骼或接触点的浮点值（0.0–1.0）实时映射到设备速度/强度：

- 每条记录绑定一个 OSC 地址
- 指定目标设备地址（留空 = 按类型匹配所有设备）
- 指定目标类型（toy / estim）
- 勾选目标通道/电机（A / B / C）
- 为每个通道设置独立的映射范围（% min–max），支持反向映射

---

### ChatBox

配置发送到 VRChat 聊天框的实时状态文本：

- 自定义消息模板，使用 `{变量名}` 占位符插入实时数据（速度、强度、电量、模式等）
- 可调节更新间隔（秒）
- 支持一键测试发送
- 可通过 `toggle_chatbox` 动作在按键中开关

---

### 日志

- 运行日志实时显示
- 调试信息面板（控制器状态、设备状态、OSC 事件）

---

### 关于

- 版本号 v1.0.0
- 开发者：可乐Shayne
- 源仓库及依赖项目链接

---

## 多设备路由规则

每个按键动作的设备寻址逻辑：

1. 若指定了 `device_address` → 精确路由到该设备
2. 若留空但指定了 `device_type`（toy / estim）→ 自动路由到第一个匹配类型的已连接设备
3. 两者均为空 → 全局动作（如 `toggle_chatbox`）

预设生成的按键默认留空（自动路由）。应用预设时选择具体设备，会将地址写入该页面所有动作。

---

## 项目结构

```
src/
├── app.py                      主窗口入口
├── fusion_controller.py        多设备融合控制器
│                               （Hold 模式、OSC 处理、强度上限、设备状态追踪）
├── panel_config.py             面板/按键配置数据模型（panels.yml）
│                               （预设生成、PRESET_TARGETS、make_panel_buttons）
├── yokonex_client.py           YokoNex WebSocket 客户端
│                               （websockets 14.x，直连 & 云端中继）
├── config.py                   配置读写（settings.yml）
├── i18n.py                     国际化（中文/英文/日文）
├── version.py                  版本号
├── gui/
│   ├── network_config_tab.py       网络 & 多设备管理（扫描、连接、云端中继）
│   ├── panel_editor_tab.py         面板编辑器（预设 + 按键配置 + 导入导出）
│   ├── button_action_dialog.py     按键动作编辑对话框
│   ├── controller_settings_tab.py  设备实时控制（滑块 + 强度上限 + 防抖）
│   ├── chatbox_tab.py              ChatBox 配置
│   ├── osc_parameters.py           OSC 交互参数映射
│   ├── log_viewer_tab.py           日志 & 调试信息
│   └── about_tab.py                关于
└── locales/
    ├── zh.yml                  中文
    ├── en.yml                  英文
    └── ja.yml                  日文
```

配置文件（与程序同目录）：

| 文件 | 内容 |
|------|------|
| `settings.yml` | 服务器地址、端口、语言等 |
| `panels.yml` | 3 个面板的按键布局与动作 |
| `osc_addresses.yml` | OSC 交互参数映射列表 |

---

## 技术说明

- **Python 3.13 兼容**：WebSocket 使用 websockets 14.x（`websockets.asyncio.client`），规避了旧版 `transfer_data` 后台任务与 Python 3.13 上下文隔离的冲突；所有异步任务均通过 `_spawn` 辅助函数在隔离上下文中创建
- **qasync + PySide6**：Qt 事件循环驱动 asyncio，GUI 操作与设备通信完全异步
- **防抖设计**：电击器强度滑块拖动时每 80ms 才向设备发送一次指令，避免 `data_error`

---

## 使用的开源项目

| 项目 | 协议 |
|------|------|
| [PySide6](https://doc.qt.io/qtforpython/) | LGPL |
| [websockets](https://websockets.readthedocs.io/) | BSD |
| [qasync](https://github.com/CabbageDevelopment/qasync) | MIT |
| [python-osc](https://github.com/attwad/python-osc) | MIT |
| [pyyaml](https://pyyaml.org/) | MIT |
| [colorlog](https://github.com/borntyping/python-colorlog) | MIT |
| [psutil](https://github.com/giampaolo/psutil) | BSD |
| [aiohttp](https://docs.aiohttp.org/) | Apache 2.0 |

---

## 免责声明

本项目为个人开源项目，仅供研究与娱乐使用。请在安全、合理的前提下使用设备，开发者不对任何使用造成的后果负责。
