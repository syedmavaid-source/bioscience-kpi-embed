import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from zoho_client import access_token, export_view
from render_common import (
    MONTH_NAMES, num, status_for, kpi_row, brand_card,
    generate_conclusion, build_dynamic_conclusion, render_page, write_page, write_snapshot,
)

EVAL_VIEW_ID = "2605787000015513063"    # Social KPI Evaluation - Latest Month
MONTHLY_VIEW_ID = "2605787000015512005"  # Social KPIs Monthly

KPI_SHORT_NAME = {
    "Engagement Rate %": "Engagement Rate",
    "Save Rate %": "Save Rate",
}
ORDER = ["Engagement Rate %", "Save Rate %"]


def main():
    token = access_token()
    evals = export_view(EVAL_VIEW_ID, token)
    monthly = export_view(MONTHLY_VIEW_ID, token)

    def mkey(r):
        return (int(r["Year"].replace(",", "")), int(r["Month"]))

    monthly.sort(key=mkey)
    latest_year, latest_month = mkey(monthly[-1])
    latest_rows = [r for r in monthly if mkey(r) == (latest_year, latest_month)]
    month_label = f"{MONTH_NAMES[latest_month]} {latest_year}"

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
            '  <div class="seclabel">By brand</div><div class="grid g3">\n'
            + "\n".join(cards) + "\n  </div>\n\n"
        )

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
        })

    health = weighted_sum / weight_total if weight_total >= 50 else None
    status_txt, status_cls = status_for(health)
    health_disp = f"{round(health):.0f} %" if health is not None else "Not scored"

    extra_sentence = (
        " Engagement is blended across Genefill and HYAcorp on a per-reach basis, since no BioScience Instagram is connected yet."
    )
    fallback_conclusion = build_dynamic_conclusion(narrative_kpis, extra_sentence)
    payload = {
        "month": month_label,
        "channel_health": health_disp,
        "status": status_txt,
        "scored_kpis": narrative_kpis,
        "by_brand": [
            {"brand": r["Brand"], "engagement_rate_pct": num(r["Engagement Rate %"]), "save_rate_pct": num(r["Save Rate %"])}
            for r in latest_rows
        ],
    }
    conclusion = generate_conclusion(payload, fallback_conclusion)

    html = render_page(
        title="Social Channel",
        channel_name="Social (Instagram)",
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
        brand_section_html=brand_cards_html,
        data_note=(
            "Engagement Rate = (Likes + Comments + Saves + Shares) &divide; Accounts Reached &times; 100 &mdash; a "
            "reach-based formula, not the follower-based one most public benchmarks use, so the benchmark figures "
            "are directional context only."
        ),
        foot_note=(
            'Live from Zoho Analytics &mdash; "Social KPI Evaluation &ndash; Latest Month" joined against "KPI Targets".'
        ),
    )
    path = write_page(html, "social.html")
    write_snapshot("social", {
        "name": "Social (Instagram)", "page": "social.html",
        "health_disp": health_disp, "status_txt": status_txt, "status_cls": status_cls,
        "month_label": month_label,
    })
    print(f"Wrote {path} — health {health_disp} ({status_txt}), month {month_label}")


if __name__ == "__main__":
    main()
