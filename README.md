# skill-eval-platform (스킬 이벨)

스킬 생산성 자동평가 플랫폼. `SKILL.md` 기반 스킬이 AI 에이전트의 업무 성공률·시간·비용을
얼마나 개선하는지 자동 측정하고, 지침 커버리지와 실패 원인을 분석한다.

**모든 리포트의 결론은 효율 상승 %** 단일 값이다:
효율 = 성공 횟수 / 총 비용(비용 없으면 시간), 효율 상승 = C0(스킬 없음) 대비 C1(스킬 적용)의
상대 증가율. 정적 진단(lint)은 같은 형태의 **추정치**를 내되 실측 아님을 병기한다.
**아낀 시간**도 기본 측정: C0·C1 **둘 다 성공한 쌍**만 골라 쌍당 (C0 시간 − C1 시간)의
평균±CI — 같은 일을 해냈을 때 스킬이 아껴준 순수 시간(성공당 시간 비교의 문제 집합
왜곡이 없음). Skill Lift(성공률 %p)·성공당 시간·비용은 구성 지표로 함께 보고된다.

전체 설계는 **[docs/PLAN.md](docs/PLAN.md)** 참조. 이 저장소는 계획서 17장 1~4단계에 해당하는
MVP 구현체다.

## 참조 연구 (계획서 §3)

