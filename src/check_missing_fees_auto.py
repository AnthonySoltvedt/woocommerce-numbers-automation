import write_gbp_orders_auto as app

script = '''
tell application "Numbers"
    set missingCount to {}

    set monthlyTables to name of every table of sheet "ORDERS ID" of document "TrimTray_Import_Test.numbers"

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
        set t to table (monthName as text) of sheet "ORDERS ID" of document "TrimTray_Import_Test.numbers"

        repeat with r from 2 to ((row count of t) - 1)
            set orderID to value of cell 17 of row r of t
            set feeValue to value of cell 4 of row r of t

            if orderID is not missing value and feeValue is missing value then
                set end of missingCount to (orderID as integer) as text
            end if
        end repeat
    end repeat

    return missingCount
end tell
'''

missing_ids = set(str(app.run_applescript(script, [] )).split(", "))

orders = app.fetch_gbp_orders()
available_ids = {
    str(order["id"])
    for order in orders
    if order["fee"] is not None
}

print("WooCommerce orders with available fees:", len(available_ids))

updates_needed = missing_ids.intersection(available_ids)
print("Missing fee order IDs:", sorted(missing_ids))
print("Orders eligible for fee updates:", sorted(updates_needed))
print("Number of updates needed:", len(updates_needed))
