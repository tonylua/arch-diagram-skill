#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_layered_svg.py —— 由 JSON 规格生成「层严格等宽」的分层架构 SVG。

Mermaid 的自动布局无法保证层等宽与横向排布（subgraph 内 direction 常被忽略、
跨 subgraph 连线会产生阶梯错乱）。本脚本直接用坐标计算，保证：
  - 所有层色带同宽、同高、等间距；JSON 中 layers 的顺序即自上而下的视觉顺序
  - 每层模块在色带内横向铺开并居中，绝不竖排；字号按实测文本宽度自适应，不溢出
  - 可选右侧「场景栏」：虚线卡片纵向排列、均分填满分层区高度，宽度按内容实测

用法:
    python gen_layered_svg.py spec.json -o out.svg
    python gen_layered_svg.py --example                 # 打印 assets/example-spec.json
    python gen_layered_svg.py spec.json --png out.png   # 可选；需本机已安装 cairosvg

规格 schema:
{
  "title": "架构标题",
  "width": 1200,                 // 分层区宽度（含左右边距，不含场景栏），默认 1200
  "arrows": true,                // 层间箭头；有 scenarios 时默认 false
  "legend": {"label": "黄底 = 兜底措施", "color": "highlight"},  // 单图例或 [...] 数组，标签含"框"时显示边框样式
  "scenarios": [                 // 可选：右侧场景栏，说明各场景如何组合下方模块
    {"title": "场景名", "description": ["A → B → C", "补充说明"]}
  ],
  "layers": [                    // 第一项画在最上方（如应用层），最后一项在最下方（如数据源层）
    {
      "name": "接入层",
      "subtitle": "Presentation",      // 可选，层名下小字
      "color": "blue",                 // 或 [fill, stroke, sep] 自定义
      "modules": [
        {"text": ["创建订单", "简要说明"]},
        {"text": ["幂等校验"], "highlight": true}
      ]
    }
  ]
}

文本宽度：优先用 Pillow + 系统 CJK 字体实测（与浏览器渲染一致），
无 Pillow 时退回按 Unicode 东亚宽度估算，脚本本身仍只依赖标准库。
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import unicodedata
from xml.sax.saxutils import escape

PAD = 40          # 画布外边距
BAND_H = 100      # 层色带高
BAND_GAP = 36     # 层间距
LABEL_W = 200     # 左侧层名栏宽
SEP_PAD = 20      # 层名栏与模块区之间的留白
MOD_GAP = 20      # 模块间距
BOX_H = 56        # 模块盒高
BOX_MAX_W = 220   # 模块盒最大宽（超过后居中，不拉伸）
BOX_MIN_W = 90    # 模块盒最小宽（不足时压缩间距）
BOX_PAD_X = 8     # 模块盒内文字左右留白
TITLE_H = 70      # 标题区高

SCN_GAP = 32         # 场景栏与分层区的间距
SCN_CARD_GAP = 20    # 场景卡片之间的间距
SCN_PAD_X = 16       # 场景卡片内左右留白
SCN_TITLE_FS = 14    # 场景标题字号（粗体）
SCN_DESC_FS = 12     # 场景描述字号
SCN_LINE_H = 20      # 场景描述行高

FONT_FAMILY = "PingFang SC, Microsoft YaHei, sans-serif"
FONT_FILES = {  # 与 FONT_FAMILY 对应的字体文件，用于实测宽度；按顺序取第一个存在的
    False: ["C:/Windows/Fonts/msyh.ttc", "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"],
    True: ["C:/Windows/Fonts/msyhbd.ttc", "/System/Library/Fonts/PingFang.ttc",
           "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"],
}

PALETTE = {
    "blue":      ("#E3F2FD", "#64B5F6", "#90CAF9"),
    "orange":    ("#FFF3E0", "#FFB74D", "#FFCC80"),
    "green":     ("#E8F5E9", "#81C784", "#A5D6A7"),
    "purple":    ("#F3E5F5", "#BA68C8", "#CE93D8"),
    "teal":      ("#E0F2F1", "#4DB6AC", "#80CBC4"),
    "grey":      ("#ECEFF1", "#90A4AE", "#B0BEC5"),
    "highlight": ("#FFF9C4", "#FBC02D", "#FBC02D"),
}
CYCLE = ["blue", "orange", "green", "purple", "teal", "grey"]

_font_cache: dict = {}


