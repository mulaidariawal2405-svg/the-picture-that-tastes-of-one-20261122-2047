#!/usr/bin/env python3
"""The picture that tastes of one ingredient: a steaming bowl of ramen.

Pure stdlib Python (zlib, struct, math, random only). Renders one
896x896 PNG to $OUTPUT_DIR/entry.png (default /output/entry.png).
No text anywhere in the image; the food does all the talking.
"""
import math
import os
import random
import struct
import zlib

W = H = 896
OUT = os.environ.get("OUTPUT_DIR", "/output")
random.seed(7)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.buf = bytearray(w * h * 3)

    def set_px(self, x, y, r, g, b):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.buf[i] = r
            self.buf[i + 1] = g
            self.buf[i + 2] = b

    def blend_px(self, x, y, r, g, b, a):
        """Alpha-blend one pixel; a in 0..1."""
        if 0 <= x < self.w and 0 <= y < self.h and a > 0:
            i = (y * self.w + x) * 3
            buf = self.buf
            buf[i] = int(buf[i] + (r - buf[i]) * a)
            buf[i + 1] = int(buf[i + 1] + (g - buf[i + 1]) * a)
            buf[i + 2] = int(buf[i + 2] + (b - buf[i + 2]) * a)

    def row_fill(self, y, x0, x1, r, g, b):
        if y < 0 or y >= self.h:
            return
        x0 = max(0, x0)
        x1 = min(self.w - 1, x1)
        if x0 > x1:
            return
        i = (y * self.w + x0) * 3
        n = x1 - x0 + 1
        self.buf[i:i + n * 3] = bytes((r, g, b)) * n

    def disc(self, cx, cy, rad, rgb):
        """Solid filled disc, fast row slices."""
        r, g, b = rgb
        r2 = rad * rad
        for y in range(max(0, cy - rad), min(self.h, cy + rad + 1)):
            dy = y - cy
            dx = int(math.sqrt(max(0, r2 - dy * dy)))
            self.row_fill(y, cx - dx, cx + dx, r, g, b)

    def disc_blend(self, cx, cy, rad, rgb, a):
        """Soft disc blended over what is already there."""
        r, g, b = rgb
        r2 = rad * rad
        for y in range(max(0, cy - rad), min(self.h, cy + rad + 1)):
            dy = y - cy
            for x in range(max(0, cx - rad), min(self.w, cx + rad + 1)):
                dx = x - cx
                if dx * dx + dy * dy <= r2:
                    self.blend_px(x, y, r, g, b, a)

    def radial_disc(self, cx, cy, rad, c0, c1):
        """Disc shading from c0 (centre) to c1 (edge), smoothstep falloff."""
        r2 = rad * rad
        for y in range(max(0, cy - rad), min(self.h, cy + rad + 1)):
            dy = y - cy
            for x in range(max(0, cx - rad), min(self.w, cx + rad + 1)):
                dx = x - cx
                d2 = dx * dx + dy * dy
                if d2 > r2:
                    continue
                t = math.sqrt(d2) / rad
                t = t * t * (3.0 - 2.0 * t)
                r = int(c0[0] + (c1[0] - c0[0]) * t)
                g = int(c0[1] + (c1[1] - c0[1]) * t)
                b = int(c0[2] + (c1[2] - c0[2]) * t)
                self.set_px(x, y, r, g, b)

    def ellipse(self, cx, cy, rx, ry, rgb):
        r, g, b = rgb
        for y in range(max(0, cy - ry), min(self.h, cy + ry + 1)):
            dy = (y - cy) / ry
            dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
            self.row_fill(y, cx - dx, cx + dx, r, g, b)

    def ellipse_blend(self, cx, cy, rx, ry, rgb, a):
        r, g, b = rgb
        for y in range(max(0, cy - ry), min(self.h, cy + ry + 1)):
            dy = (y - cy) / ry
            dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
            for x in range(max(0, cx - dx), min(self.w, cx + dx + 1)):
                self.blend_px(x, y, r, g, b, a)

    def ellipse_radial(self, cx, cy, rx, ry, c0, c1):
        for y in range(max(0, cy - ry), min(self.h, cy + ry + 1)):
            dy = (y - cy) / ry
            dx = int(rx * math.sqrt(max(0.0, 1.0 - dy * dy)))
            for x in range(max(0, cx - dx), min(self.w, cx + dx + 1)):
                nx = (x - cx) / rx
                t = math.sqrt(nx * nx + dy * dy)
                t = min(1.0, t)
                t = t * t * (3.0 - 2.0 * t)
                r = int(c0[0] + (c1[0] - c0[0]) * t)
                g = int(c0[1] + (c1[1] - c0[1]) * t)
                b = int(c0[2] + (c1[2] - c0[2]) * t)
                self.set_px(x, y, r, g, b)

    def thick_line(self, x0, y0, x1, y1, w, rgb):
        """Round-capped thick line via sampled discs."""
        length = math.hypot(x1 - x0, y1 - y0)
        steps = max(2, int(length / max(1, w // 2)))
        rad = w // 2
        for s in range(steps + 1):
            t = s / steps
            x = int(x0 + (x1 - x0) * t)
            y = int(y0 + (y1 - y0) * t)
            self.disc(x, y, rad, rgb)

    def ring(self, cx, cy, rad, thick, rgb):
        steps = max(24, int(2 * math.pi * rad / max(2, thick)))
        for s in range(steps):
            a = 2 * math.pi * s / steps
            self.disc(int(cx + rad * math.cos(a)), int(cy + rad * math.sin(a)),
                      max(1, thick // 2), rgb)

    def arc(self, cx, cy, rad, a0, a1, thick, rgb, alpha=None):
        steps = max(8, int(abs(a1 - a0) * rad / max(2, thick)))
        for s in range(steps + 1):
            a = a0 + (a1 - a0) * s / steps
            x = int(cx + rad * math.cos(a))
            y = int(cy + rad * math.sin(a))
            if alpha is None:
                self.disc(x, y, max(1, thick // 2), rgb)
            else:
                self.disc_blend(x, y, max(1, thick // 2), rgb, alpha)


# ---------------------------------------------------------------- png out
def write_png(path, cv):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.buf[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)

    def chunk(typ, data):
        out = struct.pack(">I", len(data)) + typ + data
        out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return out

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", comp) + chunk(b"IEND", b""))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ---------------------------------------------------------------- scene
BX, BY = 448, 505          # bowl centre
BOWL_R = 330               # outer bowl radius
BROTH_R = 292              # broth radius

CV = Canvas(W, H)


def draw_background():
    # Warm dark wall, vertical gradient, then a soft amber halo behind bowl.
    top = (26, 15, 10)
    bot = (58, 34, 18)
    for y in range(H):
        t = y / (H - 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        g = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        CV.row_fill(y, 0, W - 1, r, g, b)
    CV.disc_blend(448, 470, 470, (122, 66, 26), 0.20)
    CV.disc_blend(448, 470, 340, (150, 88, 34), 0.16)
    # Wooden table from y=560 down: warm planks with soft seams.
    for y in range(560, H):
        t = (y - 560) / (H - 560)
        r = int(74 + 26 * t)
        g = int(48 + 18 * t)
        b = int(28 + 10 * t)
        CV.row_fill(y, 0, W - 1, r, g, b)
    for seam in (640, 730, 820):
        for y in range(seam, seam + 3):
            CV.row_fill(y, 0, W - 1, 38, 24, 14)
    # Soft contact shadow under the bowl.
    CV.ellipse_blend(448, 852, 320, 42, (10, 6, 4), 0.55)
    CV.ellipse_blend(448, 848, 280, 32, (10, 6, 4), 0.45)


def draw_bowl_and_broth():
    # Ceramic bowl: near-black with a warm gradient and glossy rim.
    CV.radial_disc(BX, BY + 12, BOWL_R, (52, 56, 72), (16, 17, 24))
    CV.radial_disc(BX, BY, BROTH_R + 14, (30, 32, 44), (12, 13, 20))
    # Broth: rich golden-orange, glowing centre, deeper at the rim.
    CV.radial_disc(BX, BY, BROTH_R, (238, 146, 52), (168, 84, 18))
    # Oily sheen: soft lighter arcs on the broth surface.
    CV.arc(BX, BY, 220, math.radians(200), math.radians(320), 26,
           (250, 178, 84), alpha=0.35)
    CV.arc(BX, BY, 150, math.radians(20), math.radians(130), 18,
           (252, 190, 100), alpha=0.30)
    CV.arc(BX, BY, 262, math.radians(140), math.radians(250), 14,
           (214, 120, 40), alpha=0.35)
    # Glossy highlight where the light hits the broth.
    CV.ellipse_blend(360, 400, 120, 46, (255, 214, 140), 0.28)
    CV.ellipse_blend(340, 390, 60, 22, (255, 232, 180), 0.30)
    # Bright rim light along the top-left of the bowl.
    CV.arc(BX, BY, BOWL_R - 6, math.radians(150), math.radians(265), 10,
           (214, 190, 150), alpha=0.55)
    CV.arc(BX, BY, BOWL_R - 6, math.radians(180), math.radians(240), 6,
           (255, 230, 200), alpha=0.5)


def draw_noodles():
    """Wavy golden noodle strands floating on the broth, with a soft
    darker under-strand for depth. Everything is clipped to the broth."""
    tones = [(242, 193, 78), (232, 169, 59), (247, 215, 116), (226, 158, 48)]
    for strand in range(16):
        y_base = BY - 230 + strand * 30 + random.randint(-8, 8)
        amp = random.randint(10, 26)
        freq = random.uniform(0.018, 0.030)
        phase = random.uniform(0, 6.28)
        tone = tones[strand % len(tones)]
        shadow = (176, 108, 26)
        x = BX - BROTH_R + 12
        while x < BX + BROTH_R - 12:
            y = int(y_base + amp * math.sin(x * freq + phase)
                    + 6 * math.sin(x * 0.055 + phase * 2))
            if (x - BX) ** 2 + (y - BY) ** 2 < (BROTH_R - 8) ** 2:
                CV.disc(x + 2, y + 3, 6, shadow)
                CV.disc(x, y, 6, tone)
            x += 7
    # A lifted bundle of noodles draped over the rim, lower right.
    for strand in range(7):
        x0 = BX + 150 + strand * 12
        y0 = BY + 60
        for s in range(26):
            t = s / 25
            x = int(x0 + 26 * math.sin(t * 5.2 + strand) - t * 40)
            y = int(y0 + t * 190 + 8 * math.sin(t * 9 + strand * 2))
            CV.disc(x + 2, y + 3, 6, (176, 108, 26))
            CV.disc(x, y, 6, tones[(strand + 1) % len(tones)])
    # Glossy highlights on a few strands.
    for (hx, hy) in ((330, 330), (470, 640), (560, 300), (400, 700)):
        CV.disc_blend(hx, hy, 16, (255, 226, 150), 0.35)


def draw_toppings():
    # --- nori sheet, tucked under the noodles at the left rim.
    for y in range(BY - 150, BY + 60):
        t = (y - (BY - 150)) / 210
        wdt = int(64 - 18 * t)
        CV.row_fill(y, BX - BROTH_R + 8 - wdt // 2, BX - BROTH_R + 8 + wdt // 2,
                    26, 42, 24)
    CV.thick_line(BX - BROTH_R + 8, BY - 150, BX - BROTH_R + 8, BY + 60,
                  3, (74, 110, 60))
    # --- chashu: two overlapping roasted pork slices, lower left.
    for (cx, cy, rx, ry) in ((330, 600, 92, 66), (415, 660, 84, 60)):
        CV.ellipse_radial(cx, cy, rx, ry, (232, 180, 143), (150, 88, 58))
        CV.ellipse(cx - 6, cy - 8, rx - 26, ry - 22, (216, 150, 112))
        CV.ellipse_blend(cx - 14, cy - 14, 34, 20, (255, 214, 170), 0.4)
    # --- ajitama egg: glossy white, molten orange yolk, upper right.
    ex, ey = 565, 415
    CV.ellipse_radial(ex, ey, 84, 66, (255, 252, 244), (214, 196, 168))
    CV.ellipse_blend(ex - 22, ey - 20, 30, 16, (255, 255, 255), 0.55)
    CV.radial_disc(ex + 4, ey + 2, 38, (255, 158, 46), (214, 106, 8))
    CV.disc_blend(ex - 8, ey - 10, 12, (255, 196, 96), 0.5)
    CV.disc(ex + 14, ey + 12, 5, (255, 220, 140))
    # --- spring onion rings scattered over the broth.
    for _ in range(20):
        ox = BX + random.randint(-240, 240)
        oy = BY + random.randint(-240, 240)
        if (ox - BX) ** 2 + (oy - BY) ** 2 > (BROTH_R - 24) ** 2:
            continue
        if (ox - ex) ** 2 + (oy - ey) ** 2 < 95 ** 2:
            continue
        r = random.randint(7, 11)
        CV.disc(ox, oy, r, (52, 140, 66))
        CV.disc(ox, oy, max(3, r - 4), (126, 198, 92))
        CV.disc(ox, oy, max(2, r - 7), (40, 110, 52))
    # --- sesame seeds and chilli oil dots for appetite.
    for _ in range(26):
        sx = BX + random.randint(-250, 250)
        sy = BY + random.randint(-250, 250)
        if (sx - BX) ** 2 + (sy - BY) ** 2 > (BROTH_R - 18) ** 2:
            continue
        CV.disc(sx, sy, 3, (250, 238, 208))
    for (cx, cy) in ((300, 470), (620, 560), (480, 330), (380, 760), (640, 430)):
        CV.disc(cx, cy, 9, (206, 58, 12))
        CV.disc_blend(cx - 3, cy - 3, 4, (255, 120, 60), 0.6)


def draw_steam_and_chopsticks():
    # --- chopsticks resting on the rim, upper right, warm wood.
    CV.thick_line(600, 210, 838, 96, 15, (150, 100, 52))
    CV.thick_line(612, 228, 846, 118, 15, (150, 100, 52))
    CV.thick_line(600, 206, 838, 92, 5, (196, 140, 82))
    CV.thick_line(612, 224, 846, 114, 5, (196, 140, 82))
    CV.disc(600, 210, 8, (120, 78, 40))
    CV.disc(612, 228, 8, (120, 78, 40))
    # --- thin rising steam above the bowl, soft and translucent.
    for strand in range(6):
        x_base = BX - 180 + strand * 72
        phase = strand * 1.3
        for y in range(130, 330, 4):
            t = (330 - y) / 200
            x = int(x_base + 22 * math.sin(y * 0.022 + phase)
                    + 10 * math.sin(y * 0.05 + phase * 2))
            rad = int(9 + 9 * t)
            CV.disc_blend(x, y, rad, (255, 244, 226), 0.05 + 0.05 * t)
    CV.disc_blend(448, 210, 150, (255, 240, 220), 0.05)
    # --- gentle corner vignette so the bowl stays the hero.
    for (cx, cy) in ((0, 0), (W, 0), (0, H), (W, H)):
        CV.disc_blend(cx, cy, 260, (8, 5, 3), 0.30)
        CV.disc_blend(cx, cy, 170, (8, 5, 3), 0.28)


def main():
    draw_background()
    draw_bowl_and_broth()
    draw_noodles()
    draw_toppings()
    draw_steam_and_chopsticks()
    path = os.path.join(OUT, "entry.png")
    size = write_png(path, CV)
    print("wrote", path, "bytes:", size, "size:", W, "x", H)


if __name__ == "__main__":
    main()