### [SkillsBench](https://github.com/benchflow-ai/skillsbench) — 스킬 효과를 재는 기본 틀
- **아이디어**: 같은 문제를 스킬 없이 한 번, 스킬 주고 한 번 풀게 해서 성공률 차이를 잰다. 그 차이가 곧 스킬의 효과다. 실제로 87개 문제에서 좋은 스킬이 해결률을 33.9%→50.5%로 올렸다.
- **기술**: 문제 하나를 "지시문 + 시작 파일 + 채점기 + 정답 풀이" 세트로 포장해서, 누가 언제 돌려도 똑같이 채점되게 만든 것.
- **여기서 가져온 것**: 태스크 패키지 구조, 스킬 유/무 비교 방식, 그리고 **실물 통합** —
  포크([joungwoo-lee/skillsbench](https://github.com/joungwoo-lee/skillsbench))를 `upstream/skillsbench`
  서브모듈로 두고, `import-sb` 커맨드가 87개 공개 태스크를 우리 레지스트리 포맷으로 변환한다
  (verifier 어댑터가 `/root` 경로 재작성으로 로컬 채점, Docker/네트워크 요구는 `requires:`에 보존).

### [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401) — 코딩 업무로 검증
- **아이디어**: 진짜 코드 저장소의 수정 업무로 스킬을 시험한다. 성공/실패만 보지 않고 시간과 토큰(비용)이 얼마나 들었는지도 같이 잰다.
- **기술**: 채점용 테스트를 에이전트에게 숨겨서(문제 풀 때 답안지를 못 보게) 채점을 속일 수 없게 한 것.
- **여기서 가져온 것**: "채점기가 점수 매긴다"는 계약, 시간·비용 리포트.

### [Skill Coverage](https://arxiv.org/abs/2606.20659) — 스킬의 어느 줄이 실제로 쓰였나
- **아이디어**: 시험을 통과했어도 스킬 문서의 절반은 한 번도 안 쓰였을 수 있다. "스킬의 각 지침이 실전에서 확인됐는가"를 따로 세자는 것.
- **기술**: 스킬의 지침 하나하나를 "이런 상황이 오면 / 이걸 해야 하고 / 이건 하면 안 된다" 형태로 쪼개고, 실행 기록을 뒤져서 지침별로 "상황 안 옴 / 지킴 / 어김 / 판단 불가" 4가지로 도장 찍는 것.
- **여기서 가져온 것**: `constraints.json` 규칙과 판정기 전체 (원 논문 코드가 없어 직접 구현).

> 통계는 "같은 문제를 두 조건으로 풀었을 때의 짝 비교"에 맞는 표준 검정(McNemar, 부트스트랩 신뢰구간)을 쓴다 — 우연히 몇 번 잘 푼 것과 진짜 효과를 구분하기 위해서다.

## 구현 범위 (v0.1)

| 계획서 | 구현 |
|---|---|
| §5 시스템 구조 | `skill_eval/` 패키지 (registry / runners / evaluators / analyzers / statistics / report) |
| §6 태스크 패키지 규격 | `tasks/<domain>/<task-id>/` — task.md, metadata.yaml, environment/initial_state, verifier, oracle |
| §7 평가 조건 | C0 No Skill / C1 Forced Skill |
| §8 반복·통제 | 조건×반복 시드 기반 무작위 실행 순서, run마다 초기 상태 새로 복사 |
| §9 자동 채점 | 결정적 검증기 (`verifier/score.py`, JSON `{"score": float}` 계약) |
| §10 핵심 지표 | Skill Lift, Time/Cost per Success |
| §11 커버리지 | `constraints.json` 정규식 규칙 → `NOT_APPLICABLE / COVERED_PASS / COVERED_FAIL / UNJUDGEABLE` |
| §12 실패 분류 | 규칙 기반 5분류 (SKILL_DEFECT / NONCOMPLIANCE / TOOL / MODEL / VERIFIER) |
| §14 데이터 모델 | SQLite (계획서는 PostgreSQL 권장 — MVP는 단일 파일) |
| §16 통계 | McNemar 정확검정, 태스크 단위 짝지은 부트스트랩 95% CI |

미구현(후속 단계): Docker 격리 실행, FastAPI 등록 API, 대시보드.

이 플랫폼은 **측정 전용**이다 — 평가 대상 스킬을 수정·개선하는 기능은 두지 않는다.

`lint`(정적 진단)는 실행 없이 SKILL.md만 읽는 **추정**이며 두 방식을 쓴다:

- **패턴 채점**: 정규식 기반 9항목(발동조건·단계화·모호어·검증·오류대응·산출물·자원일치·오버헤드·제약정의).
  결정적·비용 0이지만 표면(단어 존재)만 본다. 한/영 패턴 대칭은 테스트로 강제.
- **LLM 판정**: 같은 루브릭 + 패턴이 못 보는 3항목(내용 타당성·내부 일관성·절차 충분성)을
  의미 기반으로 채점. 기본은 **서브에이전트 판정** — 구동 에이전트가 판정 전용
  서브에이전트를 스폰해 루브릭 JSON을 반환받아 `--judge-file`로 전달(독립 컨텍스트 =
  자기 편향 없음, 별도 CLI 프로세스 없음). 폴백: 구동 에이전트 본인 채점 →
  에이전트 밖 환경은 `--judge`(headless claude 서브프로세스).
- **최종 정적 평가**: 공유 6항목은 두 점수를 나란히 비교(차이 ≥0.4 = ⚠ 괴리 플래그,
  패턴 오탐/미탐 또는 LLM 오판 후보로 사람 확인 대상), 최종 = 평균. 합성 점수 → 추정 효율 상승 %.

실측 Skill Lift를 대체하지 않으며 실행 전 스크리닝용이다.

## 설치

```bash
git clone --recurse-submodules https://github.com/joungwoo-lee/skill-eval-platform
uv venv && uv pip install -e ".[dev]"   # 또는 pip install -e ".[dev]"
# 이미 클론했다면: git submodule update --init  (upstream/skillsbench)
```

## 사용

```bash
# 레지스트리 확인
skill-eval list

# 정적 진단(패턴) — 실행 없이 SKILL.md 구조 채점 (비용 0)
skill-eval lint --skill skills/demo-report/1.0.0 --skill <다른 스킬 경로>

# 최종 정적 평가 — 패턴 + LLM 판정 비교·합성.
# 판정은 구동 에이전트가 직접 채점한 JSON을 넘기는 셀프 판정이 기본 (추가 모델 호출 없음):
skill-eval lint --skill skills/demo-report/1.0.0 --judge-file results/judge.json
# 에이전트 밖(스크립트/CI)에서만 폴백: claude 서브프로세스 호출 (비용 발생)
skill-eval lint --skill skills/demo-report/1.0.0 --judge --judge-model claude-haiku-4-5-20251001

# 데모 태스크 × 데모 스킬, C0(스킬 없음)/C1(스킬 적용) 각 5회 (mock 어댑터 — LLM 비용 없음)
skill-eval run --task tasks/demo/hello-report-001 --skill skills/demo-report/1.0.0 \
    --conditions C0,C1 --repeats 5 --adapter mock --db results/results.db

# 리포트 (Skill Lift, CI, McNemar, 커버리지, 실패 유형)
skill-eval report --db results/results.db --skill skills/demo-report/1.0.0 --out results/report.md

# 복수 스킬 일괄 평가 (스킬별 리포트 + summary.md)
skill-eval batch --skill skills/A/1.0.0 --skill skills/B/1.0.0 \
    --conditions C0,C1 --repeats 3 --adapter mock --out-dir results/batch

# SkillsBench 공개 태스크 변환 (개별 또는 --all 87개)
skill-eval import-sb --task upstream/skillsbench/tasks/citation-check --required-skill my-skill
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