def example_spec_path() -> str:
    """示例规格与脚本相对位置固定，不依赖当前工作目录。"""
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "assets", "example-spec.json"))


def warn(msg: str):
    sys.stderr.write("[警告] %s\n" % msg)

def _pil_font(size: int, bold: bool):
    key = (size, bold)
    if key not in _font_cache:
        font = None
        try:
            from PIL import ImageFont  # 可选依赖
            for path in FONT_FILES[bold]:
                if os.path.exists(path):
                    font = ImageFont.truetype(path, size)
                    break
        except Exception:
            font = None
        _font_cache[key] = font
    return _font_cache[key]


def _estimate_width(s: str, size: int) -> float:
    em = 0.0
    for ch in s:
        ea = unicodedata.east_asian_width(ch)
        if ea in ("W", "F", "A"):   # 全角 / CJK 字体中按全角渲染的歧义宽度符号（如 →）
            em += 1.0
        elif ch == " ":
            em += 0.3
        elif ch.isupper() or ch.isdigit():
            em += 0.62
        elif ch.isalpha():
            em += 0.52
        else:
            em += 0.38
    return em * size


def text_width(s, size: int, bold: bool = False) -> float:
    """文本渲染宽度（px）。有 Pillow + 字体时实测，否则估算。"""
    s = str(s)
    font = _pil_font(size, bold)
    if font is not None:
        return float(font.getlength(s))
    return _estimate_width(s, size)


def fit_font_size(lines, max_w: float, bold_first: bool = False, sizes=(13, 12, 11, 10)) -> int:
    """在 max_w 内放得下所有行的最大字号；都放不下时返回最小字号并告警。"""
    for fs in sizes:
        if all(text_width(l, fs, bold_first and k == 0) <= max_w for k, l in enumerate(lines)):
            return fs
    warn("文本在 %dpx 内放不下，请缩短：%s" % (max_w, " / ".join(map(str, lines))))
    return sizes[-1]


def resolve_color(key, index):
    """返回 (fill, stroke, sep)。key 可为调色板名或 [fill, stroke, sep]。"""
    if isinstance(key, (list, tuple)) and len(key) >= 2:
        return key[0], key[1], (key[2] if len(key) > 2 else key[1])
    name = key or CYCLE[index % len(CYCLE)]
    return PALETTE.get(name, PALETTE["grey"])


def text_baselines(center_y, count):
    """按行数返回基线 y 列表（视觉居中）。"""
    if count == 1:
        return [center_y + 4.5]
    if count == 2:
        return [center_y - 6, center_y + 13]
    return [center_y - 14 + i * 15 for i in range(count)]


def scenario_lines(sc) -> list:
    desc = sc.get("description") or []
    return [desc] if isinstance(desc, str) else list(desc)


def scenario_column_width(scenarios) -> int:
    """场景栏宽度 = 所有卡片中最宽一行的实测宽度 + 左右留白（不写死）。"""
    widest = 0.0
    for sc in scenarios:
        widest = max(widest, text_width(sc.get("title", ""), SCN_TITLE_FS, bold=True))
        for line in scenario_lines(sc):
            widest = max(widest, text_width(line, SCN_DESC_FS))
    return int(math.ceil(widest)) + SCN_PAD_X * 2


def check_semantics(spec, layers):
    """内容层面的自检：高亮必须有图例说明含义，图例也必须有对应高亮。"""
    used = any(m.get("highlight") for l in layers for m in (l.get("modules") or []))
    if used and not spec.get("legend"):
        warn("使用了 highlight 但未提供 legend，读者无从知道黄底含义；请补图例或去掉高亮")
    if spec.get("legend") and not used:
        warn("提供了 legend 但没有任何模块 highlight，图例将不显示")
    for l in layers:
        for m in l.get("modules") or []:
            if len(m.get("text") or []) > 2:
                warn("模块超过 2 行（名称 + 简要说明即可）：%s" % " / ".join(m["text"]))
    return used

