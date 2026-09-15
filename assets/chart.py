#!/usr/bin/env python3
"""内联 SVG 图表库。无外部依赖，file:// 下可用。

两套调色板，函数接口通用，颜色靠参数传进去：
- 默认一套是方向 2「智库冷青」（TEAL / CLAY 那组，也是各函数的默认值）
- NEWS_ 打头的另一套是方向 9「新闻数据版」，用法见它们上方的注释

设计约束（来自 huashu-report/references/图表模式库.md）：
- 分类色不超过 6 个；语义色只用两端
- 直接标注优先于图例
- Y 轴从零开始，除非显式标注
"""

INK = "#231f20"        # 正文近黑
MUTE = "#6b6b6b"       # 次级灰
RULE = "#d8d8d8"       # 分隔线
TEAL = "#14505e"       # 主强调（深青）
TEAL2 = "#3d7f92"      # 中青
TEAL3 = "#8fbecb"      # 浅青
TEAL4 = "#cfe3e9"      # 极浅青
CLAY = "#a4551f"       # 负向语义（暖棕）
CLAY2 = "#c98f62"      # 负向浅
SAND = "#e8dcc8"       # 中性

# ── 方向 9「新闻数据版」调色板（晚点小数据）────────────────────────
# 和上面那一组用法不同：这里**只有一个彩色在说话**，其余全部走灰。
# 色值实测自晚点小数据的卡片，机制见 references/图表模式库.md 第 13 条。
#
#   背景 / 历史数据 → NEWS_GRAY（填充）、NEWS_LINE（线）
#   焦点           → NEWS_FOCUS，覆盖在一条**真实存在的分界线**上
#                    （时间前后 / 归类是否 / 实际与预计），不是「最重要的那条」
#   对照           → NEWS_COUNTER，画变化前的那一侧
#   第三个主体      → NEWS_THIRD，只在多主体对比时用，别和焦点色同图出现
#
# 典型调用（四个函数的接口都不用改，颜色是传进去的）：
#
#   hbar(data, colors=[NEWS_FOCUS if i == 0 else NEWS_GRAY
#                      for i in range(len(data))])
#   line_chart([("66.2%", vals, NEWS_THIRD)], xlabels)   # 末端标的是 name 位
#   paired_bars(groups, colors=(NEWS_COUNTER, NEWS_FOCUS),
#               series=("发布时价格", "调价后"))
#   stacked_row(rows, seg_colors=[NEWS_FOCUS, NEWS_GRAY],
#               legend=["HBM", "其他 DRAM"])
#
# line_chart 的末端标注本来就着系列色——把**数值**写进 series 的 name 位
# 就是「末端直标数值」，不需要改代码。
#
# ⚠️ 能传进去的只有**数据系列的颜色**。轴标签、刻度、注释行在各函数里
# 写死了 INK / MUTE / RULE（方向 2 那三个），换方向时它们不跟着变。
# 肉眼差别很小（INK #231f20 vs NEWS_INK #3c3c3c），MUTE 略深一点
# （#6b6b6b vs #8e8e8e）。要严格对齐就把上面那三个常量改掉，
# 那是全局改动，会影响方向 2——所以别在同一个项目里混用两套。
NEWS_BG      = "#f4f4f4"   # 纸色。⚠️ 只在整页都是这个底时用，
                           #    报告正文页里的图表不要自己涂底
NEWS_INK     = "#3c3c3c"   # 文字近黑
NEWS_MUTE    = "#8e8e8e"   # 次级文字：轴标签、口径、来源
NEWS_GRAY    = "#d9d9d9"   # 背景数据的填充（柱、堆叠条的其余段）
NEWS_LINE    = "#3c3c3c"   # 背景数据的线。值和 NEWS_INK 相同、角色不同：
                           # 让它退后的是不加粗、不画点，不是变浅
NEWS_FOCUS   = "#d84532"   # 焦点砖红
NEWS_COUNTER = "#21687d"   # 对照深青（变化前）
NEWS_THIRD   = "#61a05b"   # 第三个对比主体

