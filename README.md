# skill-eval-platform (스킬 이벨)

스킬 생산성 자동평가 플랫폼. `SKILL.md` 기반 스킬이 AI 에이전트의 업무 성공률·시간·비용을
얼마나 개선하는지(Skill Lift / Operational Lift) 자동 측정하고, 지침 커버리지와 실패 원인을
분석한다.

전체 설계는 **[docs/PLAN.md](docs/PLAN.md)** 참조. 이 저장소는 계획서 17장 1~4단계에 해당하는
MVP 구현체다.

## 구현 범위 (v0.1)

| 계획서 | 구현 |
|---|---|
| §5 시스템 구조 | `skill_eval/` 패키지 (registry / runners / evaluators / analyzers / statistics / report) |
| §6 태스크 패키지 규격 | `tasks/<domain>/<task-id>/` — task.md, metadata.yaml, environment/initial_state, verifier, oracle |
| §7 평가 조건 | C0 No Skill / C1 Forced Skill / C2 Auto Discovery / C3 Ablation(SKILL.md 섹션 제거) |
| §8 반복·통제 | 조건×반복 시드 기반 무작위 실행 순서, run마다 초기 상태 새로 복사 |
| §9 자동 채점 | 결정적 검증기 (`verifier/score.py`, JSON `{"score": float}` 계약) |
| §10 핵심 지표 | Skill Lift, Operational Lift, Time/Cost per Success |
| §11 커버리지 | `constraints.json` 정규식 규칙 → `NOT_APPLICABLE / COVERED_PASS / COVERED_FAIL / UNJUDGEABLE` |
| §12 실패 분류 | 규칙 기반 6분류 (ROUTING / SKILL_DEFECT / NONCOMPLIANCE / TOOL / MODEL / VERIFIER) |
| §14 데이터 모델 | SQLite (계획서는 PostgreSQL 권장 — MVP는 단일 파일) |
| §16 통계 | McNemar 정확검정, 태스크 단위 짝지은 부트스트랩 95% CI |

미구현(후속 단계): Docker 격리 실행, FastAPI 등록 API, 대시보드, 자동 스킬 개선 루프(§13),
SkillsBench 포크 통합(upstream/).

## 설치

```bash
uv venv && uv pip install -e ".[dev]"   # 또는 pip install -e ".[dev]"
```

## 사용

```bash
# 레지스트리 확인
skill-eval list

# 데모 태스크 × 데모 스킬, C0/C1/C2 각 5회 (mock 어댑터 — LLM 비용 없음)
skill-eval run --task tasks/demo/hello-report-001 --skill skills/demo-report/1.0.0 \
    --distractor skills/demo-distractor/1.0.0 \
    --conditions C0,C1,C2 --repeats 5 --adapter mock --db results/results.db

# 리포트 (Skill Lift, CI, McNemar, 커버리지, 실패 유형)
skill-eval report --db results/results.db --skill skills/demo-report/1.0.0 --out results/report.md

# 복수 스킬 일괄 평가 (스킬별 리포트 + summary.md; 서로가 C2 distractor)
skill-eval batch --skill skills/A/1.0.0 --skill skills/B/1.0.0 \
    --conditions C0,C1,C2 --repeats 3 --adapter mock --out-dir results/batch
```

## Claude 스킬로 사용 (스킬 이벨)

`claude-skill/skill-eval/`이 이 플랫폼을 구동하는 Claude Code 스킬이다.
`~/.claude/skills/skill-eval`로 링크(junction)하면 "스킬 평가해" / "스킬 이벨 돌려"로 호출된다:

```powershell
cmd /c mklink /J "$env:USERPROFILE\.claude\skills\skill-eval" "C:\Users\joung\skill-eval-platform\claude-skill\skill-eval"
```

동작: 평가할 스킬(단수/복수) 지정 → 레지스트리 임포트·constraints.json 생성 →
평가 태스크가 없으면 사용자에게 생성 여부를 한 번에 질문 → 승인 시 스킬별 태스크
자동 생성(결정적 verifier + oracle 자가검증) → `batch` 일괄 실행 → Lift·커버리지 보고.

실 에이전트 평가는 `--adapter claude-code --model claude-sonnet-5` (Claude Code headless,
비용 발생 — mock으로 파이프라인 검증 후 사용).

## 테스트

```bash
pytest
```

`tests/test_e2e.py`가 데모 태스크로 전 구간(레지스트리→러너→검증기→커버리지→실패분류→통계→리포트)을
검증한다.

## 새 태스크·스킬 추가

- 태스크: `tasks/<domain>/<task-id>/`에 §6 규격대로. 검증기는 workdir 경로 1개를 받아
  stdout 마지막 줄에 `{"score": 1.0}` JSON을 출력하면 된다.
- 스킬: `skills/<skill-id>/<version>/SKILL.md` + 선택적으로 `constraints.json`
  (정규식 기반 행동 제약 — `skills/demo-report/1.0.0/constraints.json` 참조).
