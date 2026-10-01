# 西电人工智能学院 A 测 · Proteus 软件仿真

> 2026 年秋季「1 人一组软件仿真 1（人工智能学院）」A 级实验能力达标线上测试
> 题目：**温度测控仿真系统**

本仓库是一份**可复现的参考实现**，包含完整工程、源码、编译产物与踩坑记录，
目的是让后面的同学**少走弯路**。

> ⚠️ **本仓库代码中的学号（`20230000000`）和姓名（`张三`）均为占位值**。
> 提交前请务必替换为**你自己的完整学号与姓名**，并把阈值改成
> `30 + 你的学号末位数`。题目明确禁止使用他人学号、虚拟学号或不完整学号。

**仓库地址**：https://github.com/Ge1sT0327/xidian-ai-a-test-proteus-simulation

> 📌 关于仓库名：中文名「西电人工智能学院a测_proteus软件仿真」被 GitHub 的 API 拒绝
> （HTTP 422，服务端会剥离非 ASCII 字符），因此改用拼音
> `xidian-ai-a-test-proteus-simulation`。
>
> 📌 本仓库**不包含写好的报告**。学校会提供报告模板（也见 `doc/报告模板.docx`），
> 请自行按模板撰写，注意把两张仿真截图和两段源码放进报告。

---

## 目录

