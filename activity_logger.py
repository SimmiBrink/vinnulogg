"""
Vinnulogg - Windows 11 Activity Logger
Fylgist með forritum sem eru opin og myndar Mermaid flowchart á 10 mín fresti.

Notkun: python activity_logger.py
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
    print("VILLA: Vantar pakka. Keyrðu fyrst: install.bat")
    input("Ýttu á Enter til að loka...")
    raise SystemExit(1)

# --- Stillingar ---
SAMPLE_INTERVAL_SEC = 5       # Sækir virkt glugga á 5 sek fresti
UPDATE_INTERVAL_SEC = 600     # Uppfærir flowchart á 10 mín fresti (600 sek)
MIN_ACTIVITY_SEC = 30         # Lágmarkstími til að aðgerð birtist á korti (30 sek)
LOG_FILE = "vinnulogg.json"
HTML_FILE = "flowchart.html"
MERMAID_FILE = "flowchart.mmd"


class ActivityLogger:
    def __init__(self):
        self.activities = []
        self.current_app = None
        self.current_title = None
        self.current_start = None
        self.log_date = datetime.now().date()
        self.load_log()

    # ------------------------------------------------------------------
    # Windows API
    # ------------------------------------------------------------------

    def get_active_window_info(self):
        """Skilar (forritsnafn, gluggaheiti) fyrir virka gluggann."""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return "Desktop", "Desktop"

            title = win32gui.GetWindowText(hwnd) or "Óþekkt"

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                app_name = proc.name().replace(".exe", "")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                app_name = "Óþekkt"

            return app_name, title
        except Exception:
            return "Óþekkt", "Óþekkt"

    # ------------------------------------------------------------------
    # Log handling
    # ------------------------------------------------------------------

    def load_log(self):
        """Hleður inn log frá deginum ef hann er til."""
        if not os.path.exists(LOG_FILE):
            return
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == str(self.log_date):
                self.activities = data.get("activities", [])
                print(f"Hlaðið inn {len(self.activities)} aðgerðir úr {LOG_FILE}")
        except Exception as e:
            print(f"Villa við innhleðslu log: {e}")

    def save_log(self):
        """Vista log í JSON skrá."""
        data = {"date": str(self.log_date), "activities": self.activities}
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_activity(self, app_name: str, title: str, timestamp: datetime):
        """Skráir aðgerð eða framlengir núverandi."""
        if app_name != self.current_app:
            # Vista fyrri aðgerð
            if self.current_app is not None:
                duration = (timestamp - self.current_start).seconds
                self.activities.append({
                    "app": self.current_app,
                    "title": self.current_title,
                    "start": self.current_start.isoformat(),
                    "end": timestamp.isoformat(),
                    "duration": duration,
                })
            # Byrja nýja aðgerð
            self.current_app = app_name
            self.current_title = title
            self.current_start = timestamp
        else:
            self.current_title = title  # uppfæra titil ef breytist

    # ------------------------------------------------------------------
    # Mermaid generation
    # ------------------------------------------------------------------

    def _merge_activities(self) -> list:
        """Sameinar aðgerðir sama forrits sem eru í röð."""
        all_acts = list(self.activities)

        # Bæta við núverandi opnu aðgerð
        if self.current_app is not None:
            now = datetime.now()
            all_acts.append({
                "app": self.current_app,
                "title": self.current_title,
                "start": self.current_start.isoformat(),
                "end": now.isoformat(),
                "duration": int((now - self.current_start).total_seconds()),
            })

        # Sameina samfelldar aðgerðir sama forrits
        merged = []
        for act in all_acts:
            if merged and merged[-1]["app"] == act["app"]:
                merged[-1]["end"] = act["end"]
                merged[-1]["duration"] += act["duration"]
            else:
                merged.append(dict(act))

        # Sía of stuttar aðgerðir
        return [a for a in merged if a["duration"] >= MIN_ACTIVITY_SEC]

    @staticmethod
    def _fmt_duration(seconds: int) -> str:
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours} klst {mins} mín"
        if mins > 0:
            return f"{mins} mín {secs} sek"
        return f"{secs} sek"

    @staticmethod
    def _safe(text: str) -> str:
        """Hreinsar texta fyrir Mermaid nóður."""
        return text.replace('"', "'").replace("\n", " ")[:40]

    def generate_mermaid(self) -> str:
        """Myndar Mermaid flowchart kóða."""
        merged = self._merge_activities()

        if not merged:
            return "flowchart TD\n    A([Engar aðgerðir skráðar enn])"

        lines = ["flowchart TD"]

        start_time = datetime.fromisoformat(merged[0]["start"]).strftime("%H:%M")
        lines.append(f'    START(["Dagurinn byrjar {start_time}"])')

        prev_node = "START"
        for i, act in enumerate(merged):
            node_id = f"N{i}"
            app = self._safe(act["app"])
            t_start = datetime.fromisoformat(act["start"]).strftime("%H:%M")
            t_end = datetime.fromisoformat(act["end"]).strftime("%H:%M")
            dur = self._fmt_duration(act["duration"])

            lines.append(f'    {node_id}["{app}\\n{t_start} - {t_end}\\n{dur}"]')
            lines.append(f"    {prev_node} --> {node_id}")
            prev_node = node_id

        now_str = datetime.now().strftime("%H:%M:%S")
        lines.append(f'    END(["Sidast uppfaert {now_str}"])')
        lines.append(f"    {prev_node} --> END")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # HTML generation
    # ------------------------------------------------------------------

    def generate_html(self, mermaid_code: str) -> str:
        """Myndar HTML skrá með Mermaid korti sem uppfærist sjálfkrafa."""
        date_str = datetime.now().strftime("%d.%m.%Y")
        time_str = datetime.now().strftime("%H:%M:%S")

        merged = self._merge_activities()
        total_sec = sum(a["duration"] for a in merged)
        total_hours = total_sec // 3600
        total_mins = (total_sec % 3600) // 60

        app_times: dict[str, int] = defaultdict(int)
        for act in merged:
            app_times[act["app"]] += act["duration"]

        top_apps = sorted(app_times.items(), key=lambda x: x[1], reverse=True)[:8]
        top_apps_rows = "".join(
            f"<tr><td>{app}</td><td>{self._fmt_duration(t)}</td></tr>"
            for app, t in top_apps
        )

        # Percent bar data
        bar_items = ""
        colors = ["#89b4fa", "#a6e3a1", "#fab387", "#f38ba8",
                  "#cba6f7", "#94e2d5", "#f9e2af", "#89dceb"]
        if total_sec > 0:
            for idx, (app, t) in enumerate(top_apps):
                pct = round(t / total_sec * 100, 1)
                color = colors[idx % len(colors)]
                bar_items += (
                    f'<div class="bar-item" style="width:{pct}%;background:{color}" '
                    f'title="{app}: {pct}%"></div>'
                )

        return f"""<!DOCTYPE html>