FONT = "'Songti SC','Source Han Serif SC',Georgia,serif"
SANS = "'PingFang SC','Helvetica Neue',Arial,sans-serif"


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text_w(s, size):
    """文字的粗略视觉宽度（SVG 用户单位）：CJK 按 1 em，其余按 0.55 em。

    ⚠️ 这个函数是承重的，别当成小工具。本库里所有「给文字预留一块固定
    空间」的写法都会翻车，而且翻得没有声响——SVG 不会报溢出，机械自检
    只知道那里有字，PDF 上就是标注被版心齐刷刷切掉半截。

    实测案例（370 页书）：横条图把绘图区写死 250 单位，值最大的那一行
    柱子占满 250，它的标注从 364 开始往右写，viewBox 只有 470——
    「626,155磅（成千上万次训练）」印出来是「626,155磅（成千上万次」。

    规矩：任何 pad_r / label_w / 绘图区宽度，都必须由实际标注反算，
    不许写死。宁可多留几个单位，也不能让文字出界。
    """
    return sum(1.0 if ord(c) > 0x2E80 else 0.55 for c in str(s)) * size


def clamp_x(cx, s, size, lo=2, hi=468):
    """居中文字的锚点夹回画布内。

    text-anchor="middle" 的文字在靠近左右边缘时会有一半跑到画布外。
    时间轴、末端标注、大数字都是这个形状。把锚点挪进来，标记点仍画在
    真实位置——读者看到的是「说明偏了两毫米」，而不是「说明少了三个字」。
    """
    half = text_w(s, size) / 2
    return min(max(cx, lo + half), hi - half)


def _txt(x, y, s, size=8, fill=INK, anchor="start", weight="normal", font=SANS, opacity=1):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}" '
            f'opacity="{opacity}">{_esc(s)}</text>')


def wrap(s, n):
    """按字符数粗略折行，中文友好。"""
    out, cur = [], ""
    for ch in s:
        cur += ch
        if len(cur) >= n:
            out.append(cur); cur = ""
    if cur:
        out.append(cur)
    return out


def hbar(data, w=470, rowh=22, maxv=None, fmt="{}%", label_w=None,
         colors=None, note=None, highlight=None):
    """横条图。data=[(label, value), ...]。用于类别名较长的比较。

    label_w 和右侧数值区都由实际文字宽度反算（见 text_w 的说明），
    传 label_w 只在你要跨多张图对齐左栏时才用。
    """
    maxv = maxv if maxv is not None else max(v for _, v in data) * 1.16
    h = rowh * len(data) + 22
    # 左栏按最长类别名算，右侧按最长数值标注算。两边都写死过，两边都出过界。
    if label_w is None:
        label_w = min(190, max(60, max(text_w(lab, 8.4) for lab, _ in data) + 10))
    val_w = max(text_w(fmt.format(v), 8.4) for _, v in data) + 10
    bw = max(60, w - label_w - val_w)
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for i, (lab, v) in enumerate(data):
        y = i * rowh + 8
        c = (colors[i] if colors else (TEAL if (highlight is None or i in highlight) else TEAL3))
        s.append(_txt(label_w - 8, y + 11, lab, 8.4, INK, "end"))
        bl = bw * v / maxv
        s.append(f'<rect x="{label_w}" y="{y+2}" width="{bl:.1f}" height="{rowh-8}" fill="{c}"/>')
        s.append(_txt(label_w + bl + 5, y + 11, fmt.format(v), 8.4,
                      INK, "start", "bold"))
    s.append(f'<line x1="{label_w}" y1="6" x2="{label_w}" y2="{h-14}" stroke="{RULE}" stroke-width="0.6"/>')
    if note:
        s.append(_txt(label_w, h - 3, note, 6.6, MUTE))
    s.append("</svg>")
    return "\n".join(s)


def stacked_row(rows, w=470, rowh=26, seg_colors=None, legend=None, note=None):
    """100% 堆叠条。rows=[(label,[v1,v2,...]),...]，各行和为 100。"""
    label_w = 104
    h = rowh * len(rows) + (30 if legend else 12)
    bw = w - label_w - 12
    cols = seg_colors or [TEAL, TEAL2, TEAL3, SAND, CLAY2]
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for i, (lab, vals) in enumerate(rows):
        y = i * rowh + 6
        s.append(_txt(label_w - 8, y + 13, lab, 8.4, INK, "end"))
        x = label_w
        for j, v in enumerate(vals):
            seg = bw * v / 100
            s.append(f'<rect x="{x:.1f}" y="{y+2}" width="{seg:.1f}" height="{rowh-10}" fill="{cols[j%len(cols)]}"/>')
            if seg > 26:
                lum = j < 2
                s.append(_txt(x + seg / 2, y + 13.5, f"{v:g}%", 7.6,
                              "#ffffff" if lum else INK, "middle", "bold"))
            x += seg
    if legend:
        ly = h - 12
        lx = label_w
        for j, name in enumerate(legend):
            s.append(f'<rect x="{lx}" y="{ly-6}" width="8" height="8" fill="{cols[j%len(cols)]}"/>')
            s.append(_txt(lx + 11, ly + 1, name, 7.2, MUTE))
            lx += 11 + len(name) * 7.4 + 14
    if note:
        s.append(_txt(label_w, h - 1, note, 6.6, MUTE))
    s.append("</svg>")
    return "\n".join(s)


