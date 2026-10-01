# -*- coding: utf-8 -*-
"""
设置 Proteus 工程里 COMPIM (P1) 的物理串口。

工程内 ROOT.CDB 保存着元件属性（纯文本）。COMPIM 的物理端口是 {P_PORT=COMx}。
本脚本只替换该字段，其余条目原样保留（ROOT.DSN 等二进制内容不受影响）。

用法:
  python set_compim_port.py COM11
  python set_compim_port.py            # 只显示当前值
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


def read_port():
    with zipfile.ZipFile(PRJ) as z:
        t = z.read(TARGET).decode("latin-1")
    m = re.search(r"\{P_PORT=([^}]*)\}", t)
    return m.group(1) if m else None


def main():
    if not os.path.exists(PRJ):
        print("找不到工程:", PRJ)
        return 1

    old = read_port()
    print("当前 COMPIM 物理端口:", old)

    if len(sys.argv) < 2:
        return 0

    new = sys.argv[1].strip().upper()
    if not re.fullmatch(r"COM\d{1,3}", new):
        print("端口格式不对，应形如 COM11")
        return 1
    if new == old:
        print("已经是", new, "，无需修改")
        return 0

    with zipfile.ZipFile(PRJ, "r") as z:
        infos = z.infolist()
        blobs = {i.filename: z.read(i.filename) for i in infos}

    txt = blobs[TARGET].decode("latin-1")
    m = re.search(r"\{P_PORT=([^}]*)\}", txt)
    if not m:
        print("ROOT.CDB 里没找到 {P_PORT=...}")
        return 1
    txt2 = txt[:m.start(1)] + new + txt[m.end(1):]
    blobs[TARGET] = txt2.encode("latin-1")

    # 备份一次
    bk = os.path.join(HERE, "backup", "TemCtrlSys.pdsprj.before_port")
    os.makedirs(os.path.dirname(bk), exist_ok=True)
    if not os.path.exists(bk):
        shutil.copy2(PRJ, bk)
        print("已备份 ->", bk)

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

    print("已改为:", read_port())
    with zipfile.ZipFile(PRJ) as z:
        print("ROOT.DSN 完好:", len(z.read("ROOT.DSN")), "字节")
        print("内嵌固件:", len(z.read("FIRMWARE/ATmega328P/Debug/Debug.elf")), "字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
