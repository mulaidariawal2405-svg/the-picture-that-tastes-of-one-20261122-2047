#!/usr/bin/env python3
"""Golden Hour Ramen - a steaming bowl of ramen, top-down view.

Pure stdlib (zlib, struct, math, random). Renders one appetising food
photograph procedurally and writes it to /output/entry.png.
No network, no text in the image.
"""

import math
import os
import random
import struct
import zlib

W = H = 896
OUT = "/output/entry.png"
rng = random.Random(20261122)


# ---------------------------------------------------------------- canvas
class Canvas:
    """Simple RGB float buffer with a small drawing vocabulary."""

    def __init__(self, w, h, base):
        self.w, self.h = w, h
        self.px = bytearray(base * w * h)

    def set(self, x, y, rgb):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(rgb)

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return self.px[i], self.px[i + 1], self.px[i + 2]

    def blend(self, x, y, rgb, a):
        if not (0 <= x < self.w and 0 <= y < self.h) or a <= 0:
            return
        if a >= 1:
            self.set(x, y, rgb)
            return
        i = (y * self.w + x) * 3
        for k in range(3):
            self.px[i + k] = int(self.px[i + k] * (1 - a) + rgb[k] * a)

    def disc(self, cx, cy, r, rgb, a=1.0):
        r2 = r * r
        x0, x1 = int(cx - r), int(cx + r) + 1
        y0, y1 = int(cy - r), int(cy + r) + 1
        for y in range(y0, y1):
            for x in range(x0, x1):
                dx, dy = x - cx, y - cy
                if dx * dx + dy * dy <= r2:
                    self.blend(x, y, rgb, a)

    def soft_disc(self, cx, cy, r, rgb, a=1.0):
        """Disc with a soft feathered edge."""
        r2 = r * r
        x0, x1 = int(cx - r), int(cx + r) + 1
        y0, y1 = int(cy - r), int(cy + r) + 1
        for y in range(y0, y1):
            for x in range(x0, x1):
                dx, dy = x - cx, y - cy
                d2 = dx * dx + dy * dy
                if d2 <= r2:
                    edge = 1.0 - (d2 / r2) ** 3
                    self.blend(x, y, rgb, a * edge)

    def hline(self, x0, x1, y, rgb, a=1.0):
        for x in range(int(x0), int(x1) + 1):
            self.blend(x, int(y), rgb, a)

    def vline(self, x, y0, y1, rgb, a=1.0):
        for y in range(int(y0), int(y1) + 1):
            self.blend(int(x), y, rgb, a)


def clamp(v, lo=0, hi=255):
    return max(lo, min(hi, int(v)))


def mix(c1, c2, t):
    return tuple(clamp(c1[k] * (1 - t) + c2[k] * t) for k in range(3))


def shade(rgb, f):
    return tuple(clamp(c * f) for c in rgb)


def add_noise(cv, amt, seed=7):
    r = random.Random(seed)
    for i in range(0, len(cv.px), 3):
        n = r.randint(-amt, amt)
        for k in range(3):
            cv.px[i + k] = clamp(cv.px[i + k] + n)