def paired_bars(groups, w=470, h=182, ymax=None, ymin=None, unit="%", note=None,
                colors=(TEAL, CLAY), series=("", "")):
    """成对柱。groups=[(label, a, b), ...]。支持负值——负柱从零线向下画。

    负值必须画在零线下方而不是被当成 0：把 -11% 画成空白，
    会让「下降 11%」和「没有变化」在视觉上完全一样。"""
    pad_l, pad_b, pad_t = 34, 34, 16
    vals = [v for _, a, b in groups for v in (a, b)]
    ymax = ymax if ymax is not None else max(vals) * 1.22
    ymin = ymin if ymin is not None else min(0, min(vals) * 1.25)
    pw = w - pad_l - 12
    ph = h - pad_b - pad_t
    gw = pw / len(groups)
    def Y(v): return pad_t + ph - ph * (v - ymin) / (ymax - ymin)
    zero = Y(0)
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for t in range(5):
        v = ymin + (ymax - ymin) * t / 4
        y = Y(v)
        s.append(f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w-12}" y2="{y:.1f}" stroke="{RULE}" stroke-width="0.5"/>')
        s.append(_txt(pad_l - 5, y + 2.6, f"{v:.0f}", 7, MUTE, "end"))
    if ymin < 0:
        s.append(f'<line x1="{pad_l}" y1="{zero:.1f}" x2="{w-12}" y2="{zero:.1f}" stroke="{INK}" stroke-width="0.9"/>')
    for i, (lab, a, b) in enumerate(groups):
        cx = pad_l + gw * i + gw / 2
        bw = min(20, gw * 0.3)
        for k, (val, col) in enumerate(((a, colors[0]), (b, colors[1]))):
            y0, y1 = (Y(val), zero) if val >= 0 else (zero, Y(val))
            bh = abs(y1 - y0)
            x = cx - bw - 2 + k * (bw + 4)
            s.append(f'<rect x="{x:.1f}" y="{min(y0,y1):.1f}" width="{bw:.1f}" height="{bh:.1f}" fill="{col}"/>')
            ly = (min(y0, y1) - 3.5) if val >= 0 else (max(y0, y1) + 8)
            s.append(_txt(x + bw / 2, ly, f"{val:+g}{unit}" if ymin < 0 else f"{val:g}{unit}",
                          7.4, INK, "middle", "bold"))
        for j, ln in enumerate(wrap(lab, 7)):
            s.append(_txt(cx, pad_t + ph + 11 + j * 8.6, ln, 7.2, INK, "middle"))
    if series[0]:
        lx = pad_l
        for k, name in enumerate(series):
            s.append(f'<rect x="{lx}" y="{2}" width="8" height="8" fill="{colors[k]}"/>')
            s.append(_txt(lx + 11, 9, name, 7.2, MUTE))
            lx += 11 + len(name) * 7.6 + 16
    if note:
        s.append(_txt(pad_l, h - 1, note, 6.6, MUTE))
    s.append("</svg>")
    return "\n".join(s)


