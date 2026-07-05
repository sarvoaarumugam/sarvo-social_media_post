"""Builds the burned-in live captions (.ass subtitles) for the video.

Each dialogue turn is split into short phrases (a few words at a time, like the
big podcast channels). Phrase timing comes from the REAL per-turn timings captured
during TTS stitching, distributed by word share inside each turn. Host 1 and
host 2 get different colors so viewers can follow who's talking.
"""

from app.core.config import get_settings
from app.models.episode import DialogueTurn, TurnTiming

_ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Host1,{font},{size},{c1},{c1},&H00141B26,&H96000000,-1,0,0,0,100,100,0,0,1,3,1,8,80,80,{margin},1
Style: Host2,{font},{size},{c2},{c2},&H00141B26,&H96000000,-1,0,0,0,100,100,0,0,1,3,1,8,80,80,{margin},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(seconds: float) -> str:
    """ASS timestamp H:MM:SS.cc"""
    cs = int(round(max(seconds, 0) * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def _escape(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", " ")


def _phrases(text: str, max_words: int) -> list[list[str]]:
    """Split a turn into caption-sized word chunks, breaking early at punctuation."""
    words = text.split()
    chunks: list[list[str]] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        boundary = word.rstrip('"').rstrip("'").endswith((".", ",", "!", "?", "—", "...", ":"))
        if len(current) >= max_words or (boundary and len(current) >= 2):
            chunks.append(current)
            current = []
    if current:
        if chunks and len(current) == 1:  # avoid a lonely one-word caption
            chunks[-1].extend(current)
        else:
            chunks.append(current)
    return chunks


def estimate_timings(turns: list[DialogueTurn], total_seconds: float) -> list[TurnTiming]:
    """Fallback for episodes whose audio was made before timing capture existed:
    distribute the total duration across turns by word share."""
    total_words = sum(len(t.text.split()) for t in turns) or 1
    timings, cursor = [], 0.0
    for i, turn in enumerate(turns):
        dur = (len(turn.text.split()) / total_words) * total_seconds
        timings.append(TurnTiming(index=i, start=round(cursor, 3), end=round(cursor + dur, 3)))
        cursor += dur
    return timings


def build_ass(
    turns: list[DialogueTurn],
    timings: list[TurnTiming],
    hosts: list[str],
    *,
    offset: float = 0.0,
) -> str:
    """Render the full .ass subtitle document.

    `offset`: shift ALL captions later by this many seconds — used when the video
    opens with a silent intro card and the audio starts after it.
    """
    s = get_settings()
    doc = _ASS_HEADER.format(
        font=s.caption_font,
        size=s.caption_font_size,
        c1=s.caption_host1_color,
        c2=s.caption_host2_color,
        margin=s.caption_margin_top,
    )
    by_index = {t.index: t for t in timings}
    host1 = hosts[0] if hosts else ""

    lines: list[str] = []
    for i, turn in enumerate(turns):
        timing = by_index.get(i)
        if timing is None:
            continue
        style = "Host1" if turn.speaker == host1 else "Host2"
        chunks = _phrases(turn.text, s.caption_max_words)
        if not chunks:
            continue
        total_words = sum(len(c) for c in chunks)
        span = timing.end - timing.start
        cursor = timing.start
        for chunk in chunks:
            dur = max((len(chunk) / total_words) * span, 0.30)
            end = min(cursor + dur, timing.end)
            start = cursor
            cursor = end
            text = _escape(" ".join(chunk))
            lines.append(
                f"Dialogue: 0,{_ts(start + offset)},{_ts(end + offset)},{style},,0,0,0,,"
                f"{{\\fad(100,100)}}{text}"
            )
    return doc + "\n".join(lines) + "\n"
