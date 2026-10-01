# -*- coding: utf-8 -*-
"""
设置 Proteus 工程里 BMP180 (U2) 的温度/气压设定值。

工程内 ROOT.CDB 是纯文本（latin-1），BMP180 实例属性形如：
    {SETPOINT1=860.00}   <- 气压 hPa
    {SETPOINT2=30.0}     <- 温度 °C
    {STEP2=0.1}          <- 温度步进

只替换这两个字段，其余条目（尤其 ROOT.DSN 等二进制）原样保留。

用法:
  python set_sensor.py 34.0            # 只改温度
  python set_sensor.py 34.0 860.00     # 温度 + 气压
  python set_sensor.py                 # 只显示当前值
"""
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PRJ = os.path.join(HERE, "TemCtrlSys.pdsprj")
TARGET = "ROOT.CDB"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def show():
    with zipfile.ZipFile(PRJ) as z:
        t = z.read(TARGET).decode("latin-1")
    for k in ("SETPOINT1", "SETPOINT2", "STEP1", "STEP2", "UNITS1", "UNITS2"):
        m = re.search(r"\{%s=([^}]*)\}" % k, t)
        if m:
            print("  %-10s = %s" % (k, m.group(1)))


def set_val(txt, key, val):
    """把 {key=...} 的值换成 val，返回新文本与是否成功"""
    pat = re.compile(r"(\{%s=)([^}]*)(\})" % key)
    m = pat.search(txt)
    if not m:
        return txt, False
    return txt[:m.start(2)] + val + txt[m.end(2):], True


def main():
    if not os.path.exists(PRJ):
        print("找不到工程:", PRJ)
        return 1

    print("当前 BMP180 设定值:")
    show()

    if len(sys.argv) < 2:
        return 0

    temp = sys.argv[1].strip()
    pres = sys.argv[2].strip() if len(sys.argv) > 2 else None

    if not re.fullmatch(r"-?\d+(\.\d+)?", temp):
        print("温度格式不对，例如 34.0")
        return 1
    if pres is not None and not re.fullmatch(r"\d+(\.\d+)?", pres):
        print("气压格式不对，例如 860.00")
        return 1

    with zipfile.ZipFile(PRJ, "r") as z:
        infos = z.infolist()
        blobs = {i.filename: z.read(i.filename) for i in infos}

    txt = blobs[TARGET].decode("latin-1")
    old_len = len(txt)

    txt, ok1 = set_val(txt, "SETPOINT2", temp)
    if not ok1:
        print("没找到 {SETPOINT2=...}")
        return 1
    if pres is not None:
        txt, ok2 = set_val(txt, "SETPOINT1", pres)
        if not ok2:
            print("没找到 {SETPOINT1=...}")
            return 1

    blobs[TARGET] = txt.encode("latin-1")

    bk = os.path.join(HERE, "backup", "TemCtrlSys.pdsprj.before_sensor")
    os.makedirs(os.path.dirname(bk), exist_ok=True)
    if not os.path.exists(bk):
        shutil.copy2(PRJ, bk)

    tmp = PRJ + ".new"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for i in infos:
            zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
            zi.compress_type = i.compress_type
            zi.external_attr = i.external_attr
            zi.internal_attr = i.internal_attr
            zi.create_system = i.create_system
            zo.writestr(zi, blobs[i.filename])
    shutil.move(tmp, PRJ)

    print("\n修改后:")
    show()
    with zipfile.ZipFile(PRJ) as z:
        print("检验 ROOT.DSN  :", len(z.read("ROOT.DSN")), "字节")
        print("检验 内嵌固件  :", len(z.read("FIRMWARE/ATmega328P/Debug/Debug.elf")), "字节")
        p = re.search(r"\{P_PORT=([^}]*)\}", z.read(TARGET).decode("latin-1"))
        print("检验 COMPIM端口:", p.group(1) if p else "?")
    return 0


if __name__ == "__main__":
    sys.exit(main())
