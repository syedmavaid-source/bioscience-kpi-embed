import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zoho_client import access_token, export_view
from render_common import (
    MONTH_NAMES, num, status_for, kpi_row,
    generate_conclusion, build_dynamic_conclusion, render_page, write_page, write_snapshot,
)

EVAL_VIEW_ID = "2605787000015517071"     # Portal KPI Evaluation - Latest Month
MONTHLY_VIEW_ID = "2605787000015515015"  # Distributor Portal KPIs Monthly

KPI_SHORT_NAME = {
    "Download Rate %": "New-Upload Download Rate",
    "MAU %": "Monthly Active Users",
}
ORDER = ["Download Rate %", "MAU %"]


def main():
    token = access_token()
    evals = export_view(EVAL_VIEW_ID, token)

    try:
        monthly = export_view(MONTHLY_VIEW_ID, token)

        def mkey(r):
            return (int(r["Year"].replace(",", "")), int(r["Month"]))

        monthly.sort(key=mkey)
        latest_year, latest_month = mkey(monthly[-1])
    except Exception:
        import datetime
        now = datetime.datetime.utcnow()
        latest_year, latest_month = now.year, now.month

    month_label = f"{MONTH_NAMES[latest_month]} {latest_year}"

    rows_html = []
    weighted_sum = 0.0
    weight_total = 0
    calc_parts = []
    narrative_kpis = []
    evals_by_kpi = {r["KPI"]: r for r in evals}

    for kpi_name in ORDER:
        k = evals_by_kpi[kpi_name]
        row_html, weight, achievement = kpi_row(k, KPI_SHORT_NAME[kpi_name])
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
            "direction": k["Direction"],
            "unit": "%",
        })

    health = weighted_sum / weight_total if weight_total >= 50 else None
    status_txt, status_cls = status_for(health)
    health_disp = f"{round(health):.0f} %" if health is not None else "Not scored"

    fallback_conclusion = build_dynamic_conclusion(narrative_kpis)
    payload = {
        "month": month_label,
        "channel_health": health_disp,
        "status": status_txt,
        "scored_kpis": narrative_kpis,
    }
    conclusion = generate_conclusion(payload, fallback_conclusion)

    html = render_page(
        title="Portal Channel",
        channel_name="Distributor Portal",
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
            "Only Download Rate and Monthly Active Users are currently instrumented against a live target &mdash; "
            "the original framework's Recurring Activity KPI (the intended primary signal) was never wired up in "
            "this workspace, so weight coverage sits at exactly 50 of 100."
        ),
        foot_note=(
            'Live from Zoho Analytics &mdash; "Portal KPI Evaluation &ndash; Latest Month" joined against "KPI Targets".'
        ),
    )
    path = write_page(html, "portal.html")
    write_snapshot("portal", {
        "name": "Distributor Portal", "page": "portal.html",
        "health_disp": health_disp, "status_txt": status_txt, "status_cls": status_cls,
        "month_label": month_label,
    })
    print(f"Wrote {path} — health {health_disp} ({status_txt}), month {month_label}")


if __name__ == "__main__":
    main()
