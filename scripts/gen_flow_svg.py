#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_flow_svg.py —— 按 references/flow-style.md 生成流程图 SVG。

与分层架构图不同：白底、结论式标题、颜色表示结果、主链向右、失败可以回头。
节点落在哪一行由 JSON 的 rows 决定，脚本不自动排布。

用法:
    python gen_flow_svg.py spec.json -o out.svg
    python gen_flow_svg.py --example
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_layered_svg import text_width  # noqa: E402

FONT = "PingFang SC, Microsoft YaHei, sans-serif"
PAD = 36
TITLE_FS = 28
SUB_FS = 15
CARD_RX = 14
TITLE_INK = "#1A237E"
SUB_INK = "#3949AB"
BODY = "#455A64"
GAP_LINK = 78
GAP_PLAIN = 28
ROW_GAP = 44
FRAME_PAD = 18
FRAME_TITLE_H = 34
CARD_FS = 16
LINE_FS = 13
LINE_H = 18

TONES = {
    "blue":   {"stroke": "#1E88E5", "soft": "#E3F2FD", "ink": "#1565C0"},
    "green":  {"stroke": "#43A047", "soft": "#E8F5E9", "ink": "#2E7D32"},
    "red":    {"stroke": "#E53935", "soft": "#FFEBEE", "ink": "#C62828"},
    "orange": {"stroke": "#FB8C00", "soft": "#FFF8E1", "ink": "#EF6C00"},
}


def warn(msg: str):
    sys.stderr.write("[警告] %s\n" % msg)


def tone_of(name: str) -> dict:
    return TONES.get(name or "blue", TONES["blue"])


def example_spec_path() -> str:
    return os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "assets", "example-flow-spec.json"))


def lines_of(node: dict) -> list:
    raw = node.get("lines") or []
    if isinstance(raw, str):
        raw = [raw]
    if len(raw) > 3:
        warn("卡片说明超过 3 行，请拆成独立节点：%s" % node.get("title", ""))
    return [str(x) for x in raw[:3]]


