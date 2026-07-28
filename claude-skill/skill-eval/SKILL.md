---
name: skill-eval
description: 스킬 이벨 — SKILL.md 기반 스킬(단수/복수)의 실측 효과를 일괄 평가하는 플랫폼 구동 스킬. 사용자가 "스킬 평가해", "스킬 이벨 돌려", "skill eval", "이 스킬(들) 효과 측정해"라고 하면 호출. 평가 태스크가 없으면 생성 여부를 사용자에게 물은 뒤 에이전트가 평가용 태스크를 직접 생성해 일괄 평가한다.
---

# skill-eval (스킬 이벨)

스킬 생산성 자동평가 플랫폼 구동 스킬. 같은 태스크를 스킬 없이(C0) / 스킬 적용(C1)으로
반복 실행해 **Skill Lift**(성공률 상승), 성공당 시간·비용, 지침 커버리지, 실패 원인을
수치화한다. 측정 전용 — 평가 대상 스킬은 절대 수정하지 않는다.

## 플랫폼 위치·의존성 자가점검 (스킬 발동 시 항상 먼저)

1. `C:\Users\joung\skill-eval-platform` 존재 확인 — 없으면 클론:
   `gh repo clone joungwoo-lee/skill-eval-platform C:/Users/joung/skill-eval-platform -- --recurse-submodules`
   (SkillsBench 태스크가 필요한데 `upstream/skillsbench`가 비어 있으면
   `git submodule update --init` 실행)
2. 의존성 확인 — 없으면 직접 설치 (사용자에게 묻지 말 것):
   `python -c "import yaml" || pip install pyyaml`
3. 실행 중 `ModuleNotFoundError` 발생 시에도 같은 방식으로 해당 모듈 설치 후 재시도.

설계 전문은 플랫폼 레포 `docs/PLAN.md`. 이하 모든 명령은 플랫폼 루트에서 실행.

## 절차

### 1. 평가 대상 스킬 수집

- 사용자가 지정한 스킬(경로 또는 이름, 단수/복수) 확인. 이름만 준 경우
  `~/.claude/skills/<name>` → 프로젝트 `.claude/skills/<name>` 순으로 SKILL.md 탐색.
- 각 스킬을 플랫폼 레지스트리로 임포트: `skills/<skill-id>/1.0.0/`에 SKILL.md
  (+ scripts/, references/, assets/ 있으면 함께) 복사. 같은 id가 이미 있고 내용이
  다르면 버전을 올려서(1.0.1, …) 새 디렉토리로 임포트.

### 2. constraints.json 생성 (없을 때)

커버리지·실패분류 정확도를 위해 스킬마다 `constraints.json`을 만든다.
SKILL.md 지침 중 **실행 궤적에서 관측 가능한 것만** 행동 제약으로 추출:

```json
[{
  "constraint_id": "C-001",
  "condition": "사람이 읽는 조건 설명",
  "condition_pattern": "궤적 매칭 정규식 — 조건 발생 여부",
  "required_pattern": "준수 증거 정규식",
  "forbidden_pattern": "위반 증거 정규식 (선택)",
  "severity": "high|medium|low"
}]
```

패턴은 궤적 텍스트(`event_type tool_name detail` 줄들)에 대해 case-insensitive로
매칭된다. 관측 불가능한 지침(내적 판단 등)은 넣지 않는다.

### 2.5 정적 평가 (선택 — 사용자가 "정적으로", "추산만", "lint" 요청 시 또는 실측 전 스크리닝)

```bash
# 기본(최종 정적 평가): 패턴 채점 + LLM 판정 비교·합성 — claude 호출 1회/스킬
python -m skill_eval.cli lint --skill <스킬 경로> [--skill ...] --judge
# 비용 0으로만 보려면 --judge 생략 (패턴 채점만)
```

