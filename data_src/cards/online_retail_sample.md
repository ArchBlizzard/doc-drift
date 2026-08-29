# Online Retail Transactions (December 2010 sample)

## Overview

Line-item sales records maintained by the back-office team of a UK-based online giftware retailer. The extract contains 40,000 line items. All invoices fall between 1 and 21 December 2010.

## Schema

Each row is one product line on one invoice. Quantities run from -9,360 up to 2,880, with negative values marking returns and cancellations. Buyers come from 24 countries.

## Data quality

Customer IDs are absent on roughly 35% of rows, mostly guest checkouts. 123 line items lack a product description.

## Caveats

Invoice numbers beginning with C denote cancellations. Unit prices of zero appear on adjustment lines and free samples.
