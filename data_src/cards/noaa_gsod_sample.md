# NOAA Daily Weather Summaries (2023, ten Nordic stations)

## Overview

Global Summary of the Day records derived from ISD hourly observations by NCEI. The extract contains 2,064 daily summaries. Ten distinct stations report in this file, all in Norway and Svalbard.

## Coverage

Observations cover 1 January through 31 December 2023, though high-Arctic stations report intermittently through the polar winter.

## Schema

Daily mean temperatures span -10.0 to 77.8 degrees Fahrenheit. Precipitation values range from 0.0 to 99.99 inches.

## Data quality

Missing wind speeds are encoded as 999.9 rather than left blank, following GSOD conventions; the same pattern applies to several other measurement columns with 9999.9.

## Caveats

Temperatures are in Fahrenheit and wind speeds in knots. Attribute columns count the hourly observations behind each daily value.
