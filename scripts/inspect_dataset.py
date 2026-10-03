import csv
import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "public"

def inspect_csv(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        row_count = 0
        missing_counts = {col: 0 for col in header}
        ids = set()
        duplicate_id_count = 0
        id_col = header[0]
        for row in reader:
            row_count += 1
            if row[0] in ids:
                duplicate_id_count += 1
            else:
                ids.add(row[0])
            for i, val in enumerate(row):
                if val is None or val.strip() == "":
                    missing_counts[header[i]] += 1
    return {
        "file": path.name,
        "rows": row_count,
        "columns": header,
        "id_col": id_col,
        "duplicate_ids": duplicate_id_count,
        "missing_counts": {k: v for k, v in missing_counts.items() if v > 0}
    }

def main():
    print(f"=== Inspecting NovaMart Dataset in {DATA_DIR} ===")
    if not DATA_DIR.exists():
        print(f"ERROR: {DATA_DIR} does not exist!")
        return

    csv_files = sorted(DATA_DIR.glob("*.csv"))
    for cf in csv_files:
        info = inspect_csv(cf)
        print(f"\n--- {info['file']} ---")
        print(f"Total Rows: {info['rows']}")
        print(f"Columns: {info['columns']}")
        print(f"Duplicate IDs: {info['duplicate_ids']}")
        if info['missing_counts']:
            print(f"Missing Values: {info['missing_counts']}")
        else:
            print("Missing Values: None")

    conv_file = DATA_DIR / "conversations.json"
    if conv_file.exists():
        with open(conv_file, "r", encoding="utf-8") as f:
            convs = json.load(f)
        print(f"\n--- conversations.json ---")
        print(f"Total conversations: {len(convs)}")
        if convs:
            sample = convs[0]
            print(f"Sample conversation keys: {list(sample.keys())}")
            print(f"Sample turns count: {len(sample.get('turns', sample.get('messages', [])))}")

    policies_dir = DATA_DIR / "policies"
    if policies_dir.exists():
        policy_files = sorted([p.name for p in policies_dir.glob("*.md")])
        print(f"\n--- Policy Files ({len(policy_files)}) ---")
        for pf in policy_files:
            print(f"  - {pf}")

    products_dir = DATA_DIR / "products"
    if products_dir.exists():
        prod_specs = sorted([p.name for p in products_dir.glob("*.md")])
        print(f"\n--- Product Spec Files ({len(prod_specs)}) ---")
        for ps in prod_specs:
            print(f"  - {ps}")

if __name__ == "__main__":
    main()
