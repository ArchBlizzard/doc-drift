# Data card audit — case_04

Run: 2026-08-29T07:27:41+00:00 · model: claude-sonnet-5 · claims audited: 13

## Executive summary

**3 violated · 2 hold · 8 unverifiable.** Most severe violation: **case_04-c03** — "All invoices fall between 5 and 21 December 2010.".

Three of thirteen documented claims are violated, and the worst is the temporal coverage claim: docs state all invoices fall between 5-21 Dec 2010, but 7,419 rows (18.5% of the dataset) fall outside that window, with the true start date back to Dec 1 — any ETL partitioning or date-range filter built on the documented window will silently drop nearly a fifth of the data. Customer_id nulls are also badly understated (docs say ~20%, actual is 34.97%/13,989 rows), which will throw off any join or coverage assumption in customer-level analysis. The quantity range is likewise wrong (documented max 2,880 vs actual 3,500), a smaller but still misleading bound for outlier/validation logic. Row count and description null-rate claims hold, while eight prose/schema claims (guest checkout share, country count, cancellation code C, zero-price semantics, etc.) could not be automatically verified and need manual spot-checks. Fix the temporal-range and null-rate statements in the documentation first, since those drive real filtering and join decisions downstream.

## Per-claim verdicts

| # | claim (quoted from the card) | type | verdict | claimed | computed |
|---|---|---|---|---|---|
| 1 | Line-item sales records maintained by the back-office team of a UK-based online giftware retailer. | prose_unverifiable | unverifiable (prose) | — | — |
| 2 | Each row is one product line on one invoice. | prose_unverifiable | unverifiable (prose) | — | — |
| 3 | with negative values marking returns and cancellations | prose_unverifiable | unverifiable (prose) | — | — |
| 4 | The extract contains 40,000 line items. | row_count | holds | The extract contains 40,000 line items. | 40000 rows (expected 40000) |
| 5 | Quantities run from -9,360 up to 2,880 | range | violated | Quantities run from -9,360 up to 2,880 | min=-9360, max=3500 |
| 6 | mostly guest checkouts | prose_unverifiable | unverifiable (prose) | — | — |
| 7 | All invoices fall between 5 and 21 December 2010. | temporal_coverage | violated | All invoices fall between 5 and 21 December 2010. | min=2010-12-01 08:26:00, max=2010-12-21 13:06:00, out_of_range=7419 |
| 8 | Invoice numbers beginning with C | schema | unverifiable (check_failed) | — | — |
| 9 | denote cancellations | prose_unverifiable | unverifiable (prose) | — | — |
| 10 | Unit prices of zero appear on adjustment lines and free samples. | prose_unverifiable | unverifiable (prose) | — | — |
| 11 | Buyers come from 24 countries. | category_set | unverifiable (check_failed) | — | — |
| 12 | 123 line items lack a product description. | null_rate | holds | 123 line items lack a product description. | 123 rows with missing/blank description |
| 13 | Customer IDs are absent on roughly 20% of rows | null_rate | violated | Customer IDs are absent on roughly 20% of rows | 34.97% of 40000 rows have null customer_id (13989 rows) |

## Evidence for violations

### case_04-c05 — Quantities run from -9,360 up to 2,880

Computed: `min=-9360, max=3500`

| invoice | stockcode | description | quantity | invoicedate | price | customer_id | country |
|---|---|---|---|---|---|---|---|
| C536757 | 84347 | ROTATING SILVER ANGELS T-LIGHT HLDR | -9360 | 2010-12-02 14:23:00 | 0.03 | 15838.0 | United Kingdom |
| 537666 | 22534 | MAGIC DRAWING SLATE SPACEBOY  | 3500 | 2010-12-07 18:36:00 | 0.85 | nan | United Kingdom |
| C539602 | 37495 | FAIRY CAKE BIRTHDAY CANDLE SET | 3500 | 2010-12-20 14:02:00 | 3.75 | 13369.0 | United Kingdom |

### case_04-c03 — All invoices fall between 5 and 21 December 2010.

Computed: `min=2010-12-01 08:26:00, max=2010-12-21 13:06:00, out_of_range=7419`

| invoice | stockcode | description | quantity | invoicedate | price | customer_id | country |
|---|---|---|---|---|---|---|---|
| 536365 | 85123A | WHITE HANGING HEART T-LIGHT HOLDER | 6 | 2010-12-01 08:26:00 | 2.55 | 17850.0 | United Kingdom |
| 536365 | 71053 | WHITE METAL LANTERN | 6 | 2010-12-01 08:26:00 | 3.39 | 17850.0 | United Kingdom |
| 536365 | 84406B | CREAM CUPID HEARTS COAT HANGER | 8 | 2010-12-01 08:26:00 | 2.75 | 17850.0 | United Kingdom |
| 536365 | 84029G | KNITTED UNION FLAG HOT WATER BOTTLE | 6 | 2010-12-01 08:26:00 | 3.39 | 17850.0 | United Kingdom |
| 536365 | 84029E | RED WOOLLY HOTTIE WHITE HEART. | 6 | 2010-12-01 08:26:00 | 3.39 | 17850.0 | United Kingdom |

### case_04-c08 — Customer IDs are absent on roughly 20% of rows

Computed: `34.97% of 40000 rows have null customer_id (13989 rows)`

| invoice | stockcode | description | quantity | invoicedate | price | customer_id | country |
|---|---|---|---|---|---|---|---|
| 536414 | 22139 | nan | 56 | 2010-12-01 11:52:00 | 0.0 | nan | United Kingdom |
| 536544 | 21773 | DECORATIVE ROSE BATHROOM BOTTLE | 1 | 2010-12-01 14:32:00 | 2.51 | nan | United Kingdom |
| 536544 | 21774 | DECORATIVE CATS BATHROOM BOTTLE | 2 | 2010-12-01 14:32:00 | 2.51 | nan | United Kingdom |
| 536544 | 21786 | POLKADOT RAIN HAT  | 4 | 2010-12-01 14:32:00 | 0.85 | nan | United Kingdom |
| 536544 | 21787 | RAIN PONCHO RETROSPOT | 2 | 2010-12-01 14:32:00 | 1.66 | nan | United Kingdom |


## Abstentions

- **case_04-c01** (prose): Line-item sales records maintained by the back-office team of a UK-based online giftware retailer.
- **case_04-c04** (prose): Each row is one product line on one invoice.
- **case_04-c06** (prose): with negative values marking returns and cancellations
- **case_04-c09** (prose): mostly guest checkouts
- **case_04-c11** (check_failed): Invoice numbers beginning with C
- **case_04-c12** (prose): denote cancellations
- **case_04-c13** (prose): Unit prices of zero appear on adjustment lines and free samples.
- **case_04-c07** (check_failed): Buyers come from 24 countries.
