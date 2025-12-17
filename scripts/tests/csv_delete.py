# Delete the extra 200 rows at the end of the .csv file
import os
import csv


REMOVE_N = 200
CSV_FILENAME = "350_taxodactyl_trial_no_sequence.csv"
script_dir = os.path.dirname(__file__)
csv_path = os.path.join(script_dir, "test-data", CSV_FILENAME)

print("CSV path:", csv_path)

with open(csv_path, "r", newline="", encoding="utf-8") as f:
    reader = list(csv.reader(f))
header = reader[0]
rows = reader[1:]
print(f"Original row count (excluding header): {len(rows)}")

if len(rows) > REMOVE_N:
    rows = rows[:-REMOVE_N]
else:
    print("Error: CSV has fewer rows than REMOVE_N")
    exit(1)

print(f"New row count (excluding header): {len(rows)}")

with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows)

print("Done: last 200 rows removed successfully!")
