import datetime
import json
import os

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]


def num(s):
    return float(str(s).replace(",", ""))


def status_for(h):
    if h is None:
        return ("BASELINE", "x")
    if h >= 85:
        return ("ON TRACK", "g")
    if h >= 65:
        return ("BUILDING", "a")
    return ("OFF TRACK", "r")


def bar_html(achievement, benchmark_pct):
    col = "var(--green)" if achievement >= 85 else "var(--amber)" if achievement >= 65 else "var(--red)"
    marker = ""
    if benchmark_pct is not None:
        p = max(0, min(benchmark_pct, 100))
        marker = f'<span class="bnk" style="left:{p:.0f}%"></span>'
    return (f'<span class="bar"><i style="width:{min(achievement,100):.0f}%;background:{col}"></i>{marker}</span> '
            f'<b style="color:var(--navy)">{round(achievement):.0f} %</b>')


def kpi_row(k, display_name, month_precision=1, unit_suffix=" %", target_suffix=None):
    """unit_suffix is appended to the displayed actual value (e.g. " %", "", " / month").
    target_suffix defaults to unit_suffix if not given separately."""
    if target_suffix is None:
        target_suffix = unit_suffix
    actual = num(k["Actual Value"])
    target = num(k["Target"])
    weight = int(num(k["Weight"]))
    direction = k["Direction"]
    achievement = min(actual / target * 100, 100) if direction == "hi" else min(target / actual * 100, 100)
    bench_val = num(k["Benchmark Value"]) if k["Benchmark Value"] not in ("", None) else None
    bench_pct = None
    if bench_val is not None:
        bench_pct = (bench_val / target * 100) if direction == "hi" else (target / bench_val * 100)
    status_txt = "STRONG" if achievement >= 85 else "OK" if achievement >= 65 else "GAP"
    status_cls = "g" if achievement >= 85 else "a" if achievement >= 65 else "r"
    lo_prefix = "< " if direction == "lo" else ""
    target_disp = f"{lo_prefix}{target:g}{target_suffix}"
    row_html = f"""    <tr>
      <td>{display_name}</td>
      <td><b>{actual:.{month_precision}f}{unit_suffix}</b></td>
      <td>{target_disp}</td>
      <td class="small">{k['Benchmark']}</td>
      <td>{bar_html(achievement, bench_pct)}</td>
      <td>{weight}</td>
      <td><span class="pill {status_cls}">{status_txt}</span></td>
    </tr>"""
    return row_html, weight, achievement, bench_val


def context_row(label, value):
    return f"""    <tr class="excl">
      <td>{label}</td>
      <td><b>{value:.1f} %</b></td>
      <td>&mdash;</td>
      <td class="small">context only</td>
      <td><span class="small">excluded from score</span></td>
      <td>&mdash;</td>
      <td><span class="pill x">CONTEXT</span></td>
    </tr>"""


def brand_card(brand_name, lines):
    body = "<br>".join(lines)
    return f"""    <div class="card"><div class="lab">{brand_name}</div><div class="con" style="margin-top:4px;">{body}</div></div>"""


def _kpi_lost_points(k):
    """Points lost out of this KPI's own weight, i.e. weight * (1 - achievement/100), capped at 0.
    This is the exact quantity the calc box's Sigma(weight*achievement) is short by — ranking on
    this (rather than raw achievement %) surfaces whichever KPI is actually dragging the score down
    the most, not just whichever happens to have the lowest percentage."""
    return k["weight"] * max(0, 100 - min(k["achievement_pct"], 100)) / 100


def _kpi_phrase(k):
    unit = k.get("unit", "%")
    actual_disp = f"{k['actual']:g}" if unit == "" else f"{k['actual']:.2f}" if k["direction"] == "lo" else f"{k['actual']:.1f}"
    if k["direction"] == "lo":
        return f"{k['name']} sits at {actual_disp}{unit} against a target under {k['target']:g}{unit}"
    return f"{k['name']} is at {actual_disp}{unit} against a {k['target']:g}{unit} target"


def _benchmark_clause(k):
    """If a numeric benchmark exists, say whether the actual sits above or below it, and by how much."""
    bench = k.get("benchmark_value")
    if bench is None:
        return ""
    unit = k.get("unit", "%")
    actual = k["actual"]
    if k["direction"] == "lo":
        gap = bench - actual
        verb = "under" if gap > 0 else "over"
    else:
        gap = actual - bench
        verb = "above" if gap > 0 else "below"
    return f" &mdash; {abs(gap):.1f}{unit} {verb} the {bench:g}{unit} industry benchmark"