def render(spec: dict) -> str:
    layers = spec.get("layers") or []   # 按给定顺序自上而下渲染，不做任何翻转
    if not layers:
        raise SystemExit("规格中缺少 layers")

    title = spec.get("title", "")
    scenarios = spec.get("scenarios") or []
    arrows = spec.get("arrows", not scenarios)
    highlight_used = check_semantics(spec, layers)
    legend = spec.get("legend") if highlight_used else None

    band_w = int(spec.get("width", 1200)) - PAD * 2          # 层色带宽（所有层一致）
    region_start = PAD + LABEL_W + SEP_PAD
    region_w = PAD + band_w - SEP_PAD - region_start          # 模块区宽
    if region_w <= 0:
        raise SystemExit("画布宽度过小，请调大 width")
    scn_w = scenario_column_width(scenarios) if scenarios else 0
    canvas_w = PAD + band_w + (SCN_GAP + scn_w if scenarios else 0) + PAD

    top = TITLE_H if title else 34
    n = len(layers)
    layers_h = n * BAND_H + (n - 1) * BAND_GAP
    canvas_h = top + layers_h + PAD
    band_cx = PAD + band_w / 2

    o = []
    a = o.append
    a('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
      'font-family="%s">' % (canvas_w, canvas_h, canvas_w, canvas_h, FONT_FAMILY))
    a('  <defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="6" refY="3" orient="auto">'
      '<path d="M0,0 L6,3 L0,6 Z" fill="#90A4AE"/></marker></defs>')
    a('  <rect x="0" y="0" width="%d" height="%d" fill="#FAFAFA"/>' % (canvas_w, canvas_h))

    if title:
        a('  <text x="%.0f" y="40" text-anchor="middle" font-size="22" font-weight="bold" '
          'fill="#37474F">%s</text>' % (canvas_w / 2, escape(str(title))))

    if legend:
        # 支持单个图例（旧格式）或多个图例数组（新格式）
        legends = legend if isinstance(legend, list) else [legend]
        legend_y = 26
        for leg in legends:
            label = str(leg.get("label", ""))
            # 根据标签类型选择样式：边框样式 vs 填充样式
            color_key = leg.get("color", "highlight")
            is_stroke_style = "框" in label  # 如果标签提到"框"，只显示边框

            if is_stroke_style:
                # 边框样式：白底 + 彩色边框
                lf, ls, _ = resolve_color(color_key, 0)
                a('  <rect x="%d" y="%d" width="16" height="16" rx="3" fill="#FFFFFF" stroke="%s" stroke-width="2"/>'
                  % (PAD, legend_y, ls))
            else:
                # 填充样式：彩底 + 彩边
                lf, ls, _ = resolve_color(color_key, 0)
                a('  <rect x="%d" y="%d" width="16" height="16" rx="3" fill="%s" stroke="%s"/>'
                  % (PAD, legend_y, lf, ls))

            a('  <text x="%d" y="%d" font-size="12" fill="#546E7A">%s</text>'
              % (PAD + 24, legend_y + 13, escape(label)))
            legend_y += 22  # 下一个图例项向下偏移

    for i, layer in enumerate(layers):
        by = top + i * (BAND_H + BAND_GAP)
        fill, stroke, sep = resolve_color(layer.get("color"), i)
        a('  <rect x="%d" y="%d" width="%d" height="%d" rx="10" fill="%s" stroke="%s"/>'
          % (PAD, by, band_w, BAND_H, fill, stroke))
        a('  <text x="%d" y="%d" text-anchor="middle" font-size="18" font-weight="bold" '
          'fill="#455A64">%s</text>' % (PAD + LABEL_W / 2, by + 42, escape(str(layer.get("name", "")))))
        if layer.get("subtitle"):
            a('  <text x="%d" y="%d" text-anchor="middle" font-size="11" fill="#78909C">%s</text>'
              % (PAD + LABEL_W / 2, by + 64, escape(str(layer["subtitle"]))))
        a('  <line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
          % (PAD + LABEL_W, by + 18, PAD + LABEL_W, by + BAND_H - 18, sep))

        mods = layer.get("modules") or []
        cnt = len(mods)
        if cnt:
            box_w = (region_w - MOD_GAP * (cnt - 1)) / cnt
            gap = MOD_GAP
            if box_w > BOX_MAX_W:
                box_w = BOX_MAX_W
            if box_w < BOX_MIN_W:
                box_w = BOX_MIN_W
                gap = max(6.0, (region_w - cnt * box_w) / max(1, cnt - 1))
            total = cnt * box_w + gap * (cnt - 1)
            start_x = region_start + (region_w - total) / 2
            box_y = by + (BAND_H - BOX_H) / 2
            center_y = by + BAND_H / 2

            for j, mod in enumerate(mods):
                lines = (mod.get("text") or mod.get("lines") or [""])[:3]
                hl = bool(mod.get("highlight"))
                m_fill, m_stroke = "#FFFFFF", stroke
                if hl:
                    m_fill, m_stroke, _ = PALETTE["highlight"]
                if mod.get("color"):
                    m_fill, m_stroke, _ = resolve_color(mod["color"], i)
                x = start_x + j * (box_w + gap)
                a('    <rect x="%.1f" y="%.1f" width="%.1f" height="%d" rx="6" fill="%s" '
                  'stroke="%s"/>' % (x, box_y, box_w, BOX_H, m_fill, m_stroke))
                fs = fit_font_size(lines, box_w - BOX_PAD_X * 2, bold_first=hl)
                for k, line in enumerate(lines):
                    y = text_baselines(center_y, len(lines))[k]
                    bold = ' font-weight="bold"' if (k == 0 and hl) else ""
                    a('    <text x="%.1f" y="%.1f" text-anchor="middle" font-size="%d"%s '
                      'fill="#37474F">%s</text>' % (x + box_w / 2, y, fs, bold, escape(str(line))))

        if arrows and i < n - 1:
            y1 = by + BAND_H + 2
            y2 = by + BAND_H + BAND_GAP - 6
            a('  <line x1="%.0f" y1="%d" x2="%.0f" y2="%d" stroke="#90A4AE" stroke-width="2" '
              'marker-end="url(#arrow)"/>' % (band_cx, y1, band_cx, y2))

    if scenarios:
        render_scenarios(a, scenarios, PAD + band_w + SCN_GAP, top, scn_w, layers_h)

    a('</svg>')
    return "\n".join(o)

