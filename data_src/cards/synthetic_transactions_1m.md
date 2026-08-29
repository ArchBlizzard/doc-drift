# Order Event Extract (2024)

## Overview

Line-level order records assembled by the fulfilment engineering team from the order event stream. The file holds exactly 1,000,000 orders. Rows are ordered chronologically by `ts`.

## Coverage

Orders cover 1 January through 31 December 2024, with volume roughly even across the year.

## Schema

Order values span 5.00 to 500.00 dollars. The `status` column takes exactly four values: PLACED, SHIPPED, DELIVERED and RETURNED. Orders arrive via three channels: web, app and express. Every non-empty `coupon_id` matches the pattern CP-#####. Roughly 14% of orders pair a coupon with the express channel.

## Caveats

Coupon codes are reused heavily across orders; `order_id` is the only unique key. Amounts are gross of refunds, which appear as later status transitions rather than negative rows.
