# setup_vinnulogg.ps1
# Keyrdu: powershell -ExecutionPolicy Bypass -File setup_vinnulogg.ps1

$folder = "$env:USERPROFILE\vinnulogg"
New-Item -ItemType Directory -Force -Path $folder | Out-Null
Write-Host "Mappa buinn til: $folder" -ForegroundColor Green

# --- activity_logger.py ---
$py = @'
"""
Vinnulogg - Windows 11 Activity Logger
Fylgist med forritum sem eru opin og myndar Mermaid flowchart a 10 min fresti.
Notkun: python activity_logger.py
"""

import time
import json
import os
import webbrowser
from datetime import datetime
from collections import defaultdict

try:
    import win32gui
    import win32process
    import psutil
except ImportError:
    print("VILLA: Vantar pakka. Keyrdu fyrst: install.bat")
    input("Ytttu a Enter til ad loka...")
    raise SystemExit(1)

SAMPLE_INTERVAL_SEC = 5
UPDATE_INTERVAL_SEC = 600
MIN_ACTIVITY_SEC = 30
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

    def get_active_window_info(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return "Desktop", "Desktop"
            title = win32gui.GetWindowText(hwnd) or "Othekkt"
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                proc = psutil.Process(pid)
                app_name = proc.name().replace(".exe", "")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                app_name = "Othekkt"
            return app_name, title
        except Exception:
            return "Othekkt", "Othekkt"

    def load_log(self):
        if not os.path.exists(LOG_FILE):
            return
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == str(self.log_date):
                self.activities = data.get("activities", [])
                print(f"Hladid inn {len(self.activities)} adgerdir ur {LOG_FILE}")
        except Exception as e:
            print(f"Villa vid inhladslu log: {e}")

    def save_log(self):
        data = {"date": str(self.log_date), "activities": self.activities}
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def record_activity(self, app_name, title, timestamp):
        if app_name != self.current_app:
            if self.current_app is not None:
                duration = int((timestamp - self.current_start).total_seconds())
                self.activities.append({
                    "app": self.current_app,
                    "title": self.current_title,
                    "start": self.current_start.isoformat(),
                    "end": timestamp.isoformat(),
                    "duration": duration,
                })
            self.current_app = app_name
            self.current_title = title
            self.current_start = timestamp
        else:
            self.current_title = title

    def _merge_activities(self):
        all_acts = list(self.activities)
        if self.current_app is not None:
            now = datetime.now()
            all_acts.append({
                "app": self.current_app,
                "title": self.current_title,
                "start": self.current_start.isoformat(),
                "end": now.isoformat(),
                "duration": int((now - self.current_start).total_seconds()),
            })
        merged = []
        for act in all_acts:
            if merged and merged[-1]["app"] == act["app"]:
                merged[-1]["end"] = act["end"]
                merged[-1]["duration"] += act["duration"]
            else:
                merged.append(dict(act))
        return [a for a in merged if a["duration"] >= MIN_ACTIVITY_SEC]

    @staticmethod
    def _fmt(s):
        h = s // 3600
        m = (s % 3600) // 60
        sec = s % 60
        if h > 0:
            return f"{h} klst {m} min"
        if m > 0:
            return f"{m} min {sec} sek"
        return f"{sec} sek"

    @staticmethod
    def _safe(t):
        return t.replace('"', "'").replace("\n", " ")[:40]

    def generate_mermaid(self):
        merged = self._merge_activities()
        if not merged:
            return "flowchart TD\n    A([Engar adgerdir skradar enn])"
        lines = ["flowchart TD"]
        t0 = datetime.fromisoformat(merged[0]["start"]).strftime("%H:%M")
        lines.append(f'    START(["Dagurinn byrjar {t0}"])')
        prev = "START"
        for i, a in enumerate(merged):
            nid = f"N{i}"
            app = self._safe(a["app"])
            ts = datetime.fromisoformat(a["start"]).strftime("%H:%M")
            te = datetime.fromisoformat(a["end"]).strftime("%H:%M")
            dur = self._fmt(a["duration"])
            lines.append(f'    {nid}["{app}\\n{ts} - {te}\\n{dur}"]')
            lines.append(f"    {prev} --> {nid}")
            prev = nid
        now_str = datetime.now().strftime("%H:%M:%S")
        lines.append(f'    END(["Sidast uppfaert {now_str}"])')
        lines.append(f"    {prev} --> END")
        return "\n".join(lines)

    def generate_html(self, mermaid_code):
        date_str = datetime.now().strftime("%d.%m.%Y")
        time_str = datetime.now().strftime("%H:%M:%S")
        merged = self._merge_activities()
        total_sec = sum(a["duration"] for a in merged)
        th = total_sec // 3600
        tm = (total_sec % 3600) // 60
        app_times = defaultdict(int)
        for a in merged:
            app_times[a["app"]] += a["duration"]
        top = sorted(app_times.items(), key=lambda x: x[1], reverse=True)[:8]
        rows = "".join(f"<tr><td>{app}</td><td>{self._fmt(t)}</td></tr>" for app, t in top)
        colors = ["#89b4fa","#a6e3a1","#fab387","#f38ba8","#cba6f7","#94e2d5","#f9e2af","#89dceb"]
        bars = ""
        if total_sec > 0:
            for idx, (app, t) in enumerate(top):
                pct = round(t / total_sec * 100, 1)
                bars += f'<div class="bi" style="width:{pct}%;background:{colors[idx%8]}" title="{app}: {pct}%"></div>'
        return f"""<!DOCTYPE html>
<html lang="is"><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="{UPDATE_INTERVAL_SEC}">
<title>Vinnulogg {date_str}</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#1e1e2e;color:#cdd6f4;padding:24px}}
h1{{color:#89b4fa;margin-bottom:4px;font-size:1.8rem}}
h2{{color:#cba6f7;margin-bottom:14px;font-size:1.1rem}}
.sub{{color:#6c7086;font-size:.9rem;margin-bottom:24px}}
.stats{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px}}
.card{{background:#313244;border-radius:12px;padding:16px 24px;min-width:140px;border-left:4px solid #89b4fa}}
.card h3{{color:#a6e3a1;font-size:.75rem;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}}
.card p{{font-size:1.6rem;font-weight:700}}
.sec{{background:#313244;border-radius:12px;padding:20px;margin-bottom:20px}}
.mermaid{{background:#fff;border-radius:8px;padding:16px;overflow-x:auto}}
table{{width:100%;border-collapse:collapse}}
th,td{{text-align:left;padding:10px 16px;border-bottom:1px solid #45475a}}
th{{color:#89b4fa;font-size:.8rem;text-transform:uppercase}}
tr:last-child td{{border-bottom:none}}
.bar{{display:flex;height:28px;border-radius:6px;overflow:hidden;margin-bottom:8px;gap:2px}}
.bi{{height:100%}}
.foot{{color:#585b70;font-size:.8rem;margin-top:16px}}
</style></head><body>
<h1>Vinnulogg</h1>
<p class="sub">{date_str} &mdash; Uppfaerist a {UPDATE_INTERVAL_SEC//60} min fresti</p>
<div class="stats">
<div class="card"><h3>Heildartimi</h3><p>{th}:{tm:02d} klst</p></div>
<div class="card"><h3>Forrit notud</h3><p>{len(app_times)}</p></div>
<div class="card"><h3>Adgerdir</h3><p>{len(merged)}</p></div>
</div>
<div class="sec"><h2>Notkun forrits</h2>
<div class="bar">{bars}</div>
<table><tr><th>Forrit</th><th>Timi</th></tr>{rows}</table></div>
<div class="sec"><h2>Flaedirit yfir daginn</h2>
<div class="mermaid">{mermaid_code}</div></div>
<p class="foot">Sidast uppfaert: {time_str}</p>
<script>mermaid.initialize({{startOnLoad:true,theme:'default'}});</script>
</body></html>"""

    def update_output(self):
        mc = self.generate_mermaid()
        with open(MERMAID_FILE, "w", encoding="utf-8") as f:
            f.write(mc)
        with open(HTML_FILE, "w", encoding="utf-8") as f:
            f.write(self.generate_html(mc))
        self.save_log()
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Uppfaert -> {HTML_FILE}")

    def run(self):
        print("=" * 50)
        print("  Vinnulogg - Windows 11 Activity Logger")
        print(f"  {datetime.now().strftime('%d.%m.%Y')}")
        print(f"  HTML: {os.path.abspath(HTML_FILE)}")
        print("  Ctrl+C til ad haetta")
        print("=" * 50)
        last_update = time.time() - UPDATE_INTERVAL_SEC
        browser_opened = False
        try:
            while True:
                now = datetime.now()
                if now.date() != self.log_date:
                    self.update_output()
                    self.activities = []
                    self.current_app = None
                    self.log_date = now.date()
                app_name, title = self.get_active_window_info()
                self.record_activity(app_name, title, now)
                if time.time() - last_update >= UPDATE_INTERVAL_SEC:
                    self.update_output()
                    last_update = time.time()
                    if not browser_opened:
                        try:
                            webbrowser.open("file:///" + os.path.abspath(HTML_FILE).replace("\\", "/"))
                        except Exception:
                            pass
                        browser_opened = True
                time.sleep(SAMPLE_INTERVAL_SEC)
        except KeyboardInterrupt:
            print("\nHaett. Vista log...")
            if self.current_app:
                now = datetime.now()
                self.activities.append({
                    "app": self.current_app,
                    "title": self.current_title,
                    "start": self.current_start.isoformat(),
                    "end": now.isoformat(),
                    "duration": int((now - self.current_start).total_seconds()),
                })
            self.update_output()
            print(f"Vistad. Bless!")


if __name__ == "__main__":
    logger = ActivityLogger()
    logger.run()
'@

# --- install.bat ---
$install = @'
@echo off
chcp 65001 >nul
echo Uppsetning Vinnulogg...
python -m pip install --upgrade pip --quiet
python -m pip install pywin32 psutil
echo.
echo Uppsetning lokid! Keyrdu run.bat
pause
'@

# --- run.bat ---
$run = @'
@echo off
chcp 65001 >nul
cd /d "%~dp0"
python activity_logger.py
pause
'@

# --- run_hidden.vbs ---
$vbs = @'
Dim WshShell
Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "pythonw activity_logger.py", 0, False
'@

# Vista skrarnar
Set-Content "$folder\activity_logger.py" $py -Encoding UTF8
Set-Content "$folder\install.bat"        $install -Encoding UTF8
Set-Content "$folder\run.bat"            $run -Encoding UTF8
Set-Content "$folder\run_hidden.vbs"     $vbs -Encoding UTF8

Write-Host ""
Write-Host "Allar skrar vistadar i: $folder" -ForegroundColor Cyan
Write-Host ""
Write-Host "Naesta skref:" -ForegroundColor Yellow
Write-Host "  1. cd $folder"
Write-Host "  2. install.bat"
Write-Host "  3. run.bat"
Write-Host ""
explorer $folder
