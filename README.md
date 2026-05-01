# YCY-VRCOSC — YokoNex Fusion Controller for VRChat

**版本**: v1.0.0 · **开发者**: 可乐Shayne · **协议**: MIT

基于 [DG-LAB-VRCOSC](https://github.com/ccvrc/DG-LAB-VRCOSC) 改造，通过 VRChat OSC 接口同时控制多台 **YokoNex 飞机杯**（电机 A/B/C）与 **DG-LAB 电击器**（通道 A/B）。  
WebSocket 桥接由 [YokoNex-OpenCLI](https://github.com/CiE-XinYuChen/YokoNex-OpenCLI) 提供，无需第三方 App 中转。

---

## 支持设备

| 设备 | 型号 | 控制量 |
|------|------|--------|
| 飞机杯 | YSKJ_TOY_BLE V1.1 | 电机 A / B / C，速度 0–20，模式 1–4 |
| 电击器 | DG-LAB | 通道 A / B，强度 0–276，波形 1–17 |

多台设备可同时连接，单个按键动作可一次性对多台设备发送指令。

---

## 架构

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

1. **网络配置** → 填写服务器地址（默认 `127.0.0.1:8765`）→ 点击 **连接**
2. 点击 **扫描设备** → 下拉选择设备 → 选择类型（toy / estim）→ 点击 **+ 连接**
3. 重复步骤 2 添加更多设备（无数量限制）
4. 进入 **面板** 标签页配置按键，或直接应用内置预设

---

## 面板系统

### 面板结构

3 个页面（页面 1 / 2 / 3），每页 15 个按键（3 行 × 5 列）。  
每个按键可绑定任意数量的**动作**，按住 VRChat SoundPad 按钮时并发执行。

### OSC 映射

| OSC 参数 | 值 | 说明 |
|----------|----|------|
| `/avatar/parameters/SoundPad/Page` | 0 / 1 / 2 | 切换当前页面 |
| `/avatar/parameters/SoundPad/Button/N` | True（按下） | 启动第 N 个按键（Hold 模式持续触发） |
| `/avatar/parameters/SoundPad/Button/N` | False（松开） | 停止第 N 个按键 |

**Hold 模式**：按住期间每 ~100ms 执行一次所有动作；松开时自动恢复（`fire_channel` 会还原强度）。

### 支持的动作类型

#### 飞机杯（toy）

| 动作 | 参数 | 说明 |
|------|------|------|
| `adjust_speed` | `motor`, `delta` | 相对调速，delta 可为负（预设步长 ±2） |
| `set_speed` | `motor_a/b/c` | 直接设定各电机速度（0–20） |
| `set_mode` | `motors`, `mode` | 设置模式（1–4） |
| `stop` | — | 所有电机停止 |

#### 电击器（estim）

| 动作 | 参数 | 说明 |
|------|------|------|
| `adjust_channel` | `channel`, `delta` | 相对调整强度（受通道上限约束） |
| `fire_channel` | `channel`, `fire_intensity` | 短暂提升强度，松开自动恢复 |
| `set_channel_mode` | `channel`, `mode` | 切换波形（1–17） |
| `toggle_channel` | `channel` | 开/关通道 |
| `set_channel` | `channel`, `intensity`, `mode`, … | 直接设定全部参数 |
| `stop` | — | 停止所有通道 |

#### 全局

| 动作 | 说明 |
|------|------|
| `toggle_chatbox` | 开/关 VRChat ChatBox 状态显示 |

### once 模式

在动作上标记 `once: true`：按键按下时只执行一次（不随 Hold 循环），用于切换波形、开关通道等单次操作。

---

## 预设功能

面板页内置快速预设，一键填充当前页面的按键布局。

### 使用方法

1. 在 **面板** 标签页顶部选择 **预设类型**（DG-LAB 电击 / 飞机杯）
2. 选择 **目标通道/电机**（如 通道 AB、马达 AC、马达 ABC 等）
3. 选择 **设备**（留空 = 自动按类型路由）
4. 点击 **应用到此页** — 仅替换当前页面，其他页面不受影响

### 飞机杯预设布局（每页）

| 位置 | 功能 |
|------|------|
| R1C1 停止 | 停止所有电机 |
| R1C2 归零 | 速度降至 0 |
| R1C3 −2 | 速度 −2 |
| R1C4 +2 | 速度 +2 |
| R1C5 全速 | 速度升至最大 |
| R2C1 ChatBox | 开/关状态显示 |
| R2C2–R2C5 | 模式 1 / 2 / 3 / 4 |

### 电击器预设布局（每页）

| 位置 | 功能 |
|------|------|
| R1C1 模式 | 开/关通道（once） |
| R1C2 归零 | 强度降至 0 |
| R1C3 −5 | 强度 −5 |
| R1C4 +5 | 强度 +5 |
| R1C5 +30🔥 | 急火 +30（松开还原） |
| R2C1 ChatBox | 开/关状态显示 |
| R2C2–R2C5 | 波形 1 / 2 / 3 / 4 |
| R3C1–R3C5 | 波形 5 / 6 / 7 / 8 / 9 |

---

## 控制器标签页

直接通过 GUI 控制已连接设备，无需 VRChat OSC。

### 飞机杯控制

- 每个电机（A/B/C）独立滑块控制速度（0–20）
- 模式下拉选择（1–4）
- 一键停止

### 电击器控制

- 每通道（A/B）独立强度滑块（0–276）
- **上限（Cap）**：可为每个通道单独设置强度上限，滑块范围动态调整；`adjust_channel` 和 `fire_channel` 动作同样受此上限约束
- 模式下拉选择（波形 1–17）
- 一键停止（所有通道）

---

## OSC 交互参数（PhysBone / Contact）

在 **OSC 参数** 标签页，将 Avatar 物理骨骼值（0.0–1.0）映射到设备速度/强度：

- 每条记录绑定一个 OSC 地址
- 可指定目标设备（留空 = 按类型匹配所有）、目标类型（toy / estim）
- 勾选目标通道（A / B / C），并为每个通道设置独立的映射范围（% min–max）

---

## ChatBox 状态显示

**ChatBox** 标签页配置发送到 VRChat 聊天框的实时状态文本：

- 可自定义消息模板，使用 `{变量名}` 占位符插入实时数据
- 可调节更新间隔（秒）
- 支持一键测试发送

---

## 多设备路由

- 每个按键动作可指定 `device_address`（精确路由）或留空
- 留空时按 `device_type`（toy / estim）自动路由到第一个匹配设备
- 预设生成的按键默认留空（自动路由），使用"应用预设"时可指定具体设备覆盖

---

## 云端中继（Cloud Relay）

在网络配置页勾选"通过云端中继连接"，填写 Client Token 与 Agent ID 即可通过 YokoNex-Cloud 中继连接远程 BLE 服务器，无需本地直连。

---

## 项目结构

```
src/
├── app.py                      主窗口入口
├── fusion_controller.py        多设备融合控制器（Hold 模式、OSC 处理、强度上限）
├── panel_config.py             面板/按键配置数据模型（panels.yml）
├── yokonex_client.py           YokoNex WebSocket 客户端（websockets 14.x）
├── config.py                   配置读写（settings.yml）
├── i18n.py                     国际化（中文/英文/日文）
├── version.py                  版本号
├── gui/
│   ├── network_config_tab.py       网络 & 多设备管理
│   ├── panel_editor_tab.py         面板编辑器（预设 + 按键配置）
│   ├── button_action_dialog.py     按键动作编辑对话框
│   ├── controller_settings_tab.py  设备实时控制（含电击器强度上限）
│   ├── chatbox_tab.py              ChatBox 配置
│   ├── osc_parameters.py           OSC 交互参数映射
│   ├── log_viewer_tab.py           日志 & 调试信息
│   └── about_tab.py                关于
└── locales/
    ├── zh.yml
    ├── en.yml
    └── ja.yml
```

配置文件（与程序同目录）：

| 文件 | 内容 |
|------|------|
| `settings.yml` | 服务器地址、端口、语言等 |
| `panels.yml` | 3 个面板的按键布局与动作 |
| `osc_addresses.yml` | OSC 交互参数映射列表 |

---

## 使用的开源项目

| 项目 | 协议 |
|------|------|
| PySide6 | LGPL |
| websockets | BSD |
| qasync | MIT |
| python-osc | MIT |
| pyyaml | MIT |
| colorlog | MIT |
| psutil | BSD |
| aiohttp | Apache 2.0 |

---

## 免责声明

本项目仅供个人研究与娱乐使用。请在安全、合理的前提下使用设备，开发者不对任何使用造成的后果负责。
