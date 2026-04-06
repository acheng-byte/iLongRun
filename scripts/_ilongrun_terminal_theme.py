#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
import textwrap
import unicodedata

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


def fg256(code: int) -> str:
    return f"\033[38;5;{code}m"


PALETTE = {
    "gold": fg256(220),
    "amber": fg256(214),
    "warm": fg256(178),
    "bright": fg256(226),
    "soft": fg256(229),
    "ok": fg256(48),
    "warn": fg256(221),
    "err": fg256(203),
    "muted": fg256(244),
}


def supports_color(stream=None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("CLICOLOR_FORCE") == "1" or os.environ.get("FORCE_COLOR"):
        return True
    stream = stream or sys.stdout
    return bool(getattr(stream, "isatty", lambda: False)()) and os.environ.get("TERM", "") not in {"", "dumb"}


COLOR_ENABLED = supports_color()


def paint(text: str, *styles: str, enable: bool | None = None) -> str:
    if enable is None:
        enable = COLOR_ENABLED
    if not enable or not styles:
        return text
    return "".join(styles) + text + RESET


def gradient_text(text: str, enable: bool | None = None) -> str:
    if enable is None:
        enable = COLOR_ENABLED
    if not enable:
        return text
    gradient = [178, 184, 190, 220, 226, 220, 190, 184]
    out: list[str] = []
    visible_index = 0
    for char in text:
        if char.isspace():
            out.append(char)
            continue
        color = fg256(gradient[min(visible_index, len(gradient) - 1)])
        out.append(f"{BOLD}{color}{char}{RESET}")
        visible_index += 1
    return "".join(out)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def display_width(text: str) -> int:
    plain = strip_ansi(text)
    total = 0
    for char in plain:
        if char in {"\ufe0f", "\ufe0e"}:
            continue
        if unicodedata.combining(char):
            continue
        if unicodedata.east_asian_width(char) in {"F", "W"}:
            total += 2
        elif unicodedata.category(char) == "So":
            total += 2
        else:
            total += 1
    return total


def pad_display(text: str, width: int) -> str:
    current = display_width(text)
    if current >= width:
        return text
    return text + (" " * (width - current))


def board_title(icon: str, suffix: str) -> str:
    return f"{paint(icon, PALETTE['amber'], BOLD)} {gradient_text('iLongRun')} {paint(suffix, PALETTE['gold'], BOLD)}"


def left_border() -> str:
    return paint("│", PALETTE["gold"], BOLD)


def open_top(title: str, tail_width: int = 30) -> str:
    return paint("╭─── ", PALETTE["gold"], BOLD) + title + " " + paint("─" * tail_width, PALETTE["gold"], BOLD)


def open_bottom(width: int = 52) -> str:
    return paint("╰" + ("─" * width), PALETTE["gold"], BOLD)


def board_line(label: str, value: str, label_width: int = 14) -> str:
    border = left_border()
    label_text = paint(pad_display(label, label_width), PALETTE["amber"], BOLD)
    return f"{border}  {label_text} {value}"


def section_heading(title: str) -> str:
    return paint(title, PALETTE["amber"], BOLD)


def section_rule(width: int = 34) -> str:
    return paint("─" * width, PALETTE["gold"], BOLD)


def detail_line(label: str, value: str, label_width: int = 12) -> str:
    label_text = paint(pad_display(label, label_width), PALETTE["amber"], BOLD)
    return f"  {label_text} {value}"


def ad_box(text: str, width: int = 72) -> str:
    lines = textwrap.wrap(text, width=max(20, width - 4), break_long_words=False, break_on_hyphens=False)
    border = paint("=" * width, PALETTE["gold"], BOLD)
    rows = [border]
    for raw in lines:
        inner = f"= {raw}"
        padding = width - 1 - display_width(inner)
        rows.append(paint(inner + (" " * max(0, padding)) + "=", PALETTE["gold"], BOLD))
    rows.append(border)
    return "\n".join(rows)
