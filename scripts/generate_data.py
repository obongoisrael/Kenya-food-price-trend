"""
Generate synthetic monthly retail food prices for 10 Kenyan counties (Jan 2021 – Dec 2025).

The numbers are simulated, not official statistics. They follow realistic patterns:
a national price surge in 2022–2023 (drought and global supply shocks), easing in 2024,
seasonal maize peaks before harvest, and higher prices in remote counties.

The raw files are deliberately messy, as market data often is: one file per county,
inconsistent commodity names and units, some missing months and blank prices.
scripts/clean_data.py fixes all of this.

Usage:
    python scripts/generate_data.py
Output:
    data/raw/<county>_prices.csv  (10 files)
"""
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 7
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

# county -> price premium vs national average (remote counties cost more)
COUNTIES = {
    "Nairobi": 1.00, "Mombasa": 1.04, "Kisumu": 0.98, "Nakuru": 0.94, "Uasin Gishu": 0.90,
    "Kakamega": 0.95, "Nyeri": 0.97, "Kitui": 1.06, "Garissa": 1.18, "Turkana": 1.30,
}

# commodity -> (base price KES in Jan 2021, unit, seasonal amplitude)
COMMODITIES = {
    "Maize": (48, "kg", 0.12),
    "Beans": (115, "kg", 0.06),
    "Rice": (130, "kg", 0.02),
    "Sugar": (115, "kg", 0.02),
    "Wheat flour": (105, "kg", 0.01),
    "Cooking oil": (230, "litre", 0.01),
    "Potatoes": (50, "kg", 0.10),
    "Milk": (55, "litre", 0.05),
}

# extra shock multiplier on top of the general trend
SHOCK = {"Sugar": 0.45, "Cooking oil": 0.30, "Maize": 0.35, "Wheat flour": 0.25}

# messy name variants used in the raw files
NAME_VARIANTS = {
    "Maize": ["Maize", "maize (white)", "MAIZE"],
    "Beans": ["Beans", "beans - rosecoco", "Beans "],
    "Rice": ["Rice", "rice (pishori)"],
    "Sugar": ["Sugar", "SUGAR", "sugar"],
    "Wheat flour": ["Wheat flour", "wheat Flour", "Flour (wheat)"],
    "Cooking oil": ["Cooking oil", "Cooking Oil", "veg. oil"],
    "Potatoes": ["Potatoes", "Irish potatoes", "potatoes"],
    "Milk": ["Milk", "milk (fresh)"],
}


def national_trend(months: pd.DatetimeIndex) -> np.ndarray:
    """General price level: steady rise, surge mid-2022 to mid-2023, easing in 2024."""
    t = np.arange(len(months))
    base = 1 + 0.004 * t
    surge = 0.28 * np.exp(-((t - 26) / 7.5) ** 2)  # peaks around Mar 2023
    return base + surge


def main() -> None:
    rng = np.random.default_rng(SEED)
    months = pd.date_range("2021-01-01", "2025-12-01", freq="MS")
    trend = national_trend(months)
    t = np.arange(len(months))
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for county, premium in COUNTIES.items():
        rows = []
        for commodity, (base, unit, amp) in COMMODITIES.items():
            shock = 1 + SHOCK.get(commodity, 0.10) * np.exp(-((t - 27) / 6.5) ** 2)
            # maize and potatoes peak in May–June before the long-rains harvest
            season = 1 + amp * np.cos(2 * np.pi * (months.month - 6) / 12)
            noise = rng.normal(1, 0.03, len(months))
            prices = base * premium * trend * shock * season * noise
            for m, p in zip(months, prices):
                name = rng.choice(NAME_VARIANTS[commodity])
                price, unit_out = p, unit
                # some markets report maize per 90 kg bag
                if commodity == "Maize" and county in ("Uasin Gishu", "Nakuru") and rng.random() < 0.5:
                    price, unit_out = p * 90, "90kg bag"
                rows.append({
                    "Date": m.strftime("%d/%m/%Y"),
                    "County": county.upper() if rng.random() < 0.1 else county,
                    "Commodity": name,
                    "Unit": unit_out,
                    "Price (KES)": round(price, 2),
                })
        df = pd.DataFrame(rows)
        # real-world mess: dropped rows, blank prices, a duplicated row
        df = df.drop(df.sample(frac=0.02, random_state=int(rng.integers(1e6))).index)
        blank = df.sample(frac=0.01, random_state=int(rng.integers(1e6))).index
        df["Price (KES)"] = df["Price (KES)"].astype(object)
        df.loc[blank, "Price (KES)"] = ""
        df = pd.concat([df, df.sample(3, random_state=1)])
        fname = county.lower().replace(" ", "_") + "_prices.csv"
        df.to_csv(RAW_DIR / fname, index=False)

    print(f"Wrote {len(COUNTIES)} county files to {RAW_DIR}")


if __name__ == "__main__":
    main()
