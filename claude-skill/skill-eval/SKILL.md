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

패턴(정규식 9항목, 결정적)과 LLM 판정을 항목별 비교·합성한다.
**LLM 판정은 Agent 툴로 서브에이전트를 스폰해 시킨다** — 독립 컨텍스트라 구동
에이전트의 자기 편향이 없고, 하네스 네이티브 전달이라 claude 서브프로세스의
stdin류 전달 문제도 없다. 판정 결과는 JSON 텍스트로만 반환받는다.

1. 서브에이전트 스폰 (스킬당 1개, 복수 스킬이면 병렬). **모델은 지정하지 말고
   세션 기본 모델을 그대로 상속시킨다.** 프롬프트에 반드시 포함:
   - 대상 SKILL.md **경로** (서브에이전트가 직접 Read — 본문 요약해 넘기지 말 것, 오염됨)
   - 루브릭 9항목: trigger(발동 조건 구체성) / steps(단계화) / vagueness(구체성) /
     verification(자체 검증) / recovery(오류 대응) / output_spec(산출물 명시) /
     content_validity(내용 타당성) / consistency(내부 일관성) / sufficiency(절차 충분성)
     — 각 0.0~1.0, 문서에 실제 쓰인 것만 근거, 선의 보완 해석 금지
   - 반환 형식: **JSON 하나만, 다른 텍스트 금지**:
     `{"scores": {9항목}, "rationales": {항목별 한 줄 근거}, "top_risks": [최대 3], "model": "<서브에이전트 모델명>"}`
2. 반환 JSON을 `results/judge.json`에 저장 (복수 스킬이면 `{"<skill-id>": {payload}}` 매핑).
   9항목 누락·형식 오류면 lint가 거부하므로, 그 오류 메시지로 서브에이전트에 1회 재요청.
3. 합성 실행:
   ```bash
   python -m skill_eval.cli lint --skill <스킬 경로> [--skill ...] --judge-file results/judge.json
   ```

폴백 순서: 서브에이전트 스폰 불가 환경 → 구동 에이전트 본인이 직접 채점해 같은
JSON 작성 → 그것도 불가한 에이전트 밖(스크립트/CI)에서만 `--judge`(claude 서브프로세스).

리포트의 **⚠ 괴리 항목**(패턴↔LLM 차이 ≥0.4)은 반드시 사용자에게 표시 —
패턴 오탐/미탐 또는 셀프 판정 오판 후보. **보고 시 "추정이며 실측 아님" 명시.**
사용자가 정적 평가만 원했다면 여기서 종료.

### 3. 태스크 확보

우선순위: 사용자 지정/제공 > 기존 등록 태스크 > SkillsBench 적합 태스크(인덱스 기반
서브에이전트 검토) > (질문 후) 사용자 제공 또는 직접 생성.

1. 사용자가 태스크(디렉토리 또는 업무 예시)를 지정/제공했으면 그것을 사용
   (`tasks/` 밖이면 복사해 등록, 업무 예시면 태스크 패키지로 포장).
2. 아니면 `tasks/`에서 `metadata.yaml`의 `required_skill == <skill-id>`인 기존 태스크 탐색.
3. 없으면 **SkillsBench 인덱스 기반 적합성 검토를 서브에이전트에게 시킨다**:
   - 인덱스: `docs/sb-task-index.json` (87개 태스크의 분류·난이도·태그·네트워크 요구·
     한줄 요약). 없거나 upstream이 갱신됐으면 `python -m skill_eval.cli index-sb`로 재생성.
   - 서브에이전트 스폰 (스킬당 1개, 복수 스킬 병렬, **모델 지정 금지 — 기본 모델 상속**).
     프롬프트에 포함: 대상 SKILL.md **경로** + 인덱스 JSON **경로** (둘 다 직접 Read),
     적합 기준 — (i) 태스크 주제·요구 역량이 스킬이 다루는 업무와 실질 일치
     (분류·태그·요약 근거, 표면 키워드 일치만으로 판정 금지),
     (ii) `network == "none"` 우선, 그 외는 외부 API 변동으로 채점 불안정 경고 동반.
     반환은 JSON 하나만:
     `{"fits": [{"task_id": "...", "why": "...", "caveat": "..."}], "verdict": "reuse|none"}`
   - `fits`가 있으면 질문 없이 변환해 사용하고, 무엇을 왜 골랐는지 보고에 명시
     (외부 출제라 자작보다 효과 과장 편향이 없음 — 그래서 우선):
     `python -m skill_eval.cli import-sb --task upstream/skillsbench/tasks/<id> --required-skill <skill-id>`
4. 적합 태스크가 없는 스킬만 **사용자에게 질문**한다. 텍스트로 질문하고
   (이 환경에선 AskUserQuestion 도구가 취소될 수 있음),
   **복수 스킬이어도 질문은 한 번만 묶어서** 한다:

   > 평가용 태스크가 없는 스킬: `A`, `B` (SkillsBench 인덱스에도 적합 태스크 없음).
   > (a) 실제 업무 예시를 주시면 태스크로 포장합니다 (편향 최소 — 권장)
   > (b) 스킬별 3개씩(난이도 하/중/상) 임의 생성합니다
   > 개수·난이도 조정 가능합니다.

   선택대로 진행: (a)면 받은 예시를 §6 규격으로 포장, (b)면 태스크 생성 절차(4장).
   거부하면 태스크 있는 스킬만 평가.

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
- **아낀 시간** (기본 측정): C0·C1 둘 다 성공한 쌍당 평균 시간 절감(±CI, 쌍 개수 병기)
- 성공당 시간·비용 변화, Skill Coverage와 미검증 지침 목록
- 실패 유형 분포 (SKILL_DEFECT / NONCOMPLIANCE / TOOL / MODEL / VERIFIER)
- 태스크를 자동 생성했다면 편향 한계 명시
- 반복 수가 적으면(repeats ≤ 3) 통계적 확정이 아님을 명시
