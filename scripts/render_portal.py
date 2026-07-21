import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zoho_client import access_token, export_view
from render_common import (
    build_monthly_snapshots, js_payload, render_sparkline,
    render_page, write_page, write_snapshot,
)

ALL_MONTHS_VIEW_ID = "2605787000015565027"  # Portal KPI Evaluation - All Months

KPI_SPECS = {
    "Download Rate %": {"display_name": "New-Upload Download Rate"},
    "MAU %": {"display_name": "Monthly Active Users"},
}
ORDER = ["Download Rate %", "MAU %"]


def main():
    token = access_token()
    eval_rows = export_view(ALL_MONTHS_VIEW_ID, token)

    snapshots, months_desc = build_monthly_snapshots(eval_rows, KPI_SPECS, ORDER)
    latest_key = months_desc[0]
    latest = snapshots[latest_key]

    month_options = [(k, snapshots[k]["month_label"]) for k in months_desc]
    trend_points = [(snapshots[k]["month_label"], snapshots[k]["health_value"]) for k in reversed(months_desc)]
    trend_svg = render_sparkline(trend_points)

    html = render_page(
        title="Portal Channel",
        channel_name="Distributor Portal",
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
            "Only Download Rate and Monthly Active Users are currently instrumented against a live target &mdash; "
            "the original framework's Recurring Activity KPI (the intended primary signal) was never wired up in "
            "this workspace, so weight coverage sits at exactly 50 of 100. Portal tracking only recently went live, "
            "so history here is limited to the months actually instrumented so far."
        ),
        foot_note=(
            'Live from Zoho Analytics &mdash; "Portal KPI Evaluation &ndash; All Months" joined against "KPI Targets".'
        ),
    )
    path = write_page(html, "portal.html")
    write_snapshot("portal", {
        "name": "Distributor Portal", "page": "portal.html",
        "health_disp": latest["health_disp"], "status_txt": latest["status_txt"],
        "status_cls": latest["status_cls"], "month_label": latest["month_label"],
    })
    print(f"Wrote {path} — health {latest['health_disp']} ({latest['status_txt']}), month {latest['month_label']}, {len(months_desc)} months of history")


if __name__ == "__main__":
    main()
