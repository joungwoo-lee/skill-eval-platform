# skill-eval-platform (스킬 이벨)

스킬 생산성 자동평가 플랫폼. `SKILL.md` 기반 스킬이 AI 에이전트의 업무 성공률·시간·비용을
얼마나 개선하는지(Skill Lift / Operational Lift) 자동 측정하고, 지침 커버리지와 실패 원인을
분석한다.

전체 설계는 **[docs/PLAN.md](docs/PLAN.md)** 참조. 이 저장소는 계획서 17장 1~4단계에 해당하는
MVP 구현체다.

## 참조 연구 (계획서 §3)

### [SkillsBench](https://github.com/benchflow-ai/skillsbench) — 스킬 효과를 재는 기본 틀
- **아이디어**: 같은 문제를 스킬 없이 한 번, 스킬 주고 한 번 풀게 해서 성공률 차이를 잰다. 그 차이가 곧 스킬의 효과다. 실제로 87개 문제에서 좋은 스킬이 해결률을 33.9%→50.5%로 올렸다.
- **기술**: 문제 하나를 "지시문 + 시작 파일 + 채점기 + 정답 풀이" 세트로 포장해서, 누가 언제 돌려도 똑같이 채점되게 만든 것.
- **여기서 가져온 것**: 태스크 패키지 구조, 스킬 유/무 비교 방식.

### [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401) — 코딩 업무로 검증
- **아이디어**: 진짜 코드 저장소의 수정 업무로 스킬을 시험한다. 성공/실패만 보지 않고 시간과 토큰(비용)이 얼마나 들었는지도 같이 잰다.
- **기술**: 채점용 테스트를 에이전트에게 숨겨서(문제 풀 때 답안지를 못 보게) 채점을 속일 수 없게 한 것.
- **여기서 가져온 것**: "채점기가 점수 매긴다"는 계약, 시간·비용 리포트.

### [SkillLearnBench](https://arxiv.org/abs/2604.20087) — 스킬을 자동으로 고치기
- **아이디어**: 실패한 기록을 보고 스킬 문서를 자동으로 고치게 한 뒤, 정말 좋아졌는지 다시 시험한다.
- **기술**: 연습 문제와 최종 시험 문제를 분리한 것. 같은 문제로만 고치고 시험하면 그 문제에만 맞춘 스킬이 되기 때문(시험 족보 암기 방지).
- **여기서 가져온 것**: 스킬을 버전으로 관리하는 구조. 자동 개선 자체는 후속 단계.

### [Skill Coverage](https://arxiv.org/abs/2606.20659) — 스킬의 어느 줄이 실제로 쓰였나
- **아이디어**: 시험을 통과했어도 스킬 문서의 절반은 한 번도 안 쓰였을 수 있다. "스킬의 각 지침이 실전에서 확인됐는가"를 따로 세자는 것.
- **기술**: 스킬의 지침 하나하나를 "이런 상황이 오면 / 이걸 해야 하고 / 이건 하면 안 된다" 형태로 쪼개고, 실행 기록을 뒤져서 지침별로 "상황 안 옴 / 지킴 / 어김 / 판단 불가" 4가지로 도장 찍는 것.
- **여기서 가져온 것**: `constraints.json` 규칙과 판정기 전체 (원 논문 코드가 없어 직접 구현).

### [Skill Usage](https://arxiv.org/abs/2604.04323) — 스킬을 알아서 찾아 쓰긴 하나
- **아이디어**: 아무리 좋은 스킬도 에이전트가 여러 스킬 중에서 못 찾아 쓰면 소용없다. "스킬 자체의 실력"과 "찾아 쓰는 실력"은 따로 재야 한다.
- **기술**: 정답 스킬에 엉뚱한 스킬들을 미끼로 섞어 놓고 제대로 골라 쓰는지 보는 것.
- **여기서 가져온 것**: C2 자동선택 조건, 미끼 스킬, "스킬은 좋은데 못 찾아서 실패"를 별도 실패 유형으로 분류.

### [SkillSmith](https://arxiv.org/abs/2605.15215) — 스킬 다이어트
- **아이디어**: 긴 스킬 문서는 매번 읽히는 것 자체가 토큰 낭비다. 효과는 유지하면서 최소한의 분량으로 압축하자.
- **기술**: 압축 전/후 스킬을 같은 문제로 돌려 성공률은 그대로인지, 비용은 줄었는지 비교.
- **여기서 가져온 것**: 아직 계획만 (C4 조건, 후속 단계).

> 통계는 "같은 문제를 두 조건으로 풀었을 때의 짝 비교"에 맞는 표준 검정(McNemar, 부트스트랩 신뢰구간)을 쓴다 — 우연히 몇 번 잘 푼 것과 진짜 효과를 구분하기 위해서다.

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
