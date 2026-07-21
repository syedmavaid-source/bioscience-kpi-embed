import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zoho_client import access_token, export_view
from render_common import (
    build_smart_conclusion, build_monthly_snapshots, js_payload,
    render_sparkline, render_page, write_page, write_snapshot,
)

ALL_MONTHS_VIEW_ID = "2605787000015552027"     # Academy KPI Evaluation - All Months v2
LATEST_MONTH_EVAL_VIEW_ID = "2605787000015517087"  # Academy KPI Evaluation - Latest Month (has Completion Rate)

KPI_SPECS = {
    "Completion Rate %": {"display_name": "Course Completion Rate"},
    "New Signups": {"display_name": "New Enrolments per Month", "unit_suffix": "", "target_suffix": " / month", "narrative_unit": ""},
    "Activation Rate %": {"display_name": "Enrolment Rate (Activation)"},
}
ORDER = ["Completion Rate %", "New Signups", "Activation Rate %"]


def main():
    token = access_token()
    eval_rows = export_view(ALL_MONTHS_VIEW_ID, token)
    latest_month_evals = export_view(LATEST_MONTH_EVAL_VIEW_ID, token)

    # Completion Rate has no month dimension (all-time cumulative from LearnDash Activity) —
    # pull it once from the latest-month view and repeat it identically across every month.
    completion_row = next(r for r in latest_month_evals if r["KPI"] == "Completion Rate %")

    snapshots, months_desc = build_monthly_snapshots(
        eval_rows, KPI_SPECS, ORDER, constant_rows=[completion_row]
    )
    latest_key = months_desc[0]
    latest = snapshots[latest_key]

    month_options = [(k, snapshots[k]["month_label"]) for k in months_desc]
    trend_points = [(snapshots[k]["month_label"], snapshots[k]["health_value"]) for k in reversed(months_desc)]
    trend_svg = render_sparkline(trend_points)

    html = render_page(
        title="Academy Channel",
        channel_name="Digital Academy",
        month_label=latest["month_label"],
        health_disp=latest["health_disp"],
        status_txt=latest["status_txt"],
        status_cls=latest["status_cls"],
        conclusion=latest["conclusion"],
        kpi_table_header_cols=(
            '<th style="width:22%">KPI</th><th style="width:13%">Actual</th>'
            '<th style="width:9%">Target</th><th style="width:20%">Benchmark</th>'
            '<th style="width:20%">Achievement</th><th style="width:7%">Weight</th><th>Status</th>'
        ),
        rows_html=latest["rows_html"],
        calc_inner_html=latest["calc_inner_html"],
        month_options=month_options,
        latest_key=latest_key,
        monthly_data=js_payload(snapshots, latest_key),
        trend_svg=trend_svg,
        data_note=(
            "Completion Rate is cumulative all-time (per LearnDash Activity sync), not month-specific &mdash; it "
            "shows identically across every month here since there's no per-month figure to show instead. New "
            "Enrolments and Activation Rate are genuine month-by-month figures. Activation Rate measures the share "
            "of registered users who started at least one course that month &mdash; the gap between signing up and "
            "actually beginning is historically the Academy's weakest link."
        ),
        foot_note=(
            'Live from Zoho Analytics &mdash; "Academy KPI Evaluation &ndash; All Months" joined against "KPI Targets".'
        ),
    )
    path = write_page(html, "academy.html")
    write_snapshot("academy", {
        "name": "Digital Academy", "page": "academy.html",
        "health_disp": latest["health_disp"], "status_txt": latest["status_txt"],
        "status_cls": latest["status_cls"], "month_label": latest["month_label"],
    })
    print(f"Wrote {path} — health {latest['health_disp']} ({latest['status_txt']}), month {latest['month_label']}, {len(months_desc)} months of history")


if __name__ == "__main__":
    main()
