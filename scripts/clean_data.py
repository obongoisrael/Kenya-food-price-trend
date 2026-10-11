"""
Combine and clean the 10 county price files into one tidy dataset.

Cleaning steps
1. Stack all county files into one table
2. Standardise county and commodity names
3. Convert maize "90kg bag" prices to price per kg
4. Parse dates and price values
5. Remove duplicate rows
6. Fill missing prices by interpolating within each county + commodity series
7. Add year, month and a price index (Jan 2021 = 100)

Usage:
    python scripts/clean_data.py
Output:
    data/processed/food_prices_clean.csv
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_PATH = ROOT / "data" / "processed" / "food_prices_clean.csv"

COMMODITY_MAP = {
    "maize": "Maize", "maize (white)": "Maize",
    "beans": "Beans", "beans - rosecoco": "Beans",
    "rice": "Rice", "rice (pishori)": "Rice",
    "sugar": "Sugar",
    "wheat flour": "Wheat flour", "flour (wheat)": "Wheat flour",
    "cooking oil": "Cooking oil", "veg. oil": "Cooking oil",
    "potatoes": "Potatoes", "irish potatoes": "Potatoes",
    "milk": "Milk", "milk (fresh)": "Milk",
}


def main() -> None:
    frames = [pd.read_csv(f) for f in sorted(RAW_DIR.glob("*_prices.csv"))]
    df = pd.concat(frames, ignore_index=True)
    raw_rows = len(df)

    df.columns = ["date", "county", "commodity", "unit", "price_kes"]
    df["county"] = df["county"].str.strip().str.title()
    df["commodity"] = df["commodity"].str.strip().str.lower().map(COMMODITY_MAP)
    unmapped = df["commodity"].isna().sum()
    if unmapped:
        raise ValueError(f"{unmapped} rows have an unknown commodity name")

    df["date"] = pd.to_datetime(df["date"], format="%d/%m/%Y")
    df["price_kes"] = pd.to_numeric(df["price_kes"], errors="coerce")

    bag = df["unit"] == "90kg bag"
    df.loc[bag, "price_kes"] = df.loc[bag, "price_kes"] / 90
    df.loc[bag, "unit"] = "kg"

    dupes = df.duplicated(subset=["date", "county", "commodity"]).sum()
    df = df.drop_duplicates(subset=["date", "county", "commodity"])

    # Rebuild a full monthly grid so missing months show up as gaps, then interpolate
    months = pd.date_range(df["date"].min(), df["date"].max(), freq="MS")
    units = df.groupby("commodity")["unit"].first()
    grid = pd.MultiIndex.from_product(
        [months, sorted(df["county"].unique()), sorted(df["commodity"].unique())],
        names=["date", "county", "commodity"],
    )
    df = df.set_index(["date", "county", "commodity"]).reindex(grid).reset_index()
    missing = df["price_kes"].isna().sum()
    df = df.sort_values(["county", "commodity", "date"])
    df["price_kes"] = (
        df.groupby(["county", "commodity"])["price_kes"]
        .transform(lambda s: s.interpolate(limit_direction="both"))
        .round(2)
    )
    df["unit"] = df["commodity"].map(units)

    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    first = df[df["date"] == df["date"].min()].set_index(["county", "commodity"])["price_kes"]
    df["price_index"] = (
        df["price_kes"] / df.set_index(["county", "commodity"]).index.map(first) * 100
    ).round(1)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False, date_format="%Y-%m-%d")

    print(f"Raw rows read:          {raw_rows:,}")
    print(f"Duplicates removed:     {dupes}")
    print(f"Missing prices filled:  {missing}")
    print(f"Clean rows written:     {len(df):,} -> {OUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