def build_smart_conclusion(kpis, extra_sentence=""):
    """Deterministic, no-LLM narrative. Ranks KPIs by weighted points lost (weight x gap-to-target),
    the same quantity the calc box's math is driven by, so the KPI called out here is always the one
    that would move the channel health score the most if fixed — not just whichever has the lowest
    raw achievement percentage."""
    ranked = sorted(kpis, key=_kpi_lost_points, reverse=True)
    worst, best = ranked[0], ranked[-1]
    weight_total = sum(k["weight"] for k in kpis)
    worst_lost = _kpi_lost_points(worst)

    lead = (
        f"<b>{_kpi_phrase(worst)}</b>{_benchmark_clause(worst)} &mdash; the single biggest drag on the score: "
        f"{worst['weight']} of {weight_total} weighted points at only {round(worst['achievement_pct'])}% of "
        f"target costs {worst_lost:.1f} points this month."
    )
    if best["name"] != worst["name"] and best is not worst:
        contrast = f" {best['name']} is comfortably ahead at {round(best['achievement_pct'])}% of target."
    else:
        contrast = ""
    return f"{lead}{contrast}{extra_sentence}"


def compute_health(kpis_for_health):
    """kpis_for_health: list of {'weight', 'achievement_pct'}. Returns (health_or_None, status_txt,
    status_cls, weighted_sum, weight_total)."""
    weighted_sum = sum(k["weight"] * k["achievement_pct"] for k in kpis_for_health)
    weight_total = sum(k["weight"] for k in kpis_for_health)
    health = weighted_sum / weight_total if weight_total >= 50 else None
    status_txt, status_cls = status_for(health)
    return health, status_txt, status_cls, weighted_sum, weight_total


def render_sparkline(months_asc, width=170, height=34):
    """months_asc: [(label, health_value_or_None), ...] in chronological (oldest-first) order."""
    pts = [(i, v) for i, (_, v) in enumerate(months_asc) if v is not None]
    if len(pts) < 2:
        return ""
    vals = [v for _, v in pts]
    lo, hi = min(vals), max(vals)
    span = max(hi - lo, 1)
    pad = 4
    n = len(months_asc)
    step = (width - 2 * pad) / max(n - 1, 1)
    coords = []
    for i, v in pts:
        x = pad + i * step
        y = height - pad - (v - lo) / span * (height - 2 * pad)
        coords.append((x, y))
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    last_x, last_y = coords[-1]
    last_val = pts[-1][1]
    dot_color = "var(--green)" if last_val >= 85 else "var(--amber)" if last_val >= 65 else "var(--red)"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'style="display:block;margin-top:8px;" role="img" aria-label="Channel health trend">'
        f'<polyline points="{poly}" fill="none" stroke="var(--blue)" stroke-width="1.5" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3" fill="{dot_color}"/>'
        f"</svg>"
    )


