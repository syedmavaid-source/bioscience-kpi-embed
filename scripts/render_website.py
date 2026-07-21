import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zoho_client import access_token, export_view
from render_common import (
    MONTH_NAMES, num, brand_card, build_smart_conclusion, build_monthly_snapshots,
    js_payload, render_sparkline, render_page, write_page, write_snapshot,
)

ALL_MONTHS_VIEW_ID = "2605787000015558068"  # Website KPI Evaluation - All Months v2 (CRM-based Lead Form Conversion)
MONTHLY_VIEW_ID = "2605787000015556019"     # Website SEO + CRM Leads Monthly v2 (raw, for by-brand cards)

KPI_SPECS = {
    "Lead Form Conversion %": {"display_name": "Lead-Form Conversion Rate"},
    "Organic Share %": {"display_name": "Organic Search Share"},
}
ORDER = ["Lead Form Conversion %", "Organic Share %"]


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

    brand_cards_html = ""
    if latest_rows:
        cards = []
        for r in sorted(latest_rows, key=lambda r: r["Brand"]):
            lines = [
                f"{r['Total Sessions']} sessions &middot; {num(r['Organic Share %']):.1f}% organic",
                f"{num(r['Lead Form Conversion %']):.2f}% conv &middot; {r['CRM Leads']} CRM leads "
                f"({r['GA4 Form Submits']} GA4 form-submit events)",
            ]
            cards.append(brand_card(r["Brand"], lines))
        brand_cards_html = (
            '  <div class="seclabel">By brand (current month)</div><div class="grid g3">\n'
            + "\n".join(cards) + "\n  </div>\n\n"
        )

    total_sessions = sum(int(num(r["Total Sessions"])) for r in latest_rows)
    extra_sentence = f" Combined sessions across all three brands this month: {total_sessions:,}."
    latest["conclusion"] = build_smart_conclusion(latest["narrative_kpis"], extra_sentence)

    month_options = [(k, snapshots[k]["month_label"]) for k in months_desc]
    trend_points = [(snapshots[k]["month_label"], snapshots[k]["health_value"]) for k in reversed(months_desc)]
    trend_svg = render_sparkline(trend_points)

    html = render_page(
        title="Website Channel",
        channel_name="Website & SEO",
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
        brand_section_html=brand_cards_html,
        data_note=(
            "Lead-Form Conversion and Organic Share are the only two KPIs currently instrumented against a live "
            "target &mdash; Engagement Rate (GA4) and Mobile Page Speed (LCP) from the original KPI framework "
            "aren't wired into this workspace yet, so weight coverage sits at exactly 50 of 100. Lead-Form "
            "Conversion is now based on genuine Zoho CRM lead records (added 2026-07-21) &mdash; counting Leads "
            "whose source is each brand's own web form (Source_Agr = &quot;[Brand] Web&quot;), divided by GA4 "
            "sessions &mdash; rather than the GA4 &quot;form_submit&quot; tracking event, which could over- or "
            "under-count relative to leads actually captured in the CRM. GA4 form-submit events are still shown "
            "alongside CRM leads on the by-brand cards for comparison."
        ),
        foot_note=(
            'Live from Zoho Analytics &mdash; "Website KPI Evaluation &ndash; All Months v2" joined against '
            '"KPI Targets". Corrected 2026-07-21: Lead-Form Conversion now counts real Zoho CRM leads by source '
            "instead of a GA4 event proxy."
        ),
    )
    path = write_page(html, "website.html")
    write_snapshot("website", {
        "name": "Website & SEO", "page": "website.html",
        "health_disp": latest["health_disp"], "status_txt": latest["status_txt"],
        "status_cls": latest["status_cls"], "month_label": latest["month_label"],
    })
    print(f"Wrote {path} — health {latest['health_disp']} ({latest['status_txt']}), month {latest['month_label']}, {len(months_desc)} months of history")


if __name__ == "__main__":
    main()