# ---------------------------------------------------------------- PNG out
def write_png(path, cv):
    raw = bytearray()
    stride = cv.w * 3
    prev = bytearray(stride)
    for y in range(cv.h):
        row = cv.px[y * stride:(y + 1) * stride]
        raw.append(2)  # filter Up: stores row minus row above, compresses far better
        raw += bytes((row[i] - prev[i]) & 0xFF for i in range(stride))
        prev = bytearray(row)
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# ------------------------------------------------------- warm wood table
def paint_table(cv):
    # Dark warm wooden table with a soft radial pool of light at centre.
    cx, cy = cv.w / 2, cv.h / 2
    for y in range(cv.h):
        for x in range(cv.w):
            d = math.hypot(x - cx, y - cy) / (cv.w * 0.62)
            glow = math.exp(-d * d * 1.6)
            base = (
                52 + 62 * glow,
                34 + 40 * glow,
                22 + 24 * glow,
            )
            # wood grain: slow horizontal waves
            g = math.sin((y + 9 * math.sin(x * 0.006)) * 0.045) * 0.5 + 0.5
            wob = 0.92 + 0.16 * g
            # plank seams every ~150 px
            seam = 0.82 if abs((y % 150) - 0) < 1.5 else 1.0
            cv.set(x, y, tuple(clamp(c * wob * seam) for c in base))
    # soft vignette
    for y in range(cv.h):
        for x in range(cv.w):
            d = math.hypot(x - cx, y - cy) / (cv.w * 0.55)
            if d > 0.85:
                a = min(0.5, (d - 0.85) * 1.4)
                cv.blend(x, y, (12, 8, 5), a)


# ------------------------------------------------------------- bowl+broth
def paint_bowl(cv):
    cx, cy = cv.w / 2, cv.h / 2 + 6
    R = 330          # outer bowl radius
    RIM = 26         # rim thickness
    # drop shadow under bowl
    cv.soft_disc(cx + 14, cy + 20, R + 12, (8, 5, 3), 0.55)
    # outer bowl: deep charcoal ceramic with warm highlight top-left
    for y in range(int(cy - R), int(cy + R) + 1):
        for x in range(int(cx - R), int(cx + R) + 1):
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            if d <= R:
                t = d / R
                col = mix((38, 34, 38), (16, 14, 18), t * t)
                # warm light from upper left
                lx = (-dx - dy) / (2 * R)
                col = mix(col, (96, 74, 66), max(0.0, lx) * 0.35)
                cv.set(x, y, col)
    # rim ring
    for y in range(int(cy - R), int(cy + R) + 1):
        for x in range(int(cx - R), int(cx + R) + 1):
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            if R - RIM <= d <= R - 4:
                ang = math.atan2(dy, dx)
                wob = 1 + 0.02 * math.sin(ang * 9)
                col = mix((88, 40, 30), (140, 62, 44), 0.5 + 0.5 * math.sin(ang * 3))
                cv.blend(x, y, col, 0.9 * wob)
    # broth: golden-orange gradient, brightest near centre-left light
    for y in range(int(cy - (R - RIM)), int(cy + (R - RIM)) + 1):
        for x in range(int(cx - (R - RIM)), int(cx + (R - RIM)) + 1):
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            if d <= R - RIM:
                t = d / (R - RIM)
                col = mix((238, 158, 52), (176, 92, 26), t * t)
                lx = (-dx - dy) / (2 * (R - RIM))
                col = mix(col, (255, 206, 110), max(0.0, lx) * 0.45)
                # gentle swirl
                sw = 0.5 + 0.5 * math.sin(math.atan2(dy, dx) * 3 + d * 0.03)
                col = mix(col, (214, 128, 40), sw * 0.12)
                cv.set(x, y, col)
    # oil sheen: glossy blobs on the broth
    for _ in range(26):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0, R - RIM - 30)
        ox, oy = cx + rr * math.cos(a), cy + rr * math.sin(a)
        s = rng.uniform(10, 42)
        col = rng.choice([(255, 214, 130), (250, 190, 96), (255, 232, 160)])
        cv.soft_disc(ox, oy, s, col, rng.uniform(0.10, 0.28))
    # big specular highlight upper left
    cv.soft_disc(cx - 150, cy - 150, 95, (255, 226, 160), 0.35)
    cv.soft_disc(cx - 170, cy - 170, 45, (255, 240, 200), 0.4)


