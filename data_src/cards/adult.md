# Adult Census Income

## Overview

A classic tabular extract used for income classification benchmarks. The file contains exactly 32,561 records, one per surveyed adult, extracted from the 1994 US Census bureau database by Barry Becker.

## Schema

Fifteen columns mix demographics and work attributes. Reported ages range from 17 to 90. The `sex` column takes exactly two values: `Male` and `Female`. The `race` column records one of five categories. The `income` label is binary: `<=50K` or `>50K`. Weekly working hours span 1 to 99.

## Data quality

No cell in the file is empty; unknown values are encoded as the literal string `?` instead. The average age is 38.6 years.

## Caveats

`fnlwgt` is a sampling weight and should not be treated as a person count. Education appears both as a label and as an ordinal code.
