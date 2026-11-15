#!/usr/bin/env python3
"""报告渲染器：HTML → PDF，自动回填目录页码，并做机械化排版自检。

用法：
    python3 render.py build.py 报告.html 报告.pdf
    python3 render.py build.py 报告.html 报告.pdf --check-only   # 只跑自检

三件事，每一件都对应一个踩过的坑：

1. **无条件先重建 HTML**。早期版本只在「目录页码需要改」时才重跑生成器，
   结果改了正文却一直在看上一版的 PDF，白排查两轮。渲染前必须先 build。

2. **目录页码自动回填**。手写的页码内容一改就错，而这是读者最先发现的错误。
   做法是渲染一次 → 从 PDF 文本定位每章起始页 → 回填生成器 → 再渲染。
   定位时必须跳过目录页本身——目录里也印着所有章节名，从第 1 页开始搜
   会把每一章都定位到目录那一页。

3. **页数会抖动**。目录页码从 1 位变 2 位可能让目录多占一行，进而整体页数变化。
   所以要循环到收敛，不能只跑一遍。

4. **几何自检**。把每页渲成灰度图，实测内容离纸边的四边留白（mm），
   低于阈值直接报页码。呼吸空间不再依赖「肉眼觉得还行」——
   margin=0 全出血模式下 CSS padding 是唯一防线，这层检查就是它的验收。
"""
import asyncio, os, re, subprocess, sys, tempfile

def _tool(name):
    """Resolve an external tool, with optional HUASHU_<NAME> override on Windows."""
    override = os.environ.get("HUASHU_" + name.upper().replace("-", "_"))
    return override or name

# ── 配置：改成你的报告标题 ─────────────────────────────────
REPORT_TITLE = "报告标题"

# 几何自检的留白下限（mm）。A4 竖版用默认；deck/全出血项目换成 MIN_MM_DECK。
MIN_MM_A4   = {"left": 12, "right": 12, "top": 10, "bottom": 13}
MIN_MM_DECK = {"left": 12, "right": 12, "top": 8,  "bottom": 8}
MIN_MM = MIN_MM_A4

# 目录条目 key -> 在 PDF 文本中定位该章起始页的正则
# key 必须与生成器里 toc_row("<key>", ...) 的第一个参数完全一致
ANCHORS = [
    ("摘要", r"^\s*摘要\s*$"),
    ("1", r"^\s*1\s*第一章标题"),
    # ("附录 A", r"附录 A\s*附录标题"),
]

FOOTER_TPL = """
<div style="width:100%;font-size:7pt;color:#8a8a8a;
     font-family:'PingFang SC',-apple-system,sans-serif;padding:0 19mm;">
  <div style="float:left">{title}</div>
  <div style="float:right"><span class="pageNumber"></span></div>
</div>"""
BLANK = '<div style="height:0"></div>'


async def _render(html, pdf, title):
    from playwright.async_api import async_playwright
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        pg = await b.new_page()
        await pg.goto("file://" + os.path.abspath(html), wait_until="networkidle")
        await pg.pdf(path=pdf, format="A4", print_background=True,
                     display_header_footer=True,
                     header_template=BLANK,
                     footer_template=FOOTER_TPL.format(title=title),
                     margin={"top": "17mm", "bottom": "15mm",
                             "left": "19mm", "right": "19mm"})
        await b.close()


def page_count(pdf):
    out = subprocess.run([_tool("pdfinfo"), pdf], capture_output=True, text=True).stdout
    return int(out.split("Pages:")[1].split()[0])


def page_texts(pdf, n):
    return {p: subprocess.run([_tool("pdftotext"), "-f", str(p), "-l", str(p), pdf, "-"],
                              capture_output=True, text=True).stdout
            for p in range(1, n + 1)}


def locate(pdf, anchors):
    """定位每章起始页。跳过目录页本身，否则每章都会被定位到目录那一页。

    ⚠️ 目录一旦跨页，只跳过第一页是不够的。40 页的报告目录占一页，
    100 页以上就是两三页——而目录第二页仍然印着章节名，于是排在后半段的
    条目（尤其是「附录」这种独占一行的）会被定位到目录第二页上。
    实测症状：370 页的书里「附录一」页码回填成 **3**，而且不报错。
    判据用页眉那条 crumb（目录页的 crumb 里带「目录」），不是「目录」二字
    单独成行——后者只在目录首页的大标题上成立。
    """
    n = page_count(pdf)
    pages = page_texts(pdf, n)
    toc_pages = [p for p in pages
                 if re.match(r"\s*目录\s*[|｜]", pages[p])          # 页眉 crumb
                 or re.search(r"^\s*目录\s*$", pages[p], re.M)]      # 目录首页大标题
    toc_page = max(toc_pages) if toc_pages else 0
    found = {}
    for p in sorted(pages):
        for key, pat in anchors:
            if key in found:
                continue
            # 目录之前只允许匹配排在目录前面的条目（通常只有摘要）
            if p <= toc_page and key != "摘要":
                continue
            if re.search(pat, pages[p], re.M):
                found[key] = p
    return found, n


