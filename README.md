# skill-eval-platform (스킬 이벨)

스킬 생산성 자동평가 플랫폼. `SKILL.md` 기반 스킬이 AI 에이전트의 업무 성공률·시간·비용을
얼마나 개선하는지(Skill Lift / Operational Lift) 자동 측정하고, 지침 커버리지와 실패 원인을
분석한다.

전체 설계는 **[docs/PLAN.md](docs/PLAN.md)** 참조. 이 저장소는 계획서 17장 1~4단계에 해당하는
MVP 구현체다.

## 참조 연구 (계획서 §3)

### [SkillsBench](https://github.com/benchflow-ai/skillsbench) — 기본 실행 프레임워크
- **핵심 아이디어**: 동일 태스크를 스킬 유/무 조건으로 짝지어(paired) 실행해 스킬의 효과를 성공률 차이로 직접 측정. 87개 태스크 공개, 선별된 스킬이 평균 해결률 33.9%→50.5%.
- **특징적 기술**: 자기완결 태스크 패키지(task + 초기상태 + verifier + oracle), Docker 격리 실행, Skill/No-Skill paired evaluation, 결정적 verifier 우선 채점.
- **이 구현에**: 태스크 패키지 규격(§6), C0/C1 짝 비교, oracle/verifier 구조.

### [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401) — 소프트웨어 업무 평가
- **핵심 아이디어**: 실제 Git 저장소 기반 코딩 태스크에서 스킬 효과를 숨겨진 테스트 통과율로 판정. 성공률만이 아니라 토큰·벽시계 시간까지 조건별 비교.
- **특징적 기술**: 기준 커밋 고정(재현성), hidden tests 기반 성공 판정(채점기 오염 방지), `--use-skill`/`--no-use-skill` 일괄 실행 스크립트.
- **이 구현에**: 결정적 성공 판정 계약(verifier JSON score), 토큰·시간·비용 리포트.

### [SkillLearnBench](https://arxiv.org/abs/2604.20087) — 스킬 자동 생성·개선
- **핵심 아이디어**: 실행 경험·피드백으로 스킬을 자동 생성/개선하는 방법들(One-Shot, Self-Feedback, Teacher-Feedback)을 동일 조건에서 비교. 자기평가 반복은 과적합되므로 개발/평가 태스크를 분리.
- **특징적 기술**: 스킬 버전별 평가, 실패 궤적 기반 수정 루프, 자동 생성 스킬 vs 사람 작성 스킬 비교.
- **이 구현에**: 스킬 버전 디렉토리 구조. 자동 개선 루프(§13)는 후속 단계.

### [Skill Coverage](https://arxiv.org/abs/2606.20659) — 지침 커버리지 (test adequacy)
- **핵심 아이디어**: "성공률이 높아도 스킬 지침 대부분이 한 번도 검증 안 됐을 수 있다" — 테스트 커버리지 개념을 스킬에 적용. SKILL.md 지침을 관측 가능한 행동 제약으로 변환하고, 실행 궤적이 각 제약을 실제로 검증했는지 측정.
- **특징적 기술**: 지침→행동 제약(조건/필수행동/금지행동/증거규칙) 구조화, 궤적별 4분류 판정(`NOT_APPLICABLE / COVERED_PASS / COVERED_FAIL / UNJUDGEABLE`), 미검증 지침 리스트.
- **이 구현에**: `constraints.json` 정규식 규칙 + 판정기 + 커버리지 지표 전체 직접 구현 (공식 코드 미공개).

### [Skill Usage](https://arxiv.org/abs/2604.04323) — 실운영 스킬 검색·선택 분석
- **핵심 아이디어**: 스킬이 있어도 에이전트가 못 찾거나 안 쓰면 효과 0 — 대규모 스킬 모음에서 검색·선택·사용률을 분리 측정. 스킬 효능(강제 로드)과 운영 효과(자동 발견)는 다른 수치다.
- **특징적 기술**: 유사·무관 스킬(distractor)을 섞은 자동 선택 조건, 궤적에서 스킬 사용 여부 판정, 라우팅 실패와 스킬 결함의 분리.
- **이 구현에**: C2 Auto Discovery 조건, distractor 지정, Skill Lift와 Operational Lift 분리 보고, ROUTING_FAILURE 분류.

### [SkillSmith](https://arxiv.org/abs/2605.15215) — 스킬 실행 오버헤드 최적화
- **핵심 아이디어**: 원본 SKILL.md는 컨텍스트 오버헤드가 크다 — 스킬을 최소 실행 인터페이스로 컴파일해 같은 효과를 더 적은 토큰·시간으로.
- **특징적 기술**: 스킬 컴파일, 원본 vs 컴파일본의 성공률·시간·비용 비교.
- **이 구현에**: C4 Compiled Skill 조건으로 계획만 반영 (후속 단계).

> 통계 방법론(McNemar 정확검정, 태스크 단위 짝지은 부트스트랩 CI)은 계획서 §16의 표준 짝비교 설계를 따른다.

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
