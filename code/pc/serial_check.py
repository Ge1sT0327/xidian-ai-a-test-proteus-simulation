# -*- coding: utf-8 -*-
"""
串口自检工具
用法:
    python serial_check.py                # 列出所有串口
    python serial_check.py COM2 5         # 打开 COM2，发送学号 5 次并显示回传数据

用途:
    1. 确认 VSPD 虚拟串口对已创建（应能看到成对出现的两个空闲串口）；
    2. 在打开 Proteus 仿真后，确认 Arduino 已回传温度数据。
"""
import sys
import time

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pylibs"))
    import serial
    from serial.tools import list_ports

STUDENT_ID = "23009290073"


def list_ports_():
    print("=" * 62)
    print("当前系统串口列表")
    print("=" * 62)
    found = list(list_ports.comports())
    if not found:
        print("  未检测到任何串口。请先安装 VSPD 并创建虚拟串口对。")
        return
    for p in found:
        print("  %-8s %s" % (p.device, (p.description or "").strip()))
    print()
    print("提示: 配对的两个虚拟串口会显示相同的描述（例如 Virtual Serial Port）。")
    print("      Proteus 的 COMPIM 使用其中一个，上位机使用另一个。")


def check(port, count=5, baud=9600):
    print("=" * 62)
    print("打开 %s  @ %d 8-N-1" % (port, baud))
    print("=" * 62)
    try:
        ser = serial.Serial(port, baud, timeout=0.2)
    except Exception as e:
        print("打开失败:", e)
        return 1

    print("已打开。开始发送学号 %s ..." % STUDENT_ID)
    got = 0
    for i in range(count):
        ser.write((STUDENT_ID + "\r\n").encode())
        time.sleep(0.4)
        data = ser.read(4096)
        if data:
            got += 1
            print("  第%d次 收到: %r" % (i + 1, data.decode("ascii", "ignore").strip()))
        else:
            print("  第%d次 未收到数据" % (i + 1))
    ser.close()

    print("-" * 62)
    if got:
        print("结果: 通信正常，Arduino 已回传温度数据。")
        return 0
    print("结果: 未收到任何数据。请检查：")
    print("  1) Proteus 仿真是否已点击运行 (Play)；")
    print("  2) COMPIM 的 Physical Port 是否设为配对端口的另一半；")
    print("  3) 两端波特率是否都是 9600；")
    print("  4) 是否已把编译好的固件写入 ATmega328P。")
    return 2


if __name__ == "__main__":
    if len(sys.argv) < 2:
        list_ports_()
    else:
        sys.exit(check(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 5))