def render_scenarios(a, scenarios, x, y_start, w, total_h):
    """右侧场景栏：虚线卡片纵向均分高度。"""
    n = len(scenarios)
    card_h = (total_h - SCN_CARD_GAP * (n - 1)) / n
    for i, sc in enumerate(scenarios):
        card_y = y_start + i * (card_h + SCN_CARD_GAP)
        a('  <rect x="%.1f" y="%.1f" width="%d" height="%.1f" rx="8" fill="#FFFFFF" '
          'stroke="#B0BEC5" stroke-width="1.5" stroke-dasharray="4 3"/>' % (x, card_y, w, card_h))

        scenario_title = str(sc.get("title", ""))
        a('  <text x="%.1f" y="%.1f" text-anchor="start" font-size="%d" font-weight="bold" '
          'fill="#37474F">%s</text>' % (x + SCN_PAD_X, card_y + 28, SCN_TITLE_FS, escape(scenario_title)))

        desc_y = card_y + 28 + SCN_LINE_H
        for line in scenario_lines(sc):
            a('  <text x="%.1f" y="%.1f" text-anchor="start" font-size="%d" fill="#546E7A">%s</text>'
              % (x + SCN_PAD_X, desc_y, SCN_DESC_FS, escape(str(line))))
            desc_y += SCN_LINE_H


def main():
    p = argparse.ArgumentParser(description="生成层等宽的分层架构 SVG")
    p.add_argument("spec", nargs="?", help="JSON 规格文件路径")
    p.add_argument("-o", "--out", help="输出 SVG 路径")
    p.add_argument("--example", action="store_true", help="输出示例规格并退出")
    p.add_argument("--png", help="同时导出 PNG（需本机已安装 cairosvg，脚本不代为安装）")
    args = p.parse_args()

    # Windows 控制台默认 GBK：中文输出 / 重定向到文件会乱码
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if args.example:
        path = example_spec_path()
        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                print(f.read().rstrip("\n"))
        except OSError as exc:
            raise SystemExit("读不到示例规格 %s：%s" % (path, exc))
        return

    if args.spec:
        with open(args.spec, "r", encoding="utf-8-sig") as f:
            spec = json.load(f)
    else:
        spec = json.load(sys.stdin)

    svg = render(spec)
    if args.out:
        os_dir = os.path.dirname(os.path.abspath(args.out))
        if os_dir and not os.path.isdir(os_dir):
            os.makedirs(os_dir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(svg)
        print("已生成 %s" % args.out, file=sys.stderr)
    else:
        print(svg)

    if args.png:
        try:
            from cairosvg import svg2png
            svg2png(bytestring=svg.encode("utf-8"), write_to=args.png, scale=2)
            print("已导出 %s" % args.png, file=sys.stderr)
        except ImportError:
            warn("--png 需要 cairosvg: pip install cairosvg")


if __name__ == "__main__":
    main()