# ------------------------------------------------------------- noodles
def paint_noodles(cv):
    cx, cy = cv.w / 2, cv.h / 2 + 6
    R = 268
    noodle_cols = [(246, 214, 130), (232, 190, 96), (252, 228, 158)]
    for _ in range(150):
        # wavy noodle strand: arc segment inside the broth
        a0 = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(30, R - 18)
        span = rng.uniform(0.5, 1.5)
        steps = int(span * 60)
        col = rng.choice(noodle_cols)
        for s in range(steps):
            a = a0 + s * 0.016
            wob = 7 * math.sin(s * 0.35)
            rr = r0 + wob
            x = cx + rr * math.cos(a)
            y = cy + rr * math.sin(a) * 0.98
            cv.soft_disc(x, y, 3.4, col, 0.95)
            cv.soft_disc(x, y - 1.2, 1.4, (255, 240, 190), 0.5)
    # a lifted tangle of noodles at the centre, catching the light
    for _ in range(46):
        a0 = rng.uniform(0, 2 * math.pi)
        r0 = rng.uniform(6, 78)
        span = rng.uniform(0.4, 1.0)
        steps = int(span * 55)
        col = rng.choice(noodle_cols)
        for s in range(steps):
            a = a0 + s * 0.02
            wob = 5 * math.sin(s * 0.4)
            rr = r0 + wob
            x = cx + rr * math.cos(a)
            y = cy - 8 + rr * math.sin(a) * 0.9
            cv.soft_disc(x, y, 4.2, col, 1.0)
            cv.soft_disc(x, y - 1.4, 1.6, (255, 242, 200), 0.55)
    # sesame seeds
    for _ in range(70):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(0, R - 12)
        x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
        col = rng.choice([(250, 240, 215), (222, 196, 150)])
        cv.disc(x, y, 2.6, col, 0.95)


# ------------------------------------------------------------- toppings
def paint_egg(cv):
    # Ajitama half, glossy amber yolk, lower right of the bowl.
    cx, cy = 598, 568
    cv.soft_disc(cx + 4, cy + 5, 72, (60, 30, 10), 0.35)
    # white
    for y in range(cy - 66, cy + 67):
        for x in range(cx - 66, cx + 67):
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            if d <= 64:
                t = d / 64
                col = mix((252, 246, 232), (214, 198, 176), t)
                cv.set(x, y, col)
    # amber yolk with glossy highlight
    for y in range(cy - 40, cy + 41):
        for x in range(cx - 40, cx + 41):
            dx, dy = x - cx, y - cy
            d = math.hypot(dx, dy)
            if d <= 38:
                t = d / 38
                col = mix((255, 170, 40), (214, 106, 12), t * t)
                cv.set(x, y, col)
    cv.soft_disc(cx - 14, cy - 16, 14, (255, 214, 120), 0.65)
    cv.soft_disc(cx - 12, cy - 14, 6, (255, 240, 190), 0.7)


def paint_chashu(cv):
    # Two overlapping slices of glistening chashu pork, upper left.
    for (cx, cy, r) in [(330, 330, 92), (408, 392, 78)]:
        cv.soft_disc(cx + 5, cy + 6, r, (60, 28, 12), 0.35)
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                dx, dy = x - cx, y - cy
                d = math.hypot(dx, dy)
                if d <= r:
                    t = d / r
                    # marbled pink meat with pale fat rings
                    ring = 0.5 + 0.5 * math.sin(d * 0.28 + 1.2)
                    col = mix((196, 96, 66), (150, 62, 44), t)
                    col = mix(col, (240, 204, 178), ring * 0.30)
                    cv.set(x, y, col)
        # charred sear edge + glaze highlight
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                dx, dy = x - cx, y - cy
                d = math.hypot(dx, dy)
                if r - 9 <= d <= r:
                    cv.blend(x, y, (112, 52, 30), 0.55)
        cv.soft_disc(cx - r * 0.35, cy - r * 0.4, r * 0.3, (255, 190, 140), 0.28)


