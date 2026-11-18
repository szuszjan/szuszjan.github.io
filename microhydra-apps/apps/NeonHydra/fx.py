"""NEON HYDRA - fast pixel effects (viper) drawing straight into the 240x135 RGB565 framebuffer.

All colors passed to these functions must already be in framebuffer byte order
(see swap() in __init__). Parameter arrays (array('i')) are used to keep the
viper argument count low.
"""

_W = const(240)
_H = const(135)


@micropython.viper
def fill_rows(fb, rowc, y0: int, y1: int):
    """Fill rows y0..y1-1, each with its own color from rowc (array('H') of 135)."""
    p = ptr16(fb)
    c = ptr16(rowc)
    y = y0
    while y < y1:
        col = c[y]
        i = y * 240
        e = i + 240
        while i < e:
            p[i] = col
            i += 1
        y += 1


@micropython.viper
def plasma(fb, sint, pal, prm):
    """Classic sine plasma, 2 px wide. prm: a, b, c, d (phases), palette shift."""
    p = ptr16(fb)
    s = ptr8(sint)
    c = ptr16(pal)
    q = ptr32(prm)
    a = q[0]
    b = q[1]
    d = q[2]
    e = q[3]
    shift = q[4]
    y = 0
    while y < 135:
        ry = s[(y * 2 + b) & 255] + s[(y + e) & 255] + shift
        i = y * 240
        x = 0
        while x < 240:
            v = s[(x + a) & 255] + ry + s[(x + y + d) & 255]
            col = c[v & 255]
            p[i] = col
            p[i + 1] = col
            i += 2
            x += 2
        y += 1


@micropython.viper
def tunnel(fb, tab, pal, prm):
    """2x2 block tunnel from precomputed angle/depth/shade tables (120x68 each).

    prm: u offset (rotation), v offset (movement)
    """
    p = ptr16(fb)
    t = ptr8(tab)
    c = ptr16(pal)
    q = ptr32(prm)
    du = q[0]
    dv = q[1]
    n = 8160
    j = 0
    by = 0
    while by < 68:
        k = by * 480
        last = by == 67
        bx = 0
        while bx < 120:
            u = t[j] + du
            v = t[j + n] + dv
            col = c[((((u >> 4) ^ (v >> 4)) & 1) << 7) | (((u + v) >> 2) & 7) << 4 | t[j + n + n]]
            p[k] = col
            p[k + 1] = col
            if not last:
                p[k + 240] = col
                p[k + 241] = col
            k += 2
            j += 1
            bx += 1
        by += 1


@micropython.viper
def roto(fb, tex, prm):
    """Rotozoomer of a 64x64 texture. prm: u0, v0, dux, dvx, duy, dvy (fixed point, 10 bit)."""
    p = ptr16(fb)
    t = ptr16(tex)
    q = ptr32(prm)
    u0 = q[0]
    v0 = q[1]
    dux = q[2]
    dvx = q[3]
    duy = q[4]
    dvy = q[5]
    i = 0
    y = 0
    while y < 135:
        u = u0
        v = v0
        x = 0
        while x < 240:
            p[i] = t[(((v >> 10) & 63) << 6) | ((u >> 10) & 63)]
            i += 1
            u += dux
            v += dvx
            x += 1
        u0 += duy
        v0 += dvy
        y += 1


@micropython.viper
def fire_step(buf, prm):
    """Advance the fire simulation (120 x 70 cells). prm: seed, heat (0-255), cooling per row."""
    b = ptr8(buf)
    q = ptr32(prm)
    seed = q[0]
    heat = q[1]
    cool = q[2]
    w = 120
    h = 70
    # the two bottom rows (not drawn) are the random heat source
    i = (h - 2) * w
    e = i + w + w
    while i < e:
        seed = (seed * 69069 + 1) & 0x3FFFFFFF  # small-int constants only (viper)
        r = (seed >> 14) & 255
        if r < heat:
            b[i] = 255
        else:
            b[i] = r >> 3
        i += 1
    y = 0
    while y < h - 2:
        i = y * w + 1
        e = y * w + w - 1
        while i < e:
            v = (b[i + w - 1] + b[i + w] + b[i + w + 1] + b[i + w + w]) >> 2
            if v > cool:
                v -= cool
            else:
                v = 0
            b[i] = v
            i += 1
        y += 1
    q[0] = seed


@micropython.viper
def fire_draw(fb, buf, pal, y0: int):
    """Draw fire cells as 2x2 blocks, starting at screen row y0 (cells 0..67)."""
    p = ptr16(fb)
    b = ptr8(buf)
    c = ptr16(pal)
    by = 0
    while by < 68:
        sy = y0 + by * 2
        if 0 <= sy < 134:
            k = sy * 240
            j = by * 120
            bx = 0
            while bx < 120:
                v = b[j]
                if v > 8:
                    col = c[v]
                    p[k] = col
                    p[k + 1] = col
                    p[k + 240] = col
                    p[k + 241] = col
                k += 2
                j += 1
                bx += 1
        by += 1