def patch_toc(builder, found):
    """把实际页码写回生成器的 toc_row 调用。

    注意：toc_row(...) 必须写在一行内。跨行写法会让正则匹配不到，
    页码就永远停在初始的占位值上，而且不会有任何报错。
    """
    t = open(builder).read()
    orig = t
    for key, no in found.items():
        t = re.sub(rf'(toc_row\(\s*"{re.escape(key)}"\s*,\s*"[^"]*"\s*,\s*)\d+',
                   rf'\g<1>{no}', t)
    if t != orig:
        open(builder, "w").write(t)
    return t != orig


# ── 几何自检：逐页实测四边留白 ────────────────────────────
GEO_DPI = 40                  # 40dpi 足够测留白，A4 一页约 331×468 px
_MM = 25.4 / GEO_DPI          # 每像素毫米数
INK = 200                     # 灰度低于此算「有墨」
FULLBLEED = 0.35              # 非白像素占比超过此视为设计性全出血页（封面/章首页），跳过边距检查
FOOTER_BAND_MM = 12           # 页脚带高度：页码本来就印在下边距里，测内容下边距时排除


def _read_pgm(path):
    """解析 pdftoppm -gray 输出的二进制 PGM（P5），零依赖。"""
    raw = open(path, "rb").read()
    parts, i = [], 0
    while len(parts) < 4:
        while raw[i:i + 1].isspace():
            i += 1
        if raw[i:i + 1] == b"#":
            while raw[i:i + 1] not in (b"\n", b"\r"):
                i += 1
            continue
        j = i
        while not raw[j:j + 1].isspace():
            j += 1
        parts.append(raw[i:j]); i = j
    return int(parts[1]), int(parts[2]), raw[i + 1:]


def geometry_check(pdf):
    """每页实测内容离纸边的四边留白。返回 issue 列表。

    查得出来的：内容侵入页边距 / 顶格贴边（疑似被裁）/ 下半页大面积留白候选。
    查不出来的：全出血页的内部留白是否舒服——那些页会列出来提示肉眼看。
    """
    issues, fullbleed, blank_bottom = [], [], []
    band = int(FOOTER_BAND_MM / _MM)
    with tempfile.TemporaryDirectory() as td:
        subprocess.run([_tool("pdftoppm"), "-gray", "-r", str(GEO_DPI), pdf,
                        os.path.join(td, "g")], check=True)
        for f in sorted(os.listdir(td)):
            pno = int(f.rsplit("-", 1)[-1].split(".")[0])
            w, h, px = _read_pgm(os.path.join(td, f))
            px = px[:w * h]
            if sum(1 for b in px if b < 245) / (w * h) > FULLBLEED:
                fullbleed.append(pno)
                continue
            xmin, xmax, ymin, ymax = w, -1, h, -1
            for y in range(h - band):          # 页脚带不算内容
                row = px[y * w:(y + 1) * w]
                if min(row) >= INK:
                    continue
                lo = next(x for x, b in enumerate(row) if b < INK)
                hi = w - 1 - next(x for x, b in enumerate(reversed(row)) if b < INK)
                xmin, xmax = min(xmin, lo), max(xmax, hi)
                ymin, ymax = min(ymin, y), max(ymax, y)
            if xmax < 0:
                issues.append(f"第 {pno} 页整页空白")
                continue
            m = {"left": xmin * _MM, "right": (w - 1 - xmax) * _MM,
                 "top": ymin * _MM, "bottom": (h - 1 - ymax) * _MM}
            bad = {k: v for k, v in m.items() if v < MIN_MM[k]}
            if bad:
                s = "、".join(f"{k} {v:.1f}mm(下限{MIN_MM[k]})" for k, v in bad.items())
                issues.append(f"第 {pno} 页留白不足：{s}")
            # 下半页留白候选（章末正常，章内是 bug——列出来给眼睛判断）
            y0 = int((h - band) * 0.65)
            zone = [px[y * w + x] for y in range(y0, h - band) for x in range(xmin, xmax + 1)]
            if zone and sum(1 for b in zone if b < INK) / len(zone) < 0.012:
                blank_bottom.append(pno)
    if fullbleed:
        print(f"  全出血页 {fullbleed} 跳过边距检查——这些页的内部留白肉眼确认")
    if blank_bottom:
        print(f"  下半页大面积留白候选：{blank_bottom}（章末正常，章内是分页容器切碎了）")
    return issues


