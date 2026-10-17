import write_gbp_orders_auto as app
import check_missing_fees_auto as checker

if not checker.updates_needed:
    print("No eligible fee updates. Skipping backup and changes.")
    raise SystemExit(0)


EXPECTED_FILE = "TrimTray_Import_Test.numbers"

if app.NUMBERS_FILE.name != EXPECTED_FILE:
    raise SystemExit("Stopped: incorrect workbook configured.")

orders = app.fetch_gbp_orders()

fee_lookup = {
    int(order["id"]): round(order["price"] - order["fee"], 2)
    for order in orders
    if order["fee"] is not None
}

script = r'''
on run argv
    tell application "Numbers"
        set doc to document "TrimTray_Import_Test.numbers"

        set updates to 0
        set skipped to 0

        set monthlyTables to name of every table of sheet "ORDERS ID" of doc

        repeat with monthName in monthlyTables
            set monthText to monthName as text
            set validMonths to {"January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"}
            set validName to false

            repeat with m in validMonths
                if monthText starts with ((m as text) & " 20") and (length of monthText) is ((length of (m as text)) + 5) then
                    set validName to true
                    exit repeat
                end if
            end repeat

            if not validName then
                error "STOPPED: Unexpected table name: " & monthText
            end if
            set t to table (monthName as text) of sheet "ORDERS ID" of doc

            repeat with r from 2 to ((row count of t) - 1)
                set orderID to value of cell 17 of row r of t
                set currentValue to value of cell 4 of row r of t

                if orderID is not missing value then
                    set orderIDText to (orderID as integer) as text

                    repeat with i from 1 to ((count of argv) div 2)
                        set argIndex to 1 + ((i - 1) * 2)
                        set matchingID to item argIndex of argv
                        set afterFees to item (argIndex + 1) of argv

                        if orderIDText = matchingID then
                            if currentValue is missing value then
                                set value of cell 4 of row r of t to (afterFees as number)
                                set updates to updates + 1
                            else
                                set skipped to skipped + 1
                            end if
                            exit repeat
                        end if
                    end repeat
                end if
            end repeat
        end repeat

        save doc
        return "Updated: " & updates & ", Existing values skipped: " & skipped
    end tell
end run
'''

arguments = []

for order_id, after_fees in fee_lookup.items():
    arguments.extend([str(order_id), f"{after_fees:.2f}"])

print(f"Orders with available fees: {len(fee_lookup)}")
# Create a backup before allowing Numbers to be modified.
backup = app.create_backup()
print(f"Safety backup ready: {backup}", flush=True)

print(app.run_applescript(script, arguments))
