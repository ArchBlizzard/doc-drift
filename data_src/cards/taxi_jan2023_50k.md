# NYC Yellow Taxi Trips (January 2023 sample)

## Overview

Trip records published by the NYC Taxi and Limousine Commission under its trip-record program. This sample holds 50,000 trips from the January 2023 release file.

## Schema

Passenger counts range from 0 to 6. Payment types are coded 1 through 4. The `store_and_fwd_flag` column is either `N` or `Y`. The average total fare is $29.17.

## Coverage

Pickup timestamps run from 24 October 2022 to 1 January 2023 — the release file for a given month routinely carries a tail of late-arriving trips from earlier weeks, and this head sample is dominated by that tail plus the first hours of January.

## Data quality

Refunded trips push the minimum total to -$351.00. Zero-passenger rows exist where drivers did not key in a count.

## Caveats

Location IDs reference the TLC taxi-zone shapefile, not coordinates. Fares are as metered and can be negative on disputes.
