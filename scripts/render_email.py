import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zoho_client import access_token, export_view

EVAL_VIEW_ID = "2605787000015515090"    # Email KPI Evaluation - Latest Month
MONTHLY_VIEW_ID = "2605787000015519003"  # Email KPIs Monthly

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

KPI_SHORT_NAME = {
    "CTR %": "Click-Through Rate",
    "CTOR %": "Click-to-Open Rate",
    "Open Rate %": "Open Rate",
    "Bounce Rate %": "Hard Bounce Rate",
}


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


def kpi_row(k):
    disp = KPI_SHORT_NAME[k["KPI"]]
    actual = num(k["Actual Value"])
    target = num(k["Target"])
    weight = int(num(k["Weight"]))
    achievement = num(k["Target Achievement %"])
    direction = k["Direction"]
    bench_val = num(k["Benchmark Value"]) if k["Benchmark Value"] not in ("", None) else None
    bench_pct = None
    if bench_val is not None:
        bench_pct = (bench_val / target * 100) if direction == "hi" else (target / bench_val * 100)
    status_txt = "STRONG" if achievement >= 85 else "OK" if achievement >= 65 else "GAP"
    status_cls = "g" if achievement >= 85 else "a" if achievement >= 65 else "r"
    unit = "< " if direction == "lo" else ""
    target_disp = f"{unit}{target:g} %"
    return f"""    <tr>
      <td>{disp}</td>
      <td><b>{actual:.1f} %</b></td>
      <td>{target_disp}</td>
      <td class="small">{k['Benchmark']}</td>
      <td>{bar_html(achievement, bench_pct)}</td>
      <td>{weight}</td>
      <td><span class="pill {status_cls}">{status_txt}</span></td>
    </tr>""", weight, achievement


NARRATIVE_SYSTEM_PROMPT = """You write the "conclusion" card for a live marketing-analytics dashboard tile. \
House style, matching prior editions exactly:
- 2-3 sentences, one paragraph, no line breaks.
- Lead with the single biggest problem or the single most important contrast in the numbers, using the actual figures (not vague words like "low" or "good" without a number attached).
- Wrap the one most important phrase in <b>...</b> — exactly one bolded phrase, chosen for what a reader should not miss.
- Use &mdash; (HTML entity, not a raw em dash character) for any dash.
- Plain, direct, slightly analytical tone. No emoji, no exclamation points, no hedging ("it seems", "perhaps").
- Do not restate the health score or status label — the card next to yours already shows those.
- Output ONLY the paragraph HTML fragment. No preamble, no markdown, no quotes around it."""


def generate_conclusion(month_label, kpi_rows, dist_open, dist_ctr, dist_ctor, health_disp, status_txt, fallback):
    try:
        import anthropic
    except ImportError:
        return fallback
    try:
        client = anthropic.Anthropic()
        payload = {
            "month": month_label,
            "channel_health": health_disp,
            "status": status_txt,
            "scored_kpis": kpi_rows,
            "distributor_context_unscored": {
                "open_rate_pct": round(dist_open, 1),
                "ctr_pct": round(dist_ctr, 1),
                "ctor_pct": round(dist_ctor, 1),
            },
        }
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=300,
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
            system=NARRATIVE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload, indent=2)}],
        )
        if response.stop_reason == "refusal":
            return fallback
        text = next((b.text for b in response.content if b.type == "text"), "").strip()
        return text or fallback
    except Exception as e:
        print(f"LLM narrative generation failed, using fallback: {e}")
        return fallback


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