# ── 长文档自检：100 页以上、分章外包时才需要的三项 ────────
EM_BUDGET = 6          # 一章加粗上限。规范是 3–4，留两处余量再报警
LEN_SPREAD = 2.0       # 最长章 / 最短章 的容忍倍数


def longdoc_check(html):
    """只在「章数够多」时才跑。这三项在单人写的 40 页报告里不会出问题，
    一旦把章节分给多个 agent 写就必翻车——因为它们都是「每个写作者各自
    记住一条规则」型的约束，而记忆是不会跨 agent 共享的。

    处理原则和 pangu_strip 一样：**能搬进编译器的规则不要留给写作端。**
    搬不进去的（比如加粗该加在哪句上，机器判断不了），至少要有人报数。
    """
    issues = []
    if not html or not os.path.exists(html):
        return issues
    doc = open(html, encoding="utf-8").read()
    chunks = re.split(r'<table class="pagewrap"', doc)[1:]
    bodies = [(i, re.sub(r"<[^>]+>", "", c), c) for i, c in enumerate(chunks, 1)]

    # ⚠️ 挑出「真正的章」，否则这两项全是假警报。第一次跑真书时报的是
    # 「章长差 346.6 倍」——因为它把封面、目录、幕间页（几百字符）和
    # 附录（17.8 万字符）都当成了章。假警报比漏报贵：它训练人忽略整份自检。
    # 判据：正文长度落在中位数的 1/5 到 5 倍之间。附录和扉页都会被这一刀切掉。
    cand = [(i, b, c) for i, b, c in bodies if len(b) > 1200]
    if len(cand) < 6:
        return issues                      # 章太少，方差没有意义
    med = sorted(len(b) for _, b, _ in cand)[len(cand) // 2]
    chaps = [(i, b, c) for i, b, c in cand if med / 5 <= len(b) <= med * 5]
    if len(chaps) < 6:
        return issues

    # ① 强调密度。实测：同一本书、同一份写作手册，早期批次写的 12 章是每章
    #    3–4 处，后补的 17 章是 6–36 处——差一个数量级。规则记在手册里，
    #    而手册不会跨 agent 强制执行。
    over = [(i, len(re.findall(r"<em[ >]", c))) for i, _, c in chaps
            if len(re.findall(r"<em[ >]", c)) > EM_BUDGET]
    if over:
        issues.append(f"加粗超预算的章（>{EM_BUDGET} 处）：{over}"
                      f"——规范是一章 3–4 处；分章外包时这条一定会漂")

    # ② 章长方差。一本书越往后越薄，读者读得出来，而没有任何单章是「错」的，
    #    所以只能靠报数发现。
    lens = [(i, len(b)) for i, b, _ in chaps]
    lo = min(L for _, L in lens); hi = max(L for _, L in lens)
    if hi > lo * LEN_SPREAD:
        thin = [i for i, L in lens if L < (lo + hi) / 3]
        issues.append(f"章长差 {hi/lo:.1f} 倍（最短 {lo}、最长 {hi} 字符），"
                      f"明显偏薄的章：{thin[:10]}")

    # ③ 中文标点后的残留空格。多半是「**强调。** 下一句」去掉星号后的残渣，
    #    在纸上是句号后面一个空洞。
    #    ⚠️ 这里只匹配真空格和制表符，不匹配 \s——\s 会把块元素之间的换行
    #    也算进来，那些在渲染后根本不存在，报出来全是噪声。
    #    根治在生成器：pangu 处理要跑在**最终行内 HTML** 上，不能只跑在原始
    #    markdown 上——「**平反。** 卡哈尔」里两个汉字中间隔的是星号不是空格，
    #    在 markdown 阶段规则看不见它，星号一去掉空格就露出来了。
    txt = re.sub(r"<[^>]+>", "", doc)
    gaps = re.findall(r"[。，：；？！」』）][ \t](?=[一-鿿「（])", txt)
    if gaps:
        issues.append(f"中文标点后残留空格 {len(gaps)} 处"
                      f"——pangu 处理要跑在最终行内 HTML 上，不能只跑原始 markdown")
    return issues


# ── 机械化排版自检 ────────────────────────────────────────
def selfcheck(pdf, html=None):
    """能用文本层查出来的排版缺陷。查不出来的那几类见下面的 EYE_ONLY。"""
    n = page_count(pdf)
    pages = page_texts(pdf, n)
    full = "\n".join(pages.values())
    issues = []

    # 图表编号连续性与格式统一
    figs = re.findall(r"Figure\s+([\d.]+)", full)
    if figs and "Exhibit" in full:
        issues.append("图表编号混用了 Figure 和 Exhibit，一份报告只能用一种")
    if len(set(figs)) != len(figs):
        dup = [f for f in set(figs) if figs.count(f) > 1]
        issues.append(f"图表编号重复：{dup}")

    # 目录页码 vs 实际页码
    toc_p = next((p for p in sorted(pages)
                  if re.search(r"^\s*目录\s*$", pages[p], re.M)), None)
    if toc_p:
        printed = re.findall(r"(\S[^\n]*?)\s+(\d{1,3})\s*$", pages[toc_p], re.M)
        if not printed:
            issues.append("目录页里没找到任何页码——检查 toc_row 是否渲染出来了")

    # 空白页 / 内容极少的页
    thin = [p for p, t in pages.items()
            if p > 1 and len(t.strip()) < 120]
    if thin:
        issues.append(f"内容极少的页：{thin}（可能是分节容器留白过多）")

    # tuple 陷阱的痕迹：f-string 里 {expr,} 会渲染成 ('...',)
    if re.search(r"\('<(figure|div|table)", full):
        issues.append("检测到 tuple 渲染痕迹 ('<figure…——f-string 里多写了逗号")

    # 疑似占位符残留
    # ⚠️ 早期版本直接搜「待补」，结果把正文里一句诚实的交代
    #（「这一条的完整文献信息待补，我引的是二手转述」）报成占位符，
    # 每次渲染都亮一条假警报，久了就没人看这份自检了。
    # 假警报比漏报更贵——它训练人忽略整份报告。所以只认占位符**形状**：
    # 方括号/圆括号包着的，或者独占行尾的。
    for pat in (r"placeholder", r"\bTODO\b", r"\bXXX\b", r"\bTBD\b",
                r"[\[【（(]\s*待[补補定]", r"待[补補定]\s*[\]】）)]",
                r"^\s*待[补補定]\s*$", r"\{\{[^}]*\}\}"):
        if re.search(pat, full, re.I | re.M):
            issues.append(f"正文里残留占位符：{pat}")

    # 几何自检：逐页实测四边留白
    issues += geometry_check(pdf)

    # 长文档自检（章数够多时才跑）
    issues += longdoc_check(html)

    print(f"共 {n} 页，{len(set(figs))} 张图")
    if issues:
        print("⚠ 机械自检发现：")
        for i in issues:
            print("  -", i)
    else:
        print("✓ 机械自检通过")
    print(EYE_ONLY)
    return issues


EYE_ONLY = """
机械+几何检查查不出下面这些——必须把每页渲染成 PNG 用眼睛看：
  1. 相邻列内容在列缝处粘连（读起来像「84%尚未围绕…」这种连成一句的假句子）
  2. 负值被画成零高度（「下降 11%」和「没有变化」长得一样）
  3. 图表标注被版心切掉（「626,155磅（成千上万次训练）」印成「…成千上万次」）
  4. 居中标注在最边上那个点被切（时间轴、末端标注最容易）
  5. 视觉锚数字被拦腰折断（「626,15 / 5磅」）
  6. Y 轴不从零开始，把小差异画成大差异
  7. 内容跨页时页眉丢失；长表跨页时表头没重复
  8. 双列组件里某一列塌成一个字宽、整段竖排
  9. 全出血页（封面/章首页）的内部留白与字号层级
渲染命令：pdftoppm -png -r 70 报告.pdf 自检/p

⚠️ 300 页以上不要指望一页一张地看完。做法是把 12 页拼成一张检查表
（PIL 缩到每页 430px 宽、四列三行、给每格标页码），30 张图扫一遍——
版式缺陷（切掉、塌陷、整页空白、孤儿段）在这个尺度上全都看得见，
文字细节看不见但那不是这一关要查的。扫到可疑的再单独开全尺寸那一页。
「渲成 PDF 翻了一遍」不等于逐页看过；抽检对排版缺陷无效，
因为缺陷集中在最复杂的那几页（长表、宽图、附录），不是均匀分布的。
"""


def main():
    if len(sys.argv) < 4:
        print(__doc__); sys.exit(1)
    builder, html, pdf = sys.argv[1:4]
    if "--check-only" in sys.argv:
        selfcheck(pdf, html); return

    for round_no in range(1, 5):
        # 坑 1：无条件先重建，否则改了正文也看不到
        subprocess.run([sys.executable, builder], check=True)
        asyncio.run(_render(html, pdf, REPORT_TITLE))
        found, n = locate(pdf, ANCHORS)
        missing = [k for k, _ in ANCHORS if k not in found]
        if missing:
            print(f"⚠ 第 {round_no} 轮未定位到：{missing}（检查 ANCHORS 正则）")
        if not patch_toc(builder, found):
            print(f"第 {round_no} 轮：目录页码已收敛（{n} 页）")
            break
        print(f"第 {round_no} 轮：回填页码 {found}")
    else:
        print("⚠ 4 轮仍未收敛——多半是某个 toc_row 跨行写了，正则改不到它")

    selfcheck(pdf, html)


if __name__ == "__main__":
    main()
