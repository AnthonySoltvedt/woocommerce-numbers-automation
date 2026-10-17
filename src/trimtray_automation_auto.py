from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parent

IMPORT_SCRIPT = BASE / "write_gbp_orders_auto.py"
FEES_SCRIPT = BASE / "backfill_fees_auto.py"
TEST_WORKBOOK = BASE / "TrimTray_Import_Test.numbers"

def main():
    if not TEST_WORKBOOK.exists():
        raise SystemExit("STOPPED: Test workbook not found.")

    if not IMPORT_SCRIPT.exists() or not FEES_SCRIPT.exists():
        raise SystemExit("STOPPED: Required scripts missing.")

    print("TRIMTRAY TEST AUTOMATION", flush=True)
    print("Using test workbook only.", flush=True)

    print("Opening test workbook in Numbers...", flush=True)
    subprocess.run(
        ["open", "-a", "Numbers", str(TEST_WORKBOOK)],
        check=True,
    )

    import time

    for attempt in range(20):
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "Numbers" to get name of every document'],
            capture_output=True,
            text=True,
        )
        names = [name.strip() for name in result.stdout.split(",")]
        if result.returncode == 0 and TEST_WORKBOOK.name in names:
            print("PASS: Test workbook is ready.", flush=True)
            break
        time.sleep(1)
    else:
        raise SystemExit("STOPPED: Numbers workbook did not become ready.")

    print("\nSTEP 1: Import new WooCommerce orders", flush=True)
    subprocess.run(
        [sys.executable, str(IMPORT_SCRIPT)],
        cwd=BASE,
        check=True,
    )

    print("\nSTEP 2: Fill missing WooPayments fees", flush=True)
    subprocess.run(
        [sys.executable, str(FEES_SCRIPT)],
        cwd=BASE,
        check=True,
    )

    print("\nCOMPLETE: Both automation steps finished.", flush=True)

if __name__ == "__main__":
    main()
