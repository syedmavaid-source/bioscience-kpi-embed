import datetime
import json
import os

from render_common import STYLE_BLOCK, write_page, build_overview_conclusion

CHANNEL_ORDER = ["email", "social", "website", "academy", "portal"]


def main():
    data_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "data")
    snapshots = {}
    for cid in CHANNEL_ORDER:
        path = os.path.join(data_dir, f"{cid}.json")
        if os.path.exists(path):
            with open(path) as f:
                snapshots[cid] = json.load(f)

    scored = [s for s in snapshots.values() if s["status_cls"] != "x"]
    overall = None
    if scored:
        vals = [float(s["health_disp"].replace("%", "").strip()) for s in scored]
        overall = sum(vals) / len(vals)
    overall_disp = f"{round(overall):.0f} %" if overall is not None else "Not scored"
    overall_status = "ON TRACK" if overall is not None and overall >= 85 else \
        "BUILDING" if overall is not None and overall >= 65 else \
        "OFF TRACK" if overall is not None else "BASELINE"
    overall_cls = "g" if overall_status == "ON TRACK" else "a" if overall_status == "BUILDING" else \
        "r" if overall_status == "OFF TRACK" else "x"
    overall_color = {"g": "var(--green)", "a": "var(--amber)", "r": "var(--red)", "x": "var(--grey)"}[overall_cls]

    tiles = []
    for cid in CHANNEL_ORDER:
        s = snapshots.get(cid)
        if not s:
            continue
        color = {"g": "var(--green)", "a": "var(--amber)", "r": "var(--red)", "x": "var(--grey)"}[s["status_cls"]]
        tiles.append(f"""    <a href="{s['page']}" class="tile" style="border-left-color:{color};">
      <div class="name">{s['name']}</div>
      <div class="score">{s['health_disp']}</div>
      <span class="pill {s['status_cls']}">{s['status_txt']}</span>
      <div class="drill">open channel &rsaquo;</div>
    </a>""")

    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    month_label = next(iter(snapshots.values()))["month_label"] if snapshots else ""
    overview_conclusion = build_overview_conclusion(list(snapshots.values()))

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>BioScience &middot; Digital KPI Dashboard &mdash; Live</title>
{STYLE_BLOCK}
<style>
.tilegrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;}}
.tile{{background:var(--card);border-radius:10px;padding:14px;box-shadow:0 1px 3px rgba(18,53,79,.09);
  border-left:4px solid var(--grey);text-decoration:none;display:block;transition:transform .1s,box-shadow .1s;}}
.tile:hover{{transform:translateY(-2px);box-shadow:0 5px 14px rgba(18,53,79,.16);}}
.tile .name{{font-size:13px;font-weight:700;color:var(--navy);}}
.tile .score{{font-size:28px;font-weight:800;color:var(--navy);margin:4px 0;font-variant-numeric:tabular-nums;}}
.tile .drill{{font-size:10px;color:var(--blue);font-weight:700;margin-top:8px;}}
</style>
</head><body>

<div class="wrap">
  <h2 class="sec">BioScience &middot; Digital KPI Dashboard<span class="sub">{month_label} &mdash; <span class="livechip"><span class="livedot"></span>Live, refreshed every 20 min</span></span></h2>

  <div class="grid g2" style="margin-top:16px;">
    <div class="card" style="background:var(--navy);color:#fff;border-left:5px solid {overall_color};">
      <div class="lab" style="color:#8fd8f0;">Overall digital health</div>
      <div class="val" style="color:#fff;">{overall_disp}</div>
      <span class="pill {overall_cls}">{overall_status}</span>
    </div>
    <div class="card">
      <div class="lab">The conclusion</div>
      <div class="con" style="margin-top:6px;">{overview_conclusion}</div>
    </div>
  </div>

  <div class="seclabel">5 channels &mdash; click to open</div>
  <div class="tilegrid">
{chr(10).join(tiles)}
  </div>

  <div class="foot">Live from Zoho Analytics, computed the same way each channel's own page shows &mdash; Channel Health = &Sigma;(weight &times; achievement) &divide; &Sigma;(weight), scored only once weight coverage reaches 50 of 100. Regenerated {generated_at}.</div>
</div>
</body></html>
"""
    path = write_page(html, "index.html")
    print(f"Wrote {path} — overall {overall_disp} ({overall_status})")


if __name__ == "__main__":
    main()