- [一、题目要求](#一题目要求摘要)
- [二、电路与引脚](#二电路与引脚工程已给定不可改)
- [三、目录结构](#三目录结构)
- [四、快速上手](#四快速上手最短路径)
- [五、⚠️ 核心踩坑记录](#五️-核心踩坑记录最重要的一节)
- [六、脚本说明](#六脚本说明)
- [七、通信协议](#七通信协议)
- [八、提交要求](#八提交要求)

---

## 一、题目要求（摘要）

用 **Arduino UNO（ATmega328P）** 搭一个 PC 上位机远程温度检测控制系统：

| 要求 | 说明 |
|---|---|
| 双向通信 | PC 先发**本人完整学号**，Arduino 收到后回传当前温度 |
| LCD 显示 | 第一行 `ID:学号`，第二行 `TEMP:温度值` |
| 电机控制 | 温度 **>** 阈值 → 电机转动；温度 **≤** 阈值 → 电机停止 |
| 上位机 | 必须**自行编写**，GUI 标题含学号姓名，有发送窗口、接收窗口、串口开关 |
| 温度阈值 | **30 + 学号末位数**（本实现为 30+0 = **30 ℃**） |
| 截图 | 高/低于阈值各一张，一张图里要同时看清 5 项（见下） |

**截图必须同时包含的 5 项**（老师会重点核查）：

1. 上位机发送窗口里的**完整学号**
2. 传感器（BMP180）显示的温度
3. LCD 上的学号与温度
4. 上位机接收窗口的温度值
5. 电机转动 / 停止状态

> 传感器、LCD、上位机**三处温度必须一致**；发送窗口和 LCD 的学号必须一致且是**本人完整学号**。

---

## 二、电路与引脚（工程已给定，不可改）

Proteus 工程里的器件是**预先连好**的，引脚映射是从工程网表 `ROOT.CDB` 里核对出来的：

| 器件 | 引脚 | Arduino |
|---|---|---|
| LCD1602（LM016L） | RS / E | **D12 / D11** |
| LCD1602 数据 | D4 D5 D6 D7 | **D5 / D4 / D3 / D2** |
| LCD1602 | RW / VEE | GND / 5k 电位器（对比度） |
| BMP180 | SDA / SCL | **A4 (PC4) / A5 (PC5)** |
| 直流电机驱动 | 基极（经 4.7k） | **D7 (IO7)** |
| 串口组件 COMPIM | RXD / TXD | PD0 / PD1 |

**电机驱动链路**：`D7 → 4.7k → 2N3904(NPN) → 继电器 → MOTOR-DC`

串口参数：**9600, 8, N, 1**（与 COMPIM 默认值一致）

> ⚠️ **LCD 是 4 位数据模式**，而且数据线是**错位**接的（D4→IO5、D5→IO4……）。
> 建 `LiquidCrystal` 对象时顺序必须是 `(RS, EN, D4, D5, D6, D7)`
> 也就是 `(12, 11, 5, 4, 3, 2)`。接反了 LCD 只会显示黑块或全空白。

---

## 三、目录结构

```
.
├─ code/
│  ├─ arduino/TemCtrlSys.ino      # 下位机固件（Arduino UNO）
│  └─ pc/TempMonitor.py           # PC 上位机（Python3 + Tkinter + pyserial）
│     pc/serial_check.py          # 串口自检小工具
├─ proteus/
│  ├─ TemCtrlSys.pdsprj           # 已注入固件的工程（打开按 F12 即可仿真）
│  ├─ TemCtrlSys原始工程.pdsprj     # 题目给的原始工程（未修改）
│  └─ backup/TemCtrlSys.pdsprj.orig
├─ build/
│  ├─ Debug.elf                   # VSM Studio 格式固件（关键，见第五节）
│  └─ TemCtrlSys.hex
├─ tools/                         # 辅助脚本
│  ├─ build_firmware.py           # 用 Proteus 自带工具链编译并注入固件
│  ├─ set_sensor.py               # 改 BMP180 温度设定值
│  ├─ set_compim_port.py          # 改 COMPIM 物理串口
│  ├─ make_block_diagram.py       # 生成系统框图
│  └─ make_report.py              # 按模板生成报告
├─ doc/                          # 题目原文 + 报告模板
└─ 文档/                           # 详细操作指南与踩坑详解
```

---

## 四、快速上手（最短路径）

### 0. 前置软件

| 软件 | 版本要求 | 说明 |
|---|---|---|
| **Proteus** | 8.17 SP2 或更高 | **必须完整授权版**，且含 **VSM for AVR** 模块 |
| **虚拟串口** | VSPD 或 com0com | 建一对虚拟串口，连通 Proteus 与上位机 |
| Python | 3.x | 只需 `pyserial` |

> ❌ **不要用 Proteus 官网的免费试用版**。官方明确限制：
> *"You cannot save your work"*、*"You cannot simulate your own microcontroller designs"*
> —— 不能保存工程、不能仿真自己写的单片机程序，**完全用不了**。

### 1. 装虚拟串口

本实现用的是 **VSPD 6.9**，建了一对 **COM11 ↔ COM12**：

- **COM11** → 给 Proteus 里的 COMPIM (P1) 用
- **COM12** → 给 PC 上位机用

> 💡 为什么不直接用题目写的 COM1？因为多数主板 COM1 是**真实物理串口**，
> 拿它做虚拟配对容易冲突。改用一对空闲端口更稳。

### 2. 打开仿真

双击 `proteus/TemCtrlSys.pdsprj`，按 **F12** 开始仿真。

LCD 应显示：

```
ID:20230000000
TEMP: 30.0C
```

（30.0 ℃ 是 Proteus 里 BMP180 的默认温度）

### 3. 跑上位机

```bat
cd code\pc
pip install pyserial
python TempMonitor.py
```

界面上选 **COM12** → 点「打开串口」，接收窗口会持续滚动 `TEMP:xx.xC`。

### 4. 改温度、截图

改温度有两种方式：

**方式 A（推荐，脚本改）**
```bat
python tools\set_sensor.py 34     :: 改成 34 ℃（注意必须是整数！）
```
然后重新打开工程、按 F12。

**方式 B（界面改）**
仿真运行时，双击原理图里的 **U2 (BMP180)**，面板上有 `▲/▼` 按钮可直接调温。

> ⚠️ 仿真运行中在原理图上**点器件按钮**有时不响应，
> 这是 Proteus 的常态，用方式 A 更可靠。

截图时把**上位机窗口和 Proteus 窗口并排摆好**，一张图里同时包含那 5 项。

---

## 五、⚠️ 核心踩坑记录（最重要的一节）

这一节是本仓库的主要价值。以下每条都是实际踩过并定位到的。

### 坑 1：只改元件的 "Program File" 属性，固件根本不生效 🔴

**最容易卡住的地方。**

Proteus 里双击 ATmega328P，把 `Program File` 指向你的 `.elf`，
点确定、保存、运行 —— **LCD 还是全黑**。

**原因**：Proteus 仿真 ATmega328P 时，实际加载的是**工程内嵌**的固件文件：

```
FIRMWARE/ATmega328P/Debug/Debug.elf
```

（`.pdsprj` 本质是个 zip，里面打包了 VSM Studio 的工作区）

题目给的原始工程里，这个内嵌文件是 **2021 年编译的空模板**，
`setup()` 和 `loop()` 里**什么都没有**。所以无论你 Program File 怎么改，
跑的都是那个空程序 → LCD 当然全黑。

**解决**：必须重新编译，并把产物**注入**工程 zip 里的那个路径。

本仓库的 `tools/build_firmware.py` 就是干这个的：

1. 用 **Proteus 自带的 AVR 工具链**（`avr-g++ 4.9.2`，在
   `Proteus安装目录\Tools\ARDUINO\hardware\tools\avr\bin\`）编译 sketch、core、库
2. 链接生成 `Debug.elf`
3. 把它写进 `.pdsprj` 的 `FIRMWARE/ATmega328P/Debug/Debug.elf`

```bat
python tools\build_firmware.py
```

> 顺带一提：Proteus 自带的工具链是完整的（含 `avr-g++ / avr-gcc / avr-ld / avr-objcopy`），
> **不需要额外装 Arduino IDE**。

### 坑 2：AVR 的 printf 不支持 %f，会打印乱码 🔴

固件里如果写：

```c
snprintf(line, sizeof(line), "TEMP:%.1fC", temp);   // ❌ LCD 显示 "TEMP:?C"
```

LCD 上会出现**乱码或问号**。原因是 **avr-libc 的 `printf` 默认不带浮点支持**
（除非额外链接 `-lprintf_flt`）。

**解决**：温度全程用**整数运算**，单位取 0.1 ℃：

```c
long temp10 = 347;                                   // 代表 34.7 ℃
snprintf(line, sizeof(line), "TEMP:%ld.%ldC", temp10 / 10, temp10 % 10);
```

这样既避开浮点 printf，又比 `float` 省 Flash 和 RAM。

### 坑 3：BMP180 的 I2C 地址探测不能只靠 ACK 🔴

用 `Wire.endTransmission()` 的返回值判断器件是否存在**不可靠** ——
有些器件会 ACK 但实际不响应后续读操作。

**解决**：写一个值到控制寄存器再读回来，**读回一致**才算真的在：

```c
bool i2cProbe(uint8_t dev)
{
  i2cWriteByte(dev, REG_CTRL, 0x00);
  uint16_t rb = i2cRead16(dev, REG_CTRL);
  return ((rb >> 8) == 0x00);
}
```

另外 **BMP180 的标准地址是 `0x77`**（不是 `0x76`），
而 Proteus 的 BMP180 模型**没有地址属性可以改**。

### 坑 4：用脚本改 BMP180 温度时，**必须传整数** 🔴

如果你直接改工程文件 `ROOT.CDB` 里的温度设定值：

```
{SETPOINT2=30}      ← 正确，整数
{SETPOINT2=34.0}    ← ❌ 会让 Proteus 打开工程时直接卡死（进程无响应）
```

**原因**：该属性的格式定义是 `INT,10,100`（整数、范围 10~100、步进 1），
写小数会让 Proteus 解析失败。

> 症状：双击 `.pdsprj` 后进程出现但**没有窗口**，`Responding = False`。
> 只能强杀 `PDS.EXE`，然后从备份恢复工程。

`tools/set_sensor.py` 已经强制要求整数格式。

### 坑 5：pyserial 枚举不到 VSPD 建的虚拟串口 🟡

`serial.tools.list_ports.comports()` 依赖 SetupAPI 的描述信息，
**列不出 VSPD/com0com 创建的端口**，导致上位机下拉框里根本没有 COM11/COM12。

**解决**：改用系统 API 枚举（`[System.IO.Ports.SerialPort]::GetPortNames()`）为主，
`list_ports` 只用来补描述文字：

```python
out = subprocess.run(
    ["powershell", "-NoProfile", "-Command",
     "[System.IO.Ports.SerialPort]::GetPortNames() -join ','"],
    capture_output=True, text=True, timeout=8,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
).stdout.strip()
names = [x.strip().upper() for x in out.split(",") if x.strip()]
```

`code/pc/TempMonitor.py` 里已实现三步枚举（系统 API → pyserial → 逐号试探）。

### 坑 6：工程内部文件不能有中文 🟡

`.pdsprj` 里的 `ROOT.CDB` 是 **latin-1 + 二进制混合**编码。
往里面写带中文的路径会**损坏整个文件**，Proteus 打开直接报 `Fatal Error`。

**规避**：

- 编译输出目录用**纯 ASCII 路径**（本实现用 `G:\dsh_at\`）
- 工程内嵌的 `main.ino` **注释也必须是 ASCII**（写中文会导致编译失败）

最终交付给报告的 `.ino` 可以随便写中文注释 —— 那是另一份文件。

### 坑 7：VSPD 配置工具是管理员权限，自动化操作会失效 🟡

VSPD 的 `vspdconfig.exe` 以 **High integrity（管理员）** 运行，
普通权限的自动化工具（UIPI 限制）**无法向它发送任何输入**（点击会被静默丢弃）。

**解决**：手动建串口对，一次就好，不用自动化。
建好后 VSPD 主程序可以关掉，**驱动服务 `evserial` 会继续运行**，
虚拟串口对依然有效。

### 坑 8：不要用 Proteus 官方试用版 🔴

见第四节的说明。官方试用版**不能保存工程、不能仿真自制固件**。

---

## 六、脚本说明

| 脚本 | 用途 |
|---|---|
| `tools/build_firmware.py` | 用 Proteus 自带工具链编译固件并注入工程 |
| `tools/set_sensor.py 34` | 改 BMP180 温度设定（**必须整数**） |
| `tools/set_sensor.py` | 查看当前设定值 |
| `tools/set_compim_port.py COM11` | 改 COMPIM 的物理串口 |
| `tools/make_block_diagram.py` | 生成报告用的系统框图 |
| `tools/make_report.py` | 按模板生成报告 docx |

脚本里的路径（Proteus 安装位置、工作目录）**请按自己的环境修改**。

---

## 七、通信协议

| 方向 | 内容 | 周期 |
|---|---|---|
| PC → Arduino | `20230000000\r\n` | 200 ms（可勾选自动周期发送） |
| Arduino → PC | `TEMP:34.0C\r\n` | 200 ms（收到学号后开始） |

串口：**9600, 8, N, 1**

LCD 显示格式：

```
ID:20230000000      ← 第 1 行，15 字符
TEMP: 34.0C         ← 第 2 行，11 字符（16x2 屏放得下）
```

---

## 八、提交要求

- 报告文件命名：`学号_姓名_学院_线上A测报告.pdf`
- 报告里必须包含：题目要求、阈值计算过程、两张仿真截图、参考文献、两段源码
- **源码运行结果必须与截图相符**（老师会核对，改了代码记得重新编译并重新截图）

---

## 九、免责与致谢

- 本仓库仅供学习参考。**请独立完成自己的测试**，
  特别是**学号、姓名、温度阈值**必须换成你自己的（阈值 = 30 + 你的学号末位数）。
- 严禁直接使用他人的学号 —— 题目明确禁止使用他人学号、虚拟学号、不完整学号。
- Proteus 为商业软件，**请通过学校正版渠道或实验室授权获取**。
