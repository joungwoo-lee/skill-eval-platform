# 스킬 생산성 자동평가 플랫폼 구축 계획서

- 문서 버전: 1.0
- 작성 기준일: 2026-07-28
- 목적: `SKILL.md` 기반 스킬이 AI 에이전트의 업무 성공률·속도·비용·품질을 얼마나 개선하는지 자동 측정하고, 실패 근거를 이용해 스킬을 개선한다.

---

## 1. 목표

다음 질문에 객관적인 수치로 답하는 평가 시스템을 구축한다.

1. 동일한 에이전트가 스킬을 사용할 때 업무 성공률이 얼마나 높아지는가?
2. 성공한 업무 한 건당 실행시간과 비용이 얼마나 줄어드는가?
3. 스킬의 어떤 지침이 실제로 사용됐고, 어떤 지침이 아직 검증되지 않았는가?
4. 실패 원인이 스킬 결함, 지침 미준수, 모델 능력, 도구·환경 중 어디에 있는가?
5. 실패 궤적을 이용해 스킬을 자동 개선했을 때 효과가 재현되는가?

이 시스템이 직접 측정하는 값은 **스킬 실행효과(Skill Uplift)**이다. 사람이나 조직 전체의 생산성으로 환산하려면 이후 실제 업무 발생량, 사람 검토시간, 후속 재작업 비용을 결합한다.

---

## 2. 핵심 원칙

### 2.1 동일 업무 A/B 비교

동일한 태스크를 같은 모델·도구·초기 상태에서 실행한다.

- A조건: 스킬 없음
- B조건: 대상 스킬 강제 적용
- C조건: 여러 스킬 중 에이전트가 자동 선택
- D조건: 스킬 구성요소 제거 실험

### 2.2 태스크와 스킬 작성의 분리

`SKILL.md`를 읽고 그 스킬이 잘 풀 문제를 생성하면 효과가 과장된다. 평가 태스크는 다음에서 확보한다.

1. 스킬 작성 이전의 실제 과거 업무
2. 운영 중 실패했던 업무
3. 스킬 작성자와 분리된 평가자가 만든 업무
4. 최종 평가 시에만 공개되는 숨겨진 태스크

### 2.3 결과는 결정적 검증기를 우선

평가 우선순위는 다음과 같다.

1. 단위 테스트, DB 상태, 파일 내용, API 결과 등 결정적 검증
2. 구조화된 규칙 검사
3. 자동 검증이 불가능한 경우에만 블라인드 LLM 평가

### 2.4 토큰은 생산량이 아니라 비용·비효율 지표

토큰 수를 생산성 분자로 사용하지 않는다. 다음 목적으로만 사용한다.

- 실행 비용
- 성공당 비용
- 불필요한 반복 추론
- 스킬 적용으로 인한 컨텍스트 오버헤드

---

## 3. 활용할 연구와 공개 구현

### 3.1 SkillsBench — 기본 실행 프레임워크