패턴(정규식 9항목, 결정적·비용 0)과 LLM 판정(같은 루브릭 + 내용 타당성·일관성·
절차 충분성, 의미 기반)을 항목별로 비교해 최종 점수를 합성한다.
리포트의 **⚠ 괴리 항목**(패턴↔LLM 차이 ≥0.4)은 반드시 사용자에게 표시 —
패턴 오탐/미탐 또는 LLM 오판 후보. **보고 시 "추정이며 실측 아님" 명시.**
사용자가 정적 평가만 원했다면 여기서 종료.

### 3. 태스크 확보

1. 사용자가 태스크(디렉토리)를 지정했으면 그것을 사용 (`tasks/` 밖이면 복사해 등록).
2. 아니면 `tasks/`에서 `metadata.yaml`의 `required_skill == <skill-id>`인 기존 태스크 탐색.
2.5 스킬 주제와 맞는 SkillsBench 공개 태스크(87개, `upstream/skillsbench/tasks/`)가
   있으면 변환해 재사용 — 스킬 작성과 무관한 외부 출제라 자작 태스크보다 편향이 적다:
   `python -m skill_eval.cli import-sb --task upstream/skillsbench/tasks/<id> --required-skill <skill-id>`
   (변환된 metadata.yaml의 `requires.network`가 none이 아니면 로컬 실행 실패 가능 — 확인 후 사용)
3. 태스크가 하나도 없는 스킬이 있으면 **생성 전 반드시 사용자에게 질문**한다.
   텍스트로 질문하고(이 환경에선 AskUserQuestion 도구가 취소될 수 있음),
   **복수 스킬이어도 질문은 한 번만 묶어서** 한다:

   > 평가용 태스크가 없는 스킬: `A`, `B`. 스킬별 3개씩(난이도 하/중/상) 태스크를
   > 생성할까요? 개수·난이도 조정도 가능합니다.

   승인 후 스킬 각각에 대해 태스크를 생성한다. 거부하면 태스크 있는 스킬만 평가.

### 4. 태스크 생성 (승인 시)

`references/task-authoring.md` 규격대로 스킬당 기본 3개(난이도 하/중/상) 작성.
핵심 원칙:

- 채점은 결정적: `verifier/score.py`가 workdir을 받아 stdout 마지막 줄에
  `{"score": float}` JSON 출력. 파일 내용·상태를 기계적으로 검사.
- `environment/initial_state/`에 시작 파일, `oracle/solve.py`에 정답 풀이 동봉.
- `metadata.yaml`: `required_skill: <skill-id>`, `source: generated-from-skill`.
- 생성 직후 자가검증: oracle 실행 → verifier가 1.0을 주는지, 빈 workdir엔 0을 주는지 확인.
- **편향 경고**: 스킬을 보고 만든 태스크는 효과가 과장될 수 있다(PLAN.md §2.2).
  최종 보고에 이 한계를 반드시 명시한다.

### 5. 일괄 실행

```bash
python -m skill_eval.cli batch \
    --skill skills/<idA>/1.0.0 --skill skills/<idB>/1.0.0 \
    --conditions C0,C1 --repeats 3 \
    --adapter claude-code --model claude-haiku-4-5-20251001 \
    --out-dir results/batch
```

- 실측 평가는 `--adapter claude-code` (실 LLM 실행 = 비용 발생).
  **실행 전 규모를 사용자에게 알린다**: 총 run 수 = 스킬 × 태스크 × 조건 × repeats.
  파이프라인 점검만 할 때는 `--adapter mock`(비용 0).

### 6. 보고

`results/batch/summary.md`와 스킬별 `<id>.md`를 읽고 요약 보고.
**보고의 결론 첫 줄은 반드시 효율 상승 %** (실측 = 리포트의 "결론" 값,
정적 진단 = "추정 효율 상승 ≈ %"에 추정임을 병기). 이어서:

- 스킬별 Skill Lift(95% CI, McNemar p)
- 성공당 시간·비용 변화, Skill Coverage와 미검증 지침 목록
- 실패 유형 분포 (SKILL_DEFECT / NONCOMPLIANCE / TOOL / MODEL / VERIFIER)
- 태스크를 자동 생성했다면 편향 한계 명시
- 반복 수가 적으면(repeats ≤ 3) 통계적 확정이 아님을 명시
