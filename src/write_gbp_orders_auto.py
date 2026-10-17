
import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

import requests
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent

NUMBERS_FILE = PROJECT_DIR / "TrimTray_Import_Test.numbers"
ENV_FILE = PROJECT_DIR / ".env"

SHEET_NAME = "ORDERS ID"
TABLE_NAME = "October 2026"  # Default for now


def get_table_name(order):
    """Return the monthly Numbers table for a WooCommerce order."""
    return order["month"]

# Row 18 currently contains your totals.
TOTALS_ROW = 18

load_dotenv(ENV_FILE)

WOOCOMMERCE_URL = os.getenv("WOOCOMMERCE_URL", "").rstrip("/")
CONSUMER_KEY = os.getenv("WOOCOMMERCE_CONSUMER_KEY", "")
CONSUMER_SECRET = os.getenv("WOOCOMMERCE_CONSUMER_SECRET", "")


# ============================================================
# HELPERS
# ============================================================

def normalise_order_id(value):
    """Make 990, 990.0 and '990' compare as the same ID."""
    if value is None:
        return ""

    text = str(value).strip()

    if not text or text.lower() in {"none", "missing value"}:
        return ""

    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except ValueError:
        pass

    return text


def run_applescript(script, arguments=None):
    """Execute AppleScript and return its output."""
    command = ["osascript", "-e", script]

    if arguments:
        command.extend(str(arg) for arg in arguments)

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(details or "AppleScript failed.")

    return result.stdout.strip()


def read_numbers(table_name=TABLE_NAME):
    """Read IDs, row count and the current table structure."""
    script = r'''
on run argv
    tell application "Numbers"
        set doc to document "TrimTray_Import_Test.numbers"
        set t to table (item 2 of argv) of sheet "ORDERS ID" of doc

        set outputText to "ROWCOUNT|" & (count of rows of t)

        repeat with r from 2 to (count of rows of t)
            set v to value of cell 17 of row r of t
            set idText to ""

            if v is not missing value then
                set idText to v as text
            end if

            set outputText to outputText & linefeed & ¬
                "ID|" & r & "|" & idText
        end repeat

        return outputText
    end tell
end run
'''

    output = run_applescript(script, [str(NUMBERS_FILE), table_name])

    row_count = 0
    existing_ids = set()

    for line in output.splitlines():
        parts = line.split("|")

        if len(parts) >= 2 and parts[0] == "ROWCOUNT":
            row_count = int(parts[1])

        elif len(parts) >= 3 and parts[0] == "ID":
            order_id = normalise_order_id(parts[2])
            if order_id:
                existing_ids.add(order_id)


    return existing_ids, row_count



def find_totals_row(table_name=TABLE_NAME):
    """Find the TOTALS row in the test Numbers spreadsheet."""
    script = r"""
    on run argv
    tell application "Numbers"
    set t to table (item 1 of argv) of sheet "ORDERS ID" of document "TrimTray_Import_Test.numbers"
    set matches to {}

    repeat with r from 2 to (count of rows of t)
        set v to value of cell 1 of row r of t

        if v is not missing value then
            if (v as text) is "TOTALS" then
                set end of matches to r
            end if
        end if
    end repeat

    if (count of matches) is not 1 then
        error "Expected exactly one TOTALS row."
    end if

        return item 1 of matches
end tell
end run
"""

    result = run_applescript(script, [table_name])
    return int(result.strip())


def fetch_gbp_orders():
    """Fetch recent WooCommerce orders and filter for GBP."""
    endpoint = f"{WOOCOMMERCE_URL}/wp-json/wc/v3/orders"

    orders = []
    page = 1

    while True:
        response = requests.get(
            endpoint,
            auth=(CONSUMER_KEY, CONSUMER_SECRET),
            params={
                "per_page": 100,
                "page": page,
                "orderby": "date",
                "order": "desc",
            },
            timeout=30,
        )

        response.raise_for_status()
        batch = response.json()

        if not isinstance(batch, list):
            raise RuntimeError("Unexpected response from WooCommerce.")

        orders.extend(batch)
        print(f"  Page {page}: fetched {len(batch)} orders")

        if len(batch) < 100:
            break

        page += 1

    gbp_orders = []

    for order in orders:
        if str(order.get("currency", "")).upper() != "GBP":
            continue

        if order.get("status") not in ("processing", "completed"):
            continue

        if order.get("refunds"):
            continue

        order_id = normalise_order_id(order.get("id"))
        if not order_id:
            continue

        billing = order.get("billing") or {}

        first = (billing.get("first_name") or "").strip()
        last = (billing.get("last_name") or "").strip()
        customer_name = f"{first} {last}".strip()

        if not customer_name:
            customer_name = "WooCommerce Customer"

        items = order.get("line_items") or []

        quantity = sum(
            int(item.get("quantity") or 0)
            for item in items
        )

        price = float(order.get("total") or 0)

        fee_values = [
            item.get("value")
            for item in (order.get("meta_data") or [])
            if item.get("key") == "_wcpay_transaction_fee"
        ]

        fee = (
            float(fee_values[0])
            if fee_values and fee_values[0] not in (None, "")
            else None
        )

        from datetime import datetime

        created = order.get("date_created")
        if not created:
            raise RuntimeError(f"Order {order_id} has no creation date.")

        order_month = datetime.fromisoformat(created).strftime("%B %Y")

        gbp_orders.append({
            "id": order_id,
            "name": customer_name,
            "quantity": quantity,
            "price": price,
            "fee": fee,
            "month": order_month,
        })

    return gbp_orders


