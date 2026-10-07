"""Tests for ohlc. No network: every case uses candles built in the test.

    python -m unittest discover -v
"""

import io
import unittest

import ohlc
from ohlc import ASCII_BLOCKS, BLOCKS, Candle, draw, from_text, pick_glyphs, summary

HOUR = 3600
T0 = 1_790_000_000


def series(*closes, start=100.0):
    """A candle per close, each opening where the last one closed."""
    out, open_ = [], start
    for i, close in enumerate(closes):
        out.append(Candle(T0 + i * HOUR, open_, max(open_, close) * 1.01,
                          min(open_, close) * 0.99, close, 1000))
        open_ = close
    return out


class ParsingTests(unittest.TestCase):
    def test_csv_with_a_header(self):
        text = "time,open,high,low,close,volume\n1790000000,10,12,9,11,500\n1790003600,11,13,10,12,600\n"
        candles = from_text(text)
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0].open, 10)
        self.assertEqual(candles[1].close, 12)
        self.assertEqual(candles[0].volume, 500)

    def test_csv_without_a_header(self):
        candles = from_text("1790000000,10,12,9,11\n")
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0].volume, 0.0)

    def test_json_array_of_arrays(self):
        candles = from_text("[[1790000000,10,12,9,11,500]]")
        self.assertEqual(candles[0].high, 12)

    def test_json_array_of_objects(self):
        candles = from_text('[{"time":1790000000,"open":10,"high":12,"low":9,"close":11}]')
        self.assertEqual(candles[0].close, 11)

    def test_json_short_keys(self):
        candles = from_text('[{"t":1790000000,"o":10,"h":12,"l":9,"c":11,"v":7}]')
        self.assertEqual(candles[0].volume, 7)

    def test_a_geckoterminal_payload_is_unwrapped(self):
        candles = from_text('{"ohlcv_list":[[1790000000,10,12,9,11,500]]}')
        self.assertEqual(len(candles), 1)

    def test_candles_come_back_oldest_first(self):
        candles = from_text("[[1790003600,11,13,10,12],[1790000000,10,12,9,11]]")
        self.assertLess(candles[0].time, candles[1].time)

    def test_empty_input_is_refused(self):
        with self.assertRaises(SystemExit):
            from_text("   \n")


class CandleTests(unittest.TestCase):
    def test_rising_and_falling(self):
        self.assertTrue(Candle(T0, 10, 11, 9, 11).rising)
        self.assertFalse(Candle(T0, 11, 11, 9, 10).rising)
        self.assertTrue(Candle(T0, 10, 10, 10, 10).rising, "flat counts as rising")


class DrawingTests(unittest.TestCase):
    def test_the_chart_has_the_asked_for_shape(self):
        lines = draw(series(101, 102, 103, 104), height=8, width=40, colour=False)
        self.assertEqual(len(lines), 9, "one row per level plus the time axis")
        self.assertTrue(lines[-1].lstrip().startswith(BLOCKS["corner"]))

    def test_only_the_last_candles_are_drawn(self):
        candles = series(*range(100, 160))
        lines = draw(candles, height=6, width=10, colour=False)
        body = lines[0].split(BLOCKS["axis"], 1)[1]
        self.assertLessEqual(len(body), 10)

    def test_a_flat_series_does_not_divide_by_zero(self):
        flat = [Candle(T0 + i * HOUR, 50, 50, 50, 50) for i in range(5)]
        lines = draw(flat, height=5, width=20, colour=False)
        self.assertEqual(len(lines), 6)

    def test_a_single_candle_is_drawable(self):
        lines = draw(series(105), height=5, width=20, colour=False)
        self.assertEqual(len(lines), 6)

    def test_the_price_axis_runs_high_to_low(self):
        lines = draw(series(110, 120, 130), height=6, width=20, colour=False)
        axis = [float(line.split(BLOCKS["axis"])[0].strip().replace(",", "")) for line in lines[:-1]]
        self.assertEqual(axis, sorted(axis, reverse=True))

    def test_colour_adds_escapes_and_plain_does_not(self):
        plain = "\n".join(draw(series(101, 99), height=5, width=10, colour=False))
        tinted = "\n".join(draw(series(101, 99), height=5, width=10, colour=True))
        self.assertNotIn("\033[", plain)
        self.assertIn("\033[", tinted)

    def test_ascii_output_stays_inside_ascii(self):
        lines = draw(series(101, 103, 99, 104), height=8, width=20,
                     colour=False, glyphs=ASCII_BLOCKS)
        joined = "\n".join(lines)
        joined.encode("ascii")  # raises if any glyph slipped through
        self.assertNotIn(BLOCKS["full"], joined)

    def test_wicks_reach_beyond_the_body(self):
        # one candle with a tiny body and a long upper wick
        tall = [Candle(T0, 100, 140, 99, 101)]
        lines = draw(tall, height=10, width=5, colour=False)
        column = [line.split(BLOCKS["axis"], 1)[1][0] for line in lines[:-1]]
        self.assertIn(BLOCKS["wick_upper"] if BLOCKS["wick_upper"] in column
                      else BLOCKS["wick_full"], column)
        self.assertTrue(any(c in (BLOCKS["full"], BLOCKS["upper"], BLOCKS["lower"])
                            for c in column), "the body must be drawn too")


class Stubborn:
    """A stream stuck on one encoding, like a console that refuses to be changed."""

    def __init__(self, encoding):
        self.encoding = encoding

    def reconfigure(self, **_):
        raise OSError("this stream cannot be reconfigured")


class GlyphTests(unittest.TestCase):
    def test_a_console_that_can_be_switched_to_utf8_keeps_box_drawing(self):
        stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1254")
        self.assertIs(pick_glyphs(stream), BLOCKS)
        self.assertEqual(stream.encoding, "utf-8", "the stream should have been switched")

    def test_a_console_stuck_on_a_legacy_page_falls_back_to_ascii(self):
        self.assertIs(pick_glyphs(Stubborn("cp1254")), ASCII_BLOCKS)

    def test_a_stream_with_no_encoding_at_all_falls_back(self):
        self.assertIs(pick_glyphs(Stubborn(None)), ASCII_BLOCKS)

    def test_utf8_keeps_the_box_drawing(self):
        self.assertIs(pick_glyphs(io.TextIOWrapper(io.BytesIO(), encoding="utf-8")), BLOCKS)


class SummaryTests(unittest.TestCase):
    def test_the_change_is_open_to_close_across_the_range(self):
        line = summary(series(110, 120), colour=False)
        self.assertIn("+20.00%", line)          # 100 -> 120
        self.assertIn("2 candles", line)

    def test_a_fall_is_signed(self):
        self.assertIn("-10.00%", summary(series(90), colour=False))

    def test_volume_is_left_out_when_there_is_none(self):
        quiet = [Candle(T0, 10, 11, 9, 10, 0)]
        self.assertNotIn("volume", summary(quiet, colour=False))
        self.assertIn("volume", summary(series(101), colour=False))


class CliTests(unittest.TestCase):
    def test_no_arguments_is_an_error(self):
        import contextlib
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            ohlc.main([])

    def test_a_file_renders(self):
        import tempfile, pathlib
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "c.csv"
            path.write_text("1790000000,10,12,9,11\n1790003600,11,13,10,12\n", encoding="utf-8")
            self.assertEqual(ohlc.main([str(path), "--no-colour", "--width", "20"]), 0)


if __name__ == "__main__":
    unittest.main()
