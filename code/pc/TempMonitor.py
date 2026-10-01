# -*- coding: utf-8 -*-
"""
================================================================
 PC 上位机 —— 温度测控仿真系统
 学号: 23009290073      姓名: 高晨曦
 功能:
   1. 打开/关闭串口，与 Proteus 中的 Arduino UNO(COMPIM) 双向通信
   2. 向 Arduino 发送本人完整学号（发送窗口可见）
   3. 接收 Arduino 回传的实时温度值（接收窗口可见）
   4. 根据温度与阈值(30+学号末位数=33.0℃)的比较，显示直流电机转动/停止状态
 运行环境: Python 3.x + pyserial (pip install pyserial)
================================================================
"""

import re
import sys
import time
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("缺少 pyserial 库，请先执行:  pip install pyserial")
    sys.exit(1)

# ---------------------------------------------------------------
# 基本参数
# ---------------------------------------------------------------
STUDENT_ID = "23009290073"          # 本人完整学号
STUDENT_NAME = "高晨曦"              # 本人姓名
LAST_DIGIT = int(STUDENT_ID[-1])     # 学号末位数 = 3
TEMP_LIMIT = 30 + LAST_DIGIT         # 温度阈值 = 33 ℃

BAUD_RATE = 9600                     # 必须与 Proteus 中 COMPIM 一致
SEND_PERIOD_MS = 200                 # 学号重发周期(ms)

# 本工程用 VSPD 建了一对虚拟串口 COM11 <-> COM12：
#   COM11 -> Proteus 里 COMPIM (P1) 使用
#   COM12 -> 本上位机使用
# 若你的配对端口不同，把这里改成对应端口即可（界面上也能选）。
PREFERRED_PORT = "COM12"

TITLE = "温度测控仿真系统上位机  —  学号:%s  姓名:%s" % (STUDENT_ID, STUDENT_NAME)

BG = "#1e2430"
FG = "#e6edf3"
ACCENT = "#2f81f7"
GREEN = "#3fb950"
RED = "#f85149"
GRAY = "#8b949e"


