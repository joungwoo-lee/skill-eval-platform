# demo-report

CSV 데이터에서 요약 리포트를 작성하는 스킬.

## Instructions

1. `data.csv`를 읽고 `amount` 컬럼의 합계와 행 수를 계산한다.
2. `report.md`를 작성한다. 반드시 다음을 포함한다:
   - `# Sales Report` 제목
   - `Total: <합계>` 줄
   - `Rows: <행 수>` 줄
3. 작성 후 반드시 자체 검증(run_verifier)으로 결과를 확인한 뒤 반환한다.

## Scripts

- `scripts/summarize.py` — CSV 합계 계산 헬퍼

## References

- 사내 리포트 포맷 가이드 v2