def create_backup():
    """Back up the Numbers file before modifying it."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_path = PROJECT_DIR / (
        f"TrimTray_Import_Test_Backup_{timestamp}.numbers"
    )

    if NUMBERS_FILE.is_dir():
        shutil.copytree(NUMBERS_FILE, backup_path)
    else:
        shutil.copy2(NUMBERS_FILE, backup_path)

    print(f"Backup created: {backup_path.name}")
    return backup_path


def insert_rows_and_write(orders, totals_row, table_name=TABLE_NAME):
    """
    Insert rows above the totals row, then write new orders.

    Original totals row is shifted down by Numbers when rows
    are inserted above it.
    """
    script = r'''
on run argv
    set filePath to item 1 of argv
    set totalsRow to (item 2 of argv) as integer
    set orderCount to ((count of argv) - 3) div 5

    tell application "Numbers"
        set doc to document "TrimTray_Import_Test.numbers"
        set t to table (item 3 of argv) of sheet "ORDERS ID" of doc

        -- Add space immediately above the existing totals row.
        repeat with i from 1 to orderCount
            add row above row totalsRow of t
        end repeat

        -- Write each new order into the inserted rows.
        repeat with i from 1 to orderCount
            set argIndex to 4 + ((i - 1) * 5)
            set targetRow to totalsRow - 1 + i

            set orderID to item argIndex of argv
            set customerName to item (argIndex + 1) of argv
            set quantityText to item (argIndex + 2) of argv
            set priceText to item (argIndex + 3) of argv
            set afterFeesText to item (argIndex + 4) of argv

            set value of cell 1 of row targetRow of t to customerName
            set value of cell 2 of row targetRow of t to ¬
                (quantityText as number)
            set value of cell 3 of row targetRow of t to ¬
                (priceText as number)
            if afterFeesText is not "" then
                set value of cell 4 of row targetRow of t to ¬
                    (afterFeesText as number)
            end if
            set value of cell 17 of row targetRow of t to ¬
                (orderID as number)
        end repeat

        -- Update the totals formulas to include every order.
        set newTotalsRow to totalsRow + orderCount
        set lastOrderRow to newTotalsRow - 1

        set value of cell 2 of row newTotalsRow of t to ¬
            "=SUM(B2:B" & lastOrderRow & ")"
        set value of cell 3 of row newTotalsRow of t to ¬
            "=SUM(C2:C" & lastOrderRow & ")"
        set value of cell 4 of row newTotalsRow of t to ¬
            "=SUM(D2:D" & lastOrderRow & ")"

        save doc
    end tell

    return "WRITE_COMPLETE"
end run
'''

    arguments = [str(NUMBERS_FILE), str(totals_row), table_name]

    for order in orders:
        arguments.extend([
            order["id"],
            order["name"],
            str(order["quantity"]),
            f'{order["price"]:.2f}',
            (
                f'{order["price"] - order["fee"]:.2f}'
                if order["fee"] is not None
                else ""
            ),
        ])

    result = run_applescript(script, arguments)

    if "WRITE_COMPLETE" not in result:
        raise RuntimeError(
            "Numbers did not confirm that the write completed."
        )


def verify_import(orders, table_name=TABLE_NAME):
    """Verify all four fields for each imported order."""
    import subprocess

    script = r"""
    on run argv
    tell application "Numbers"
    set t to table (item 1 of argv) of sheet "ORDERS ID" of document "TrimTray_Import_Test.numbers"
    set outputText to ""

    repeat with r from 2 to (row count of t)
        set orderID to value of cell 17 of row r of t

        if orderID is not missing value then
            set customerName to value of cell 1 of row r of t
            set qty to value of cell 2 of row r of t
            set price to value of cell 3 of row r of t
            set afterFees to value of cell 4 of row r of t

            set outputText to outputText & (orderID as text) & tab

            if customerName is missing value then
                set outputText to outputText & "MISSING"
            else
                set outputText to outputText & (customerName as text)
            end if

            set outputText to outputText & tab

            if qty is missing value then
                set outputText to outputText & "MISSING"
            else
                set outputText to outputText & (qty as text)
            end if

            set outputText to outputText & tab

            if price is missing value then
                set outputText to outputText & "MISSING"
            else
                set outputText to outputText & (price as text)
            end if

            set outputText to outputText & tab
            if afterFees is missing value then
                set outputText to outputText & "MISSING"
            else
                set outputText to outputText & (afterFees as text)
            end if

            set outputText to outputText & linefeed
        end if
    end repeat

        return outputText