class TempMonitorApp:

    def __init__(self, root):
        self.root = root
        self.ser = None                     # 串口对象
        self.conn_state = False             # 串口是否已打开
        self.rx_buffer = ""                 # 接收缓冲
        self.sample_count = 0               # 已接收温度样本数
        self.temp_history = []              # 温度历史，用于判断趋势
        self.last_rx_time = 0.0

        self._build_ui()

        self.refresh_ports()

        # 启动周期任务
        self.root.after(200, self._tick_send_id)
        self.root.after(100, self._tick_read_serial)

    # ===========================================================
    #  界面构建
    # ===========================================================
    def _build_ui(self):
        self.root.title(TITLE)
        self.root.geometry("980x640")
        self.root.minsize(880, 580)
        self.root.configure(bg=BG)

        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TLabel", background=BG, foreground=FG, font=("Microsoft YaHei", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabelframe", background=BG, foreground=ACCENT,
                        font=("Microsoft YaHei", 10, "bold"))
        style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                        font=("Microsoft YaHei", 10, "bold"))
        style.configure("TButton", font=("Microsoft YaHei", 10), padding=6)
        style.configure("TCombobox", font=("Consolas", 10))

        # ---------------- 顶部信息栏 ----------------
        top = tk.Frame(self.root, bg="#111823", height=92)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)

        tk.Label(top, text="温度测控仿真系统  PC 上位机", bg="#111823", fg=FG,
                 font=("Microsoft YaHei", 17, "bold")).place(x=18, y=12)
        tk.Label(top, text="学号：%s      姓名：%s" % (STUDENT_ID, STUDENT_NAME),
                 bg="#111823", fg=GREEN, font=("Microsoft YaHei", 12, "bold")).place(x=20, y=52)
        tk.Label(top, text="温度阈值 = 30 + 学号末位数(%d) = %d ℃" % (LAST_DIGIT, TEMP_LIMIT),
                 bg="#111823", fg=GRAY, font=("Microsoft YaHei", 10)).place(x=430, y=56)

        # ---------------- 串口控制条 ----------------
        ctl = ttk.LabelFrame(self.root, text=" 串口设置 ")
        ctl.pack(fill="x", padx=12, pady=(10, 6))

        row = ttk.Frame(ctl)
        row.pack(fill="x", padx=10, pady=8)

        ttk.Label(row, text="串口:").pack(side="left")
        self.cmb_port = ttk.Combobox(row, width=26, state="readonly")
        self.cmb_port.pack(side="left", padx=(6, 4))

        ttk.Button(row, text="刷新", width=6, command=self.refresh_ports).pack(side="left")

        ttk.Label(row, text="波特率:").pack(side="left", padx=(18, 0))
        self.cmb_baud = ttk.Combobox(row, width=9, state="readonly",
                                     values=["9600", "19200", "38400", "57600", "115200"])
        self.cmb_baud.set(str(BAUD_RATE))
        self.cmb_baud.pack(side="left", padx=6)

        self.btn_open = tk.Button(row, text="打开串口", width=12, bg=ACCENT, fg="white",
                                  activebackground="#1f6feb", activeforeground="white",
                                  relief="flat", font=("Microsoft YaHei", 10, "bold"),
                                  command=self.toggle_port)
        self.btn_open.pack(side="left", padx=(20, 6))

        self.lbl_state = tk.Label(row, text="● 串口已关闭", bg=BG, fg=RED,
                                  font=("Microsoft YaHei", 10, "bold"))
        self.lbl_state.pack(side="left", padx=8)

        # ---------------- 中部：发送 / 接收 ----------------
        mid = ttk.Frame(self.root)
        mid.pack(fill="both", expand=True, padx=12, pady=4)
        mid.columnconfigure(0, weight=1, uniform="c")
        mid.columnconfigure(1, weight=1, uniform="c")
        mid.rowconfigure(0, weight=1)

        # ---- 发送窗口 ----
        f_send = ttk.LabelFrame(mid, text=" 发送窗口（发送给 Arduino 的学号） ")
        f_send.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=4)

        self.txt_send = tk.Text(f_send, height=8, bg="#0d1117", fg="#7ee787",
                                insertbackground=FG, font=("Consolas", 12),
                                relief="flat", wrap="word")
        self.txt_send.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        srow = ttk.Frame(f_send)
        srow.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(srow, text="学号:").pack(side="left")
        self.var_id = tk.StringVar(value=STUDENT_ID)
        ttk.Entry(srow, textvariable=self.var_id, width=18,
                  font=("Consolas", 11)).pack(side="left", padx=6)
        self.var_auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(srow, text="自动周期发送", variable=self.var_auto).pack(side="left", padx=4)
        ttk.Button(srow, text="手动发送", command=self.manual_send).pack(side="left", padx=6)
        ttk.Button(srow, text="清空", width=6,
                   command=lambda: self.txt_send.delete("1.0", "end")).pack(side="left")

        # ---- 接收窗口 ----
        f_recv = ttk.LabelFrame(mid, text=" 接收窗口（Arduino 回传的温度值） ")
        f_recv.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=4)

        self.txt_recv = tk.Text(f_recv, height=8, bg="#0d1117", fg="#ffa657",
                                insertbackground=FG, font=("Consolas", 12),
                                relief="flat", wrap="word", state="disabled")
        self.txt_recv.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        rrow = ttk.Frame(f_recv)
        rrow.pack(fill="x", padx=8, pady=(0, 8))
        self.lbl_count = ttk.Label(rrow, text="已接收温度样本：0")
        self.lbl_count.pack(side="left")
        ttk.Button(rrow, text="清空", width=6, command=self.clear_recv).pack(side="right")

        # ---------------- 底部：温度 / 电机状态 ----------------
        bot = ttk.Frame(self.root)
        bot.pack(fill="x", padx=12, pady=(4, 12))

        # 温度显示
        f_temp = tk.Frame(bot, bg="#0d1117", bd=0)
        f_temp.pack(side="left", fill="both", expand=True, padx=(0, 6))
        tk.Label(f_temp, text="当前温度", bg="#0d1117", fg=GRAY,
                 font=("Microsoft YaHei", 10)).pack(pady=(8, 0))
        self.lbl_temp = tk.Label(f_temp, text="--.- ℃", bg="#0d1117", fg="#ffa657",
                                 font=("Consolas", 34, "bold"))
        self.lbl_temp.pack(pady=(0, 10))

        # 阈值
        f_lim = tk.Frame(bot, bg="#0d1117")
        f_lim.pack(side="left", fill="both", padx=6)
        tk.Label(f_lim, text="温度阈值", bg="#0d1117", fg=GRAY,
                 font=("Microsoft YaHei", 10)).pack(pady=(8, 0))
        tk.Label(f_lim, text="%d.0 ℃" % TEMP_LIMIT, bg="#0d1117", fg=ACCENT,
                 font=("Consolas", 34, "bold")).pack(pady=(0, 10), padx=22)

        # 电机状态
        f_motor = tk.Frame(bot, bg="#0d1117")
        f_motor.pack(side="left", fill="both", expand=True, padx=(6, 0))
        tk.Label(f_motor, text="直流电机状态", bg="#0d1117", fg=GRAY,
                 font=("Microsoft YaHei", 10)).pack(pady=(8, 0))
        self.lbl_motor = tk.Label(f_motor, text="● 停止", bg="#0d1117", fg=GRAY,
                                  font=("Microsoft YaHei", 22, "bold"))
        self.lbl_motor.pack(pady=(2, 10))
        self.lbl_rule = tk.Label(f_motor, text="温度 <= %d.0℃ → 电机停止" % TEMP_LIMIT,
                                 bg="#0d1117", fg=GRAY, font=("Microsoft YaHei", 9))
        self.lbl_rule.pack()

        self.log("程序已启动。请选择虚拟串口（与 Proteus 中 COMPIM 配对的另一端）后点击“打开串口”。")

    # ===========================================================
    #  日志
    # ===========================================================
    def log(self, msg):
        self.txt_send.insert("end", "[%s] %s\n" % (time.strftime("%H:%M:%S"), msg))
        self.txt_send.see("end")

    # ===========================================================
    #  串口管理
    # ===========================================================
    def refresh_ports(self):
        ports = []
        # 端口枚举：pyserial 的 list_ports 有时会漏掉虚拟串口驱动
        # (VSPD/com0com) 创建的端口，因为它依赖 SetupAPI 的描述信息。
        # 这里以系统 API 枚举为主，再用 pyserial 的描述补全。
        names = []

        # 1) 系统枚举（最可靠，能列出 VSPD 虚拟口）
        try:
            import subprocess
            ps = ("[System.IO.Ports.SerialPort]::GetPortNames() -join ','")
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=8,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ).stdout.strip()
            if out:
                names = [x.strip().upper() for x in out.split(",") if x.strip()]
        except Exception:
            names = []

        # 2) pyserial 枚举（补充描述；也作为系统枚举失败时的回退）
        descs = {}
        try:
            for p in list_ports.comports():
                dev = (p.device or "").upper()
                if dev:
                    descs[dev] = (p.description or "").strip()
                    if dev not in names:
                        names.append(dev)
        except Exception:
            pass

        # 3) 兜底：探测 COM1..COM32 中能打开、但上面都没列出的端口
        if not names:
            for n in range(1, 33):
                dev = "COM%d" % n
                try:
                    s = serial.Serial(dev, BAUD_RATE, timeout=0.01)
                    s.close()
                    names.append(dev)
                except Exception:
                    pass

        # 按端口号排序
        def key(d):
            m = re.fullmatch(r"COM(\d+)", d)
            return (0, int(m.group(1))) if m else (1, d)
        names = sorted(set(names), key=key)

        for d in names:
            dsc = descs.get(d, "")
            ports.append("%s - %s" % (d, dsc) if dsc else d)

        if not ports:
            ports = ["<未检测到串口>"]
        self.cmb_port["values"] = ports

        # 优先选中首选项端口；否则退回第一个可用端口
        pick = None
        for i, s in enumerate(ports):
            if s.upper().startswith(PREFERRED_PORT.upper() + " ") or \
               s.upper() == PREFERRED_PORT.upper():
                pick = i
                break
        self.cmb_port.current(pick if pick is not None else 0)

    def toggle_port(self):
        if self.conn_state:
            self.close_port()
        else:
            self.open_port()

    def open_port(self):
        sel = self.cmb_port.get()
        if not sel or sel.startswith("<"):
            messagebox.showwarning("提示", "未选择有效串口，请确认 VSPD 已创建虚拟串口对并点击“刷新”。")
            return
        port = sel.split(" ")[0]
        try:
            self.ser = serial.Serial(port=port,
                                     baudrate=int(self.cmb_baud.get()),
                                     bytesize=serial.EIGHTBITS,
                                     parity=serial.PARITY_NONE,
                                     stopbits=serial.STOPBITS_ONE,
                                     timeout=0.05)
        except Exception as e:
            messagebox.showerror("串口打开失败", "无法打开 %s：\n%s" % (port, e))
            return

        self.conn_state = True
        self.btn_open.config(text="关闭串口", bg=RED, activebackground="#da3633")
        self.lbl_state.config(text="● 串口已打开 (%s)" % port, fg=GREEN)
        self.log("串口 %s 已打开，波特率 %s" % (port, self.cmb_baud.get()))
        self.var_auto.set(True)

    def close_port(self):
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
        self.ser = None
        self.conn_state = False
        self.btn_open.config(text="打开串口", bg=ACCENT, activebackground="#1f6feb")
        self.lbl_state.config(text="● 串口已关闭", fg=RED)
        self.lbl_motor.config(text="● 停止", fg=GRAY)
        self.log("串口已关闭")

    # ===========================================================
    #  发送
    # ===========================================================
    def _write_serial(self, text):
        if not self.conn_state or self.ser is None:
            return False
        try:
            self.ser.write(text.encode("ascii", "ignore"))
            self.ser.flush()
            return True
        except Exception as e:
            self.log("发送失败：%s" % e)
            return False

    def manual_send(self):
        sid = self.var_id.get().strip()
        if not sid:
            return
        if not self.conn_state:
            messagebox.showwarning("提示", "请先打开串口。")
            return
        if self._write_serial(sid + "\r\n"):
            self.log("发送学号 -> %s" % sid)

    def _tick_send_id(self):
        """周期发送学号，保证 Arduino 持续回传温度"""
        if self.conn_state and self.var_auto.get():
            sid = self.var_id.get().strip() or STUDENT_ID
            self._write_serial(sid + "\r\n")
        self.root.after(SEND_PERIOD_MS, self._tick_send_id)

    # ===========================================================
    #  接收
    # ===========================================================
    def clear_recv(self):
        self.txt_recv.config(state="normal")
        self.txt_recv.delete("1.0", "end")
        self.txt_recv.config(state="disabled")
        self.sample_count = 0
        self.lbl_count.config(text="已接收温度样本：0")

    def _append_recv(self, line):
        self.txt_recv.config(state="normal")
        self.txt_recv.insert("end", line + "\n")
        # 限制显示行数，避免长时间运行卡顿
        if int(self.txt_recv.index("end-1c").split(".")[0]) > 400:
            self.txt_recv.delete("1.0", "100.0")
        self.txt_recv.see("end")
        self.txt_recv.config(state="disabled")

    def _tick_read_serial(self):
        if self.conn_state and self.ser is not None:
            try:
                n = self.ser.in_waiting
                if n:
                    data = self.ser.read(n).decode("ascii", "ignore")
                    self.rx_buffer += data
                    while "\n" in self.rx_buffer:
                        line, self.rx_buffer = self.rx_buffer.split("\n", 1)
                        line = line.strip()
                        if line:
                            self._handle_line(line)
            except Exception as e:
                self.log("读取异常：%s" % e)
                self.close_port()

        # 3 秒无数据则提示通信中断
        if (self.conn_state and self.last_rx_time and
                time.time() - self.last_rx_time > 3.0):
            self.lbl_temp.config(text="--.- ℃", fg=GRAY)

        self.root.after(80, self._tick_read_serial)

    def _handle_line(self, line):
        self.last_rx_time = time.time()
        self._append_recv(line)

        m = re.search(r"(-?\d+(?:\.\d+)?)", line)
        if not m:
            return
        try:
            temp = float(m.group(1))
        except ValueError:
            return

        self.sample_count += 1
        self.lbl_count.config(text="已接收温度样本：%d" % self.sample_count)

        # ---- 显示温度 ----
        self.lbl_temp.config(text="%.1f ℃" % temp,
                             fg=RED if temp > TEMP_LIMIT else "#58a6ff")

        # ---- 更新电机状态 ----
        if temp > TEMP_LIMIT:
            self.lbl_motor.config(text="● 转动", fg=GREEN)
            self.lbl_rule.config(text="温度 > %d.0℃ → 电机转动" % TEMP_LIMIT, fg=GREEN)
        else:
            self.lbl_motor.config(text="● 停止", fg=GRAY)
            self.lbl_rule.config(text="温度 <= %d.0℃ → 电机停止" % TEMP_LIMIT, fg=GRAY)


def main():
    root = tk.Tk()
    TempMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