<html lang="is">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="{UPDATE_INTERVAL_SEC}">
  <title>Vinnulogg - {date_str}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background: #1e1e2e;
      color: #cdd6f4;
      padding: 24px;
      min-height: 100vh;
    }}
    h1 {{ color: #89b4fa; margin-bottom: 4px; font-size: 1.8rem; }}
    h2 {{ color: #cba6f7; margin-bottom: 14px; font-size: 1.1rem; }}
    .subtitle {{ color: #6c7086; font-size: 0.9rem; margin-bottom: 24px; }}
    .stats {{
      display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px;
    }}
    .stat-card {{
      background: #313244; border-radius: 12px;
      padding: 16px 24px; min-width: 140px;
      border-left: 4px solid #89b4fa;
    }}
    .stat-card h3 {{ color: #a6e3a1; font-size: 0.75rem; text-transform: uppercase;
      letter-spacing: 1px; margin-bottom: 6px; }}
    .stat-card p {{ font-size: 1.6rem; font-weight: 700; }}
    .section {{
      background: #313244; border-radius: 12px;
      padding: 20px; margin-bottom: 20px;
    }}
    .mermaid {{ background: #fff; border-radius: 8px; padding: 16px;
      overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 10px 16px;
      border-bottom: 1px solid #45475a; }}
    th {{ color: #89b4fa; font-size: 0.8rem; text-transform: uppercase; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #3d3d5c; }}
    .bar-container {{
      display: flex; height: 28px; border-radius: 6px; overflow: hidden;
      margin-bottom: 8px; gap: 2px;
    }}
    .bar-item {{ height: 100%; transition: opacity .2s; cursor: default; }}
    .bar-item:hover {{ opacity: 0.8; }}
    .footer {{ color: #585b70; font-size: 0.8rem; margin-top: 16px; }}
  </style>
</head>
<body>
  <h1>Vinnulogg</h1>
  <p class="subtitle">{date_str} &mdash; Uppfærist sjálfvirkt á {UPDATE_INTERVAL_SEC // 60} mín fresti</p>

  <div class="stats">
    <div class="stat-card">
      <h3>Heildartimi</h3>
      <p>{total_hours}:{total_mins:02d} klst</p>
    </div>
    <div class="stat-card">
      <h3>Forrit notuð</h3>
      <p>{len(app_times)}</p>
    </div>
    <div class="stat-card">
      <h3>Aðgerðir</h3>
      <p>{len(merged)}</p>
    </div>
  </div>

  <div class="section">
    <h2>Notkun forrits</h2>
    <div class="bar-container">{bar_items}</div>
    <table>
      <tr><th>Forrit</th><th>Timi</th></tr>
      {top_apps_rows}
    </table>
  </div>

  <div class="section">
    <h2>Flæðirit yfir daginn</h2>
    <div class="mermaid">
{mermaid_code}
    </div>
  </div>

  <p class="footer">Sidast uppfaert: {time_str}</p>

  <script>mermaid.initialize({{ startOnLoad: true, theme: 'default' }});</script>
</body>
</html>"""

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def update_output(self):
        """Myndar og vistar Mermaid og HTML skrár."""
        mermaid_code = self.generate_mermaid()

        with open(MERMAID_FILE, "w", encoding="utf-8") as f:
            f.write(mermaid_code)

        html = self.generate_html(mermaid_code)
        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write(html)

        self.save_log()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Uppfaert -> {HTML_FILE}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        print("=" * 55)
        print("  Vinnulogg - Windows 11 Activity Logger")
        print(f"  Dagsetning : {datetime.now().strftime('%d.%m.%Y')}")
        print(f"  Sýnataka   : á {SAMPLE_INTERVAL_SEC} sek fresti")
        print(f"  Flowchart  : uppfaerist á {UPDATE_INTERVAL_SEC // 60} min fresti")
        print(f"  HTML skra  : {os.path.abspath(HTML_FILE)}")
        print("  Ctrl+C til að hætta")
        print("=" * 55)

        # Opna HTML í vafra þegar ræst
        import webbrowser
        html_path = os.path.abspath(HTML_FILE)

        # Keyra strax fyrstu uppfærslu
        last_update = time.time() - UPDATE_INTERVAL_SEC

        try:
            while True:
                now = datetime.now()

                # Nýr dagur?
                if now.date() != self.log_date:
                    print(f"\n[{now.strftime('%H:%M')}] Nyr dagur - vista og hreinsa log")
                    self.update_output()
                    self.activities = []
                    self.current_app = None
                    self.log_date = now.date()

                # Sækja virkt glugga
                app_name, title = self.get_active_window_info()
                self.record_activity(app_name, title, now)

                # Uppfæra á 10 mín fresti
                if time.time() - last_update >= UPDATE_INTERVAL_SEC:
                    self.update_output()
                    last_update = time.time()
                    # Opna vafra í fyrsta skipti
                    if last_update < UPDATE_INTERVAL_SEC + 30:
                        try:
                            webbrowser.open(f"file:///{html_path.replace(os.sep, '/')}")
                        except Exception:
                            pass

                time.sleep(SAMPLE_INTERVAL_SEC)

        except KeyboardInterrupt:
            print("\n\nHaett. Vista sidasta log...")
            # Vista núverandi aðgerð
            if self.current_app is not None:
                now = datetime.now()
                self.activities.append({
                    "app": self.current_app,
                    "title": self.current_title,
                    "start": self.current_start.isoformat(),
                    "end": now.isoformat(),
                    "duration": int((now - self.current_start).total_seconds()),
                })
            self.update_output()
            print(f"Vinnulogg vistað í {HTML_FILE}. Bless!")


if __name__ == "__main__":
    logger = ActivityLogger()
    logger.run()
