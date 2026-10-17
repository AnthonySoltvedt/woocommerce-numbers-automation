from pathlib import Path

WORKBOOK = Path(__file__).resolve().parent / "TrimTray_Import_Test.numbers"

EXPECTED_HEADERS = [
    "Name ", "Quantity", "Sale Price",
    "Sale Price (After Fees)", "Profit", "Company ",
    "Location", "Address", "Chair 1", "Chair 2",
    "Chair 3", "Chair 4", "Not Started",
    "Printing", "Printed ", "Shipped", "Order ID",
]

def create_monthly_table(month):
    """Create a new monthly table after validating the template."""
    if not WORKBOOK.exists():
        raise FileNotFoundError("Test workbook not found.")

    print(f"Monthly table requested: {month}")
    print("Template: November 2026")
    print("Workbook:", WORKBOOK.name)
    print("Next: implement safe AppleScript table creation.")

if __name__ == "__main__":
    print("Monthly table creation module ready.")

import subprocess

def list_monthly_tables():
    script = '''
tell application "Numbers"
    get name of every table of sheet "ORDERS ID" of document "TrimTray_Import_Test.numbers"
end tell
'''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Numbers AppleScript failed: {result.stderr.strip()}")
    return [name.strip() for name in result.stdout.strip().split(",") if name.strip()]

print("Existing monthly tables:", list_monthly_tables())
print("December 2026 exists:", "December 2026" in list_monthly_tables())

def create_new_month(month):
    """Create an empty monthly table in the TEST workbook only."""
    from datetime import datetime

    try:
        parsed = datetime.strptime(month, "%B %Y")
        if parsed.strftime("%B %Y") != month:
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Invalid month. Example: January 2027")
    if month in list_monthly_tables():
        print(f"SKIPPED: {month} already exists.")
        return

    script = '''
on run argv
    set monthName to item 1 of argv
tell application "Numbers"
    set doc to document "TrimTray_Import_Test.numbers"
    set targetSheet to sheet "ORDERS ID" of doc
    set templateTable to table "November 2026" of targetSheet

    if (row count of templateTable) is not 2 or (column count of templateTable) is not 17 then
        error "STOPPED: November template has unexpected dimensions."
    end if

    tell targetSheet
        set newTable to make new table with properties {name:"" & monthName}
    end tell
    set row count of newTable to 2
    set column count of newTable to 17
    set header row count of newTable to 1

    repeat with c from 1 to 17
        set value of cell c of row 1 of newTable to value of cell c of row 1 of templateTable
    end repeat

    set value of cell 1 of row 2 of newTable to "TOTALS"
    set value of cell 2 of row 2 of newTable to 0
    set value of cell 3 of row 2 of newTable to 0
    set value of cell 4 of row 2 of newTable to 0

    save doc
end tell
end run
'''
    result = subprocess.run(
        ["osascript", "-e", script, month],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    print(f"CREATED: {month}")
