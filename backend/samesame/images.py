"""Deterministic illustrative images (no photos of real hotels, ever). Always labelled "illustrative"."""
import hashlib
import random

PALETTES = [("#fde68a", "#f97316"), ("#bae6fd", "#0ea5e9"), ("#ddd6fe", "#7c3aed"), ("#bbf7d0", "#059669"),
            ("#fecaca", "#e11d48"), ("#e2e8f0", "#475569"), ("#fed7aa", "#c2410c"), ("#a5f3fc", "#0e7490")]


def _rng(key: str) -> random.Random:
    return random.Random(int(hashlib.sha256(key.encode()).hexdigest()[:12], 16))


def hotel_svg(key: str, w: int = 480, h: int = 300) -> str:
    """Skyline-style hotel illustration: sky gradient, towers with lit windows, optional pool."""
    r = _rng(key)
    sky, accent = r.choice(PALETTES)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice">',
             f'<defs><linearGradient id="s" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{sky}"/>'
             f'<stop offset="1" stop-color="#ffffff"/></linearGradient></defs>',
             f'<rect width="{w}" height="{h}" fill="url(#s)"/>',
             f'<circle cx="{r.randint(40, w - 40)}" cy="{r.randint(30, 80)}" r="{r.randint(14, 26)}" fill="#fff" opacity=".7"/>']
    x = -10
    while x < w:
        bw, bh = r.randint(50, 110), r.randint(90, 240)
        main = r.random() < 0.25
        fill = accent if main else r.choice(["#334155", "#475569", "#64748b", "#1e293b"])
        parts.append(f'<rect x="{x}" y="{h - bh}" width="{bw}" height="{bh}" fill="{fill}"/>')
        for wy in range(h - bh + 12, h - 20, 16):
            for wx in range(x + 8, x + bw - 10, 14):
                if r.random() < 0.55:
                    parts.append(f'<rect x="{wx}" y="{wy}" width="7" height="9" fill="#fef9c3" opacity="{r.uniform(.4, .95):.2f}"/>')
        x += bw + r.randint(2, 14)
    if r.random() < 0.5:
        parts.append(f'<rect x="0" y="{h - 26}" width="{w}" height="26" fill="#38bdf8" opacity=".85"/>')
    parts.append("</svg>")
    return "".join(parts)


def activity_svg(key: str, w: int = 480, h: int = 300) -> str:
    """Water/landscape scene for tours: river band, boats, hills."""
    r = _rng(key)
    sky, accent = r.choice(PALETTES)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice">',
             f'<rect width="{w}" height="{h}" fill="{sky}"/>']
    for i in range(3):
        cx, ry = r.randint(0, w), r.randint(60, 120)
        parts.append(f'<ellipse cx="{cx}" cy="{h * .55:.0f}" rx="{r.randint(120, 240)}" ry="{ry}" fill="#15803d" opacity="{.35 + i * .15:.2f}"/>')
    parts.append(f'<rect x="0" y="{h * .6:.0f}" width="{w}" height="{h * .4:.0f}" fill="#0e7490"/>')
    for _ in range(r.randint(2, 5)):
        bx, by = r.randint(10, w - 90), r.randint(int(h * .65), h - 30)
        parts.append(f'<path d="M{bx} {by} h80 l-12 14 h-56 z" fill="{accent}"/>')
        parts.append(f'<circle cx="{bx + 40}" cy="{by - 8}" r="8" fill="#fde68a"/>')
    parts.append("</svg>")
    return "".join(parts)
