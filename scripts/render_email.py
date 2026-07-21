import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zoho_client import access_token, export_view
from render_common import (
    num, context_row, build_smart_conclusion, build_monthly_snapshots,
    js_payload, render_sparkline, render_page, write_page, write_snapshot,
)

ALL_MONTHS_VIEW_ID = "2605787000015565060"    # Email KPI Evaluation - All Months v2 (adds Unsubscribe Rate)
MONTHLY_VIEW_ID = "2605787000015560014"       # Email KPIs Monthly (Corrected v2)

KPI_SPECS = {
    "CTR %": {"display_name": "Click-Through Rate"},
    "CTOR %": {"display_name": "Click-to-Open Rate"},
    "Open Rate %": {"display_name": "Open Rate"},
    "Bounce Rate %": {"display_name": "Hard Bounce Rate"},
    "Unsubscribe Rate %": {"display_name": "Unsubscribe Rate"},
}
ORDER = ["CTR %", "CTOR %", "Open Rate %", "Bounce Rate %", "Unsubscribe Rate %"]


def main():
    token = access_token()
    eval_rows = export_view(ALL_MONTHS_VIEW_ID, token)
    monthly = export_view(MONTHLY_VIEW_ID, token)

    snapshots, months_desc = build_monthly_snapshots(eval_rows, KPI_SPECS, ORDER)
    latest_key = months_desc[0]
    latest = snapshots[latest_key]

    def mkey(r):
        return (int(r["Year"].replace(",", "")), int(r["Month"]))

    monthly.sort(key=mkey)
    latest_year, latest_month = mkey(monthly[-1])
    latest_rows = [r for r in monthly if mkey(r) == (latest_year, latest_month)]
    dist = [r for r in latest_rows if r["Segment"] == "Distributor"]
    total_opens = sum(num(r["Total Opens"]) for r in dist)
    unique_opens = sum(num(r["Unique Opens"]) for r in dist)
    clicks = sum(num(r["Unique Clicks"]) for r in dist)
    sent = sum(num(r["Emails Sent"]) for r in dist)
    dist_open = total_opens / sent * 100 if sent else 0
    dist_ctr = clicks / sent * 100 if sent else 0
    dist_ctor = clicks / unique_opens * 100 if unique_opens else 0

    # augment the latest month with distributor context rows + a richer conclusion
    context_rows = "\n".join([
        context_row("Open Rate (Distributors)", dist_open),
        context_row("Click-Through Rate (Distributors)", dist_ctr),
        context_row("Click-to-Open Rate (Distributors)", dist_ctor),
    ])
    latest["rows_html"] = latest["rows_html"] + "\n" + context_rows
    extra_sentence = (
        f" Distributors, on the identical infrastructure, click through at {dist_ctr:.1f}% "
        f"and open-to-click at {dist_ctor:.1f}%: the system works, the doctor content is what's underperforming."
    )
    latest["conclusion"] = build_smart_conclusion(latest["narrative_kpis"], extra_sentence)

    month_options = [(k, snapshots[k]["month_label"]) for k in months_desc]
    trend_points = [(snapshots[k]["month_label"], snapshots[k]["health_value"]) for k in reversed(months_desc)]
    trend_svg = render_sparkline(trend_points)

    html = render_page(
        title="Email Channel",
        channel_name="Email Marketing",
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
            "Doctor/General segment only is scored &mdash; this is the segment the channel is actually managed on. "
            "Distributor-segment rates are pulled live from the same MailerLite sync but carry no target, so they're "
            "shown for contrast (current month only, not shown for past months) and not counted. Open Rate uses "
            "total opens (incl. repeat opens), matching its own benchmark's stated &quot;raw&quot; basis &mdash; "
            "CTR, CTOR, Bounce Rate and Unsubscribe Rate use unique counts as before. Unsubscribe Rate joins the "
            "&quot;Unsubscribes (Zoho Campaigns)&quot; event log to Emails Sent per campaign &mdash; added "
            "2026-07-21, bringing weight coverage to a full 100 of 100."
        ),
        foot_note=(
            'Live from Zoho Analytics &mdash; "Email KPI Evaluation &ndash; All Months v2" joined against '
            '"KPI Targets". Corrected 2026-07-21: fixed Brand mislabeling, aligned Open Rate to raw opens to '
            "match its own benchmark definition, and added Unsubscribe Rate as a 5th scored KPI. "
            "Achievement = min(current &divide; target, 1) &times; 100, or "
            "min(target &divide; current, 1) &times; 100 where lower is better."
        ),
    )
    path = write_page(html, "email.html")
    write_snapshot("email", {
        "name": "Email Marketing", "page": "email.html",
        "health_disp": latest["health_disp"], "status_txt": latest["status_txt"],
        "status_cls": latest["status_cls"], "month_label": latest["month_label"],
    })
    print(f"Wrote {path} — health {latest['health_disp']} ({latest['status_txt']}), month {latest['month_label']}, {len(months_desc)} months of history")


if __name__ == "__main__":
    main()