def build_monthly_snapshots(eval_rows, kpi_specs, order, constant_rows=None):
    """Turn an "All Months" evaluation view's raw rows into a per-month dataset for the month
    picker + trend. eval_rows: rows with KPI/Actual Value/Target/Weight/Direction/Benchmark/
    Benchmark Value/Year/Month. kpi_specs: {kpi_key: {"display_name", "unit_suffix", "target_suffix",
    "month_precision", "narrative_unit"}}. order: display order of kpi_keys. constant_rows: KPI rows
    with no month dimension (e.g. an all-time cumulative metric) applied identically to every month.

    Returns (snapshots: {"YYYY-MM": {...}}, months_desc: ["YYYY-MM", ...] latest first).
    """
    by_month = {}
    for r in eval_rows:
        y_raw, m_raw = r.get("Year"), r.get("Month")
        if not y_raw or not m_raw:
            continue
        try:
            y, m = int(str(y_raw).replace(",", "")), int(m_raw)
        except ValueError:
            continue
        by_month.setdefault(f"{y:04d}-{m:02d}", {})[r["KPI"]] = r

    if constant_rows:
        for key in by_month:
            for r in constant_rows:
                by_month[key].setdefault(r["KPI"], r)

    months_desc = sorted(by_month.keys(), reverse=True)
    snapshots = {}
    for key in months_desc:
        _, m = key.split("-")
        month_label = f"{MONTH_NAMES[int(m)]} {key[:4]}"
        rows_html, calc_parts, narrative_kpis, kpis_for_health = [], [], [], []
        for kpi_key in order:
            r = by_month[key].get(kpi_key)
            if r is None:
                continue
            spec = kpi_specs[kpi_key]
            row_html, weight, achievement, bench_val = kpi_row(
                r, spec["display_name"],
                month_precision=spec.get("month_precision", 1),
                unit_suffix=spec.get("unit_suffix", " %"),
                target_suffix=spec.get("target_suffix"),
            )
            rows_html.append(row_html)
            contribution = weight * achievement / 100
            calc_parts.append(f"{spec['display_name']} {weight} &times; {round(achievement):.0f}% = {contribution:.1f}")
            narrative_kpis.append({
                "name": spec["display_name"],
                "actual": round(num(r["Actual Value"]), 2),
                "target": num(r["Target"]),
                "benchmark_value": bench_val,
                "achievement_pct": round(achievement, 1),
                "weight": weight,
                "direction": r["Direction"],
                "unit": spec.get("narrative_unit", "%"),
            })
            kpis_for_health.append({"weight": weight, "achievement_pct": achievement})
        if not narrative_kpis:
            continue
        health, status_txt, status_cls, weighted_sum, weight_total = compute_health(kpis_for_health)
        health_disp = f"{round(health):.0f} %" if health is not None else "Not scored"
        snapshots[key] = {
            "month_label": month_label,
            "rows_html": "\n".join(rows_html),
            "calc_inner_html": (
                f"{'&nbsp; | &nbsp;'.join(calc_parts)}<br>"
                f'<span class="res">&rarr; {weighted_sum/100:.1f} &divide; {weight_total} = {health_disp}</span>'
                f'<span class="cov">Weight coverage: <b style="color:inherit">{weight_total} of 100</b> '
                f"measurable (scored only when &ge; 50).</span>"
            ),
            "health_disp": health_disp,
            "status_txt": status_txt,
            "status_cls": status_cls,
            "status_color": {"g": "var(--green)", "a": "var(--amber)", "r": "var(--red)", "x": "var(--grey)"}[status_cls],
            "conclusion": build_smart_conclusion(narrative_kpis),
            "health_value": health,
            "narrative_kpis": narrative_kpis,
        }
    return snapshots, months_desc


def js_payload(snapshots, latest_key):
    """Strip server-only fields (narrative_kpis, health_value) before embedding as page JSON."""
    months = {
        k: {kk: vv for kk, vv in v.items() if kk not in ("narrative_kpis", "health_value")}
        for k, v in snapshots.items()
    }
    return {"months": months, "latest": latest_key}


def build_overview_conclusion(channel_snapshots):
    """Deterministic cross-channel synthesis for the index page — same weighted-drag logic, applied
    to channel health scores instead of individual KPIs."""
    scored = [s for s in channel_snapshots if s["status_cls"] != "x"]
    if not scored:
        return "No channels are scored yet this month."
    ranked = sorted(scored, key=lambda s: float(s["health_disp"].replace("%", "").strip()))
    worst, best = ranked[0], ranked[-1]
    counts = {"g": 0, "a": 0, "r": 0}
    for s in scored:
        counts[s["status_cls"]] = counts.get(s["status_cls"], 0) + 1
    status_bits = []
    if counts.get("r"):
        status_bits.append(f"{counts['r']} OFF TRACK")
    if counts.get("a"):
        status_bits.append(f"{counts['a']} BUILDING")
    if counts.get("g"):
        status_bits.append(f"{counts['g']} ON TRACK")
    lead = f"<b>{worst['name']} is the weakest link this month at {worst['health_disp']}</b> ({worst['status_txt']})."
    if best["name"] != worst["name"]:
        contrast = f" {best['name']} leads at {best['health_disp']} ({best['status_txt']})."
    else:
        contrast = ""
    tail = f" Of {len(scored)} scored channels: {', '.join(status_bits)}."
    return f"{lead}{contrast}{tail}"


