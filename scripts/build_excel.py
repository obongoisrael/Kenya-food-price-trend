"""
Build the interactive Excel workbook from the clean data.

Every summary number is a live formula (AVERAGEIFS / RANK / INDEX-MATCH) that reads the
Data sheet, and the County and Trend sheets have dropdowns to switch commodity and year.

Usage:
    python scripts/build_excel.py
Output:
    excel/kenya_food_prices.xlsx
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "food_prices_clean.csv"
OUT = ROOT / "excel" / "kenya_food_prices.xlsx"

FONT = "Arial"
HEAD_FILL = PatternFill("solid", start_color="1F4E5A")
INPUT_FILL = PatternFill("solid", start_color="FFF2CC")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def font(**kw):
    return Font(name=FONT, **kw)


def header_row(ws, row, values, start_col=1):
    for i, v in enumerate(values):
        c = ws.cell(row=row, column=start_col + i, value=v)
        c.font = font(bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX


def title(ws, text, subtitle):
    ws["A1"] = text
    ws["A1"].font = font(bold=True, size=14, color="1F4E5A")
    ws["A2"] = subtitle
    ws["A2"].font = font(italic=True, size=9, color="595959")


def main() -> None:
    df = pd.read_csv(SRC, parse_dates=["date"])
    commodities = sorted(df["commodity"].unique())
    counties = sorted(df["county"].unique())
    years = sorted(df["year"].unique())
    months = sorted(df["date"].unique())
    n = len(df) + 1  # last data row

    wb = Workbook()

    # ---------------- Data ----------------
    data = wb.active
    data.title = "Data"
    cols = ["date", "county", "commodity", "unit", "price_kes", "year", "month", "price_index"]
    data.append(cols)
    for r in df[cols].itertuples(index=False):
        data.append([r.date.to_pydatetime(), *r[1:]])
    for row in data.iter_rows(min_row=2, min_col=1, max_col=1):
        row[0].number_format = "yyyy-mm-dd"
    for row in data.iter_rows(min_row=2, min_col=5, max_col=5):
        row[0].number_format = "#,##0.00"
    tbl = Table(displayName="Prices", ref=f"A1:H{n}")
    tbl.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    data.add_table(tbl)
    for i, w in enumerate([12, 14, 14, 8, 12, 8, 8, 12], 1):
        data.column_dimensions[get_column_letter(i)].width = w
    data.freeze_panes = "A2"

    rng = lambda col: f"Data!${col}$2:${col}${n}"  # noqa: E731
    PRICE, COUNTY, COMM, YEAR, DATE = rng("E"), rng("B"), rng("C"), rng("F"), rng("A")

    # ---------------- Lists (dropdown sources) ----------------
    lists = wb.create_sheet("Lists")
    lists["A1"], lists["B1"] = "Commodity", "Year"
    for i, c in enumerate(commodities, 2):
        lists.cell(row=i, column=1, value=c)
    for i, y in enumerate(years, 2):
        lists.cell(row=i, column=2, value=str(y))
    lists.sheet_state = "hidden"
    comm_list = f"=Lists!$A$2:$A${len(commodities) + 1}"
    year_list = f"=Lists!$B$2:$B${len(years) + 1}"

    # ---------------- Annual Averages ----------------
    ann = wb.create_sheet("Annual Averages", 0)
    title(ann, "Average national food prices by year (KES)",
          "All 10 counties averaged. Every value is an AVERAGEIFS formula on the Data sheet.")
    hdr = ["Commodity", "Unit"] + [str(y) for y in years] + [f"Change {years[0]}–{years[-1]}", "Peak year"]
    header_row(ann, 4, hdr)
    units = df.groupby("commodity")["unit"].first()
    first_col = 3
    last_col = first_col + len(years) - 1
    for r, c in enumerate(commodities, 5):
        ann.cell(row=r, column=1, value=c).font = font(bold=True)
        ann.cell(row=r, column=2, value=units[c]).font = font()
        for j, y in enumerate(years):
            cell = ann.cell(row=r, column=first_col + j,
                            value=f'=AVERAGEIFS({PRICE},{COMM},$A{r},{YEAR},{y})')
            cell.number_format = "#,##0"
            cell.font = font()
        a, b = get_column_letter(first_col), get_column_letter(last_col)
        chg = ann.cell(row=r, column=last_col + 1, value=f"={b}{r}/{a}{r}-1")
        chg.number_format = "+0.0%;-0.0%;0.0%"
        chg.font = font()
        peak = ann.cell(row=r, column=last_col + 2,
                        value=f"=INDEX(${a}$4:${b}$4,MATCH(MAX({a}{r}:{b}{r}),{a}{r}:{b}{r},0))")
        peak.font = font()
        peak.alignment = Alignment(horizontal="center")
        for col in range(1, last_col + 3):
            ann.cell(row=r, column=col).border = BOX
    end_r = 4 + len(commodities)
    ann.conditional_formatting.add(
        f"{get_column_letter(first_col)}5:{get_column_letter(last_col)}{end_r}",
        ColorScaleRule(start_type="min", start_color="FFFFFF", end_type="max", end_color="F4B183"),
    )
    ann.column_dimensions["A"].width = 16
    ann.column_dimensions["B"].width = 8
    for col in range(first_col, last_col + 3):
        ann.column_dimensions[get_column_letter(col)].width = 12
    ann.cell(row=end_r + 2, column=1,
             value="Colour scale: darker = higher price within the table.").font = font(size=9, italic=True)

    # ---------------- County Comparison ----------------
    cty = wb.create_sheet("County Comparison", 1)
    title(cty, "County price comparison",
          "Pick a commodity and year in the yellow cells. The table and chart update automatically.")
    cty["A4"], cty["A5"] = "Commodity", "Year"
    cty["B4"], cty["B5"] = "Maize", str(years[-1])
    for ref in ("A4", "A5"):
        cty[ref].font = font(bold=True)
    for ref in ("B4", "B5"):
        cty[ref].fill = INPUT_FILL
        cty[ref].font = font(bold=True, color="0000FF")
        cty[ref].border = BOX
    dv1 = DataValidation(type="list", formula1=comm_list, allow_blank=False)
    dv2 = DataValidation(type="list", formula1=year_list, allow_blank=False)
    cty.add_data_validation(dv1)
    cty.add_data_validation(dv2)
    dv1.add("B4")
    dv2.add("B5")
    cty["A6"] = "National average"
    cty["A6"].font = font(bold=True)
    cty["B6"] = f"=AVERAGEIFS({PRICE},{COMM},$B$4,{YEAR},VALUE($B$5))"
    cty["B6"].number_format = "#,##0.00"
    cty["B6"].font = font(bold=True)

    header_row(cty, 8, ["County", "Avg price (KES)", "vs national avg", "Rank (1 = cheapest)"])
    first, last = 9, 8 + len(counties)
    for r, c in enumerate(counties, first):
        cty.cell(row=r, column=1, value=c).font = font()
        p = cty.cell(row=r, column=2,
                     value=f'=AVERAGEIFS({PRICE},{COMM},$B$4,{YEAR},VALUE($B$5),{COUNTY},$A{r})')
        p.number_format = "#,##0.00"
        d = cty.cell(row=r, column=3, value=f"=B{r}/$B$6-1")
        d.number_format = "+0.0%;-0.0%;0.0%"
        k = cty.cell(row=r, column=4, value=f"=RANK(B{r},$B${first}:$B${last},1)")
        k.alignment = Alignment(horizontal="center")
        for col in range(1, 5):
            cty.cell(row=r, column=col).border = BOX
            cty.cell(row=r, column=col).font = font()
    cty.conditional_formatting.add(
        f"C{first}:C{last}",
        ColorScaleRule(start_type="min", start_color="63BE7B", mid_type="num", mid_value=0,
                       mid_color="FFFFFF", end_type="max", end_color="F8696B"),
    )
    for col, w in zip("ABCD", [18, 16, 16, 18]):
        cty.column_dimensions[col].width = w

    bar = BarChart()
    bar.type = "bar"
    bar.title = "Average price by county"
    bar.y_axis.title = "KES"
    bar.add_data(Reference(cty, min_col=2, min_row=8, max_row=last), titles_from_data=True)
    bar.set_categories(Reference(cty, min_col=1, min_row=first, max_row=last))
    bar.legend = None
    bar.height, bar.width = 9, 15
    cty.add_chart(bar, "F4")

    # ---------------- Monthly Trend ----------------
    tr = wb.create_sheet("Monthly Trend", 2)
    title(tr, "Monthly price trend",
          "Pick a commodity and up to two counties in the yellow cells to compare with the national average.")
    labels = ["Commodity", "County 1", "County 2"]
    defaults = ["Maize", "Nairobi", "Turkana"]
    county_dv = DataValidation(type="list", formula1='"' + ",".join(counties) + '"')
    tr.add_data_validation(county_dv)
    comm_dv = DataValidation(type="list", formula1=comm_list)
    tr.add_data_validation(comm_dv)
    for i, (lab, val) in enumerate(zip(labels, defaults), 4):
        tr.cell(row=i, column=1, value=lab).font = font(bold=True)
        c = tr.cell(row=i, column=2, value=val)
        c.fill = INPUT_FILL
        c.font = font(bold=True, color="0000FF")
        c.border = BOX
        (comm_dv if i == 4 else county_dv).add(c.coordinate)

    header_row(tr, 8, ["Month", "National avg", "County 1", "County 2"])
    tr["C8"] = "=B5"
    tr["D8"] = "=B6"
    for ref in ("C8", "D8"):
        tr[ref].font = font(bold=True, color="FFFFFF")
    t_first = 9
    for r, m in enumerate(months, t_first):
        dc = tr.cell(row=r, column=1, value=pd.Timestamp(m).to_pydatetime())
        dc.number_format = "mmm yyyy"
        tr.cell(row=r, column=2, value=f"=AVERAGEIFS({PRICE},{COMM},$B$4,{DATE},$A{r})")
        tr.cell(row=r, column=3, value=f"=AVERAGEIFS({PRICE},{COMM},$B$4,{DATE},$A{r},{COUNTY},$B$5)")
        tr.cell(row=r, column=4, value=f"=AVERAGEIFS({PRICE},{COMM},$B$4,{DATE},$A{r},{COUNTY},$B$6)")
        for col in range(1, 5):
            tr.cell(row=r, column=col).font = font()
            tr.cell(row=r, column=col).border = BOX
            if col > 1:
                tr.cell(row=r, column=col).number_format = "#,##0.00"
    t_last = t_first + len(months) - 1
    for col, w in zip("ABCD", [14, 14, 14, 14]):
        tr.column_dimensions[col].width = w
    tr.freeze_panes = "A9"

    line = LineChart()
    line.title = "Monthly price (KES)"
    line.y_axis.title = "KES"
    line.add_data(Reference(tr, min_col=2, max_col=4, min_row=8, max_row=t_last), titles_from_data=True)
    line.set_categories(Reference(tr, min_col=1, min_row=t_first, max_row=t_last))
    line.x_axis.number_format = "mmm yy"
    line.height, line.width = 10, 22
    tr.add_chart(line, "F4")

    # ---------------- About ----------------
    about = wb.create_sheet("About", 0)
    title(about, "Kenya Food Price Trends, 2021–2025", "Workbook guide")
    notes = [
        ("Sheet", "What it shows"),
        ("Annual Averages", "National average price per commodity for each year, change over 5 years and the peak year."),
        ("County Comparison", "Pick a commodity and year to rank all 10 counties and compare them with the national average."),
        ("Monthly Trend", "Pick a commodity and two counties to chart 60 months of prices against the national average."),
        ("Data", "4,800 clean rows: 10 counties × 8 commodities × 60 months (output of scripts/clean_data.py)."),
        ("", ""),
        ("Yellow cells", "Inputs you can change (dropdowns). Everything else is calculated by formulas."),
        ("Data note", "Prices are synthetic, generated by scripts/generate_data.py to mimic real market patterns. "
                      "Replace the Data sheet with WFP / KNBS figures for a real-data version."),
    ]
    for i, (a, b) in enumerate(notes, 4):
        about.cell(row=i, column=1, value=a).font = font(bold=(i == 4 or a != ""))
        about.cell(row=i, column=2, value=b).font = font(bold=(i == 4))
        about.cell(row=i, column=2).alignment = Alignment(wrap_text=True, vertical="top")
    header_row(about, 4, ["Sheet", "What it shows"])
    about["A10"].fill = INPUT_FILL
    about.column_dimensions["A"].width = 20
    about.column_dimensions["B"].width = 90

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"Saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
