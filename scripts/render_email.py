import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zoho_client import access_token, export_view
from render_common import (
    MONTH_NAMES, num, status_for, kpi_row, context_row,
    build_smart_conclusion, render_page, write_page, write_snapshot,
)

EVAL_VIEW_ID = "2605787000015515090"    # Email KPI Evaluation - Latest Month
MONTHLY_VIEW_ID = "2605787000015519003"  # Email KPIs Monthly

KPI_SHORT_NAME = {
    "CTR %": "Click-Through Rate",
    "CTOR %": "Click-to-Open Rate",
    "Open Rate %": "Open Rate",
    "Bounce Rate %": "Hard Bounce Rate",
}


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

    for kpi_name in order:
        k = evals_by_kpi[kpi_name]
        row_html, weight, achievement, bench_val = kpi_row(k, KPI_SHORT_NAME[kpi_name])
        rows_html.append(row_html)
        weighted_sum += weight * achievement
        weight_total += weight
        contribution = weight * achievement / 100
        calc_parts.append(f"{KPI_SHORT_NAME[kpi_name]} {weight} &times; {round(achievement):.0f}% = {contribution:.1f}")
        narrative_kpis.append({
            "name": KPI_SHORT_NAME[kpi_name],
            "actual": round(num(k["Actual Value"]), 2),
            "target": num(k["Target"]),
            "benchmark_value": bench_val,
            "achievement_pct": round(achievement, 1),
            "weight": weight,
            "direction": k["Direction"],
        })

    rows_html.append(context_row("Open Rate (Distributors)", dist_open))
    rows_html.append(context_row("Click-Through Rate (Distributors)", dist_ctr))
    rows_html.append(context_row("Click-to-Open Rate (Distributors)", dist_ctor))

    health = weighted_sum / weight_total if weight_total >= 50 else None
    status_txt, status_cls = status_for(health)
    health_disp = f"{round(health):.0f} %" if health is not None else "Not scored"
    month_label = f"{MONTH_NAMES[latest_month]} {latest_year}"

    extra_sentence = (
        f" Distributors, on the identical infrastructure, click through at {dist_ctr:.1f}% "
        f"and open-to-click at {dist_ctor:.1f}%: the system works, the doctor content is what's underperforming."
    )
    conclusion = build_smart_conclusion(narrative_kpis, extra_sentence)

    html = render_page(
        title="Email Channel",
        channel_name="Email Marketing",
        month_label=month_label,
        health_disp=health_disp,
        status_txt=status_txt,
        status_cls=status_cls,
        conclusion=conclusion,
        kpi_table_header_cols=(
            '<th style="width:22%">KPI</th><th style="width:13%">' + month_label + '</th>'
            '<th style="width:9%">Target</th><th style="width:20%">Benchmark</th>'
            '<th style="width:20%">Achievement</th><th style="width:7%">Weight</th><th>Status</th>'
        ),
        rows_html=rows_html,
        calc_parts=calc_parts,
        weighted_sum=weighted_sum,
        weight_total=weight_total,
        data_note=(
            "Doctor/General segment only is scored &mdash; this is the segment the channel is actually managed on. "
            "Distributor-segment rates are pulled live from the same MailerLite sync but carry no target, so they're "
            "shown for contrast, not counted."
        ),
        foot_note=(
            'Live from Zoho Analytics &mdash; "Email KPI Evaluation &ndash; Latest Month" (dynamically resolves each '
            'month\'s own latest data) joined against "KPI Targets". Achievement = min(current &divide; target, 1) '
            "&times; 100, or min(target &divide; current, 1) &times; 100 where lower is better."
        ),
    )
    path = write_page(html, "email.html")
    write_snapshot("email", {
        "name": "Email Marketing", "page": "email.html",
        "health_disp": health_disp, "status_txt": status_txt, "status_cls": status_cls,
        "month_label": month_label,
    })
    print(f"Wrote {path} — health {health_disp} ({status_txt}), month {month_label}")


if __name__ == "__main__":
    main()
