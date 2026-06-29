"""Composes the final 1920x1080 card: an optional AI background (cover-fitted and
darkened for readability) with the crisp brand + title + hosts drawn on top.

Text is always drawn by Pillow — never by the image model — so the title is
guaranteed sharp and correct.
"""

from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from app.core.config import get_settings


def _load_font(size: int, *, bold: bool) -> ImageFont.FreeTypeFont:
    s = get_settings()
    candidates = (
        [s.image_font_bold, "C:/Windows/Fonts/segoeuib.ttf"]
        if bold
        else [s.image_font_regular, "C:/Windows/Fonts/segoeui.ttf"]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize+center-crop so the image fills wxh without distortion."""
    src, dst = img.width / img.height, w / h
    if src > dst:
        new_h, new_w = h, int(h * src)
    else:
        new_w, new_h = w, int(w / src)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left, top = (new_w - w) // 2, (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def compose(
    base_png: bytes | None,
    title: str,
    brand: str,
    hosts: list[str],
    *,
    overlay_text: bool = True,
) -> bytes:
    """Build the final card. `base_png` is the AI image, or None for a solid card."""
    s = get_settings()
    w, h = s.image_width, s.image_height

    if base_png is not None:
        canvas = _cover(Image.open(BytesIO(base_png)).convert("RGB"), w, h)
    else:
        canvas = Image.new("RGB", (w, h), s.image_bg_color)

    # If we're not overlaying text, the AI image stands on its own.
    if not overlay_text:
        buf = BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()

    # Dark wash so white text always pops against any background.
    if base_png is not None and s.image_scrim_opacity > 0:
        scrim = Image.new("RGBA", (w, h), (0, 0, 0, s.image_scrim_opacity))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), scrim).convert("RGB")

    draw = ImageDraw.Draw(canvas)
    margin = int(w * 0.08)
    max_text_w = w - 2 * margin

    # Accent bar + brand (top).
    draw.rectangle([margin, int(h * 0.165), margin + int(w * 0.10), int(h * 0.17)],
                   fill=s.image_accent_color)
    draw.text((margin, int(h * 0.10)), brand.upper(), font=_load_font(48, bold=True),
              fill=s.image_accent_color)

    # Title (centered, auto-shrinks to fit).
    for size in (132, 116, 100, 84, 72):
        title_font = _load_font(size, bold=True)
        lines = _wrap(draw, title, title_font, max_text_w)
        line_h = int(size * 1.15)
        if len(lines) <= 4:
            break
    y = (h - line_h * len(lines)) // 2
    for line in lines:
        lw = draw.textlength(line, font=title_font)
        draw.text(((w - lw) // 2, y), line, font=title_font, fill=s.image_title_color)
        y += line_h

    # Hosts (bottom).
    if hosts:
        sub_font = _load_font(44, bold=False)
        sub = f"with {' & '.join(hosts)}"
        sw = draw.textlength(sub, font=sub_font)
        draw.text(((w - sw) // 2, int(h * 0.86)), sub, font=sub_font, fill=s.image_subtitle_color)

    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()
