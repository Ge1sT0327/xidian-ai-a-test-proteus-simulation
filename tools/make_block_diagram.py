# -*- coding: utf-8 -*-
"""绘制《温度测控仿真系统》系统框图（报告插图）"""
import math
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "screenshots", "sys_block.png")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

SCALE = 3
W, H = 1180, 620
img = Image.new("RGB", (W * SCALE, H * SCALE), "white")
d = ImageDraw.Draw(img)

BLUE_F, BLUE_O = "#e8f0ff", "#2f6fd0"
GREEN_F, GREEN_O = "#e7f9ee", "#2f9e58"


def font(size, bold=False):
    for c in ((r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
              (r"C:\Windows\Fonts\simhei.ttf" if bold else r"C:\Windows\Fonts\simsun.ttc")):
        if os.path.exists(c):
            try:
                return ImageFont.truetype(c, size * SCALE)
            except Exception:
                pass
    return ImageFont.load_default()


F = font(15)
FB = font(17, bold=True)
FS = font(14)


def box(x, y, w, h, text, fill=BLUE_F, outline=BLUE_O, f=None):
    d.rounded_rectangle([x * SCALE, y * SCALE, (x + w) * SCALE, (y + h) * SCALE],
                        radius=9 * SCALE, fill=fill, outline=outline, width=2 * SCALE)
    f = f or FB
    tb = d.textbbox((0, 0), text, font=f)
    d.text(((x + w / 2) * SCALE - (tb[2] - tb[0]) / 2,
            (y + h / 2) * SCALE - (tb[3] - tb[1]) / 2 - tb[1]), text, font=f, fill="#12243d")


def arrow(x1, y1, x2, y2, label=None, color=BLUE_O, both=False, side="above"):
    d.line([x1 * SCALE, y1 * SCALE, x2 * SCALE, y2 * SCALE], fill=color, width=2 * SCALE)
    ang = math.atan2(y2 - y1, x2 - x1)
    L, sp = 13, math.radians(21)
    tips = [(x2, y2, ang), (x1, y1, ang + math.pi)] if both else [(x2, y2, ang)]
    for tx, ty, a in tips:
        d.polygon([(tx * SCALE, ty * SCALE),
                   ((tx - L * math.cos(a - sp)) * SCALE, (ty - L * math.sin(a - sp)) * SCALE),
                   ((tx - L * math.cos(a + sp)) * SCALE, (ty - L * math.sin(a + sp)) * SCALE)],
                  fill=color)
    if label:
        f = FS
        tb = d.textbbox((0, 0), label, font=f)
        tw, th = tb[2] - tb[0], tb[3] - tb[1]
        if side == "above":
            px = (x1 + x2) / 2 * SCALE - tw / 2
            py = (y1 + y2) / 2 * SCALE - th - 9 * SCALE
        elif side == "right":
            px = (x1 + x2) / 2 * SCALE + 10 * SCALE
            py = (y1 + y2) / 2 * SCALE - th / 2
        else:  # below
            px = (x1 + x2) / 2 * SCALE - tw / 2
            py = (y1 + y2) / 2 * SCALE + 7 * SCALE
        d.rectangle([px - 4 * SCALE, py - 2 * SCALE, px + tw + 4 * SCALE, py + th + 3 * SCALE],
                    fill="white")
        d.text((px, py - tb[1]), label, font=f, fill="#5a6b80")


# ---------------- 布局 ----------------
AX, AY, AW, AH = 460, 90, 260, 76          # Arduino UNO
SX, SY, SW, SH = 50, 90, 250, 76           # 温度传感器
MX, MY, MW, MH = 860, 90, 270, 76          # 直流电机控制驱动
LX, LY, LW, LH = 860, 270, 270, 76         # LCD 显示
PX, PY, PW, PH = 460, 300, 260, 76         # 串口接口组件
CX, CY, CW, CH = 50, 300, 250, 76          # PC 上位机

box(SX, SY, SW, SH, "温度传感器 BMP180")
box(AX, AY, AW, AH, "Arduino UNO", fill="#d8e7ff")
box(MX, MY, MW, MH, "直流电机控制驱动")
box(LX, LY, LW, LH, "LCD1602 显示")
box(PX, PY, PW, PH, "串口接口组件")
box(CX, CY, CW, CH, "PC 上位机", fill=GREEN_F, outline=GREEN_O)

d.text((AX * SCALE, (AY + AH + 4) * SCALE), "ATmega328P  16 MHz", font=F, fill="#5a6b80")

arrow(SX + SW, SY + SH / 2, AX, AY + AH / 2, "I2C  SDA=A4  SCL=A5", side="above")
arrow(AX + AW, AY + AH / 2, MX, MY + MH / 2, "IO7 (D7)", side="above")
arrow(AX + AW, AY + AH - 6, LX, LY + 14, "IO2~IO5, IO11, IO12", side="right")
arrow(AX + AW / 2, AY + AH, PX + PW / 2, PY, "TXD / RXD", both=True, side="right")
arrow(PX, PY + PH / 2, CX + CW, CY + CH / 2, "9600 8-N-1", color=GREEN_O, side="above")
arrow(CX + CW, CY + CH / 2, PX, PY + PH / 2, None, color=GREEN_O)

d.text((SX * SCALE, 560 * SCALE),
       "说明：传感器温度由手动调节；温度 > 33 ℃ 时 IO7 输出高电平，驱动直流电机转动；"
       "温度 ≤ 33 ℃ 时电机停止。", font=F, fill="#7a879b")
d.text((SX * SCALE, 588 * SCALE),
       "LCD 第一行显示 ID：23009290073，第二行显示 TEMP：温度值；温度值同时回传 PC 上位机显示。",
       font=F, fill="#7a879b")

img = img.resize((W, H), Image.LANCZOS)
img.save(OUT)
print("已生成:", OUT, img.size)
