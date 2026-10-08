"""One-shot PNG export for compose/k8s topology (drawio CLI unavailable)."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent
BLUE = (67, 141, 213)
BLUE_STROKE = (60, 127, 192)
GRAY = (153, 153, 153)
GRAY_STROKE = (102, 102, 102)
NOTE_BG = (255, 242, 204)
NOTE_STROKE = (214, 182, 86)
TEXT = (255, 255, 255)
DARK = (51, 51, 51)
WHITE = (255, 255, 255)
BG = (255, 255, 255)

try:
    font_sm = ImageFont.truetype("arial.ttf", 12)
    font_b = ImageFont.truetype("arialbd.ttf", 14)
except OSError:
    font_sm = ImageFont.load_default()
    font_b = font_sm


def text_size(draw: ImageDraw.ImageDraw, text: str, f) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=f)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text_center(draw, box, text, f, fill=TEXT):
    x, y, w, h = box
    lines = text.split("\n")
    sizes = [text_size(draw, ln, f) for ln in lines]
    total_h = sum(s[1] for s in sizes) + 4 * (len(lines) - 1)
    cy = y + (h - total_h) // 2
    for ln, (tw, th) in zip(lines, sizes):
        draw.text((x + (w - tw) // 2, cy), ln, font=f, fill=fill)
        cy += th + 4


def rounded_rect(draw, box, fill, outline, radius=10, width=2):
    x, y, w, h = box
    draw.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=outline, width=width)


def dashed_rect(draw, box, outline=GRAY_STROKE, dash=8, gap=6, width=2):
    x, y, w, h = box
    for (x0, y0, x1, y1) in (
        (x, y, x + w, y),
        (x, y + h, x + w, y + h),
        (x, y, x, y + h),
        (x + w, y, x + w, y + h),
    ):
        length = math.hypot(x1 - x0, y1 - y0) or 1
        dx, dy = (x1 - x0) / length, (y1 - y0) / length
        pos = 0.0
        on = True
        while pos < length:
            seg = min(dash if on else gap, length - pos)
            if on:
                sx, sy = x0 + dx * pos, y0 + dy * pos
                ex, ey = x0 + dx * (pos + seg), y0 + dy * (pos + seg)
                draw.line([(sx, sy), (ex, ey)], fill=outline, width=width)
            pos += seg
            on = not on


def draw_container(draw, box, label, external=False):
    fill = GRAY if external else BLUE
    stroke = GRAY_STROKE if external else BLUE_STROKE
    rounded_rect(draw, box, fill, stroke)
    draw_text_center(draw, box, label, font_sm)


def draw_db(draw, box, label):
    x, y, w, h = box
    ellipse_h = 14
    draw.ellipse([x, y, x + w, y + ellipse_h], fill=BLUE, outline=BLUE_STROKE, width=2)
    draw.rectangle([x + 1, y + ellipse_h // 2, x + w - 1, y + h - ellipse_h // 2], fill=BLUE)
    draw.line([(x, y + ellipse_h // 2), (x, y + h - ellipse_h // 2)], fill=BLUE_STROKE, width=2)
    draw.line([(x + w, y + ellipse_h // 2), (x + w, y + h - ellipse_h // 2)], fill=BLUE_STROKE, width=2)
    draw.ellipse([x, y + h - ellipse_h, x + w, y + h], fill=BLUE, outline=BLUE_STROKE, width=2)
    draw_text_center(draw, (x, y + 10, w, h - 18), label, font_sm)


def draw_note(draw, box, text):
    x, y, w, h = box
    draw.rectangle([x, y, x + w, y + h], fill=NOTE_BG, outline=NOTE_STROKE, width=2)
    fold = 14
    draw.polygon(
        [(x + w - fold, y), (x + w, y + fold), (x + w - fold, y + fold)],
        fill=WHITE,
        outline=NOTE_STROKE,
    )
    draw.multiline_text((x + 10, y + 10), text, font=font_sm, fill=DARK, spacing=4)


def _arrow_head(draw, p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    ang = math.atan2(y2 - y1, x2 - x1)
    ah = 8
    for a in (ang + 2.6, ang - 2.6):
        draw.line([(x2, y2), (x2 + ah * math.cos(a), y2 + ah * math.sin(a))], fill=GRAY_STROKE, width=2)


def _line(draw, p1, p2, dashed=False):
    x1, y1 = p1
    x2, y2 = p2
    if not dashed:
        draw.line([p1, p2], fill=GRAY_STROKE, width=2)
        return
    length = math.hypot(x2 - x1, y2 - y1) or 1
    dx, dy = (x2 - x1) / length, (y2 - y1) / length
    pos = 0.0
    on = True
    while pos < length:
        seg = min(8 if on else 6, length - pos)
        if on:
            sx, sy = x1 + dx * pos, y1 + dy * pos
            ex, ey = x1 + dx * (pos + seg), y1 + dy * (pos + seg)
            draw.line([(sx, sy), (ex, ey)], fill=GRAY_STROKE, width=2)
        pos += seg
        on = not on


def _label(draw, x, y, text):
    tw, th = text_size(draw, text, font_sm)
    draw.rectangle([x - tw // 2 - 2, y - 1, x + tw // 2 + 2, y + th + 1], fill=WHITE)
    draw.text((x - tw // 2, y), text, font=font_sm, fill=DARK)


def arrow(draw, p1, p2, dashed=False, label=None):
    _line(draw, p1, p2, dashed=dashed)
    _arrow_head(draw, p1, p2)
    if label:
        _label(draw, (p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2 - 12, label)


def ortho_h_then_v(draw, p1, p2, dashed=False, label=None):
    mid = (p2[0], p1[1])
    _line(draw, p1, mid, dashed=dashed)
    _line(draw, mid, p2, dashed=dashed)
    _arrow_head(draw, mid, p2)
    if label:
        _label(draw, (p1[0] + p2[0]) // 2, p1[1] - 12, label)


def center(box, side):
    x, y, w, h = box
    mapping = {
        "b": (x + w // 2, y + h),
        "t": (x + w // 2, y),
        "r": (x + w, y + h // 2),
        "l": (x, y + h // 2),
        "r25": (x + w, y + int(h * 0.25)),
        "r35": (x + w, y + int(h * 0.35)),
        "r45": (x + w, y + int(h * 0.45)),
        "r55": (x + w, y + int(h * 0.55)),
        "r65": (x + w, y + int(h * 0.65)),
        "r70": (x + w, y + int(h * 0.70)),
        "r75": (x + w, y + int(h * 0.75)),
        "r85": (x + w, y + int(h * 0.85)),
        "r20": (x + w, y + int(h * 0.2)),
    }
    return mapping[side]


def render_compose():
    img = Image.new("RGB", (1100, 640), BG)
    d = ImageDraw.Draw(img)
    draw_note(
        d,
        (40, 20, 360, 70),
        "Compose = side-stack only.\nK8s owns api/frontend/stores/minio.\nZero overlap.",
    )

    ctrl = (40, 120, 280, 340)
    data = (400, 120, 320, 280)
    for box, title in ((ctrl, "control (obs)"), (data, "data (llm)")):
        dashed_rect(d, box)
        d.text((box[0] + 8, box[1] + 6), title, font=font_b, fill=DARK)

    prom = (ctrl[0] + 40, ctrl[1] + 50, 180, 60)
    graf = (ctrl[0] + 40, ctrl[1] + 140, 180, 60)
    jaeger = (ctrl[0] + 40, ctrl[1] + 230, 180, 60)
    draw_container(d, prom, "prometheus\n:9090")
    draw_container(d, graf, "grafana\n:3000")
    draw_container(d, jaeger, "jaeger\n:16686")

    oll = (data[0] + 40, data[1] + 50, 200, 70)
    vllm = (data[0] + 40, data[1] + 150, 200, 70)
    draw_container(d, oll, "ollama\n:11434 mem 3g")
    draw_container(d, vllm, "vllm (opt)\n:8000")

    k8s = (800, 200, 200, 80)
    draw_container(d, k8s, "K8s kp\napi+stores+minio", external=True)

    arrow(d, center(graf, "t"), center(prom, "b"))
    arrow(d, center(k8s, "l"), center(oll, "r"), dashed=True, label="LLM")
    arrow(d, center(k8s, "l"), center(jaeger, "r"), dashed=True, label="OTLP")
    arrow(d, center(prom, "r"), center(k8s, "l"), dashed=True, label="scrape")

    path = OUT / "compose-topology.png"
    img.save(path, "PNG")
    print(f"wrote {path}")


def render_k8s():
    img = Image.new("RGB", (1480, 860), BG)
    d = ImageDraw.Draw(img)
    draw_note(
        d,
        (40, 20, 400, 70),
        "Hybrid: platform in K8s.\nCompose side: ollama + obs.\nIngress LB :8088.",
    )
    browser = (40, 200, 120, 50)
    draw_container(d, browser, "Browser", external=True)

    node = (220, 110, 1000, 620)
    dashed_rect(d, node)
    d.text((node[0] + 8, node[1] + 6), "Docker Desktop Node", font=font_b, fill=DARK)

    ing = (node[0] + 40, node[1] + 50, 160, 70)
    draw_container(d, ing, "ingress-nginx\nLB :8088", external=True)

    ns = (node[0] + 40, node[1] + 150, 920, 430)
    dashed_rect(d, ns)
    d.text((ns[0] + 8, ns[1] + 6), "namespace kp", font=font_b, fill=DARK)

    edgep = (ns[0] + 30, ns[1] + 40, 200, 160)
    ctrlp = (ns[0] + 260, ns[1] + 40, 220, 160)
    datap = (ns[0] + 30, ns[1] + 230, 860, 170)
    for box, title in ((edgep, "plane=edge"), (ctrlp, "plane=control"), (datap, "plane=data")):
        dashed_rect(d, box)
        d.text((box[0] + 8, box[1] + 6), title, font=font_b, fill=DARK)

    fe = (edgep[0] + 20, edgep[1] + 50, 160, 80)
    api = (ctrlp[0] + 30, ctrlp[1] + 50, 160, 80)
    draw_container(d, fe, "deploy/frontend\nsvc :80")
    draw_container(d, api, "deploy/api\nsvc :8080")

    dbs = []
    for i, lab in enumerate(["postgres", "neo4j", "qdrant", "redis", "minio"]):
        box = (datap[0] + 20 + i * 150, datap[1] + 50, 120, 70)
        draw_db(d, box, lab)
        dbs.append(box)

    hostoll = (1280, 280, 160, 70)
    draw_container(d, hostoll, "Compose ollama\n:11434 host", external=True)

    arrow(d, center(browser, "r"), center(ing, "l"), label="kp.local")
    arrow(d, center(ing, "b"), center(fe, "t"), label="/")
    ortho_h_then_v(d, center(ing, "r"), center(api, "t"), label="/api")
    for db in dbs:
        arrow(d, center(api, "b"), center(db, "t"))
    arrow(d, center(api, "r"), center(hostoll, "l"), dashed=True, label="host.docker.internal")

    path = OUT / "k8s-topology.png"
    img.save(path, "PNG")
    print(f"wrote {path}")


if __name__ == "__main__":
    render_compose()
    render_k8s()
