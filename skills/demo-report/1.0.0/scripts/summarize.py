"""CSV amount 컬럼 합계 계산 헬퍼."""
import csv
import sys


def summarize(csv_path: str) -> tuple[float, int]:
    total = 0.0
    rows = 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += float(row["amount"])
            rows += 1
    return total, rows


if __name__ == "__main__":
    total, rows = summarize(sys.argv[1])
    print(f"Total: {total:g}")
    print(f"Rows: {rows}")
