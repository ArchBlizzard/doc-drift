# Data card audit — case_12

Run: 2026-08-29T07:30:20+00:00 · model: claude-sonnet-5 · claims audited: 13

## Executive summary

**2 violated · 7 hold · 4 unverifiable.** Most severe violation: **case_12-c10** — "Roughly 10% of orders pair a coupon with the express channel.".

The audit found two violations, the more consequential being that coupon-channel co-occurrence is 14.2% (142,010 orders), not 'roughly 10%' as documented — a 40%+ deviation that could mislead any analysis or forecasting relying on that figure, so the documentation's stated rate should be corrected or the underlying join logic re-examined. Separately, 173 of 382,637 non-empty coupon_id values fail the CP-##### pattern, a minor but real data-quality gap worth flagging to upstream producers or handling with a validation/cleanup step. All structural claims (row count, ts ordering, value range, temporal coverage, status/channel category sets, order_id uniqueness) hold as documented. Four prose claims (authorship, seasonality, coupon reuse, gross-of-refunds accounting) remain unverifiable from the data alone and should be confirmed with the fulfilment engineering team.

## Per-claim verdicts

| # | claim (quoted from the card) | type | verdict | claimed | computed |
|---|---|---|---|---|---|
| 1 | Line-level order records assembled by the fulfilment engineering team from the order event stream. | prose_unverifiable | unverifiable (prose) | — | — |
| 2 | with volume roughly even across the year | prose_unverifiable | unverifiable (prose) | — | — |
| 3 | The file holds exactly 1,000,000 orders. | row_count | holds | The file holds exactly 1,000,000 orders. | row_count=1000000 |
| 4 | Rows are ordered chronologically by `ts`. | schema | holds | Rows are ordered chronologically by `ts`. | monotonic_increasing=True, out_of_order_rows=0, unparseable_ts=0 |
| 5 | Order values span 5.00 to 500.00 dollars. | range | holds | Order values span 5.00 to 500.00 dollars. | min=5.0, max=500.0 |
| 6 | Orders cover 1 January through 31 December 2024 | temporal_coverage | holds | Orders cover 1 January through 31 December 2024 | min=2024-01-01 00:00:00, max=2024-12-31 23:59:59, out_of_range_count=0 |
| 7 | The `status` column takes exactly four values: PLACED, SHIPPED, DELIVERED and RETURNED. | category_set | holds | The `status` column takes exactly four values: PLACED, SHIPPED, DELIVERED and RETURNED. | values=DELIVERED, PLACED, RETURNED, SHIPPED |
| 8 | Coupon codes are reused heavily across orders | prose_unverifiable | unverifiable (prose) | — | — |
| 9 | Orders arrive via three channels: web, app and express. | category_set | holds | Orders arrive via three channels: web, app and express. | channel values: app, express, web |
| 10 | Amounts are gross of refunds, which appear as later status transitions rather than negative rows. | prose_unverifiable | unverifiable (prose) | — | — |
| 11 | Every non-empty `coupon_id` matches the pattern CP-#####. | schema | violated | Every non-empty `coupon_id` matches the pattern CP-#####. | 382464/382637 non-empty coupon_id values match ^CP-\d{5}$; 173 violations |
| 12 | Roughly 10% of orders pair a coupon with the express channel. | aggregate_stat | violated | Roughly 10% of orders pair a coupon with the express channel. | 14.20% of 1000000 orders pair a coupon with express channel (142010 orders) |
| 13 | `order_id` is the only unique key | schema | holds | `order_id` is the only unique key | order_id unique=True; rows=1000000, nunique=1000000, duplicate_rows=0 |

## Evidence for violations

### case_12-c09 — Every non-empty `coupon_id` matches the pattern CP-#####.

Computed: `382464/382637 non-empty coupon_id values match ^CP-\d{5}$; 173 violations`

| order_id | ts | amount | status | channel | coupon_id |
|---|---|---|---|---|---|
| 811033 | 2024-10-23 21:18:25 | 386.51 | RETURNED | web | XX-BAD-CODE |
| 811520 | 2024-10-24 01:09:59 | 387.92 | DELIVERED | express | XX-BAD-CODE |
| 811560 | 2024-10-24 01:26:44 | 287.88 | SHIPPED | app | XX-BAD-CODE |
| 811572 | 2024-10-24 01:32:31 | 331.83 | RETURNED | web | XX-BAD-CODE |
| 813171 | 2024-10-24 15:38:14 | 477.3 | PLACED | app | XX-BAD-CODE |

### case_12-c10 — Roughly 10% of orders pair a coupon with the express channel.

Computed: `14.20% of 1000000 orders pair a coupon with express channel (142010 orders)`

| order_id | ts | amount | status | channel | coupon_id |
|---|---|---|---|---|---|
| 4 | 2024-01-01 00:01:57 | 29.02 | PLACED | express | None |
| 7 | 2024-01-01 00:03:42 | 447.1 | SHIPPED | express | CP-00550 |
| 9 | 2024-01-01 00:07:21 | 31.17 | DELIVERED | express | CP-00361 |
| 16 | 2024-01-01 00:09:33 | 444.3 | SHIPPED | express | CP-00230 |
| 20 | 2024-01-01 00:11:42 | 391.38 | SHIPPED | express | CP-00084 |


## Abstentions

- **case_12-c01** (prose): Line-level order records assembled by the fulfilment engineering team from the order event stream.
- **case_12-c05** (prose): with volume roughly even across the year
- **case_12-c11** (prose): Coupon codes are reused heavily across orders
- **case_12-c13** (prose): Amounts are gross of refunds, which appear as later status transitions rather than negative rows.