@micropython.viper
def build_cols(font, text, out) -> int:
    """Convert text into 32-bit column masks (16x32 font, 16 columns per char).

    Returns the number of columns written.
    """
    g = ptr8(font)
    s = ptr8(text)
    o = ptr32(out)
    n = int(len(text))
    col = 0
    ci = 0
    while ci < n:
        base = s[ci] * 64
        cx = 0
        while cx < 16:
            m = 0
            r = 0
            byte_off = cx >> 3
            bit = 7 - (cx & 7)
            while r < 32:
                if (g[base + r * 2 + byte_off] >> bit) & 1:
                    m |= 1 << r
                r += 1
            o[col] = m
            col += 1
            cx += 1
        ci += 1
    return col


@micropython.viper
def big_text(fb, cols, prm, ctab):
    """Draw column-mask text with a sine wave and a vertical color gradient.

    prm: ncols, scroll (screen x of column 0 is -scroll), y base, amplitude,
         sine phase, sine x-speed, x scale shift (0/1), y scale (1/2),
         gradient offset, shadow color (0 = none), clip y0, clip y1
    ctab: array('H'): [0..255] sine table values 0..255, [256..319] gradient colors
    """
    p = ptr16(fb)
    m = ptr32(cols)
    q = ptr32(prm)
    t = ptr16(ctab)
    ncols = q[0]
    scroll = q[1]
    ybase = q[2]
    amp = q[3]
    phase = q[4]
    xs = q[5]
    sh = q[6]
    ys = q[7]
    goff = q[8]
    shadow = q[9]
    cy0 = q[10]
    cy1 = q[11]
    x = 0
    while x < 240:
        c = (scroll + x) >> sh
        if 0 <= c < ncols:
            mask = m[c]
            if mask:
                y = ybase + (((t[(x * xs + phase) & 255] - 128) * amp) >> 7)
                r = 0
                while r < 32:
                    if (mask >> r) & 1:
                        col = t[256 + ((r + goff) & 63)]
                        k = 0
                        while k < ys:
                            yy = y + r * ys + k
                            if cy0 <= yy < cy1:
                                p[yy * 240 + x] = col
                                if shadow:
                                    yd = yy + 3
                                    if yd < cy1 and x + 3 < 240:
                                        if p[yd * 240 + x + 3] != col:
                                            p[yd * 240 + x + 3] = shadow
                            k += 1
                    r += 1
        x += 1


@micropython.viper
def twister(fb, prm, tabs):
    """Rotating twisted bar. prm: center x, half width, angle base, twist phase, twist amount.

    tabs: array('H'): [0..255] sine 0..255, [256..319] 4 faces x 16 shades colors
    """
    p = ptr16(fb)
    q = ptr32(prm)
    t = ptr16(tabs)
    cx = q[0]
    hw = q[1]
    base = q[2]
    ph = q[3]
    tw = q[4]
    y = 0
    while y < 135:
        a = base + (((t[(y * 2 + ph) & 255] - 128) * tw) >> 7)
        f = 0
        xprev = cx + (((t[(a + 64) & 255] - 128) * hw) >> 7)
        while f < 4:
            a2 = a + (f + 1) * 64
            xn = cx + (((t[(a2 + 64) & 255] - 128) * hw) >> 7)
            if xn > xprev:
                w = xn - xprev
                shade = (w * 15) // (hw + hw)
                if shade > 15:
                    shade = 15
                col = t[256 + f * 16 + shade]
                i = y * 240 + xprev
                e = y * 240 + xn
                while i < e:
                    p[i] = col
                    i += 1
                # dark edge line
                p[y * 240 + xprev] = t[256 + f * 16]
            xprev = xn
            f += 1
        y += 1


@micropython.viper
def blend(fb, prm):
    """Blend every pixel toward a color. prm: amount 0..32, r5, g6, b5, swapped(0/1)."""
    p = ptr16(fb)
    q = ptr32(prm)
    k = q[0]
    tr = q[1]
    tg = q[2]
    tb = q[3]
    sw = q[4]
    ik = 32 - k
    i = 0
    while i < 32400:
        c = p[i]
        if sw:
            c = ((c & 255) << 8) | (c >> 8)
        r = (((c >> 11) * ik) + tr * k) >> 5
        g = ((((c >> 5) & 63) * ik) + tg * k) >> 5
        b = (((c & 31) * ik) + tb * k) >> 5
        c = (r << 11) | (g << 5) | b
        if sw:
            c = ((c & 255) << 8) | (c >> 8)
        p[i] = c
        i += 1
