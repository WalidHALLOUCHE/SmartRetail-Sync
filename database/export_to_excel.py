"""
Export SmartRetail PostgreSQL data to an Excel .xlsx workbook.

This script intentionally uses only the Python standard library. It reads data
through the running Docker PostgreSQL container with psql and writes a minimal
multi-sheet XLSX file.
"""

from __future__ import annotations

import csv
import re
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape


ROOT_DIR = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT_DIR / "exports"
OUTPUT_FILE = EXPORT_DIR / "SmartRetail-PowerBI-Tables.xlsx"

SHEETS = [
    (
        "public_dim_dates",
        """
        SELECT *
        FROM dim_dates
        ORDER BY date_id
        """,
    ),
    (
        "public_dim_inventory",
        """
        SELECT *
        FROM dim_inventory
        ORDER BY inventory_id
        """,
    ),
    (
        "public_dim_products",
        """
        SELECT *
        FROM dim_products
        ORDER BY product_id
        """,
    ),
    (
        "public_dim_stores",
        """
        SELECT *
        FROM dim_stores
        ORDER BY store_id
        """,
    ),
    (
        "public_vw_inventory_alerts",
        """
        SELECT *
        FROM vw_inventory_alerts
        ORDER BY stock_level ASC
        """,
    ),
    (
        "public_vw_sales_summary",
        """
        SELECT *
        FROM vw_sales_summary
        ORDER BY full_date DESC, product_name
        """,
    ),
]


def run_query(query: str) -> tuple[list[str], list[list[str]]]:
    command = [
        "docker-compose",
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        "smartretail_user",
        "-d",
        "smartretail_db",
        "--csv",
        "-c",
        " ".join(query.split()),
    ]
    result = subprocess.run(
        command,
        cwd=ROOT_DIR,
        text=True,
        capture_output=True,
        check=True,
    )
    reader = csv.reader(result.stdout.splitlines())
    rows = list(reader)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def column_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?$")


def is_number(value: str) -> bool:
    return bool(NUMBER_RE.match(value)) and not value.startswith("0")


def cell_xml(row_index: int, column_index: int, value: str, header: bool = False) -> str:
    cell_ref = f"{column_name(column_index)}{row_index}"
    if value is None:
        value = ""
    value = str(value)

    if not header and is_number(value):
        return f'<c r="{cell_ref}"><v>{value}</v></c>'

    style = ' s="1"' if header else ""
    return (
        f'<c r="{cell_ref}" t="inlineStr"{style}>'
        f"<is><t>{escape(value)}</t></is>"
        f"</c>"
    )


def sheet_xml(headers: list[str], rows: list[list[str]]) -> str:
    xml_rows = []
    header_cells = "".join(
        cell_xml(1, column_index, header, header=True)
        for column_index, header in enumerate(headers)
    )
    xml_rows.append(f'<row r="1">{header_cells}</row>')

    for row_number, row in enumerate(rows, start=2):
        cells = "".join(
            cell_xml(row_number, column_index, value)
            for column_index, value in enumerate(row)
        )
        xml_rows.append(f'<row r="{row_number}">{cells}</row>')

    column_defs = "".join(
        f'<col min="{index}" max="{index}" width="20" customWidth="1"/>'
        for index in range(1, len(headers) + 1)
    )

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <cols>{column_defs}</cols>
  <sheetData>{''.join(xml_rows)}</sheetData>
</worksheet>
"""


def workbook_xml(sheet_names: Iterable[str]) -> str:
    sheets_xml = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>{sheets_xml}</sheets>
</workbook>
"""


def workbook_rels_xml(sheet_count: int) -> str:
    rels = "".join(
        f'<Relationship Id="rId{index}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    rels += (
        f'<Relationship Id="rId{sheet_count + 1}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        f'Target="styles.xml"/>'
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {rels}
</Relationships>
"""


def content_types_xml(sheet_count: int) -> str:
    sheets = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
  {sheets}
</Types>
"""


def root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
                Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
                Target="xl/workbook.xml"/>
</Relationships>
"""


def styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/></font>
    <font><b/><sz val="11"/><name val="Calibri"/></font>
  </fonts>
  <fills count="2">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
  </fills>
  <borders count="1"><border/></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>
  </cellXfs>
</styleSheet>
"""


def main() -> None:
    EXPORT_DIR.mkdir(exist_ok=True)
    loaded_sheets = []

    for sheet_name, query in SHEETS:
        headers, rows = run_query(query)
        loaded_sheets.append((sheet_name, headers, rows))

    with zipfile.ZipFile(OUTPUT_FILE, "w", zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", content_types_xml(len(loaded_sheets)))
        workbook.writestr("_rels/.rels", root_rels_xml())
        workbook.writestr("xl/workbook.xml", workbook_xml(sheet[0] for sheet in loaded_sheets))
        workbook.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml(len(loaded_sheets)))
        workbook.writestr("xl/styles.xml", styles_xml())

        for index, (_, headers, rows) in enumerate(loaded_sheets, start=1):
            workbook.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(headers, rows))

    print(f"Created {OUTPUT_FILE}")
    print(f"Exported at {datetime.now().isoformat(timespec='seconds')}")
    for sheet_name, _, rows in loaded_sheets:
        print(f"- {sheet_name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
