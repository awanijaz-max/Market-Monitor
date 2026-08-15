# MT5 Drawing-Level Alerts

Lets you draw horizontal lines, trendlines, or Fibonacci retracements
directly on your MT5 chart, and get an alert the moment price crosses
one — on top of the RSI/MA conditions already running.

## How it works

```
MT5 Desktop (you draw a line)
   -> LevelExporter.mq5 (runs inside MT5, exports levels every 5s)
   -> levels_export.json (fixed path, written to disk)
   -> levels_feed.py (Python reads it)
   -> alert_engine.py (checks: did price just cross this level?)
   -> notifier.py (Telegram / Discord / ntfy, same as everything else)
```

**Important constraint:** this only works while MT5 desktop is open,
logged into your account, and has the LevelExporter EA attached to a
chart. Unlike the RSI/MA alerts (which run for free on GitHub Actions
24/7), this piece has to run on your own PC. Run `python main.py`
locally whenever you want it checked, or leave `continuous_runner.py`
open in the background while trading.

## Setup

### 1. Compile the Expert Advisor
1. Open MT5 -> press `F4` (or Tools -> MetaQuotes Language Editor) to
   open MetaEditor.
2. File -> Open -> navigate to `mt5_bridge/LevelExporter.mq5` from
   this project, or File -> New -> Expert Advisor and paste its
   contents in.
3. Press `F7` to compile. You want to see "0 errors" at the bottom.
   (If you hit red errors: different MT5 builds occasionally want
   minor syntax tweaks — paste the exact error text back and it can
   be fixed quickly.)

### 2. Attach it to a chart
1. Back in MT5, open the **Navigator** panel (Ctrl+N if hidden).
2. Under **Expert Advisors**, find `LevelExporter` and drag it onto
   your XAU/USD chart.
3. In the dialog that appears, go to the **Common** tab and make sure
   **"Allow file I/O"** (or "Allow Algo Trading" if that's the only
   toggle shown) is checked. Click OK.
4. You should see a small icon (usually top-right of the chart)
   confirming the EA is running.

### 3. Draw something
Use MT5's normal tools — **Insert -> Line Studies -> Horizontal Line**,
**Trend Line**, or **Insert -> Fibonacci -> Retracement** — anywhere on
your chart. The EA picks up anything you draw automatically, no extra
step needed.

### 4. Confirm the export file is being written
Open this path in File Explorer (paste it directly into the address bar):
```
%APPDATA%\MetaQuotes\Terminal\Common\Files\levels_export.json
```
Open it in Notepad — you should see your drawn level(s) listed with
their current price. If the file's price for a trendline looks off,
that's worth double-checking visually against the chart (trendline
price extrapolation can occasionally need the "ray"/extend-right
option enabled on the line for it to make sense as a live level).

### 5. Run the Python side
From the project folder:
```powershell
python main.py
```
If a level's price has just been crossed, you'll get the same
Telegram/Discord/ntfy alert as any other condition — the message will
say which specific line/level you crossed.

## Notes
- Only gold (XAU/USD) is wired up to check MT5 levels currently, since
  that's what we set up MT5 for. Extending this to BTC too is a small
  change in `alert_engine.py` if you want it later.
- Deleting a drawn line in MT5 removes it from the next export, and
  its alert condition simply stops being checked — no cleanup needed
  on the Python side.
- Renaming a line in MT5 changes its exported `name`, which resets its
  fire-once state (Python sees it as a "new" level). Redrawing a line
  in roughly the same place after deleting the old one behaves the
  same way — that's expected, not a bug.