def paint_nori(cv):
    # Dark green-black nori sheet tucked at the bowl edge, upper right.
    cx, cy = 648, 300
    for y in range(cy - 62, cy + 95):
        for x in range(cx - 44, cx + 45):
            if 0 <= x < cv.w and 0 <= y < cv.h:
                wob = 10 * math.sin((y - cy) * 0.05)
                xx = x + wob
                if abs(xx - cx) < 42 and abs(y - cy) < 92:
                    edge = min(1.0, (42 - abs(xx - cx)) / 8.0)
                    col = mix((12, 26, 14), (34, 58, 30), 0.5 + 0.5 * math.sin(x * 0.3 + y * 0.22))
                    cv.blend(x, y, col, 0.96 * edge)
    cv.soft_disc(cx - 12, cy - 30, 20, (70, 110, 60), 0.25)


def paint_scallions(cv):
    # Bright green scallion rings scattered over the broth.
    cx, cy = cv.w / 2, cv.h / 2 + 6
    for _ in range(34):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(90, 250)
        x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
        r = rng.uniform(7, 12)
        col = rng.choice([(58, 168, 74), (86, 196, 96), (38, 140, 58)])
        cv.disc(x, y, r, col, 0.95)
        cv.disc(x, y, r * 0.55, (16, 84, 34), 0.95)
        cv.soft_disc(x - r * 0.3, y - r * 0.3, r * 0.3, (190, 240, 150), 0.5)


def paint_chili_oil(cv):
    # Ruby chili-oil droplets and a swirl on the broth surface.
    cx, cy = cv.w / 2, cv.h / 2 + 6
    for _ in range(16):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(60, 250)
        x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
        cv.soft_disc(x, y, rng.uniform(5, 13), (178, 32, 16), rng.uniform(0.5, 0.8))
        cv.soft_disc(x - 2, y - 2, 2.5, (255, 120, 70), 0.5)


def paint_chopsticks(cv):
    # Wooden chopsticks resting across the bowl's upper-right rim.
    x0, y0 = 640, 130
    x1, y1 = 880, 420
    n = 260
    for k in range(n):
        t = k / n
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        wdt = 5.5 - 3.0 * t
        for dy in range(-int(wdt), int(wdt) + 1):
            shade_col = mix((146, 96, 52), (196, 146, 88), 0.5 + 0.5 * math.sin(t * 40))
            cv.blend(int(x), int(y + dy), shade_col, 0.95)
        cv.blend(int(x), int(y - wdt), (220, 178, 118), 0.6)
    # second stick, slightly offset
    x0, y0 = 624, 148
    x1, y1 = 866, 440
    for k in range(n):
        t = k / n
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t
        wdt = 5.5 - 3.0 * t
        for dy in range(-int(wdt), int(wdt) + 1):
            shade_col = mix((132, 86, 46), (182, 132, 78), 0.5 + 0.5 * math.sin(t * 40))
            cv.blend(int(x), int(y + dy), shade_col, 0.95)
        cv.blend(int(x), int(y - wdt), (210, 166, 108), 0.6)


def paint_steam(cv):
    # Thin rising steam wisps above the bowl.
    cx = cv.w / 2
    for s in range(7):
        bx = cx - 190 + s * 62
        ph = rng.uniform(0, 6.28)
        for y in range(60, 250):
            sway = 26 * math.sin(y * 0.028 + ph + s)
            x = bx + sway
            fade = math.sin((y - 60) / 190 * math.pi)
            a = 0.10 * fade
            cv.soft_disc(x, y, 9, (255, 246, 232), a)


# ------------------------------------------------------------------ main
def main():
    cv = Canvas(W, H, (44, 29, 19))
    paint_table(cv)
    paint_bowl(cv)
    paint_noodles(cv)
    paint_chashu(cv)
    paint_nori(cv)
    paint_egg(cv)
    paint_scallions(cv)
    paint_chili_oil(cv)
    paint_chopsticks(cv)
    paint_steam(cv)
    add_noise(cv, 2)
    size = write_png(OUT, cv)
    print(f"wrote {OUT} {W}x{H} {size} bytes")


if __name__ == "__main__":
    main()


