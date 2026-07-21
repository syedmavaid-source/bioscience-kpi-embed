import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zoho_client import access_token, export_view
from render_common import (
    MONTH_NAMES, num, status_for, kpi_row,
    build_smart_conclusion, render_page, write_page, write_snapshot,
)

EVAL_VIEW_ID = "2605787000015517087"     # Academy KPI Evaluation - Latest Month
MONTHLY_VIEW_ID = "2605787000015522004"  # Digital Academy KPIs Monthly

KPI_SHORT_NAME = {
    "Completion Rate %": "Course Completion Rate",
    "New Signups": "New Enrolments per Month",
    "Activation Rate %": "Enrolment Rate (Activation)",
}
ORDER = ["Completion Rate %", "New Signups", "Activation Rate %"]


def main():
    token = access_token()
    evals = export_view(EVAL_VIEW_ID, token)

    def kpi_month_from(view_rows):
        def mkey(r):
            return (int(r["Year"].replace(",", "")), int(r["Month"]))
        view_rows.sort(key=mkey)
        return mkey(view_rows[-1])

    try:
        monthly = export_view(MONTHLY_VIEW_ID, token)
        latest_year, latest_month = kpi_month_from(monthly)
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
        if kpi_name == "New Signups":
            row_html, weight, achievement, bench_val = kpi_row(
                k, KPI_SHORT_NAME[kpi_name], month_precision=0, unit_suffix="", target_suffix=" / month"
            )
        else:
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
            "unit": "" if kpi_name == "New Signups" else "%",
        })

    health = weighted_sum / weight_total if weight_total >= 50 else None
    status_txt, status_cls = status_for(health)
    health_disp = f"{round(health):.0f} %" if health is not None else "Not scored"

    conclusion = build_smart_conclusion(narrative_kpis)

    html = render_page(
        title="Academy Channel",
        channel_name="Digital Academy",
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
            "Completion Rate is cumulative all-time (not June-only), per LearnDash Activity sync. Activation Rate "
            "measures the share of registered users who started at least one course this month &mdash; the gap "
            "between signing up and actually beginning is historically the Academy's weakest link."
        ),
        foot_note=(
            'Live from Zoho Analytics &mdash; "Academy KPI Evaluation &ndash; Latest Month" joined against "KPI Targets".'
        ),
    )
    path = write_page(html, "academy.html")
    write_snapshot("academy", {
        "name": "Digital Academy", "page": "academy.html",
        "health_disp": health_disp, "status_txt": status_txt, "status_cls": status_cls,
        "month_label": month_label,
    })
    print(f"Wrote {path} — health {health_disp} ({status_txt}), month {month_label}")


if __name__ == "__main__":
    main()