- 논문/프로젝트: [SkillsBench](https://www.skillsbench.ai/)
- 저장소: <https://github.com/benchflow-ai/skillsbench>
- 역할: Skill/No-Skill 평가, 태스크 패키지, 격리 실행, Verifier, 모델·에이전트 비교

공개 저장소는 BenchFlow·Harbor 형식의 태스크, Docker 기반 실행, 실험 노트북과 평가 명령을 제공한다. 현재 공개 릴리스는 87개 태스크를 포함하며, 논문 집계에서 선별된 스킬이 평균 해결률을 33.9%에서 50.5%로 높였다.

**본 프로젝트에서 재사용할 부분**

- 태스크 및 환경 포맷
- Skill/No-Skill paired evaluation
- Docker 격리 실행
- Oracle·Verifier 구조
- 실행 결과 저장 방식

### 3.2 SWE-Skills-Bench — 소프트웨어 업무 평가

- 논문: [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401)
- 저장소: <https://github.com/GeniusHTX/SWE-Skills-Bench>
- 역할: 실제 저장소 기반 코딩 태스크, 테스트 통과율, 토큰·시간 분석

저장소는 49개 소프트웨어 엔지니어링 태스크에 대해 `--use-skill`과 `--no-use-skill` 실행, 테스트 평가, 실패 테스트 분석, 토큰·벽시계 시간 비교 기능을 제공한다.

**본 프로젝트에서 재사용할 부분**

- Git 저장소와 기준 커밋 고정
- 숨겨진 테스트 기반 성공 판정
- Skill/No-Skill 일괄 실행 스크립트
- 토큰·실행시간 비교 리포트

### 3.3 SkillLearnBench — 스킬 자동 생성·개선

- 논문: [SkillLearnBench](https://arxiv.org/abs/2604.20087)
- 저장소: <https://github.com/cxcscmu/SkillLearnBench>
- 역할: 실행 경험과 피드백을 이용한 스킬 생성·개선 방법 비교

20개 태스크, 100개 검증 인스턴스를 제공하며 One-Shot, Self-Feedback, Teacher-Feedback 등 여러 스킬 생성·개선 방법을 비교할 수 있다.

**본 프로젝트에서 재사용할 부분**

- 스킬 버전별 평가
- 실패 궤적 기반 수정 루프
- 개발 태스크와 평가 태스크 분리
- 자동 생성 스킬과 사람 작성 스킬 비교

### 3.4 Skill Coverage — `SKILL.md` 지침 커버리지

- 논문: [Skill Coverage: A Test Adequacy Metric for Agent Skills](https://arxiv.org/abs/2606.20659)
- 프로젝트: <https://shuaijiumei.github.io/skillcoverage/>
- 공식 코드: 작성 시점에 공개 저장소를 확인하지 못함
- 역할: 스킬 지침에서 관측 가능한 행동 제약을 추출하고 실행 궤적이 이를 실제로 검증했는지 측정

**본 프로젝트에서 직접 구현할 부분**

- 지침 → 행동 제약 변환
- 궤적별 `NOT_APPLICABLE / COVERED_PASS / COVERED_FAIL / UNJUDGEABLE` 판정
- 전체 스킬 커버리지와 미검증 지침 목록

### 3.5 Skill Usage — 실제 스킬 검색·선택·사용 분석

- 논문: [How Well Do Agentic Skills Work in the Wild](https://arxiv.org/abs/2604.04323)
- 저장소: <https://github.com/UCSB-NLP-Chang/Skill-Usage>
- 역할: 대규모 스킬 모음에서 검색·선택·사용률과 커버리지 분석

**본 프로젝트에서 재사용할 부분**

- 자동 스킬 선택 조건
- 스킬 사용 여부 분석
- Skill Coverage 판정 스크립트 구조
- 다수 스킬이 존재하는 실제 운영 환경 모사

### 3.6 SkillSmith — 스킬 실행 오버헤드 최적화

- 논문: [SkillSmith](https://arxiv.org/abs/2605.15215)
- 저장소: <https://github.com/AetherHeart-AI/Aeloon>
- 역할: 원본 스킬을 최소 실행 인터페이스로 컴파일하여 토큰·추론·실행시간 절감

초기 평가 플랫폼 완성 후, 원본 스킬과 컴파일된 스킬의 성공률·시간·비용을 비교하는 최적화 단계에 활용한다.

---

## 4. 권장 기술 선택

### 기본 프레임워크

**SkillsBench를 포크해 평가 실행의 중심으로 사용한다.**

- 실행·격리·태스크 구조: SkillsBench
- 코딩 태스크와 테스트: SWE-Skills-Bench
- 자동 검색·선택 평가: Skill Usage
- 지침 커버리지: Skill Coverage 방식 직접 구현
- 자동 개선: SkillLearnBench 방식
- 실행 최적화: SkillSmith 선택 적용

### 권장 구성요소

- Python 3.11+
- Docker 또는 사내 격리 컨테이너
- `uv` 기반 의존성 고정
- PostgreSQL: 실험·메트릭·스킬 버전 저장
- MinIO 또는 파일 스토리지: 궤적·산출물·컨테이너 로그
- Langfuse: 모델·도구 호출 관찰성
- FastAPI: 스킬·태스크 등록 및 평가 API
- React 또는 Grafana: 결과 대시보드
- Git: 스킬과 태스크 버전 관리

---

## 5. 전체 시스템 구조

```text
Skill Productivity Evaluation Platform
├── Skill Registry
│   ├── SKILL.md
│   ├── scripts/
│   ├── references/
│   ├── assets/
│   └── version metadata
│
├── Task Registry
│   ├── task.md
│   ├── initial_state/
│   ├── environment/Dockerfile
│   ├── verifier/
│   ├── hidden_tests/
│   └── task metadata
│
├── Experiment Runner
│   ├── No-Skill Runner
│   ├── Forced-Skill Runner
│   ├── Auto-Discovery Runner
│   └── Ablation Runner
│
├── Trace Collector
│   ├── model calls
│   ├── tool calls
│   ├── file and state changes
│   ├── timestamps
│   └── token and cost
│
├── Evaluator
│   ├── deterministic verifier
│   ├── policy checker
│   ├── quality scorer
│   └── blind LLM judge
│
├── Skill Analyzer
│   ├── static constraint extractor
│   ├── trajectory coverage analyzer
│   ├── failure attribution
│   └── skill refinement generator
│
└── Report Generator
    ├── Skill Lift
    ├── Operational Lift
    ├── time and cost
    ├── skill coverage
    ├── failure modes
    └── confidence intervals
```

---

## 6. 태스크 패키지 규격

```text
tasks/<domain>/<task-id>/
├── task.md
├── metadata.yaml
├── environment/
│   ├── Dockerfile
│   └── initial_state/
├── oracle/
│   └── solve.sh
├── verifier/
│   ├── test.sh
│   └── score.py
└── hidden_tests/
```

예시 메타데이터:

```yaml
task_id: api-error-handling-001
domain: software-engineering
task_type: defect-fix
source: historical-task
required_skill: python-resilience

difficulty_features:
  repositories: 1
  systems: 2
  external_integrations: 1
  database_change: false

limits:
  wall_clock_seconds: 1800
  max_model_calls: 50
  max_tool_calls: 100

success:
  verifier: verifier/test.sh
  minimum_score: 1.0
```

---

## 7. 평가 조건

### C0. No Skill

스킬을 제공하지 않는다. 모델의 기본 능력을 측정한다.

### C1. Forced Skill

대상 스킬을 명시적으로 로드한다. 스킬 자체의 최대 효능을 측정한다.

### C2. Auto Discovery

대상 스킬과 유사하거나 무관한 스킬을 함께 제공한다. 에이전트가 올바른 스킬을 찾고 사용하는 실제 운영 효과를 측정한다.

### C3. Ablation

스킬 구성요소를 하나씩 제거한다.

- `SKILL.md`만 제공
- 스크립트 제거
- 참고자료 제거
- 검증 절차 제거
- 특정 지침 제거

이를 통해 실제 성능 향상에 기여한 구성요소를 찾는다.

### C4. Compiled Skill — 선택

SkillSmith 방식으로 컴파일한 스킬과 원본 스킬을 비교한다.

---

## 8. 반복 실행과 통제

각 `태스크 × 조건 × 모델`을 파일럿에서는 3회, 정식 평가에서는 5~10회 반복한다.

다음 항목을 동일하게 고정한다.

- 모델과 버전
- 에이전트 하네스
- 초기 상태
- 허용 도구와 권한
- 시간·토큰·행동 제한
- 샘플링 설정
- 네트워크 접근 정책

실행 순서는 무작위화하고, 실행 간 메모리와 캐시는 공유하지 않는다.

---

## 9. 자동 채점

### 9.1 결정적 검증

- 테스트 통과
- 목표 DB 상태 도달
- 필수 파일 및 필드 존재
- API 응답 일치
- 기존 기능 회귀 없음
- 금지된 파일·시스템 변경 없음
- 테스트·채점기 변조 없음

### 9.2 문서·분석 결과 평가

자동 검증이 어려운 경우 다음을 적용한다.

- 구조적 필수 항목 검사
- 근거 문서와 사실 일치 검사
- 복수 블라인드 평가 에이전트
- Skill/No-Skill 조건과 모델명을 평가자에게 비공개

---

## 10. 핵심 지표

### 10.1 Skill Lift

```text
Skill Lift = P(success | Forced Skill) - P(success | No Skill)
```

### 10.2 Operational Lift

```text
Operational Lift = P(success | Auto Discovery) - P(success | No Skill)
```

Forced Skill은 스킬 자체의 효능이고, Auto Discovery는 실제 운영에서 얻을 수 있는 효과이다.

### 10.3 성공당 시간

```text
Time per Success = 전체 실행시간 / 성공 횟수
```

단순 평균 실행시간은 빠른 실패 때문에 왜곡될 수 있으므로 성공당 시간을 함께 보고한다.

### 10.4 성공당 비용

```text
Cost per Success = 전체 모델·도구 비용 / 성공 횟수
```

### 10.5 품질조정 효용

```text
Skill Utility = 품질점수 × 성공확률 / (실행시간 + 모델비용 + 재작업비용)
```

### 10.6 부정적 효과

- 스킬 사용 후 성공률 하락
- 토큰과 실행시간 증가
- 불필요한 도구 호출 증가
- 금지 행동 증가
- 오래되거나 잘못된 지침 사용
- 결과 품질 저하

---

## 11. `SKILL.md` 정적 분석과 커버리지

### 11.1 행동 제약 추출

`SKILL.md`에서 다음을 구조화한다.

- 트리거 조건
- 필수 행동
- 금지 행동
- 실행 순서
- 검증 절차
- 오류 복구
- 출력 요구사항

예시:

```json
{
  "constraint_id": "C-017",
  "condition": "기존 DOCX를 수정하는 경우",
  "required_action": "수정 후 렌더링해 시각 검증한다",
  "forbidden_action": "렌더링 검증 없이 결과를 반환한다",
  "observable_evidence": [
    "render command",
    "page image",
    "verification result"
  ],
  "severity": "high"
}
```

### 11.2 궤적 판정

각 제약을 실행 궤적과 비교한다.

| 판정 | 의미 |
|---|---|
| `NOT_APPLICABLE` | 해당 조건이 발생하지 않음 |
| `COVERED_PASS` | 조건이 발생했고 지침을 준수함 |
| `COVERED_FAIL` | 조건이 발생했지만 지침을 위반함 |
| `UNJUDGEABLE` | 증거가 부족해 판정 불가 |

### 11.3 커버리지

```text
Skill Coverage = 평가 가능한 상태로 실행된 제약 수 / 전체 행동 제약 수
```

성공률이 높더라도 커버리지가 낮으면 스킬의 상당 부분은 아직 검증되지 않은 것이다.

---

## 12. 실패 원인 분류

```text
ROUTING_FAILURE
  필요한 스킬을 검색·선택하지 못함

SKILL_DEFECT
  스킬 지침이 틀렸거나 불완전함

INSTRUCTION_NONCOMPLIANCE
  올바른 지침이 있었으나 에이전트가 따르지 않음

TOOL_FAILURE
  도구·권한·환경 문제

MODEL_CAPABILITY_FAILURE
  지침을 따르더라도 모델 능력 부족

VERIFIER_OR_TASK_DEFECT
  태스크 또는 채점기의 오류
```

실패 원인은 실행 로그와 Skill Coverage 판정을 기반으로 자동 분류하고, 불확실한 경우에만 사람이 검토한다.

---

## 13. 스킬 자동 개선 루프

```text
스킬 실행
→ 실패 궤적 수집
→ 실패 원인 분류
→ 위반되거나 누락된 제약 식별
→ SKILL.md 수정안 생성
→ 개발 태스크에서 재평가
→ 회귀시험
→ 숨겨진 평가 태스크 검증
→ 기준을 통과한 버전만 승격
```

### 자동 승격 기준 예시

- 성공률 5%p 이상 상승
- 성공당 비용이 20% 이상 악화되지 않음
- 기존 성공 태스크의 회귀 없음
- 금지 행동 증가 없음
- 숨겨진 평가 세트에서도 개선 재현

자기평가만 반복하면 스킬이 특정 태스크에 과적합되거나 잘못된 방향으로 변할 수 있으므로, 개선 에이전트와 평가 태스크를 분리한다.

---

## 14. 데이터 모델

### 주요 테이블

```text
skills
  skill_id, version, git_commit, metadata, created_at

tasks
  task_id, domain, type, source, difficulty_features

experiments
  experiment_id, skill_id, skill_version, task_id,
  condition, model, harness, seed, limits

runs
  run_id, experiment_id, started_at, finished_at,
  success, score, tokens, cost, wall_time

trajectory_events
  run_id, timestamp, event_type, tool_name,
  input_hash, output_hash, artifact_uri

skill_constraints
  skill_id, version, constraint_id, condition,
  required_action, forbidden_action, evidence_rule

constraint_results
  run_id, constraint_id, verdict, evidence_uri

failure_attributions
  run_id, failure_type, confidence, rationale
```

민감한 입력과 산출물 본문은 가능한 한 별도 보안 스토리지에 저장하고, 분석 DB에는 해시·메타데이터·참조 URI만 둔다.

---

## 15. 권장 저장소 구조

```text
skill-eval-platform/
├── upstream/
│   └── skillsbench/
├── skills/
│   └── <skill-id>/<version>/
├── tasks/
│   └── <domain>/<task-id>/
├── adapters/
│   ├── claude_code.py
│   ├── codex.py
│   ├── openhands.py
│   └── custom_agent.py
├── runners/
│   ├── paired_runner.py
│   ├── discovery_runner.py
│   └── ablation_runner.py
├── evaluators/
│   ├── deterministic.py
│   ├── policy.py
│   └── llm_judge.py
├── analyzers/
│   ├── skill_constraints.py
│   ├── trajectory_coverage.py
│   ├── failure_attribution.py
│   └── skill_refiner.py
├── statistics/
│   ├── paired_bootstrap.py
│   ├── mcnemar.py
│   └── report_metrics.py
├── api/
├── dashboards/
└── results/
```

---

## 16. 통계 분석

동일 태스크를 Skill/No-Skill 조건에서 비교하므로 짝지은 분석을 사용한다.

- 성공 여부: McNemar 검정
- 성공률 차이: 태스크 단위 짝지은 부트스트랩 신뢰구간
- 실행시간·비용: 성공 태스크 기준 짝 비교 및 성공당 비용 비교
- 여러 모델·부서·태스크 유형: 혼합효과 회귀
- 평균값과 함께 95% 신뢰구간 보고

보고 예시:

```text
전체 Skill Lift: +12.0%p
95% 신뢰구간: +5.1~+18.7%p

전문 절차 업무: +24.0%p
단순 업무:       +2.0%p
장기 업무:       -4.0%p
```

---

## 17. 단계별 구현 계획

### 1단계. 외부 프레임워크 재현

- SkillsBench 포크
- 공개 태스크 5~10개 실행
- Docker, Verifier, Skill/No-Skill 비교 확인
- 실행 로그와 결과 스키마 정의

**완료 기준**

- 동일 태스크의 paired run 자동 실행
- 성공률·시간·토큰·비용 리포트 생성

### 2단계. 사내 태스크 이식

- 우선 대상 부서 1개 선정
- 과거 실제 업무 20~30개 수집
- 초기 상태와 결정적 검증기 작성
- 개발용과 숨겨진 평가용 태스크 분리

**완료 기준**

- 사내 스킬 3~5개에 대해 Skill/No-Skill 비교 가능
- 태스크의 80% 이상이 자동 채점 가능

### 3단계. 스킬 커버리지 구현

- `SKILL.md` 행동 제약 자동 추출
- 실행 궤적과 제약 매핑
- 커버리지·미준수 지침 리포트

**완료 기준**

- 지침별 Pass/Fail/Not Applicable 판정
- 사람이 검토한 표본과 85% 이상 일치

### 4단계. 실제 운영 조건 평가

- Auto Discovery 조건 추가
- 여러 스킬 중 선택 정확도 측정
- 호출 실패와 스킬 효능을 분리

**완료 기준**

- Forced Skill Lift와 Operational Lift를 별도로 제공

### 5단계. 자동 개선

- 실패 원인 분류
- 수정안 자동 생성
- 개발 세트 재평가와 회귀시험
- 승인된 버전만 스킬 레지스트리에 승격

**완료 기준**

- 최소 1개 스킬에서 숨겨진 세트 성능 향상 재현

### 6단계. 부서·조직 생산성 연결

벤치마크의 스킬 실행효과를 실제 운영 데이터와 연결한다.

- 업무 유형별 월간 발생량
- 사람 검토시간
- 재작업·결함 비용
- 실제 채택률
- PMO 인력·예산

```text
조직 기대 절감시간
= 업무 발생량
× (No-Skill 사람 개입시간 - Skill 사람 개입시간)
× 실제 스킬 적용률
× 품질조정 성공률
```

---

## 18. 파일럿 권장 범위

처음에는 다음 범위로 제한한다.

- 대상 부서: 1개
- 스킬: 3개
- 태스크: 스킬당 10개, 총 30개
- 조건: No Skill / Forced Skill / Auto Discovery
- 반복: 조건당 태스크별 5회
- 모델: 1개
- 총 실행: 약 450회

Ablation과 자동 개선은 파일럿 이후 추가한다.

---

## 19. 주요 위험과 통제

| 위험 | 통제 방안 |
|---|---|
| 스킬에 맞춘 태스크 생성 | 과거 실제 업무·숨겨진 평가 세트 사용 |
| 평가기 노출 또는 변조 | hidden tests 분리, 읽기 전용 마운트 |
| 한 번의 우연한 성공 | 태스크별 반복 실행과 신뢰구간 |
| 토큰 증가를 생산성으로 오인 | 성공률·성공당 시간·성공당 비용 중심 |
| LLM 평가 편향 | 결정적 검증 우선, 블라인드 복수 평가 |
| 스킬 자동 개선의 과적합 | 개발·검증·숨겨진 테스트 분리 |
| 민감한 사내 데이터 유출 | 격리 실행, 최소 저장, 비식별화 |
| 특정 모델에만 최적화 | 모델·하네스별 결과 분리 보고 |

---

## 20. 최종 산출물

1. SkillsBench 기반 사내 평가 실행기
2. 사내 태스크 레지스트리와 작성 가이드
3. 스킬 버전 레지스트리
4. Skill/No-Skill/Auto Discovery 실험 실행기
5. 결정적 검증기 SDK
6. `SKILL.md` 행동 제약 추출기
7. Skill Coverage 및 실패 원인 분석기
8. 자동 스킬 개선·회귀시험 파이프라인
9. 성공률·시간·비용·커버리지 대시보드
10. 부서 생산성 환산용 데이터 인터페이스

---

## 21. 최종 권고

새 평가 시스템을 처음부터 전부 개발하지 않는다.

> **SkillsBench를 실행 기반으로 포크하고, SWE-Skills-Bench의 결정적 테스트 방식, Skill Usage의 자동 검색·선택 분석, Skill Coverage의 지침 커버리지를 결합한다. 이후 SkillLearnBench 방식의 자동 개선 루프를 추가한다.**

첫 번째 구현 목표는 다음으로 제한하는 것이 적절하다.

```text
SkillsBench 포크
→ 사내 태스크 30개
→ 스킬 3개
→ Skill/No-Skill/Auto Discovery 각 5회 반복
→ 결정적 검증
→ 성공률·성공당 시간·성공당 비용 보고
```

이 결과가 안정적으로 나오면 지침 커버리지, Ablation, 자동 개선, 조직 생산성 환산 순서로 확장한다.