def icon_svg(name: str, x: float, y: float) -> str:
    """24px 线框图标。未知名称则不画。"""
    s = 24
    ink = "#37474F"
    sw = 1.6
    a = []
    if name == "doc":
        a.append('<rect x="%.1f" y="%.1f" width="16" height="20" rx="2" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 4, y + 2, ink, sw))
        a.append('<path d="M%.1f %.1f h8 M%.1f %.1f h8 M%.1f %.1f h5" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 7, y + 8, x + 7, y + 12, x + 7, y + 16, ink, sw))
    elif name == "search":
        a.append('<circle cx="%.1f" cy="%.1f" r="6" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 10, y + 10, ink, sw))
        a.append('<path d="M%.1f %.1f l6 6" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 14.5, y + 14.5, ink, sw))
    elif name == "gear":
        a.append('<circle cx="%.1f" cy="%.1f" r="4" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 12, y + 12, ink, sw))
        a.append('<circle cx="%.1f" cy="%.1f" r="8" fill="none" stroke="%s" stroke-width="%s" stroke-dasharray="3 2"/>'
                 % (x + 12, y + 12, ink, sw))
    elif name == "flag":
        a.append('<path d="M%.1f %.1f v16 M%.1f %.1f h10 l-3 4 l3 4 h-10" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 6, y + 3, x + 6, y + 3, ink, sw))
    elif name == "warn":
        a.append('<path d="M%.1f %.1f l10 -16 l10 16 z" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 2, y + 20, ink, sw))
        a.append('<path d="M%.1f %.1f v5 M%.1f %.1f v1" stroke="%s" stroke-width="%s"/>'
                 % (x + 12, y + 8, x + 12, y + 16, ink, sw))
    elif name == "list":
        a.append('<rect x="%.1f" y="%.1f" width="16" height="18" rx="2" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 6, y + 3, ink, sw))
        a.append('<path d="M%.1f %.1f h8 M%.1f %.1f h8 M%.1f %.1f h8" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 9, y + 8, x + 9, y + 12, x + 9, y + 16, ink, sw))
    elif name == "bulb":
        a.append('<circle cx="%.1f" cy="%.1f" r="6" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 12, y + 9, ink, sw))
        a.append('<path d="M%.1f %.1f h6 M%.1f %.1f h4" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 9, y + 18, x + 10, y + 21, ink, sw))
    elif name == "clock":
        a.append('<circle cx="%.1f" cy="%.1f" r="8" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 12, y + 12, ink, sw))
        a.append('<path d="M%.1f %.1f v-5 M%.1f %.1f h4" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x + 12, y + 12, x + 12, y + 12, ink, sw))
    else:
        return ""
    return "".join(a)


def measure_node(node: dict) -> dict:
    kind = node.get("kind") or "card"
    title = str(node.get("title") or "")
    lines = lines_of(node)
    badge = str(node.get("badge") or "")
    icon = node.get("icon") or ""
    tone = node.get("tone") or ("orange" if kind == "diamond" else "blue")
    title_w = text_width(title, CARD_FS, bold=True)
    line_w = max([text_width(line, LINE_FS) for line in lines], default=0)
    if kind == "banner":
        width = max(360.0, title_w + 48)
        height = 52.0
    elif kind == "diamond":
        width = min(240.0, max(150.0, title_w + 56))
        height = 96.0
    else:
        text_w = max(title_w + (30 if badge else 0), line_w)
        width = min(340.0, max(188.0, text_w + 36 + (36 if icon else 0)))
        text_h = 24 + len(lines) * LINE_H
        height = 28 + max(text_h, 32.0 if icon else 0)
    return {
        "id": node.get("id"),
        "kind": kind,
        "title": title,
        "lines": lines,
        "badge": badge,
        "icon": icon if icon_svg(icon, 0, 0) else "",
        "tone": tone,
        "dashed": bool(node.get("dashed")),
        "w": width,
        "h": height,
    }


def node_gap(left: dict, right: dict, linked: set) -> float:
    pair = (left["id"], right["id"])
    if pair in linked:
        return GAP_LINK
    return GAP_PLAIN


def render(spec: dict) -> str:
    if "rows" not in spec:
        raise SystemExit("流程图规格需要 rows。分层图请改用 gen_layered_svg.py")
    rows_in = spec.get("rows") or []
    if not rows_in:
        raise SystemExit("规格中缺少 rows")

    edges = spec.get("edges") or []
    forward = set()
    for edge in edges:
        if edge.get("route") == "under":
            continue
        forward.add((edge.get("from"), edge.get("to")))

    rows = []
    by_id = {}
    for raw_row in rows_in:
        nodes = [measure_node(n) for n in (raw_row.get("nodes") or [])]
        if not nodes:
            continue
        for i, node in enumerate(nodes):
            if not node["id"]:
                raise SystemExit("每个节点都需要 id")
            if node["id"] in by_id:
                raise SystemExit("节点 id 重复：%s" % node["id"])
            by_id[node["id"]] = node
        gaps = [node_gap(nodes[i], nodes[i + 1], forward) for i in range(len(nodes) - 1)]
        inner_w = sum(n["w"] for n in nodes) + sum(gaps)
        frame = raw_row.get("frame") or ""
        frame_w = text_width(frame, 15, bold=True) + FRAME_PAD * 2 if frame else 0
        outer_w = max(inner_w, frame_w) + (FRAME_PAD * 2 if frame else 0)
        outer_h = max(n["h"] for n in nodes) + (FRAME_TITLE_H + FRAME_PAD if frame else 0) + (FRAME_PAD if frame else 0)
        rows.append({
            "nodes": nodes,
            "gaps": gaps,
            "inner_w": inner_w,
            "outer_w": outer_w,
            "outer_h": outer_h,
            "frame": frame,
            "dashed": bool(raw_row.get("dashed")),
            "tone": raw_row.get("tone") or "blue",
        })

    has_under = any(e.get("route") == "under" for e in edges)
    side = 52 if has_under else 0
    title = str(spec.get("title") or "")
    subtitle = str(spec.get("subtitle") or "")
    callouts = spec.get("callouts") or []
    footer = spec.get("footer") or []
    if isinstance(footer, str):
        footer = [footer]

    left_pad = PAD + side
    content_w = max([r["outer_w"] for r in rows] + [text_width(title, TITLE_FS, bold=True), 640])
    for row in rows:
        for node in row["nodes"]:
            if node["kind"] == "banner" and len(row["nodes"]) == 1:
                node["w"] = content_w - (FRAME_PAD * 2 if row["frame"] else 0)
                row["inner_w"] = node["w"]
                row["outer_w"] = content_w
    content_w = max(r["outer_w"] for r in rows)
    canvas_w = left_pad + content_w + PAD + side

    y = 28.0
    title_y = y + TITLE_FS
    y = title_y + 16
    if subtitle:
        y += SUB_FS + 10
    y += 8

    for row in rows:
        row["y"] = y
        row["x"] = left_pad + (content_w - row["outer_w"]) / 2
        inner_x = row["x"] + (FRAME_PAD if row["frame"] else 0)
        inner_y = row["y"] + ((FRAME_TITLE_H + FRAME_PAD / 2) if row["frame"] else 0)
        max_h = max(n["h"] for n in row["nodes"])
        x = inner_x + max(0, (row["inner_w"] - (sum(n["w"] for n in row["nodes"]) + sum(row["gaps"]))) / 2)
        # inner_w already includes gaps; start at inner_x, but if frame is wider, center the nodes
        used = sum(n["w"] for n in row["nodes"]) + sum(row["gaps"])
        x = inner_x + max(0.0, (row["outer_w"] - (FRAME_PAD * 2 if row["frame"] else 0) - used) / 2)
        for i, node in enumerate(row["nodes"]):
            node["x"] = x
            node["y"] = inner_y + (max_h - node["h"]) / 2
            x += node["w"] + (row["gaps"][i] if i < len(row["gaps"]) else 0)
        y += row["outer_h"] + ROW_GAP

    lane_y = y + 8 if has_under else y
    if has_under:
        y = lane_y + 28
    if callouts:
        y += 8
        callout_y = y
        y += len(callouts) * 26
    else:
        callout_y = y
    if footer:
        y += 8
        footer_y = y
        y += 48
    else:
        footer_y = y
    canvas_h = y + 20

    o = []
    a = o.append
    a('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="%s">'
      % (canvas_w, canvas_h, canvas_w, canvas_h, FONT))
    a("<defs>")
    for name, tone in TONES.items():
        a('<marker id="arrow-%s" markerWidth="10" markerHeight="8" refX="8" refY="3" orient="auto">'
          '<path d="M0,0 L8,3 L0,6 Z" fill="%s"/></marker>' % (name, tone["ink"]))
    a("</defs>")
    a('<rect width="%d" height="%d" fill="#FFFFFF"/>' % (canvas_w, canvas_h))
    if title:
        a('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="%d" font-weight="bold" fill="%s">%s</text>'
          % (canvas_w / 2, title_y, TITLE_FS, TITLE_INK, escape(title)))
    if subtitle:
        a('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="%d" fill="%s">%s</text>'
          % (canvas_w / 2, title_y + 16 + SUB_FS, SUB_FS, SUB_INK, escape(subtitle)))

    for row in rows:
        if row["frame"]:
            tone = tone_of(row["tone"])
            dash = ' stroke-dasharray="6 4"' if row["dashed"] else ""
            a('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="16" fill="%s" stroke="%s" stroke-width="1.5"%s/>'
              % (row["x"], row["y"], row["outer_w"], row["outer_h"], tone["soft"], tone["stroke"], dash))
            a('<text x="%.1f" y="%.1f" font-size="15" font-weight="bold" fill="%s">%s</text>'
              % (row["x"] + FRAME_PAD, row["y"] + 24, tone["ink"], escape(row["frame"])))
        for node in row["nodes"]:
            draw_node(a, node)

    gutter_x = 24
    gutter_right = canvas_w - 24
    for edge in edges:
        src = by_id.get(edge.get("from"))
        dst = by_id.get(edge.get("to"))
        if src is None or dst is None:
            raise SystemExit("边引用了不存在的节点：%s -> %s" % (edge.get("from"), edge.get("to")))
        draw_edge(a, src, dst, edge, gutter_x, gutter_right, lane_y)

    for i, call in enumerate(callouts):
        tone = tone_of(call.get("tone") or "red")
        a('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="14" font-weight="bold" fill="%s">%s</text>'
          % (canvas_w / 2, callout_y + 16 + i * 26, tone["ink"], escape(str(call.get("text") or ""))))

    if footer:
        text = "    |    ".join(str(item) for item in footer)
        a('<rect x="%d" y="%.1f" width="%d" height="40" rx="12" fill="#E8EAF6" stroke="#3949AB"/>'
          % (PAD, footer_y, canvas_w - PAD * 2))
        a('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="14" font-weight="bold" fill="%s">!  %s</text>'
          % (canvas_w / 2, footer_y + 26, TITLE_INK, escape(text)))

    a("</svg>")
    return "\n".join(o) + "\n"


def draw_node(a, node: dict):
    tone = tone_of(node["tone"])
    x, y, w, h = node["x"], node["y"], node["w"], node["h"]
    dash = ' stroke-dasharray="6 4"' if node["dashed"] else ""
    if node["kind"] == "diamond":
        cx, cy = x + w / 2, y + h / 2
        points = "%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" % (
            cx, y + 6, x + w - 4, cy, cx, y + h - 6, x + 4, cy)
        a('<polygon points="%s" fill="%s" stroke="%s" stroke-width="2"/>' % (points, tone["soft"], tone["stroke"]))
        a('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="15" font-weight="bold" fill="%s">%s</text>'
          % (cx, cy + 5, tone["ink"], escape(node["title"])))
        return
    if node["kind"] == "banner":
        a('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="12" fill="%s" stroke="%s" stroke-width="2"%s/>'
          % (x, y, w, h, tone["soft"], tone["stroke"], dash))
        a('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="15" font-weight="bold" fill="%s">%s</text>'
          % (x + w / 2, y + h / 2 + 5, tone["ink"], escape(node["title"])))
        return

    a('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d" fill="#FFFFFF" stroke="%s" stroke-width="2"%s/>'
      % (x, y, w, h, CARD_RX, tone["stroke"], dash))
    text_x = x + 16
    if node["icon"]:
        a(icon_svg(node["icon"], x + 14, y + (h - 24) / 2))
        text_x = x + 48
    title_x = text_x
    if node["badge"]:
        a('<circle cx="%.1f" cy="%.1f" r="12" fill="%s"/>' % (text_x + 12, y + 26, tone["ink"]))
        a('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="12" font-weight="bold" fill="#FFFFFF">%s</text>'
          % (text_x + 12, y + 30, escape(node["badge"])))
        title_x = text_x + 32
    a('<text x="%.1f" y="%.1f" font-size="%d" font-weight="bold" fill="%s">%s</text>'
      % (title_x, y + 30, CARD_FS, TITLE_INK, escape(node["title"])))
    ly = y + 52
    for line in node["lines"]:
        a('<text x="%.1f" y="%.1f" font-size="%d" fill="%s">%s</text>'
          % (text_x, ly, LINE_FS, BODY, escape(line)))
        ly += LINE_H


def draw_edge(a, src, dst, edge, gutter_x, gutter_right, lane_y):
    tone = tone_of(edge.get("tone") or "blue")
    label = str(edge.get("label") or "")
    dash = ' stroke-dasharray="6 4"' if edge.get("dashed") else ""
    marker = "url(#arrow-%s)" % (edge.get("tone") or "blue")
    common = 'fill="none" stroke="%s" stroke-width="2"%s marker-end="%s"' % (tone["ink"], dash, marker)

    def label_at(lx, ly):
        if label:
            a('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="13" font-weight="bold" fill="%s">%s</text>'
              % (lx, ly, tone["ink"], escape(label)))

    if edge.get("route") == "under":
        # 从源卡片右侧出去，沿画布外缘绕到底部，再从左侧进入目标，避免穿过下方通栏。
        sy = src["y"] + src["h"] / 2
        dy = dst["y"] + dst["h"] / 2
        a('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f" %s/>' % (
            src["x"] + src["w"], sy,
            gutter_right, sy,
            gutter_right, lane_y,
            gutter_x, lane_y,
            gutter_x, dy,
            dst["x"], dy,
            common))
        label_at((gutter_x + gutter_right) / 2, lane_y - 8)
        return

    same_band = abs((src["y"] + src["h"] / 2) - (dst["y"] + dst["h"] / 2)) < 30
    forward = dst["x"] > src["x"]
    if same_band and forward and dst["x"] - (src["x"] + src["w"]) < GAP_LINK + 8:
        y = src["y"] + src["h"] / 2
        x1 = src["x"] + src["w"] + 2
        x2 = dst["x"] - 2
        a('<path d="M%.1f %.1f L%.1f %.1f" %s/>' % (x1, y, x2, y, common))
        label_at((x1 + x2) / 2, y - 8)
        return

    if same_band and forward:
        y = min(src["y"], dst["y"]) - 14
        a('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f" %s/>' % (
            src["x"] + src["w"] / 2, src["y"],
            src["x"] + src["w"] / 2, y,
            dst["x"] + dst["w"] / 2, y,
            dst["x"] + dst["w"] / 2, dst["y"],
            common))
        label_at((src["x"] + dst["x"] + dst["w"]) / 2, y - 6)
        return

    # 跨行：先竖后横再竖，避免穿卡片
    mid_y = (src["y"] + src["h"] + dst["y"]) / 2
    a('<path d="M%.1f %.1f L%.1f %.1f L%.1f %.1f L%.1f %.1f" %s/>' % (
        src["x"] + src["w"] / 2, src["y"] + src["h"],
        src["x"] + src["w"] / 2, mid_y,
        dst["x"] + dst["w"] / 2, mid_y,
        dst["x"] + dst["w"] / 2, dst["y"],
        common))
    label_at((src["x"] + src["w"] / 2 + dst["x"] + dst["w"] / 2) / 2, mid_y - 8)


def main():
    parser = argparse.ArgumentParser(description="按流程图风格生成 SVG")
    parser.add_argument("spec", nargs="?", help="JSON 规格文件路径")
    parser.add_argument("-o", "--out", help="输出 SVG 路径")
    parser.add_argument("--example", action="store_true", help="打印示例规格并退出")
    parser.add_argument("--png", help="同时导出 PNG（需本机已安装 cairosvg，脚本不代为安装）")
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if args.example:
        path = example_spec_path()
        try:
            with open(path, "r", encoding="utf-8-sig") as handle:
                print(handle.read().rstrip("\n"))
        except OSError as exc:
            raise SystemExit("读不到示例规格 %s：%s" % (path, exc))
        return

    if args.spec:
        with open(args.spec, "r", encoding="utf-8-sig") as handle:
            spec = json.load(handle)
    else:
        spec = json.load(sys.stdin)

    svg = render(spec)
    if args.out:
        folder = os.path.dirname(os.path.abspath(args.out))
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(svg)
        print("已生成 %s" % args.out, file=sys.stderr)
    else:
        print(svg)

    if args.png:
        try:
            from cairosvg import svg2png
            svg2png(bytestring=svg.encode("utf-8"), write_to=args.png, scale=2)
            print("已导出 %s" % args.png, file=sys.stderr)
        except ImportError:
            warn("--png 需要 cairosvg，脚本不代为安装")


if __name__ == "__main__":
    main()