def main():
    token = access_token()
    evals = export_view(EVAL_VIEW_ID, token)
    monthly = export_view(MONTHLY_VIEW_ID, token)

    def mkey(r):
        return (int(r["Year"].replace(",", "")), int(r["Month"]))

    monthly.sort(key=mkey)
    latest_year, latest_month = mkey(monthly[-1])
    latest_rows = [r for r in monthly if mkey(r) == (latest_year, latest_month)]
    dist = [r for r in latest_rows if r["Segment"] == "Distributor"]
    opens = sum(num(r["Unique Opens"]) for r in dist)
    clicks = sum(num(r["Unique Clicks"]) for r in dist)
    sent = sum(num(r["Emails Sent"]) for r in dist)
    dist_open = opens / sent * 100 if sent else 0
    dist_ctr = clicks / sent * 100 if sent else 0
    dist_ctor = clicks / opens * 100 if opens else 0

    rows_html = []
    weighted_sum = 0.0
    weight_total = 0
    calc_parts = []
    narrative_kpis = []
    order = ["CTR %", "CTOR %", "Open Rate %", "Bounce Rate %"]
    evals_by_kpi = {r["KPI"]: r for r in evals}
    ctr_actual = num(evals_by_kpi["CTR %"]["Actual Value"])
    ctr_bench = num(evals_by_kpi["CTR %"]["Benchmark Value"])

    for kpi_name in order:
        k = evals_by_kpi[kpi_name]
        row_html, weight, achievement = kpi_row(k)
        rows_html.append(row_html)
        weighted_sum += weight * achievement
        weight_total += weight
        contribution = weight * achievement / 100
        calc_parts.append(f"{KPI_SHORT_NAME[kpi_name]} {weight} &times; {round(achievement):.0f}% = {contribution:.1f}")
        narrative_kpis.append({
            "name": KPI_SHORT_NAME[kpi_name],
            "actual": round(num(k["Actual Value"]), 2),
            "target": num(k["Target"]),
            "benchmark": k["Benchmark"],
            "achievement_pct": round(achievement, 1),
            "weight": weight,
        })

    rows_html.append(context_row("Open Rate (Distributors)", dist_open))
    rows_html.append(context_row("Click-Through Rate (Distributors)", dist_ctr))
    rows_html.append(context_row("Click-to-Open Rate (Distributors)", dist_ctor))

    health = weighted_sum / weight_total if weight_total >= 50 else None
    status_txt, status_cls = status_for(health)
    status_color = {"g": "var(--green)", "a": "var(--amber)", "r": "var(--red)", "x": "var(--grey)"}[status_cls]
    health_disp = f"{round(health):.0f} %" if health is not None else "Not scored"

    month_label = f"{MONTH_NAMES[latest_month]} {latest_year}"
    fallback_conclusion = (
        f"Deliverability is fine &mdash; hard bounces sit above the ceiling but aren't catastrophic &mdash; "
        f"while doctor <b>clicks have all but disappeared</b> (CTR {ctr_actual:.1f}% vs a {ctr_bench:.2f}% benchmark). "
        f"Distributors, on the identical infrastructure, click through at {dist_ctr:.1f}% and open-to-click at {dist_ctor:.1f}%: "
        f"the system works, the doctor content isn't landing."
    )
    conclusion = generate_conclusion(
        month_label, narrative_kpis, dist_open, dist_ctr, dist_ctor, health_disp, status_txt, fallback_conclusion
    )

    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>BioScience · Email Channel — Live</title>
