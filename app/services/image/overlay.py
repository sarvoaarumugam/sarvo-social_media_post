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


def compose_background(base_png: bytes | None, brand: str) -> bytes:
    """The in-video background: art cover-fitted, with a small brand mark in the
    TOP-LEFT corner (center stays clear for captions, bottom for the waveform)."""
    s = get_settings()
    w, h = s.image_width, s.image_height
    if base_png is not None:
        canvas = _cover(Image.open(BytesIO(base_png)).convert("RGB"), w, h)
    else:
        canvas = Image.new("RGB", (w, h), s.image_bg_color)

    if brand:  # empty brand = use the art exactly as-is
        draw = ImageDraw.Draw(canvas)
        font = _load_font(44, bold=True)
        text = brand.upper()
        x, y = int(w * 0.03), int(h * 0.04)
        draw.text((x + 2, y + 2), text, font=font, fill="#000000")
        draw.text((x, y), text, font=font, fill=s.image_accent_color)

    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def _load_title_font(size: int) -> ImageFont.FreeTypeFont:
    s = get_settings()
    for path in (s.thumbnail_title_font, "C:/Windows/Fonts/ariblk.ttf", s.image_font_bold):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _clean_title(title: str) -> str:
    """Keep only the punchy core: drop '| Learn English Fast'-style SEO tails."""
    core = title.split("|")[0].strip()
    if len(core) > 48 and "—" in core:
        core = core.split("—")[0].strip()
    return core or title


def _region_is_light(img: Image.Image, x0: int, y0: int, x1: int, y1: int) -> bool:
    """Average brightness of the area the text will occupy (0-255 scale)."""
    region = img.crop((x0, y0, x1, y1)).convert("L").resize((32, 32))
    hist_mean = sum(i * c for i, c in enumerate(region.histogram())) / (32 * 32)
    return hist_mean > 140


def compose_thumbnail_card(base_png: bytes, title: str) -> bytes:
    """The thumbnail / intro card, done like top channels do it:

    - shortened, UPPERCASE title in a bold display font (Impact)
    - fitted to the EMPTY CENTER COLUMN so it never overlaps the hosts
    - text color auto-switches with the artwork brightness (dark-on-light /
      white-on-dark), one line popped in the accent color
    - soft drop shadow instead of a hard outline
    """
    s = get_settings()
    w, h = s.image_width, s.image_height
    canvas = _cover(Image.open(BytesIO(base_png)).convert("RGB"), w, h)
    draw = ImageDraw.Draw(canvas)

    text = _clean_title(title) if s.thumbnail_title_shorten else title
    if s.thumbnail_title_uppercase:
        text = text.upper()

    # Fit into the center column, at most 3 lines, block no deeper than ~42% height.
    max_text_w = int(w * s.thumbnail_title_width_ratio)
    size = s.thumbnail_title_font_size
    while size >= 40:
        font = _load_title_font(size)
        lines = _wrap(draw, text, font, max_text_w)
        line_h = int(size * 1.12)
        if len(lines) <= 3 and line_h * len(lines) <= int(h * 0.42):
            break
        size = int(size * 0.85)

    block_h = line_h * len(lines)
    y0 = s.thumbnail_title_margin_top

    # Pick colors from the brightness of the exact area the text sits on.
    light = _region_is_light(canvas, (w - max_text_w) // 2, y0,
                             (w + max_text_w) // 2, y0 + block_h)
    primary = s.thumbnail_text_on_light if light else s.thumbnail_text_on_dark
    accent = s.thumbnail_accent_on_light if light else s.thumbnail_accent_on_dark
    shadow = "#00000055" if light else "#00000099"

    # Which line pops in the accent color: the middle of 3, the 2nd of 2.
    accent_line = {3: 1, 2: 1}.get(len(lines), -1)

    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    y = y0
    off = max(3, size // 28)  # shadow offset scales with font size
    for i, line in enumerate(lines):
        lw = odraw.textlength(line, font=font)
        x = (w - lw) // 2
        color = accent if i == accent_line else primary
        odraw.text((x + off, y + off), line, font=font, fill=shadow)
        odraw.text((x, y), line, font=font, fill=color)
        y += line_h

    # Single-line titles: pop the longest word instead of a whole line.
    if len(lines) == 1:
        words = lines[0].split()
        if len(words) > 2:
            target = max(words, key=len)
            x = (w - odraw.textlength(lines[0], font=font)) // 2
            for word in words:
                word_w = odraw.textlength(word + " ", font=font)
                if word == target:
                    odraw.text((x, y0), word, font=font, fill=accent)
                x += word_w

    canvas = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


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