end tell
end run
"""

    result = subprocess.run(
        ["osascript", "-e", script, table_name],
        capture_output=True,
        text=True,
        check=True,
    )

    found = {}

    for line in result.stdout.splitlines():
        parts = line.split("\t")

        if len(parts) == 5:
            order_id = str(int(float(parts[0])))
            if order_id in found:
                raise RuntimeError(f"Duplicate order ID {order_id} in Numbers")
            found[order_id] = parts[1:]

    for order in orders:
        order_id = str(order["id"])

        if order_id not in found:
            raise RuntimeError(f"Order {order_id}: missing from Numbers")

        name, qty, price, after_fees = found[order_id]

        if name != str(order["name"]):
            raise RuntimeError(f"Order {order_id}: customer name mismatch")

        if qty == "MISSING" or int(float(qty)) != int(order["quantity"]):
            raise RuntimeError(f"Order {order_id}: quantity mismatch")

        if price == "MISSING" or abs(float(price) - float(order["price"])) > 0.01:
            raise RuntimeError(f"Order {order_id}: sale price mismatch")

        if order["fee"] is not None:
            expected = round(order["price"] - order["fee"], 2)
            if after_fees == "MISSING" or abs(float(after_fees) - expected) > 0.01:
                raise RuntimeError(f"Order {order_id}: after-fees amount mismatch")
        elif after_fees != "MISSING":
            raise RuntimeError(f"Order {order_id}: unexpected after-fees value")

    print(f"Verification passed: all five fields checked for {len(orders)} orders.")


# ============================================================
# MAIN
# ============================================================

from create_monthly_table_test import create_new_month, list_monthly_tables

def main():
    print("\nTrimTray WooCommerce → Apple Numbers")
    print("=" * 42)

    if not NUMBERS_FILE.exists():
        raise RuntimeError(f"Numbers file not found: {NUMBERS_FILE}")

    if not WOOCOMMERCE_URL or not CONSUMER_KEY or not CONSUMER_SECRET:
        raise RuntimeError(
            "WooCommerce settings are missing from .env. "
            "Check the variable names; do not share your credentials."
        )

    print("\nFetching GBP orders...")
    orders = fetch_gbp_orders()
    print(f"GBP orders fetched: {len(orders)}")

    if not orders:
        print("No GBP orders found. Nothing to import.")
        return

    print("\nReading existing order IDs from Numbers...")
    existing_ids = set()
    row_count = 0

    available_months = set(list_monthly_tables())

    for month in sorted(available_months):
        month_ids, month_rows = read_numbers(month)
        existing_ids.update(month_ids)
        print(f"{month}: {len(month_ids)} existing order IDs")

    print(f"Numbers table rows: {row_count}")
    print(f"Existing order IDs found: {len(existing_ids)}")

    new_orders = [
        order for order in orders
        if order["id"] not in existing_ids
    ]

    print("\nDuplicate check:")
    for order in orders:
        if order["id"] in existing_ids:
            print(f'  SKIP duplicate: Order {order["id"]}')
        else:
            print(f'  NEW order:      Order {order["id"]}')

    if not new_orders:
        print("\nNothing to import. All fetched GBP orders already exist.")
        print("No changes made.")
        return

    # Identify monthly tables that need creating.
    required_months = {get_table_name(order) for order in new_orders}
    missing_months = sorted(required_months - available_months)

    if missing_months:
        print(f"Monthly tables to create: {', '.join(missing_months)}")

    print(f"\nNew orders to import: {len(new_orders)}")
    for order in new_orders:
        print(
            f'  {order["id"]} | {order["name"]} | '
            f'Qty {order["quantity"]} | £{order["price"]:.2f}'
        )

    print(
        "\nThe script will insert each new order above "
        "the TOTALS row in its corresponding monthly table."
    )

    print("Automatic mode: backing up before import.")

    # Create backup before any spreadsheet modification.
    create_backup()

    # Create missing monthly tables only after backing up.
    for month in missing_months:
        print(f"Creating monthly table: {month}")
        create_new_month(month)

    new_ids = {order["id"] for order in new_orders}

    for month in sorted({get_table_name(order) for order in new_orders}):
        month_orders = [
            order for order in new_orders
            if get_table_name(order) == month
        ]

        print(f"\nImporting {len(month_orders)} order(s) into {month}...")

        month_totals_row = find_totals_row(month)
        insert_rows_and_write(month_orders, month_totals_row, month)
        verify_import(month_orders, month)

    print(f"\nSUCCESS: {len(new_orders)} new order(s) imported.")
    print("Please inspect the spreadsheet and confirm the totals.")


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as error:
        print(f"\nWooCommerce HTTP error: {error}")
        if error.response is not None:
            print(error.response.text[:1000])
        sys.exit(1)
    except Exception as error:
        print(f"\nERROR: {error}")
        print(
            "Stop here and inspect the spreadsheet and backup "
            "before running the script again."
        )
        sys.exit(1)
