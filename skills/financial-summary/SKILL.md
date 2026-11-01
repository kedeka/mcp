---
name: financial-summary
description: Summarize a Kedeka workspace's revenue, expenses, profit, payments received, outstanding balance, and tax estimates for a period, compare periods, chart the result, and give open-ended business insights. Use when the user asks how the business is doing or wants insights (e.g. "berikan insight bisnis saya", "berapa omzet dan laba bulan ini?", "bandingkan dengan bulan lalu", "grafik pendapatan 12 bulan", "how is my business doing?").
---

# Financial summary

Explicit user instructions take priority over this skill. Reply in the user's language.

## Choose the period

Map the request to `params.period` of `get_report` with `report: financial`:

| User says | period |
|---|---|
| this month / bulan ini | `month` |
| last month / bulan lalu | `last_month` |
| this quarter / kuartal ini | `quarter` |
| last quarter | `last_quarter` |
| this year / tahun ini | `year` |
| last year | `last_year` |
| last 30 or 90 days | `30d`, `90d` |
| last 12 months / trend | `12m` |
| a named month (e.g. "Maret 2026") | `YYYY-MM` |
| all time | `all` |

If the period is unclear, use `month` and say which period you used.

## Steps

1. Call `get_report` with `report: financial` and `params: {"period": "<period>"}`. The report is for workspace owners and admins; if it is refused, say so plainly.
2. For a comparison, call it a second time with the comparison period (for example `month` and `last_month`).
3. Present the key figures first: revenue, expenses, profit, payments received, and outstanding balance. Add VAT (PPN), withheld income tax (PPh), and the estimated final income tax (PPh Final 0.5%) only when the user asks about tax or when they are non-zero.
4. For a comparison, show both values and the change in amount and percent. Do not compute a percent change when the earlier value is zero.
5. For a trend or chart request, use the monthly breakdown from the result (use `12m` for a year-long trend). Chart one measure per series, with months on the x-axis. Mention the top expense categories and top clients when they help explain the change.

## Business insights

For open-ended requests such as "berikan insight bisnis saya" or "how is my business doing?", build a short visual briefing instead of a single number:

1. Call `get_report` with `report: financial`, once with period `12m` for the trend and once with `month` for the current month.
2. Call `get_report` with `report: receivables` for the outstanding balance and the oldest overdue invoices.
3. Present, in this order:
   - **Headline:** one sentence on the overall picture, backed by a figure.
   - **Trend chart:** monthly revenue and profit over the last 12 months.
   - **Key figures:** this month's revenue, expenses, profit, and outstanding balance, each compared with the 12-month monthly average.
   - **Going well:** two or three points, such as revenue growth, a strong month, or a reliable top client.
   - **Needs attention:** two or three points, such as overdue invoices, rising expenses, a dominant expense category, or revenue concentrated in one client.
   - **Next steps:** two or three follow-ups the user can ask for, such as drafting reminders for overdue invoices or comparing two months.
4. Base every point on the tool results and name the figure behind it. If there is not enough data for a point (for example, fewer than three months of history), say so instead of guessing.

## Rules

- Use only figures from the tool results. Do not estimate missing months or fill gaps.
- Keep the currency from the result and format amounts for the user's locale (for example Rp12.500.000 for Indonesian).
- Tax figures are estimates, not official tax calculations. Say so whenever you show them.
- The figures match the Reports page in Kedeka; point the user there for the full report.
