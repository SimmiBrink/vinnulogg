"""
Work Log - Windows 11 Activity Logger

Tracks the active application every 5 seconds.
- Writes a detailed English work log (worklog.txt) in real time.
- Takes a screenshot every 30 minutes (saved in /screenshots/).
- Regenerates the Mermaid flowchart HTML every 2 hours.

Usage: python activity_logger.py
"""

import time
import json
import os
from datetime import datetime
from collections import defaultdict

try:
    import win32gui
    import win32process
    import psutil
except ImportError:
    print("ERROR: Missing packages. Run install.bat first.")
    input("Press Enter to close...")
    raise SystemExit(1)

# --- Settings ---
SAMPLE_INTERVAL_SEC     = 5       # Poll active window every 5 seconds
CHART_INTERVAL_SEC      = 7200    # Regenerate Mermaid chart every 2 hours
SCREENSHOT_INTERVAL_SEC = 1800    # Take screenshot every 30 minutes
MIN_ACTIVITY_SEC        = 30      # Minimum session length shown in chart

LOG_FILE        = "vinnulogg.json"
HTML_FILE       = "flowchart.html"
MERMAID_FILE    = "flowchart.mmd"
WORKLOG_FILE    = "worklog.txt"
SCREENSHOTS_DIR = "screenshots"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_duration(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def describe_activity(app: str, title: str, duration_sec: int) -> str:
    """Return a detailed English sentence describing what the user was doing."""
    app_l  = app.lower()
    title_l = title.lower()
    title_s = title[:80]
    dur    = fmt_duration(duration_sec)

    # --- Web browsers ---
    if any(b in app_l for b in ("chrome", "firefox", "msedge", "edge", "brave", "opera")):
        if any(k in title_l for k in ("github", "gitlab", "bitbucket")):
            action = "Browsing a code repository on GitHub/GitLab"
        elif any(k in title_l for k in ("youtube", "netflix", "twitch")):
            action = "Watching online video"
        elif any(k in title_l for k in ("gmail", "outlook.live", "mail")):
            action = "Reading or writing email in the browser"
        elif any(k in title_l for k in ("docs.google", "google docs", "sheets", "slides")):
            action = "Working in Google Docs / Sheets / Slides"
        elif any(k in title_l for k in ("stackoverflow", "stack overflow")):
            action = "Looking up answers on Stack Overflow"
        elif any(k in title_l for k in ("chatgpt", "claude.ai", "copilot", "gemini", "perplexity")):
            action = "Working with an AI assistant"
        elif any(k in title_l for k in ("jira", "linear", "trello", "asana", "notion")):
            action = "Managing tasks or projects in the browser"
        elif any(k in title_l for k in ("figma", "miro", "lucidchart")):
            action = "Working on design or diagrams in the browser"
        else:
            action = "Browsing the web"
        return f"{action} — {dur} — \"{title_s}\""

    # --- Code editors / IDEs ---
    if any(e in app_l for e in ("code", "cursor", "vscodium", "pycharm", "idea", "rider",
                                 "webstorm", "phpstorm", "clion", "goland",
                                 "sublime_text", "atom", "notepad++", "vim", "nvim")):
        if "debug" in title_l or "debugger" in title_l:
            action = "Debugging code"
        elif "test" in title_l:
            action = "Running or writing tests"
        else:
            action = "Writing or editing code"
        return f"{action} in {app} — {dur} — \"{title_s}\""

    # --- Terminals ---
    if any(t in app_l for t in ("cmd", "powershell", "windowsterminal", "wt",
                                  "conhost", "bash", "mintty", "pwsh")):
        return f"Working in the terminal / command line — {dur} — \"{title_s}\""

    # --- Git GUI clients ---
    if any(g in app_l for g in ("gitkraken", "sourcetree", "fork", "gitextensions", "github desktop")):
        return f"Managing git repository in {app} — {dur}"

    # --- Communication ---
    if any(c in app_l for c in ("slack", "teams", "discord", "zoom", "skype", "webex")):
        if any(k in title_l for k in ("call", "meeting", "video", "huddle")):
            action = "In a video call or meeting"
        else:
            action = "Communicating via chat"
        return f"{action} in {app} — {dur} — \"{title_s}\""

    # --- Email clients ---
    if any(m in app_l for m in ("outlook", "thunderbird", "mailbird")):
        return f"Reading or writing email in {app} — {dur} — \"{title_s}\""

    # --- Office / documents ---
    if any(o in app_l for o in ("winword", "word", "excel", "powerpnt", "powerpoint",
                                  "onenote", "libreoffice", "soffice")):
        return f"Working on a document in {app} — {dur} — \"{title_s}\""

    # --- File management ---
    if "explorer" in app_l:
        return f"Managing files in Windows Explorer — {dur} — \"{title_s}\""

    # --- Design tools ---
    if any(d in app_l for d in ("figma", "photoshop", "illustrator", "gimp",
                                  "inkscape", "affinity", "xd", "sketch")):
        return f"Working on design in {app} — {dur} — \"{title_s}\""

    # --- Music / media ---
    if any(m in app_l for m in ("spotify", "vlc", "musicbee", "foobar", "winamp")):
        return f"Listening to music or media in {app} — {dur} — \"{title_s}\""

    # --- Desktop / unknown ---
    if app_l in ("desktop",):
        return f"At the desktop or switching between tasks — {dur}"

    return f"Using {app} — {dur} — \"{title_s}\""


# ---------------------------------------------------------------------------
# ActivityLogger
# ---------------------------------------------------------------------------

class ActivityLogger:
    def __init__(self):
        self.activities    = []
        self.current_app   = None
        self.current_title = None
        self.current_start = None
        self.log_date      = datetime.now().date()
        self._pillow_ok    = None   # lazy: None = unchecked, True/False = result

        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
        self.load_log()

    # ------------------------------------------------------------------
    # Windows API
    # ------------------------------------------------------------------

    def get_active_window_info(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return "Desktop", "Desktop"
            title = win32gui.GetWindowText(hwnd) or "Unknown"
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                app_name = proc.name().replace(".exe", "")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                app_name = "Unknown"
            return app_name, title
        except Exception:
            return "Unknown", "Unknown"

    # ------------------------------------------------------------------
    # Screenshots
    # ------------------------------------------------------------------

    def _check_pillow(self) -> bool:
        if self._pillow_ok is None:
            try:
                from PIL import ImageGrab  # noqa: F401
                self._pillow_ok = True
            except ImportError:
                self._pillow_ok = False
                print("[WARNING] Pillow not installed — screenshots disabled.")
                print("          Run:  pip install Pillow")
        return self._pillow_ok

    def take_screenshot(self):
        if not self._check_pillow():
            return
        try:
            from PIL import ImageGrab
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(SCREENSHOTS_DIR, f"screenshot_{ts}.png")
            img  = ImageGrab.grab()
            w, h = img.size
            img  = img.resize((w // 2, h // 2))   # 50% size to save space
            img.save(path, "PNG", optimize=True)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Screenshot -> {path}")
            self._worklog_event(f"Screenshot saved: {path}")
        except Exception as e:
            print(f"Screenshot failed: {e}")

    # ------------------------------------------------------------------
    # JSON log
    # ------------------------------------------------------------------

    def load_log(self):
        if not os.path.exists(LOG_FILE):
            return
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == str(self.log_date):
                self.activities = data.get("activities", [])
                print(f"Loaded {len(self.activities)} activities from {LOG_FILE}")
        except Exception as e:
            print(f"Error loading log: {e}")

    def save_log(self):
        data = {"date": str(self.log_date), "activities": self.activities}
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_activity(self, app_name: str, title: str, timestamp: datetime):
        if app_name != self.current_app:
            if self.current_app is not None:
                duration = int((timestamp - self.current_start).total_seconds())
                entry = {
                    "app":      self.current_app,
                    "title":    self.current_title,
                    "start":    self.current_start.isoformat(),
                    "end":      timestamp.isoformat(),
                    "duration": duration,
                }
                self.activities.append(entry)
                if duration >= MIN_ACTIVITY_SEC:
                    self._worklog_activity(entry)
            self.current_app   = app_name
            self.current_title = title
            self.current_start = timestamp
        else:
            self.current_title = title  # update title if it changes within same app

    # ------------------------------------------------------------------
    # Work log (English text file)
    # ------------------------------------------------------------------

    def _worklog_activity(self, act: dict):
        """Append a detailed English line for a completed activity session."""
        t_start = datetime.fromisoformat(act["start"]).strftime("%H:%M")
        t_end   = datetime.fromisoformat(act["end"]).strftime("%H:%M")
        desc    = describe_activity(act["app"], act["title"], act["duration"])
        line    = f"[{t_start} → {t_end}]  {desc}\n"
        with open(WORKLOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)

    def _worklog_event(self, msg: str):
        """Write a timestamped event line (e.g. screenshot, start, stop)."""
        ts = datetime.now().strftime("%H:%M")
        with open(WORKLOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}]  >>> {msg}\n")

    def _worklog_header(self):
        """Write a day header to the work log."""
        date_str = datetime.now().strftime("%A, %B %d %Y")
        with open(WORKLOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"  Work Log — {date_str}\n")
            f.write(f"{'='*60}\n")

    # ------------------------------------------------------------------
    # Mermaid chart
    # ------------------------------------------------------------------

    def _merge_activities(self) -> list:
        all_acts = list(self.activities)
        if self.current_app is not None:
            now = datetime.now()
            all_acts.append({
                "app":      self.current_app,
                "title":    self.current_title,
                "start":    self.current_start.isoformat(),
                "end":      now.isoformat(),
                "duration": int((now - self.current_start).total_seconds()),
            })
        merged = []
        for act in all_acts:
            if merged and merged[-1]["app"] == act["app"]:
                merged[-1]["end"]       = act["end"]
                merged[-1]["duration"] += act["duration"]
            else:
                merged.append(dict(act))
        return [a for a in merged if a["duration"] >= MIN_ACTIVITY_SEC]

    @staticmethod
    def _safe(text: str) -> str:
        return text.replace('"', "'").replace("\n", " ")[:40]

    def generate_mermaid(self) -> str:
        merged = self._merge_activities()
        if not merged:
            return "flowchart TD\n    A([No activities recorded yet])"

        lines = ["flowchart TD"]
        t0 = datetime.fromisoformat(merged[0]["start"]).strftime("%H:%M")
        lines.append(f'    START(["Day started {t0}"])')

        prev = "START"
        for i, act in enumerate(merged):
            nid    = f"N{i}"
            app    = self._safe(act["app"])
            ts     = datetime.fromisoformat(act["start"]).strftime("%H:%M")
            te     = datetime.fromisoformat(act["end"]).strftime("%H:%M")
            dur    = fmt_duration(act["duration"])
            lines.append(f'    {nid}["{app}\\n{ts} - {te}\\n{dur}"]')
            lines.append(f"    {prev} --> {nid}")
            prev = nid

        now_str = datetime.now().strftime("%H:%M:%S")
        lines.append(f'    END(["Last updated {now_str}"])')
        lines.append(f"    {prev} --> END")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # HTML dashboard
    # ------------------------------------------------------------------

    def generate_html(self, mermaid_code: str) -> str:
        date_str  = datetime.now().strftime("%d.%m.%Y")
        time_str  = datetime.now().strftime("%H:%M:%S")
        merged    = self._merge_activities()
        total_sec = sum(a["duration"] for a in merged)
        th        = total_sec // 3600
        tm        = (total_sec % 3600) // 60

        app_times: dict[str, int] = defaultdict(int)
        for act in merged:
            app_times[act["app"]] += act["duration"]

        top_apps = sorted(app_times.items(), key=lambda x: x[1], reverse=True)[:8]
        top_rows = "".join(
            f"<tr><td>{app}</td><td>{fmt_duration(t)}</td></tr>"
            for app, t in top_apps
        )

        colors = ["#89b4fa","#a6e3a1","#fab387","#f38ba8",
                  "#cba6f7","#94e2d5","#f9e2af","#89dceb"]
        bar_items = ""
        if total_sec > 0:
            for idx, (app, t) in enumerate(top_apps):
                pct   = round(t / total_sec * 100, 1)
                color = colors[idx % len(colors)]
                bar_items += (
                    f'<div class="bar-item" style="width:{pct}%;background:{color}" '
                    f'title="{app}: {pct}%"></div>'
                )

        # Embed last 60 lines of worklog.txt
        worklog_html = "<em>No entries yet.</em>"
        if os.path.exists(WORKLOG_FILE):
            try:
                with open(WORKLOG_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                recent = lines[-60:] if len(lines) > 60 else lines
                worklog_html = "".join(
                    f'<div class="log-line">{line.rstrip()}</div>'
                    for line in recent
                )
            except Exception:
                pass

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="{CHART_INTERVAL_SEC}">
  <title>Work Log — {date_str}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background: #1e1e2e; color: #cdd6f4;
      padding: 24px; min-height: 100vh;
    }}
    h1  {{ color: #89b4fa; margin-bottom: 4px; font-size: 1.8rem; }}
    h2  {{ color: #cba6f7; margin-bottom: 14px; font-size: 1.1rem; }}
    .subtitle {{ color: #6c7086; font-size: 0.9rem; margin-bottom: 24px; }}
    .stats {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
    .stat-card {{
      background: #313244; border-radius: 12px;
      padding: 16px 24px; min-width: 140px;
      border-left: 4px solid #89b4fa;
    }}
    .stat-card h3 {{
      color: #a6e3a1; font-size: 0.75rem; text-transform: uppercase;
      letter-spacing: 1px; margin-bottom: 6px;
    }}
    .stat-card p {{ font-size: 1.6rem; font-weight: 700; }}
    .section {{ background: #313244; border-radius: 12px; padding: 20px; margin-bottom: 20px; }}
    .mermaid {{ background: #fff; border-radius: 8px; padding: 16px; overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 10px 16px; border-bottom: 1px solid #45475a; }}
    th {{ color: #89b4fa; font-size: 0.8rem; text-transform: uppercase; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #3d3d5c; }}
    .bar-container {{
      display: flex; height: 28px; border-radius: 6px;
      overflow: hidden; margin-bottom: 8px; gap: 2px;
    }}
    .bar-item {{ height: 100%; transition: opacity .2s; cursor: default; }}
    .bar-item:hover {{ opacity: 0.8; }}
    .worklog {{
      font-family: 'Cascadia Code', Consolas, monospace;
      font-size: 0.82rem; line-height: 1.75;
      max-height: 420px; overflow-y: auto;
      background: #181825; border-radius: 8px; padding: 16px;
    }}
    .log-line {{ color: #cdd6f4; white-space: pre-wrap; }}
    .log-line:hover {{ background: #2a2a3d; }}
    .footer {{ color: #585b70; font-size: 0.8rem; margin-top: 16px; }}
  </style>
</head>
<body>
  <h1>Work Log</h1>
  <p class="subtitle">
    {date_str} &mdash;
    Chart regenerates every {CHART_INTERVAL_SEC // 3600} hours &mdash;
    Screenshots every {SCREENSHOT_INTERVAL_SEC // 60} min &mdash;
    Last updated {time_str}
  </p>

  <div class="stats">
    <div class="stat-card"><h3>Total Time</h3><p>{th}:{tm:02d}h</p></div>
    <div class="stat-card"><h3>Apps Used</h3><p>{len(app_times)}</p></div>
    <div class="stat-card"><h3>Sessions</h3><p>{len(merged)}</p></div>
  </div>

  <div class="section">
    <h2>App Usage</h2>
    <div class="bar-container">{bar_items}</div>
    <table>
      <tr><th>Application</th><th>Time</th></tr>
      {top_rows}
    </table>
  </div>

  <div class="section">
    <h2>Detailed Activity Log</h2>
    <div class="worklog">{worklog_html}</div>
  </div>

  <div class="section">
    <h2>Day Timeline (Flowchart)</h2>
    <div class="mermaid">
{mermaid_code}
    </div>
  </div>

  <p class="footer">
    Logs: worklog.txt &nbsp;|&nbsp;
    Screenshots: /{SCREENSHOTS_DIR}/ &nbsp;|&nbsp;
    Data: {LOG_FILE}
  </p>
  <script>mermaid.initialize({{ startOnLoad: true, theme: 'default' }});</script>
</body>
</html>"""

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def update_output(self):
        mermaid_code = self.generate_mermaid()
        with open(MERMAID_FILE, "w", encoding="utf-8") as f:
            f.write(mermaid_code)
        html = self.generate_html(mermaid_code)
        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write(html)
        self.save_log()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Chart updated -> {HTML_FILE}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        print("=" * 58)
        print("  Work Log - Windows 11 Activity Logger")
        print(f"  Date        : {datetime.now().strftime('%d.%m.%Y')}")
        print(f"  Sampling    : every {SAMPLE_INTERVAL_SEC}s")
        print(f"  Chart       : every {CHART_INTERVAL_SEC // 3600}h")
        print(f"  Screenshots : every {SCREENSHOT_INTERVAL_SEC // 60} min  -> /{SCREENSHOTS_DIR}/")
        print(f"  Work log    : {os.path.abspath(WORKLOG_FILE)}")
        print(f"  HTML        : {os.path.abspath(HTML_FILE)}")
        print("  Ctrl+C to stop")
        print("=" * 58)

        import webbrowser
        html_path = os.path.abspath(HTML_FILE)

        self._worklog_header()
        self._worklog_event("Activity logger started")

        last_chart      = time.time() - CHART_INTERVAL_SEC  # trigger chart right away
        last_screenshot = time.time()
        first_open      = True

        try:
            while True:
                now = datetime.now()
                t   = time.time()

                # New day?
                if now.date() != self.log_date:
                    print(f"\n[{now.strftime('%H:%M')}] New day — saving and resetting log")
                    self.update_output()
                    self.activities  = []
                    self.current_app = None
                    self.log_date    = now.date()
                    self._worklog_header()

                # Sample active window
                app_name, title = self.get_active_window_info()
                self.record_activity(app_name, title, now)

                # Screenshot every 30 minutes
                if t - last_screenshot >= SCREENSHOT_INTERVAL_SEC:
                    self.take_screenshot()
                    last_screenshot = t

                # Regenerate chart every 2 hours
                if t - last_chart >= CHART_INTERVAL_SEC:
                    self.update_output()
                    last_chart = t
                    if first_open:
                        first_open = False
                        try:
                            webbrowser.open(f"file:///{html_path.replace(os.sep, '/')}")
                        except Exception:
                            pass

                time.sleep(SAMPLE_INTERVAL_SEC)

        except KeyboardInterrupt:
            print("\n\nStopped. Saving final log...")
            if self.current_app is not None:
                now   = datetime.now()
                entry = {
                    "app":      self.current_app,
                    "title":    self.current_title,
                    "start":    self.current_start.isoformat(),
                    "end":      now.isoformat(),
                    "duration": int((now - self.current_start).total_seconds()),
                }
                self.activities.append(entry)
                if entry["duration"] >= MIN_ACTIVITY_SEC:
                    self._worklog_activity(entry)
            self._worklog_event("Activity logger stopped")
            self.update_output()
            print(f"Saved to {HTML_FILE} and {WORKLOG_FILE}. Goodbye!")


if __name__ == "__main__":
    logger = ActivityLogger()
    logger.run()