def line_chart(series, xlabels, w=470, h=190, ymin=None, ymax=None, unit="%",
               note=None, annotate=None, yfmt="{:.0f}"):
    """折线。series=[(name, [v...], color), ...]，末端直接标注名字，不用图例。"""
    # pad_r 曾经写死 78。系列名一长（「星际争霸职业选手」= 8 个汉字 ≈ 61 单位，
    # 再长一点就出界），末端标注被切掉尾巴。按最长系列名反算。
    pad_l, pad_b, pad_t = 32, 30, 14
    pad_r = max(40, max(text_w(name, 7.6) for name, _, _ in series) + 12)
    vals = [v for _, ys, _ in series for v in ys]
    ymin = 0 if ymin is None else ymin
    ymax = ymax if ymax is not None else max(vals) * 1.15
    pw, ph = w - pad_l - pad_r, h - pad_b - pad_t
    n = len(xlabels)
    def X(i): return pad_l + pw * i / max(1, n - 1)
    def Y(v): return pad_t + ph - ph * (v - ymin) / (ymax - ymin)
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for t in range(5):
        v = ymin + (ymax - ymin) * t / 4
        s.append(f'<line x1="{pad_l}" y1="{Y(v):.1f}" x2="{pad_l+pw}" y2="{Y(v):.1f}" stroke="{RULE}" stroke-width="0.5"/>')
        s.append(_txt(pad_l - 5, Y(v) + 2.6, yfmt.format(v), 7, MUTE, "end"))
    for i, xl in enumerate(xlabels):
        s.append(_txt(X(i), pad_t + ph + 12, xl, 7, MUTE, "middle"))
    for name, ys, col in series:
        pts = " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(ys))
        s.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.9"/>')
        for i, v in enumerate(ys):
            s.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="2.2" fill="{col}"/>')
        s.append(_txt(X(n - 1) + 6, Y(ys[-1]) + 3, name, 7.6, col, "start", "bold"))
    if annotate:
        for i, v, label in annotate:
            s.append(_txt(X(i), Y(v) - 7, label, 7.2, INK, "middle", "bold"))
    if note:
        s.append(_txt(pad_l, h - 1, note, 6.6, MUTE))
    s.append("</svg>")
    return "\n".join(s)


def big_stat(value, caption, sub=None, w=150, color=TEAL):
    """大数字视觉锚。一页最多一个。

    ⚠️ 38pt 下 4 个汉字就是 152 单位，已经超过默认的 w=150。数字长到
    「626,155磅」「9,000,000–110,000,000」这一档时，画布必须跟着长，
    否则要么被切、要么（在 HTML 版里）被拦腰折成「626,15 / 5磅」。
    宁可这一块变宽，也不要让一个视觉锚缺半截。
    """
    lines = wrap(caption, 11)
    vw = text_w(value, 38)
    w = max(w, vw + 16)
    h = 66 + len(lines) * 11 + (11 if sub else 0)
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    s.append(_txt(w / 2, 40, value, 38, color, "middle", "bold", SANS))
    for i, ln in enumerate(lines):
        s.append(_txt(w / 2, 56 + i * 11, ln, 8, INK, "middle"))
    if sub:
        s.append(_txt(w / 2, 58 + len(lines) * 11 + 6, sub, 7, MUTE, "middle"))
    s.append("</svg>")
    return "\n".join(s)


def diverging(rows, w=470, rowh=24, note=None, legend=None):
    """发散堆叠条。rows=[(label,[neg...],[pos...])]，负向左、正向右。"""
    label_w = 104
    h = rowh * len(rows) + (30 if legend else 14)
    bw = (w - label_w - 14) / 2
    negc = [CLAY, CLAY2]
    posc = [TEAL, TEAL2]
    mid = label_w + bw
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    s.append(f'<line x1="{mid}" y1="4" x2="{mid}" y2="{h-16}" stroke="{INK}" stroke-width="0.8"/>')
    for i, (lab, neg, pos) in enumerate(rows):
        y = i * rowh + 8
        s.append(_txt(label_w - 8, y + 12, lab, 8.4, INK, "end"))
        x = mid
        for j, v in enumerate(neg):
            seg = bw * v / 100
            x -= seg
            s.append(f'<rect x="{x:.1f}" y="{y+2}" width="{seg:.1f}" height="{rowh-9}" fill="{negc[j%2]}"/>')
            if seg > 22:
                s.append(_txt(x + seg / 2, y + 13, f"{v:g}%", 7.4, "#fff", "middle", "bold"))
        x = mid
        for j, v in enumerate(pos):
            seg = bw * v / 100
            s.append(f'<rect x="{x:.1f}" y="{y+2}" width="{seg:.1f}" height="{rowh-9}" fill="{posc[j%2]}"/>')
            if seg > 22:
                s.append(_txt(x + seg / 2, y + 13, f"{v:g}%", 7.4, "#fff", "middle", "bold"))
            x += seg
    if legend:
        ly = h - 12; lx = label_w
        allc = negc + posc
        for j, name in enumerate(legend):
            s.append(f'<rect x="{lx}" y="{ly-6}" width="8" height="8" fill="{allc[j%len(allc)]}"/>')
            s.append(_txt(lx + 11, ly + 1, name, 7.2, MUTE))
            lx += 11 + len(name) * 7.4 + 12
    if note:
        s.append(_txt(label_w, h - 1, note, 6.6, MUTE))
    s.append("</svg>")
    return "\n".join(s)


