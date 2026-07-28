# 평가 태스크 작성 규격 (PLAN.md §6 요약)

## 디렉토리 구조

```text
tasks/<domain>/<task-id>/
├── task.md                        # 에이전트에게 주는 업무 지시문 (스킬 언급 금지!)
├── metadata.yaml
├── environment/
│   └── initial_state/             # 작업 시작 시점 파일들 (workdir로 복사됨)
├── oracle/
│   └── solve.py                   # 정답 풀이: python solve.py <workdir> → 산출물 생성
└── verifier/
    └── score.py                   # 채점기: python score.py <workdir> → JSON 출력
```

## metadata.yaml 템플릿

```yaml
task_id: <task-id>
domain: <domain>
task_type: <report-generation | defect-fix | data-processing | ...>
source: generated-from-skill      # 에이전트 생성 태스크는 반드시 이 값 (편향 추적용)
required_skill: <skill-id>        # 이 값으로 batch가 스킬↔태스크 매칭

limits:
  wall_clock_seconds: 600
  max_model_calls: 30
  max_tool_calls: 60

success:
  verifier: verifier/score.py
  minimum_score: 1.0
```

## verifier 계약

- 인자 1개: workdir 경로
- stdout **마지막 줄**에 JSON: `{"score": 1.0, "checks": {...}}` (score 0.0~1.0)
- exit 0 이외 / JSON 파싱 불가 = 검증기 오류 → VERIFIER_OR_TASK_DEFECT로 분류됨
- 결정적으로만 채점: 파일 존재, 정확한 값(정규식), 상태 일치. LLM 호출 금지.

## 작성 원칙

1. **task.md에 스킬 이름·지침을 절대 쓰지 않는다.** 순수 업무 지시만. (C0 조건에서도
   동일 지시문을 쓰므로 스킬 힌트가 들어가면 비교가 오염된다.)
2. 스킬이 다루는 업무 영역에서 출제하되, 스킬 문장을 베낀 문제는 금지.
   가능하면 스킬 예시와 다른 데이터·수치·상황으로 변형.
3. 난이도 3단계 권장:
   - 하: 지시문만 따라도 풀 수 있으나 스킬이 있으면 더 안정적으로 성공
   - 중: 스킬의 절차·검증 지침이 성공률을 실질적으로 가르는 수준
   - 상: 엣지케이스 포함 (스킬의 오류 복구·검증 지침이 없으면 실패하기 쉬움)
4. verifier가 요구하는 값은 initial_state에서 **계산으로 도출**한다 (하드코딩하면
   initial_state 수정 시 태스크가 깨진다).
5. 작성 직후 자가검증 (필수):

```bash
# oracle이 verifier를 통과하는가 (score 1.0)
cp -r tasks/<d>/<id>/environment/initial_state /tmp/tw && \
python tasks/<d>/<id>/oracle/solve.py /tmp/tw && \
python tasks/<d>/<id>/verifier/score.py /tmp/tw
# 빈 workdir은 실패하는가 (score < 1.0)
cp -r tasks/<d>/<id>/environment/initial_state /tmp/tw2 && \
python tasks/<d>/<id>/verifier/score.py /tmp/tw2
```

둘 다 통과 못 하면 태스크 결함 — 등록 금지.

## 참고 예시

플랫폼 레포 `tasks/demo/hello-report-001/` 이 최소 완전 예시다.