STYLE_BLOCK = """<style>
:root{
  --blue:#1C8CBE; --navy:#12354F; --deep:#0d2740; --teal:#2FA9BE; --gold:#B8862F;
  --ink:#1f2b30; --mute:#6b7c85; --green:#2f9e5f; --amber:#E08A1E; --red:#D64531;
  --grey:#9aa6ad; --line:#dde7e9; --card:#ffffff; --bg:#eef3f4;
  --calc-bg:#12354F; --calc-fg:#ffffff; --calc-accent:#8fd8f0; --calc-res:#e7c589;
}
:root[data-theme="dark"]{
  --ink:#e7edf0; --mute:#93a5ad; --card:#152634; --bg:#0b1720; --line:#233544;
  --navy:#1a5a86; --navy-fg:#eaf6fb; --blue:#3ea8d6; --gold:#d6ac6a;
  --calc-bg:#0a1c2a; --calc-fg:#dfe9ee; --calc-accent:#7fc9e6; --calc-res:#e7c589;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ink:#e7edf0; --mute:#93a5ad; --card:#152634; --bg:#0b1720; --line:#233544;
    --navy:#1a5a86; --navy-fg:#eaf6fb; --blue:#3ea8d6; --gold:#d6ac6a;
    --calc-bg:#0a1c2a; --calc-fg:#dfe9ee; --calc-accent:#7fc9e6; --calc-res:#e7c589;
  }
}
*{box-sizing:border-box;margin:0;padding:0;font-family:'Helvetica Neue',Arial,sans-serif;}
body{background:var(--bg);color:var(--ink);}
.wrap{max-width:1120px;margin:0 auto;padding:22px 20px 40px;}
.crumb{font-size:12px;color:var(--mute);margin-bottom:2px;}
.crumb b{color:var(--navy);font-weight:700;}
.crumb a{color:var(--blue);text-decoration:none;font-weight:600;}
h2.sec{font-size:20px;color:var(--navy);font-weight:800;margin:6px 0 2px;}
h2.sec .sub{font-size:12.5px;color:var(--mute);font-weight:500;display:block;margin-top:3px;}
.seclabel{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gold);font-weight:700;margin:20px 0 8px;}
.grid{display:grid;gap:12px;}
.g2{grid-template-columns:2fr 3fr;}
.g3{grid-template-columns:repeat(3,1fr);}
.card{background:var(--card);border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(18,53,79,.09);}
.card .lab{font-size:11px;color:var(--mute);font-weight:700;text-transform:uppercase;letter-spacing:.3px;}
.card .val{font-size:28px;font-weight:800;color:var(--navy);margin:4px 0 2px;font-variant-numeric:tabular-nums;}
.card .con{font-size:12px;color:var(--ink);line-height:1.5;}
.pill{display:inline-block;font-size:9.5px;font-weight:700;border-radius:20px;padding:2px 10px;color:#fff;letter-spacing:.3px;}
.g{background:var(--green);} .a{background:var(--amber);} .r{background:var(--red);} .x{background:var(--grey);}
.tw{overflow-x:auto;}
table{width:100%;border-collapse:separate;border-spacing:0 7px;min-width:720px;}
th{font-size:9.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--mute);text-align:left;padding:0 12px;font-weight:700;}
td{background:var(--card);padding:11px 12px;font-size:12.5px;vertical-align:middle;}
tr td:first-child{border-radius:8px 0 0 8px;font-weight:700;color:var(--navy);}
tr td:last-child{border-radius:0 8px 8px 0;}
tr.excl td{background:color-mix(in srgb, var(--card) 88%, var(--mute));color:var(--mute);}
tr.excl td:first-child{color:var(--mute);font-weight:600;}
.bar{height:8px;background:var(--line);border-radius:5px;position:relative;width:150px;display:inline-block;vertical-align:middle;}
.bar i{position:absolute;left:0;top:0;height:8px;border-radius:5px;}
.bnk{position:absolute;top:-3px;width:2px;height:14px;background:var(--navy);}
.small{font-size:10px;color:var(--mute);}
.legend{display:flex;gap:20px;flex-wrap:wrap;font-size:10.5px;color:var(--mute);align-items:center;margin:11px 0 0;}
.calc{margin-top:14px;background:var(--calc-bg);color:var(--calc-fg);border-radius:8px;padding:14px 16px;font-size:11.5px;font-family:'SF Mono','Courier New',monospace;line-height:1.8;}
.calc b{color:var(--calc-accent);}
.calc .res{color:var(--calc-res);font-weight:700;}
.calc .cov{color:var(--calc-accent);opacity:.85;font-size:10.5px;display:block;margin-top:6px;}
.warnbox{margin-top:14px;background:color-mix(in srgb, var(--gold) 12%, var(--card));border-left:4px solid var(--gold);border-radius:0 8px 8px 0;padding:12px 15px;font-size:12px;line-height:1.55;}
.foot{font-size:10.5px;color:var(--mute);margin-top:24px;border-top:1px solid var(--line);padding-top:10px;line-height:1.6;}
.livechip{display:inline-flex;align-items:center;gap:5px;font-size:9.5px;font-weight:700;color:var(--green);letter-spacing:.3px;text-transform:uppercase;}
.livedot{width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 0 2px color-mix(in srgb, var(--green) 25%, transparent);}
.monthpick{font-size:11px;font-weight:600;color:var(--navy);background:var(--card);border:1px solid var(--line);border-radius:6px;padding:4px 8px;margin-left:8px;}
</style>"""