<style>
:root{{
  --blue:#1C8CBE; --navy:#12354F; --deep:#0d2740; --teal:#2FA9BE; --gold:#B8862F;
  --ink:#1f2b30; --mute:#6b7c85; --green:#2f9e5f; --amber:#E08A1E; --red:#D64531;
  --grey:#9aa6ad; --line:#dde7e9; --card:#ffffff; --bg:#eef3f4;
  --calc-bg:#12354F; --calc-fg:#ffffff; --calc-accent:#8fd8f0; --calc-res:#e7c589;
}}
:root[data-theme="dark"]{{
  --ink:#e7edf0; --mute:#93a5ad; --card:#152634; --bg:#0b1720; --line:#233544;
  --navy:#1a5a86; --navy-fg:#eaf6fb; --blue:#3ea8d6; --gold:#d6ac6a;
  --calc-bg:#0a1c2a; --calc-fg:#dfe9ee; --calc-accent:#7fc9e6; --calc-res:#e7c589;
}}
@media (prefers-color-scheme: dark){{
  :root:not([data-theme="light"]){{
    --ink:#e7edf0; --mute:#93a5ad; --card:#152634; --bg:#0b1720; --line:#233544;
    --navy:#1a5a86; --navy-fg:#eaf6fb; --blue:#3ea8d6; --gold:#d6ac6a;
    --calc-bg:#0a1c2a; --calc-fg:#dfe9ee; --calc-accent:#7fc9e6; --calc-res:#e7c589;
  }}
}}
*{{box-sizing:border-box;margin:0;padding:0;font-family:'Helvetica Neue',Arial,sans-serif;}}
body{{background:var(--bg);color:var(--ink);}}
.wrap{{max-width:1120px;margin:0 auto;padding:22px 20px 40px;}}
.crumb{{font-size:12px;color:var(--mute);margin-bottom:2px;}}
.crumb b{{color:var(--navy);font-weight:700;}}
h2.sec{{font-size:20px;color:var(--navy);font-weight:800;margin:6px 0 2px;}}
h2.sec .sub{{font-size:12.5px;color:var(--mute);font-weight:500;display:block;margin-top:3px;}}
.seclabel{{font-size:10px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gold);font-weight:700;margin:20px 0 8px;}}
.grid{{display:grid;gap:12px;}}
.g2{{grid-template-columns:2fr 3fr;}}
.card{{background:var(--card);border-radius:10px;padding:14px 16px;box-shadow:0 1px 3px rgba(18,53,79,.09);}}
.card .lab{{font-size:11px;color:var(--mute);font-weight:700;text-transform:uppercase;letter-spacing:.3px;}}
.card .val{{font-size:28px;font-weight:800;color:var(--navy);margin:4px 0 2px;font-variant-numeric:tabular-nums;}}
.card .con{{font-size:12px;color:var(--ink);line-height:1.5;}}
.pill{{display:inline-block;font-size:9.5px;font-weight:700;border-radius:20px;padding:2px 10px;color:#fff;letter-spacing:.3px;}}
.g{{background:var(--green);}} .a{{background:var(--amber);}} .r{{background:var(--red);}} .x{{background:var(--grey);}}
.tw{{overflow-x:auto;}}
table{{width:100%;border-collapse:separate;border-spacing:0 7px;min-width:720px;}}
th{{font-size:9.5px;text-transform:uppercase;letter-spacing:.5px;color:var(--mute);text-align:left;padding:0 12px;font-weight:700;}}
td{{background:var(--card);padding:11px 12px;font-size:12.5px;vertical-align:middle;}}
tr td:first-child{{border-radius:8px 0 0 8px;font-weight:700;color:var(--navy);}}
tr td:last-child{{border-radius:0 8px 8px 0;}}
tr.excl td{{background:color-mix(in srgb, var(--card) 88%, var(--mute));color:var(--mute);}}
tr.excl td:first-child{{color:var(--mute);font-weight:600;}}
.bar{{height:8px;background:var(--line);border-radius:5px;position:relative;width:150px;display:inline-block;vertical-align:middle;}}
.bar i{{position:absolute;left:0;top:0;height:8px;border-radius:5px;}}
.bnk{{position:absolute;top:-3px;width:2px;height:14px;background:var(--navy);}}
.small{{font-size:10px;color:var(--mute);}}
.legend{{display:flex;gap:20px;flex-wrap:wrap;font-size:10.5px;color:var(--mute);align-items:center;margin:11px 0 0;}}
.calc{{margin-top:14px;background:var(--calc-bg);color:var(--calc-fg);border-radius:8px;padding:14px 16px;font-size:11.5px;font-family:'SF Mono','Courier New',monospace;line-height:1.8;}}
.calc b{{color:var(--calc-accent);}}
.calc .res{{color:var(--calc-res);font-weight:700;}}
.calc .cov{{color:var(--calc-accent);opacity:.85;font-size:10.5px;display:block;margin-top:6px;}}
.warnbox{{margin-top:14px;background:color-mix(in srgb, var(--gold) 12%, var(--card));border-left:4px solid var(--gold);border-radius:0 8px 8px 0;padding:12px 15px;font-size:12px;line-height:1.55;}}
.foot{{font-size:10.5px;color:var(--mute);margin-top:24px;border-top:1px solid var(--line);padding-top:10px;line-height:1.6;}}
.livechip{{display:inline-flex;align-items:center;gap:5px;font-size:9.5px;font-weight:700;color:var(--green);letter-spacing:.3px;text-transform:uppercase;}}
.livedot{{width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 0 2px color-mix(in srgb, var(--green) 25%, transparent);}}
</style></head><body>

<div class="wrap">
  <div class="crumb"><span>Overview</span> &rsaquo; <b>Email Marketing</b></div>
  <h2 class="sec">Level 2 &middot; Email Marketing<span class="sub">What exactly is off? &middot; <span class="livechip"><span class="livedot"></span>Live &mdash; {month_label} actuals</span></span></h2>

  <div class="grid g2" style="margin-top:12px;">
    <div class="card" style="border-left:5px solid {status_color};">
      <div class="lab">Channel health</div>
      <div class="val">{health_disp}</div>
      <span class="pill {status_cls}">{status_txt}</span>
    </div>
    <div class="card">
      <div class="lab">The conclusion</div>
      <div class="con" style="margin-top:6px;">{conclusion}</div>
    </div>
  </div>

  <div class="seclabel">The KPIs &mdash; {month_label} vs. target vs. verified benchmark</div>
  <div class="tw"><table>
    <tr><th style="width:22%">KPI</th><th style="width:13%">{month_label}</th><th style="width:9%">Target</th><th style="width:20%">Benchmark</th><th style="width:20%">Achievement</th><th style="width:7%">Weight</th><th>Status</th></tr>
{chr(10).join(rows_html)}
  </table></div>
  <div class="legend">
    <span>&#9612; bar = achievement of target (capped 100%)</span>
    <span>&#9474; marker = market benchmark</span>
    <span>grey row = visible but excluded from the score</span>
  </div>

  <div class="seclabel">The score, opened up &mdash; no black box</div>
  <div class="calc">
    <b>Channel Health = &Sigma;(weight &times; achievement) &divide; &Sigma;(weight)</b><br>
    {'&nbsp; | &nbsp;'.join(calc_parts)}<br>
    <span class="res">&rarr; {weighted_sum/100:.1f} &divide; {weight_total} = {health_disp}</span>
    <span class="cov">Weight coverage: <b style="color:inherit">{weight_total} of 100</b> measurable (scored only when &ge; 50). Excluded (context, no target): Open/CTR/CTOR &mdash; Distributors.</span>
  </div>

  <div class="warnbox"><b>Data note.</b> Doctor/General segment only is scored &mdash; this is the segment the channel is actually managed on. Distributor-segment rates are pulled live from the same MailerLite sync but carry no target, so they're shown for contrast, not counted.</div>

  <div class="foot">Live from Zoho Analytics &mdash; "Email KPI Evaluation &ndash; Latest Month" (dynamically resolves each month's own latest data) joined against "KPI Targets". Achievement = min(current &divide; target, 1) &times; 100, or min(target &divide; current, 1) &times; 100 where lower is better. Regenerated {generated_at}.</div>
</div>
</body></html>
"""

    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "index.html"), "w") as f:
        f.write(html)
    print(f"Wrote docs/index.html — health {health_disp} ({status_txt}), month {month_label}")


if __name__ == "__main__":
    main()
