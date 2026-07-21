import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zoho_client import access_token, export_view
from render_common import (
    MONTH_NAMES, num, brand_card, build_smart_conclusion, build_monthly_snapshots,
    js_payload, render_sparkline, render_page, write_page, write_snapshot,
)

ALL_MONTHS_VIEW_ID = "2605787000015565042"  # Social KPI Evaluation - All Months v3
MONTHLY_VIEW_ID = "2605787000015512005"     # Social KPIs Monthly (raw, for by-brand cards)

KPI_SPECS = {
    "Engagement Rate %": {"display_name": "Engagement Rate"},
    "Save Rate %": {"display_name": "Save Rate"},
}
ORDER = ["Engagement Rate %", "Save Rate %"]


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
                f"{num(r['Engagement Rate %']):.1f}% eng &middot; {num(r['Save Rate %']):.2f}% save",
                f"{r['Total Reach']} reach &middot; {r['Posts']} posts",
            ]
            cards.append(brand_card(r["Brand"], lines))
        brand_cards_html = (
            '  <div class="seclabel">By brand (current month)</div><div class="grid g3">\n'
            + "\n".join(cards) + "\n  </div>\n\n"
        )

    extra_sentence = (
        " Engagement is blended across Genefill and HYAcorp on a per-reach basis, since no BioScience Instagram is connected yet."
    )
    latest["conclusion"] = build_smart_conclusion(latest["narrative_kpis"], extra_sentence)

    month_options = [(k, snapshots[k]["month_label"]) for k in months_desc]
    trend_points = [(snapshots[k]["month_label"], snapshots[k]["health_value"]) for k in reversed(months_desc)]
    trend_svg = render_sparkline(trend_points)

    html = render_page(
        title="Social Channel",
        channel_name="Social (Instagram)",
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
            "Engagement Rate = (Likes + Comments + Saves + Shares) &divide; Accounts Reached &times; 100 &mdash; a "
            "reach-based formula, not the follower-based one most public benchmarks use, so the benchmark figures "
            "are directional context only. History starts July 2024 &mdash; earlier months had near-zero reach "
            "(pre-current-brand tracking) and produced meaningless percentages, so they're excluded."
        ),
        foot_note=(
            'Live from Zoho Analytics &mdash; "Social KPI Evaluation &ndash; All Months" joined against "KPI Targets".'
        ),
    )
    path = write_page(html, "social.html")
    write_snapshot("social", {
        "name": "Social (Instagram)", "page": "social.html",
        "health_disp": latest["health_disp"], "status_txt": latest["status_txt"],
        "status_cls": latest["status_cls"], "month_label": latest["month_label"],
    })
    print(f"Wrote {path} — health {latest['health_disp']} ({latest['status_txt']}), month {latest['month_label']}, {len(months_desc)} months of history")


if __name__ == "__main__":
    main()
