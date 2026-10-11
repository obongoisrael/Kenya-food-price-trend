# Tableau Dashboard Guide

Build an interactive version in **Tableau Public** (free) from `data/processed/food_prices_clean.csv`,
then publish it and add the link to the README.

## Sheets to build
| Sheet | Setup |
| --- | --- |
| **Price trend** | Columns: `MONTH(date)` (continuous) · Rows: `AVG(price_index)` · Colour: `commodity` |
| **County map** | Double-click `county` (set Geographic Role → County, Country = Kenya) · Colour: `AVG(price_kes)` |
| **County ranking** | Rows: `county` · Columns: `AVG(price_kes)` · sort descending |
| **Seasonality** | Columns: `MONTH(date)` (discrete) · Rows: `AVG(price_index)` · filter `commodity` = Maize |

## Calculated field
```
// Change vs 2021 average
(AVG([price_kes]) - { FIXED [commodity], [county] : AVG(IF YEAR([date]) = 2021 THEN [price_kes] END) })
/ { FIXED [commodity], [county] : AVG(IF YEAR([date]) = 2021 THEN [price_kes] END) }
```

## Dashboard
1. Add filters for `commodity` (single-value dropdown) and `year` (slider), applied to all sheets.
2. Use the county map as a filter: click a county to update the trend line.
3. Title: *"Kenya Food Prices 2021–2025: the 2023 shock and the cost of living in remote counties"*.
4. Publish to Tableau Public and paste the link into the README.
