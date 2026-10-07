# ohlc

Candlestick charts in the terminal. Real candles — body and wicks — using
half-block characters, so one column is one candle and one row is two price
levels.

```
$ ohlc.py --pool Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE -t 1h -n 60

122.527 │        │                             ╷
122.008 │█╷╷   ╷╷│    ╷│       ╷╷              ││      ╷
 121.49 │█│▄▄ ╷██▄╷   ││   ╷  ╷││││           ╷██╷ ╷╷│││╷│
120.972 │▀▀▀█▄│█╵▀█▄▄▄▄▄   │ ╷▄███▀█╷│   ╷╷ ╷╷▄█▀█╷▄▄████│╷
120.453 │ │ │▀██  │▀▀││█   ││▄█││││▀█▄▄╷██││▄▄█││█▄█▀▀│╵▀▀█
119.935 │   ╵╵▀▀  ╵│╵││█│ ▄█▀▀│   ╵╵▀▀█▄█▀██▀││  ││ ││  ╵│█
119.417 │     │    │ ││▀█▄█││││     ╵╵╵│╵╵│││││  ││ ││    █│
118.899 │     ╵         ▀▀│               │               ▀█  ╷│▄▄
 118.38 │               │││                                ████▀▀█▄
117.862 │               ╵╵╵                                ││││  ╵█▄╷
117.344 │                                                  │ ╵    ╵▀▀
116.825 │                                                  │       ╵
        └05 Oct 00:00                                    07 Oct 11:00

60 candles   last 117.624   -3.58%   high 122.527   low 116.825   volume 270,357,746
```

Green for a rising candle, red for a falling one. One Python file, standard
library only, no API key.

## Install

```bash
curl -O https://raw.githubusercontent.com/MKivrak/ohlc-term/main/ohlc.py
chmod +x ohlc.py
```

Python 3.9 or newer.

## Use

### Straight from GeckoTerminal

Any pool on any chain they index, no key needed:

```bash
ohlc.py --pool <POOL_ADDRESS>                      # solana, 1h, 100 candles
ohlc.py --pool <POOL_ADDRESS> -t 15m -n 200
ohlc.py --pool <POOL_ADDRESS> --network ethereum
```

Timeframes: `1m` `5m` `15m` `1h` `4h` `12h` `1d`.

Find a pool address from a token:

```bash
curl -s "https://api.geckoterminal.com/api/v2/networks/solana/tokens/<MINT>/pools" \
  | python -c "import json,sys; print(json.load(sys.stdin)['data'][0]['id'].split('_')[-1])"
```

### From your own data

CSV, with or without a header — `time,open,high,low,close[,volume]`:

```bash
ohlc.py candles.csv
```

JSON, as arrays or objects, from a file or a pipe:

```bash
echo '[[1790000000,10,12,9,11]]' | ohlc.py -
curl -s <some-api> | ohlc.py -
```

Object keys may be long (`time`, `open`, …) or short (`t`, `o`, `h`, `l`, `c`,
`v`). A payload wrapped in `{"ohlcv_list": …}`, `{"candles": …}` or
`{"data": …}` is unwrapped for you.

### Size and colour

```bash
ohlc.py candles.csv --height 24        # taller
ohlc.py candles.csv --width 80         # narrower; 0 fits the terminal
ohlc.py candles.csv --no-colour        # plain
NO_COLOR=1 ohlc.py candles.csv         # same, by convention
```

Colour is switched off automatically when the output is not a terminal, so
piping to a file gives you clean text.

## Terminals that cannot draw boxes

Windows consoles often start on a legacy code page with none of the block
characters. `ohlc` switches the stream to UTF-8 where it can, and where it
cannot it falls back to an ASCII set (`#`, `'`, `.`, `|`) rather than crashing
with a `UnicodeEncodeError`.

## How a candle is drawn

Each row is two price levels, upper and lower half-block. For a candle:

- the body spans open to close and is drawn with filled blocks
- the wicks reach out to high and low and are drawn with thin verticals
- where a body fills both halves of a row it becomes a full block

That is what lets a 14-row chart show 28 distinct price levels, which is
enough for the shape of a move to be legible at a glance.

## Tests

```bash
python -m unittest -v
```

Twenty-six tests, no network. They cover CSV and JSON parsing in every shape
accepted, the drawing geometry, the flat-series and single-candle edges, the
ASCII fallback, and the summary line.

## Licence

MIT
