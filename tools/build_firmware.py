# -*- coding: utf-8 -*-
"""
用 Proteus 自带的 Arduino AVR 工具链编译 TemCtrlSys.ino，
生成 VSM Studio 期望的 Debug.elf，并注入 .pdsprj 工程。

为什么要这样做：
  Proteus 仿真 ATmega328P 时，真正加载的是工程内嵌的
      FIRMWARE/ATmega328P/Debug/Debug.elf
  这个文件是 VSM Studio 编译产生的。如果只改 Program File 属性，
  仿真仍会跑旧的 Debug.elf。因此必须重新编译并把它注入工程。

用法:
  python build_firmware.py            # 编译 + 注入
  python build_firmware.py --noinject # 只编译
"""
import os
import re
import shutil
import subprocess
import sys
import zipfile

# 控制台按 UTF-8 输出，避免中文/替换字符导致编码异常
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ------------------------------------------------------------------
HERE   = os.path.dirname(os.path.abspath(__file__))
WSROOT = os.path.dirname(HERE)                      # default-workspace

PROTEUS = r"G:\Proteus\Proteus 8 Professional"
TOOLS   = os.path.join(PROTEUS, "Tools", "ARDUINO")
AVRBIN  = os.path.join(TOOLS, "hardware", "tools", "avr", "bin")
HWDIR   = os.path.join(TOOLS, "hardware", "arduino", "avr")
LIBS    = os.path.join(TOOLS, "libraries")

SKETCH  = os.path.join(HERE, "code", "TemCtrlSys", "TemCtrlSys.ino")
PRJ     = os.path.join(HERE, "TemCtrlSys.pdsprj")

# 允许命令行覆盖： python build_firmware.py <sketch> <prj> [--noinject]
_argv = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(_argv) >= 1:
    SKETCH = _argv[0]
if len(_argv) >= 2:
    PRJ = _argv[1]
    BUILD = os.path.join(os.path.dirname(PRJ), "_build")

# 编译输出目录必须放在纯 ASCII 路径下（工具链对中文路径不友好）
BUILD   = r"G:\dsh_at\build"
ELF_NAME = "Debug.elf"

MCU     = "atmega328p"
F_CPU   = "16000000"
BOARD   = "uno"
CORE    = os.path.join(HWDIR, "cores", "arduino")
VARIANT = os.path.join(HWDIR, "variants", "standard")


def run(cmd, desc):
    p = subprocess.run(cmd, capture_output=True, text=True,
                       errors="replace")
    if p.returncode != 0:
        print("[FAIL] %s" % desc)
        print("CMD:", " ".join(cmd[:6]), "...")
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        print(out[-4000:])
        sys.exit(1)
    return p


