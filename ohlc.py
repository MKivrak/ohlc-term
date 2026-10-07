#!/usr/bin/env python3
"""ohlc — candlestick charts in the terminal.

Draws real candles, with a body and wicks, using half-block characters so each
column is one candle and each row is two price levels. Reads OHLCV from a file,
from stdin, or straight from GeckoTerminal's public API.

    ohlc.py --pool <ADDRESS>              # fetch and draw
    ohlc.py candles.csv                   # time,open,high,low,close[,volume]
    cat candles.json | ohlc.py -          # a JSON array of arrays or objects

Only the standard library. No API key.

MIT licensed.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

GT = "https://api.geckoterminal.com/api/v2"
TIMEFRAMES = {
    "1m": ("minute", 1), "5m": ("minute", 5), "15m": ("minute", 15),
    "1h": ("hour", 1), "4h": ("hour", 4), "12h": ("hour", 12), "1d": ("day", 1),
}

RESET = "\033[0m"
GREEN = "\033[38;5;42m"
RED = "\033[38;5;203m"
DIM = "\033[38;5;244m"

BLOCKS = {
    "upper": "▀", "lower": "▄", "full": "█",
    "wick_upper": "╵", "wick_lower": "╷", "wick_full": "│",
    "axis": "│", "corner": "└",
}
# Windows consoles often run a legacy code page that has none of the above.
ASCII_BLOCKS = {
    "upper": "'", "lower": ".", "full": "#",
    "wick_upper": "|", "wick_lower": "|", "wick_full": "|",
    "axis": "|", "corner": "+",
}


def pick_glyphs(stream) -> dict[str, str]:
    """Use box drawing where the terminal can encode it, ASCII where it cannot."""
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass
    encoding = getattr(stream, "encoding", None) or "ascii"
    try:
        "".join(BLOCKS.values()).encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return ASCII_BLOCKS
    return BLOCKS


@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    @property
    def rising(self) -> bool:
        return self.close >= self.open


# ---------------------------------------------------------------- input

def from_gecko(network: str, pool: str, timeframe: str, limit: int) -> list[Candle]:
    unit, aggregate = TIMEFRAMES[timeframe]
    url = f"{GT}/networks/{network}/pools/{pool}/ohlcv/{unit}?aggregate={aggregate}&limit={limit}"
    request = urllib.request.Request(url, headers={"accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f"GeckoTerminal answered {error.code} for that pool") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"could not reach GeckoTerminal: {error.reason}") from error

    rows = payload.get("data", {}).get("attributes", {}).get("ohlcv_list") or []
    if not rows:
        raise SystemExit("that pool returned no candles")
    candles = [Candle(int(r[0]), *(float(x) for x in r[1:6])) for r in rows]
    return sorted(candles, key=lambda c: c.time)


def parse_rows(rows) -> list[Candle]:
    out: list[Candle] = []
    for row in rows:
        if isinstance(row, dict):
            get = lambda *names: next((row[n] for n in names if n in row), 0)  # noqa: E731
            out.append(Candle(
                int(get("time", "t", "timestamp")),
                float(get("open", "o")), float(get("high", "h")),
                float(get("low", "l")), float(get("close", "c")),
                float(get("volume", "v") or 0),
            ))
        else:
            values = list(row)
            out.append(Candle(int(float(values[0])), *(float(v) for v in values[1:5]),
                              float(values[5]) if len(values) > 5 else 0.0))
    return sorted(out, key=lambda c: c.time)


def from_text(text: str) -> list[Candle]:
    stripped = text.strip()
    if not stripped:
        raise SystemExit("no input")
    if stripped[0] in "[{":
        data = json.loads(stripped)
        if isinstance(data, dict):
            for key in ("ohlcv_list", "candles", "data"):
                if key in data:
                    data = data[key]
                    break
        return parse_rows(data)

    reader = csv.reader(io.StringIO(stripped))
    rows = [r for r in reader if r and r[0].strip()]
    if rows and not rows[0][0].strip().lstrip("-").replace(".", "", 1).isdigit():
        rows = rows[1:]        # a header line
    return parse_rows(rows)


# ---------------------------------------------------------------- drawing

def draw(candles: list[Candle], height: int, width: int, colour: bool,
         glyphs: dict[str, str] = BLOCKS) -> list[str]:
    """One column per candle, two price levels per row, wicks included."""
    candles = candles[-width:]
    low = min(c.low for c in candles)
    high = max(c.high for c in candles)
    if high == low:
        high, low = high + 0.5, low - 0.5
    span = high - low
    levels = height * 2

    def level(price: float) -> int:
        """0 at the bottom, levels-1 at the top."""
        return max(0, min(levels - 1, int((price - low) / span * (levels - 1) + 0.5)))

    grid = [[" "] * len(candles) for _ in range(height)]
    colours = [[None] * len(candles) for _ in range(height)]

    for x, candle in enumerate(candles):
        body_low, body_high = sorted((level(candle.open), level(candle.close)))
        wick_low, wick_high = level(candle.low), level(candle.high)
        tint = GREEN if candle.rising else RED

        for lv in range(wick_low, wick_high + 1):
            row = height - 1 - lv // 2
            top_half = lv % 2 == 1
            inside_body = body_low <= lv <= body_high
            cell = grid[row][x]

            if inside_body:
                mark = glyphs["upper"] if top_half else glyphs["lower"]
                both = (glyphs["upper"], glyphs["lower"])
                grid[row][x] = glyphs["full"] if cell in both and cell != mark else mark
            else:
                mark = glyphs["wick_upper"] if top_half else glyphs["wick_lower"]
                both = (glyphs["wick_upper"], glyphs["wick_lower"])
                if cell == " ":
                    grid[row][x] = mark
                elif cell in both and cell != mark:
                    grid[row][x] = glyphs["wick_full"]
            colours[row][x] = tint

    labels = [f"{low + span * (height - 1 - r) / max(1, height - 1):,.6g}" for r in range(height)]
    pad = max(len(s) for s in labels)

    lines = []
    for r in range(height):
        cells = []
        for x in range(len(candles)):
            ch = grid[r][x]
            if ch == " " or not colour:
                cells.append(ch)
            else:
                cells.append(f"{colours[r][x]}{ch}{RESET}")
        axis = f"{labels[r]:>{pad}}"
        if colour:
            axis = f"{DIM}{axis}{RESET}"
        lines.append(f"{axis} {glyphs['axis']}{''.join(cells)}")

    first = datetime.fromtimestamp(candles[0].time, timezone.utc).strftime("%d %b %H:%M")
    last = datetime.fromtimestamp(candles[-1].time, timezone.utc).strftime("%d %b %H:%M")
    gap = max(0, len(candles) - len(first) - len(last))
    footer = f"{' ' * pad} {glyphs['corner']}{first}{' ' * gap}{last}"
    lines.append(f"{DIM}{footer}{RESET}" if colour else footer)
    return lines


def summary(candles: list[Candle], colour: bool) -> str:
    first, last = candles[0], candles[-1]
    change = (last.close - first.open) / first.open * 100 if first.open else 0.0
    tint = (GREEN if change >= 0 else RED) if colour else ""
    end = RESET if colour else ""
    sign = "+" if change >= 0 else ""
    volume = sum(c.volume for c in candles)
    return (f"{len(candles)} candles   last {last.close:,.6g}   "
            f"{tint}{sign}{change:.2f}%{end}   "
            f"high {max(c.high for c in candles):,.6g}   low {min(c.low for c in candles):,.6g}"
            + (f"   volume {volume:,.0f}" if volume else ""))


# ---------------------------------------------------------------- cli

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Candlestick charts in the terminal.",
        epilog="examples:\n"
               "  ohlc.py --pool Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE -t 1h\n"
               "  ohlc.py candles.csv --height 16\n"
               "  curl -s <url> | ohlc.py -",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source", nargs="?", help="a CSV or JSON file, or - for stdin")
    parser.add_argument("--pool", help="fetch this pool from GeckoTerminal instead")
    parser.add_argument("--network", default="solana", help="chain for --pool (default: solana)")
    parser.add_argument("-t", "--timeframe", default="1h", choices=sorted(TIMEFRAMES),
                        help="candle size for --pool (default: 1h)")
    parser.add_argument("-n", "--limit", type=int, default=100, help="how many candles (default: 100)")
    parser.add_argument("--height", type=int, default=14, help="rows of chart (default: 14)")
    parser.add_argument("--width", type=int, default=0, help="columns; 0 fits the terminal")
    parser.add_argument("--no-colour", "--no-color", dest="colour", action="store_false",
                        help="plain output")
    args = parser.parse_args(argv)

    if not args.source and not args.pool:
        parser.error("give a file, - for stdin, or --pool")

    if args.pool:
        candles = from_gecko(args.network, args.pool, args.timeframe, args.limit)
    elif args.source == "-":
        candles = from_text(sys.stdin.read())
    else:
        with open(args.source, encoding="utf-8") as handle:
            candles = from_text(handle.read())

    if not candles:
        raise SystemExit("no candles to draw")

    glyphs = pick_glyphs(sys.stdout)
    colour = args.colour and sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    width = args.width or max(20, min(len(candles), (os.get_terminal_size().columns - 14)
                                      if sys.stdout.isatty() else 100))

    print()
    for line in draw(candles, max(4, args.height), width, colour, glyphs):
        print(line)
    print()
    print(summary(candles, colour))
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
