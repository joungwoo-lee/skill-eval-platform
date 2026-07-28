"""Oracle: 태스크 정답 풀이 (PLAN.md §6). MockAdapter 성공 경로에서 사용."""
import csv
import sys
from pathlib import Path


def main() -> int:
    workdir = Path(sys.argv[1])
    total = 0.0
    rows = 0
    with (workdir / "data.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += float(row["amount"])
            rows += 1
    (workdir / "report.md").write_text(
        f"# Sales Report\n\nTotal: {total:g}\nRows: {rows}\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