def main():
    if not os.path.exists(SKETCH):
        print("找不到源码:", SKETCH); return 1
    if not os.path.exists(AVRBIN):
        print("找不到 Proteus AVR 工具链:", AVRBIN); return 1

    os.makedirs(BUILD, exist_ok=True)
    gcc = os.path.join(AVRBIN, "avr-g++.exe")
    gcc_c = os.path.join(AVRBIN, "avr-gcc.exe")
    ar = os.path.join(AVRBIN, "avr-ar.exe")

    # ---------------- 公共编译选项 ----------------
    includes = [
        "-I" + CORE, "-I" + VARIANT,
        "-I" + os.path.join(LIBS, "LiquidCrystal", "src"),
        "-I" + os.path.join(HWDIR, "libraries", "Wire", "src"),
        "-I" + os.path.join(HWDIR, "libraries", "Wire", "src", "utility"),
    ]
    common = [
        "-c", "-g", "-Os", "-w",
        "-std=gnu++11", "-fpermissive",
        "-ffunction-sections", "-fdata-sections",
        "-mmcu=" + MCU, "-DF_CPU=" + F_CPU,
        "-DARDUINO=10801",
        "-DARDUINO_AVR_UNO", "-DARDUINO_ARCH_AVR",
    ] + includes

    need_arduino_h = ["-I" + os.path.join(BUILD, "sketch")]

    objs = []

    # ---------------- 1. 把 .ino 转成 .cpp ----------------
    sk_dir = os.path.join(BUILD, "sketch")
    os.makedirs(sk_dir, exist_ok=True)
    src = open(SKETCH, encoding="utf-8").read()
    cpp = os.path.join(sk_dir, "TemCtrlSys.ino.cpp")
    with open(cpp, "w", encoding="utf-8") as f:
        f.write("#include <Arduino.h>\n")
        f.write(src)
    print("[1/5] 已生成", cpp)

    # ---------------- 2. 编译 sketch ----------------
    o = os.path.join(BUILD, "TemCtrlSys.ino.cpp.o")
    run([gcc] + common + need_arduino_h + [cpp, "-o", o], "编译 sketch")
    objs.append(o)
    print("[2/5] sketch 编译完成")

    # ---------------- 3. 编译 core ----------------
    core_objs = []
    for fn in sorted(os.listdir(CORE)):
        if not fn.endswith((".cpp", ".c", ".S")):
            continue
        path = os.path.join(CORE, fn)
        obj = os.path.join(BUILD, "core_" + fn + ".o")
        if fn.endswith(".cpp"):
            run([gcc] + common + [path, "-o", obj], "编译 core/" + fn)
        elif fn.endswith(".c"):
            run([gcc_c] + common + ["-x", "c", path, "-o", obj], "编译 core/" + fn)
        else:
            run([gcc_c] + common + ["-x", "assembler-with-cpp", path, "-o", obj],
                "编译 core/" + fn)
        core_objs.append(obj)
        objs.append(obj)
    # core 下的子目录（avr-libc 等）
    for sub in sorted(os.listdir(CORE)):
        sd = os.path.join(CORE, sub)
        if not os.path.isdir(sd):
            continue
        for fn in sorted(os.listdir(sd)):
            if not fn.endswith((".cpp", ".c", ".S")):
                continue
            path = os.path.join(sd, fn)
            obj = os.path.join(BUILD, "core_%s_%s.o" % (sub, fn))
            if fn.endswith(".cpp"):
                run([gcc] + common + [path, "-o", obj], "编译 core/%s/%s" % (sub, fn))
            elif fn.endswith(".c"):
                run([gcc_c] + common + ["-x", "c", path, "-o", obj],
                    "编译 core/%s/%s" % (sub, fn))
            else:
                run([gcc_c] + common + ["-x", "assembler-with-cpp", path, "-o", obj],
                    "编译 core/%s/%s" % (sub, fn))
            core_objs.append(obj)
            objs.append(obj)
    print("[3/5] core 编译完成 (%d 个文件)" % len(core_objs))

    # ---------------- 4. 编译库 ----------------
    lib_dirs = [
        os.path.join(LIBS, "LiquidCrystal", "src"),
        os.path.join(HWDIR, "libraries", "Wire", "src"),
        os.path.join(HWDIR, "libraries", "Wire", "src", "utility"),
    ]
    lib_objs = []
    seen = set()
    for ld in lib_dirs:
        if not os.path.isdir(ld):
            continue
        for fn in sorted(os.listdir(ld)):
            if not fn.endswith((".cpp", ".c")):
                continue
            key = fn
            if key in seen:
                continue
            seen.add(key)
            path = os.path.join(ld, fn)
            obj = os.path.join(BUILD, "lib_" + fn + ".o")
            if fn.endswith(".cpp"):
                run([gcc] + common + [path, "-o", obj], "编译库 " + fn)
            else:
                run([gcc_c] + common + ["-x", "c", path, "-o", obj], "编译库 " + fn)
            lib_objs.append(obj)
            objs.append(obj)
    print("[4/5] 库编译完成 (%d 个文件)" % len(lib_objs))

    # ---------------- 5. 链接 ----------------
    elf = os.path.join(BUILD, ELF_NAME)
    run([gcc, "-Os", "-g", "-mmcu=" + MCU, "-Wl,--gc-sections",
         "-o", elf] + objs + ["-lm"], "链接")
    print("[5/5] 链接完成 ->", elf, os.path.getsize(elf), "字节")

    # 顺带导出 hex，便于其它方式烧录
    objcopy = os.path.join(AVRBIN, "avr-objcopy.exe")
    hexf = os.path.join(BUILD, "TemCtrlSys.hex")
    subprocess.run([objcopy, "-O", "ihex", "-R", ".eeprom", elf, hexf],
                   capture_output=True)
    print("      同时导出:", hexf)

    if "--noinject" in sys.argv:
        return 0

    # ---------------- 注入工程 ----------------
    if not os.path.exists(PRJ):
        print("找不到工程:", PRJ); return 1
    blobs = {}
    with zipfile.ZipFile(PRJ, "r") as z:
        infos = z.infolist()
        for i in infos:
            blobs[i.filename] = z.read(i.filename)

    target = "FIRMWARE/ATmega328P/Debug/Debug.elf"
    if target not in blobs:
        print("工程中没有", target, "实际条目:", list(blobs)); return 1
    blobs[target] = open(elf, "rb").read()

    # sketch 源码也一并写入（供 VSM Studio 显示）
    blobs["FIRMWARE/ATmega328P/main.ino"] = src.encode("ascii", "replace")

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
    print("已注入工程:", PRJ, os.path.getsize(PRJ), "字节")

    with zipfile.ZipFile(PRJ) as z:
        d = z.read(target)
        print("校验 Debug.elf:", len(d), "字节, ELF 魔数 =", d[:4])
        print("ROOT.DSN 完好:", len(z.read("ROOT.DSN")), "字节")
    return 0


if __name__ == "__main__":
    sys.exit(main())