def slope(pairs, w=470, h=180, unit="%", left_label="", right_label="", note=None):
    """斜率图。pairs=[(name, v_left, v_right, color)]。用于「从A到B」的排名/水平变化。"""
    pad_t, pad_b = 22, 20
    ph = h - pad_t - pad_b
    xl, xr = 108, w - 118
    vals = [v for _, a, b, _ in pairs for v in (a, b)]
    lo, hi = min(vals) * 0.86, max(vals) * 1.08
    def Y(v): return pad_t + ph - ph * (v - lo) / (hi - lo)
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    s.append(f'<line x1="{xl}" y1="{pad_t-6}" x2="{xl}" y2="{pad_t+ph+6}" stroke="{RULE}" stroke-width="0.6"/>')
    s.append(f'<line x1="{xr}" y1="{pad_t-6}" x2="{xr}" y2="{pad_t+ph+6}" stroke="{RULE}" stroke-width="0.6"/>')
    s.append(_txt(xl, pad_t - 11, left_label, 7.4, MUTE, "middle"))
    s.append(_txt(xr, pad_t - 11, right_label, 7.4, MUTE, "middle"))
    for name, a, b, col in pairs:
        s.append(f'<line x1="{xl}" y1="{Y(a):.1f}" x2="{xr}" y2="{Y(b):.1f}" stroke="{col}" stroke-width="1.7"/>')
        s.append(f'<circle cx="{xl}" cy="{Y(a):.1f}" r="2.6" fill="{col}"/>')
        s.append(f'<circle cx="{xr}" cy="{Y(b):.1f}" r="2.6" fill="{col}"/>')
        s.append(_txt(xl - 7, Y(a) + 3, f"{name} {a:g}{unit}", 7.6, col, "end", "bold"))
        s.append(_txt(xr + 7, Y(b) + 3, f"{b:g}{unit}", 7.6, col, "start", "bold"))
    if note:
        s.append(_txt(xl - 60, h - 1, note, 6.6, MUTE))
    s.append("</svg>")
    return "\n".join(s)


def quadrant(points, w=470, h=270, xlab="", ylab="", qlabels=None, note=None):
    """象限散点 + 直接标注。points=[(name,x,y,color)]，x/y 为 0-100。"""
    pad = 40
    pw, ph = w - pad - 76, h - pad - 26
    def X(v): return pad + pw * v / 100
    def Y(v): return 14 + ph - ph * v / 100
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    s.append(f'<rect x="{pad}" y="14" width="{pw}" height="{ph}" fill="none" stroke="{RULE}" stroke-width="0.6"/>')
    s.append(f'<line x1="{X(50)}" y1="14" x2="{X(50)}" y2="{14+ph}" stroke="{RULE}" stroke-width="0.6" stroke-dasharray="3,2"/>')
    s.append(f'<line x1="{pad}" y1="{Y(50)}" x2="{pad+pw}" y2="{Y(50)}" stroke="{RULE}" stroke-width="0.6" stroke-dasharray="3,2"/>')
    if qlabels:
        for (qx, qy, t) in qlabels:
            s.append(_txt(X(qx), Y(qy), t, 7, MUTE, "middle", "bold"))
    for name, x, y, col in points:
        s.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="3.4" fill="{col}" opacity="0.9"/>')
        s.append(_txt(X(x) + 5.5, Y(y) + 2.6, name, 7.2, INK))
    s.append(_txt(pad + pw / 2, h - 10, xlab, 7.6, INK, "middle", "bold"))
    s.append(f'<text x="12" y="{14+ph/2}" font-family="{SANS}" font-size="7.6" fill="{INK}" '
             f'font-weight="bold" text-anchor="middle" transform="rotate(-90 12 {14+ph/2})">{_esc(ylab)}</text>')
    if note:
        s.append(_txt(pad, h - 1, note, 6.6, MUTE))
    s.append("</svg>")
    return "\n".join(s)
