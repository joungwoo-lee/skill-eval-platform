"""결정적 검증기: report.md 존재 + 제목 + 정확한 합계·행수 (PLAN.md §9.1).

stdout 마지막 줄에 JSON {"score": float} 출력.
"""
import csv
import json
import re
import sys
from pathlib import Path


def main() -> int:
    workdir = Path(sys.argv[1])
    report = workdir / "report.md"
    if not report.exists():
        print(json.dumps({"score": 0.0, "reason": "report.md missing"}))
        return 0

    data = workdir / "data.csv"
    total = 0.0
    rows = 0
    with data.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total += float(row["amount"])
            rows += 1

    text = report.read_text(encoding="utf-8")
    checks = {
        "title": bool(re.search(r"^# Sales Report", text, re.MULTILINE)),
        "total": bool(re.search(rf"Total:\s*{re.escape(f'{total:g}')}", text)),
        "rows": bool(re.search(rf"Rows:\s*{rows}\b", text)),
    }
    score = sum(checks.values()) / len(checks)
    print(json.dumps({"score": 1.0 if score == 1.0 else round(score, 3), "checks": checks}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
