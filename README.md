# Vinnulogg - Windows 11 Activity Logger

Forrit sem fylgist með því sem þú gerir í tölvunni yfir daginn og myndar sjálfvirkt **Mermaid flowchart** sem uppfærist á 10 mínútna fresti.

---

## Hvað gerir þetta forrit?

- **Fylgist** með hvaða forrit eru virk (active window) á 5 sek fresti
- **Skráir** allt í `vinnulogg.json` svo ekkert glatist
- **Myndar Mermaid flowchart** sem sýnir flæði dagsins
- **Uppfærir** `flowchart.html` og `flowchart.mmd` á 10 mín fresti
- **Opnar HTML** sjálfkrafa í vafra í fyrsta skipti
- **Hreinsar** log við miðnætti og byrjar upp á nýtt

---

## Uppsetning

### Kröfur
- Windows 10/11
- Python 3.9+ ([python.org](https://python.org))

### Skref 1 – Setja upp pakka
Tvísmelltu á `install.bat` (eða keyrðu í terminal):
```
install.bat
```

### Skref 2 – Ræsa logger
```
run.bat
```

Til að keyra **án terminal glugga** (í bakgrunni):
```
Tvísmelltu á run_hidden.vbs
```

---

## Skrár

| Skrá | Lýsing |
|---|---|
| `activity_logger.py` | Aðalforritið |
| `requirements.txt` | Python pakkar |
| `install.bat` | Uppsetningarforskrift |
| `run.bat` | Ræsir forritið með terminal |
| `run_hidden.vbs` | Ræsir í bakgrunni (án terminal) |
| `flowchart.html` | **HTML með Mermaid korti** (opna í vafra) |
| `flowchart.mmd` | Mermaid kóðinn einn og sér |
| `vinnulogg.json` | Log skráin (uppfærist stöðugt) |

---

## Flowchart dæmi

```mermaid
flowchart TD
    START(["Dagurinn byrjar 08:30"])
    N0["chrome\n08:30 - 08:45\n15 mín"]
    N1["Code\n08:45 - 10:00\n1 klst 15 mín"]
    N2["Slack\n10:00 - 10:10\n10 mín"]
    N3["Code\n10:10 - 12:00\n1 klst 50 mín"]
    END(["Sidast uppfaert 12:00:00"]
    START --> N0 --> N1 --> N2 --> N3 --> END
```

---

## Stillingar

Í `activity_logger.py` má breyta:

```python
SAMPLE_INTERVAL_SEC = 5    # Hversu oft er virkt forrit skoðað (sek)
UPDATE_INTERVAL_SEC = 600  # Hversu oft er flowchart uppfært (600 = 10 mín)
MIN_ACTIVITY_SEC = 30      # Lágmarkstími til að aðgerð birtist á korti
```

---

## Ræsa sjálfkrafa við Windows uppræsingu

1. Ýttu á `Win + R`, skrifaðu `shell:startup`, ýttu Enter
2. Settu flýtileið (shortcut) á `run_hidden.vbs` í þá möppu
3. Nú ræsist Vinnulogg sjálfkrafa við hvert innskráning