def render_page(*, title, channel_name, month_label, health_disp, status_txt, status_cls,
                 conclusion, kpi_table_header_cols, rows_html, calc_inner_html,
                 data_note, foot_note, brand_section_html="", legend_extra="",
                 month_options=None, latest_key=None, monthly_data=None, trend_svg=""):
    """rows_html/calc_inner_html are pre-built HTML strings (e.g. straight from a
    build_monthly_snapshots() snapshot) so the initial render can never drift from the JS payload
    used when switching months. month_options: [(key, label), ...] latest-first, for the picker
    dropdown. monthly_data: {"months": {key: snapshot}, "latest": key}. Omit month_options/
    monthly_data for a single-month page with no picker."""
    status_color = {"g": "var(--green)", "a": "var(--amber)", "r": "var(--red)", "x": "var(--grey)"}[status_cls]
    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    picker_html = ""
    script_html = ""
    if month_options and monthly_data:
        opts = "\n".join(
            f'<option value="{k}"{" selected" if k == latest_key else ""}>{lbl}</option>'
            for k, lbl in month_options
        )
        picker_html = f'<select class="monthpick" id="monthPicker" onchange="switchMonth(this.value)">\n{opts}\n</select>'
        script_html = f"""
<script>
const MONTHLY = {json.dumps(monthly_data)};
function switchMonth(key) {{
  const d = MONTHLY.months[key];
  if (!d) return;
  document.getElementById('healthVal').textContent = d.health_disp;
  const pill = document.getElementById('healthPill');
  pill.textContent = d.status_txt;
  pill.className = 'pill ' + d.status_cls;
  document.getElementById('healthCard').style.borderLeftColor = d.status_color;
  document.getElementById('conclusionText').innerHTML = d.conclusion;
  document.getElementById('kpiRows').innerHTML = d.rows_html;
  document.getElementById('calcInner').innerHTML = d.calc_inner_html;
  document.getElementById('liveLabel').innerHTML =
    (key === MONTHLY.latest
      ? '<span class="livedot"></span>Live &mdash; ' + d.month_label + ' actuals'
      : d.month_label + ' actuals (historical)');
}}
</script>"""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>BioScience &middot; {title} &mdash; Live</title>
{STYLE_BLOCK}</head><body>

<div class="wrap">
  <div class="crumb"><a href="index.html">Overview</a> &rsaquo; <b>{channel_name}</b></div>
  <h2 class="sec">Level 2 &middot; {channel_name}<span class="sub">What exactly is off? &middot; <span class="livechip" id="liveLabel"><span class="livedot"></span>Live &mdash; {month_label} actuals</span>{picker_html}</span></h2>

  <div class="grid g2" style="margin-top:12px;">
    <div class="card" style="border-left:5px solid {status_color};" id="healthCard">
      <div class="lab">Channel health</div>
      <div class="val" id="healthVal">{health_disp}</div>
      <span class="pill {status_cls}" id="healthPill">{status_txt}</span>
      {trend_svg}
    </div>
    <div class="card">
      <div class="lab">The conclusion</div>
      <div class="con" style="margin-top:6px;" id="conclusionText">{conclusion}</div>
    </div>
  </div>

{brand_section_html}
  <div class="seclabel">The KPIs &mdash; vs. target vs. verified benchmark</div>
  <div class="tw"><table>
    <thead><tr>{kpi_table_header_cols}</tr></thead>
    <tbody id="kpiRows">
{rows_html}
    </tbody>
  </table></div>
  <div class="legend">
    <span>&#9612; bar = achievement of target (capped 100%)</span>
    <span>&#9474; marker = market benchmark</span>
    <span>grey row = visible but excluded from the score</span>{legend_extra}
  </div>

  <div class="seclabel">The score, opened up &mdash; no black box</div>
  <div class="calc" id="calcBox">
    <b>Channel Health = &Sigma;(weight &times; achievement) &divide; &Sigma;(weight)</b><br>
    <span id="calcInner">
    {calc_inner_html}
    </span>
  </div>

  <div class="warnbox"><b>Data note.</b> {data_note}</div>

  <div class="foot">{foot_note} Regenerated {generated_at}.</div>
</div>
{script_html}
</body></html>
"""


def write_page(html, filename):
    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w") as f:
        f.write(html)
    return path


def write_snapshot(channel_id, data):
    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "data")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{channel_id}.json")
    with open(path, "w") as f:
        json.dump(data, f)
    return path
