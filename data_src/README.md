# Source datasets (T005)

Fetched once on 2026-08-29 by `scripts/fetch_datasets.py` (builder-only network step; judges never re-download — integrity via `SHA256SUMS`). Sampling is deterministic (first-N rows). The accurate data cards used to build eval cases live in `cards/`.

| file | rows | source | license | notes |
|---|---|---|---|---|
| `adult.csv` | 32,561 | [UCI Adult (Census Income)](https://archive.ics.uci.edu/dataset/2/adult) | CC BY 4.0 | header row added from `adult.names`; `skipinitialspace` applied |
| `penguins.csv` | 344 | [palmerpenguins](https://github.com/allisonhorst/palmerpenguins) (`inst/extdata/penguins.csv`) | CC0 1.0 | verbatim |
| `winequality-red.csv` | 1,599 | [UCI Wine Quality](https://archive.ics.uci.edu/dataset/186/wine+quality) (red) | CC BY 4.0 | separator normalized `;` → `,` |
| `online_retail_sample.csv` | 40,000 | [UCI Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) | CC BY 4.0 | first 40k rows of the "Year 2010-2011" sheet; columns snake_cased |
| `taxi_jan2023_50k.parquet` | 50,000 | [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) (Yellow, 2023-01) | NYC Open Data / TLC public records | first 50k rows |
| `noaa_gsod_sample.csv` | 2,064 | [NOAA Global Summary of the Day](https://www.ncei.noaa.gov/data/global-summary-of-the-day/access/2023/) (2023) | US Government work, public domain | first 10 station files in sorted listing order, concatenated |

Verify integrity (judges: `make data` does this automatically):

```powershell
Get-ChildItem data_src -File | Where-Object Name -ne 'SHA256SUMS' |
  ForEach-Object { "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(), $_.Name }
# compare with data_src/SHA256SUMS
```
