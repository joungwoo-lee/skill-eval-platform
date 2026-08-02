# 세션 → 업무 매칭 트리거 설계

아바타 효율성 구조(→ [avatar-overview-map.html](avatar-overview-map.html) · [avatar-structure-map.html](avatar-structure-map.html))에서
"세션 종료 시 Haiku가 세션 내용을 읽어 역할·업무에 매칭하고 효율계수 η를 산정"하는 작업의 실행 설계.

**채택안: 클로드 세션 시작 시점에 백그라운드 스위퍼를 띄워, 시작 시점 이전의 미처리 transcript를 소급 처리한다.**

## 1. 분석 대상 파일 — transcript

- 위치: `~/.claude/projects/<cwd 인코딩 폴더>/<세션uuid>.jsonl`
- **작업폴더(cwd)별 폴더 분리 저장**. 인코딩 규칙: 절대경로의 `[^a-zA-Z0-9]` 전부 `-` 치환

```
C--Users-joung                                ← C:\Users\joung
C--Users-joung-agent-gateway-discord          ← C:\Users\joung\agent-gateway-discord
C--Users-joung-agent-gateway-discord-web-ui   ← …\agent-gateway-discord\web-ui  (하위 폴더도 별개)
C--Users-joung-skill-eval-platform            ← C:\Users\joung\skill-eval-platform
```

- 세션 1개 = JSONL 1개 (파일명 = 세션 uuid). resume 시 같은 파일에 이어 씀
- 내용: user/assistant 메시지 레코드 + `type:"summary"` 요약 라인
- `%USERPROFILE%\.claude\projects\` 루트가 **PC 로그인 계정당 하나** → 로그인 ID 기준 아바타 선별과 자연스럽게 일치
- Haiku 매칭 입력은 파일 전체가 아니라 **첫 user 프롬프트 + 마지막 N개 메시지(또는 summary 라인)** 만 — 토큰 절약

참고: SessionEnd hook은 정상 종료(exit, `/clear`, logout)에서만 발화한다.
방치·강제 종료·크래시에서 안 걸리므로 종료 이벤트 기반 수집은 채택하지 않았다.
세션 시작을 트리거로 쓰면 "이전에 어떻게 끝났든" 다음 기동 때 반드시 잡힌다.

## 2. 채택 설계 — SessionStart 스위퍼

1. settings.json에 SessionStart hook 등록 (matcher `startup` — resume/clear 제외)
2. hook은 스위퍼 스크립트를 **detach 스폰 후 즉시 리턴**
   (hook이 안 끝나면 세션 기동이 블록됨 → `Start-Process -WindowStyle Hidden` 필수)
3. 스위퍼: `~/.claude/projects/` 전체에서 다음 조건의 transcript만 골라 Haiku 매칭 → 처리 원장(ledger)에 기록

**처리 대상 조건 (세션 시작 시점 기준):**
- `mtime < 이번 세션 시작 시각`
- AND 처리 원장에 없는 uuid (또는 원장 기록 이후 mtime이 갱신된 uuid — resume 재매칭)
- AND mtime이 최근 30분 이내가 아님 (다른 진행 중 세션 제외)
- AND 자기 자신 uuid 아님

```json
"hooks": {
  "SessionStart": [{
    "matcher": "startup",
    "hooks": [{ "type": "command",
      "command": "powershell -Command \"Start-Process powershell -WindowStyle Hidden -ArgumentList '-File C:\\Users\\joung\\sweep-transcripts.ps1'\"" }]
  }]
}
```

**필수 가드 3개:**
1. **락파일 단일 인스턴스** — 세션 동시 다발 기동 시 스위퍼 중복 방지
2. **스로틀** — 마지막 스윕 후 N시간 경과 시에만 실행 (원장에 lastSweep 기록)
3. **진행 중 세션 제외** — mtime 최근 30분 이내 스킵 + 자기 자신 uuid 제외

**공통 원칙:** 매칭 결과는 **세션 uuid 기준 upsert** (resume으로 이어진 세션은 다음 스윕에서 재매칭·갱신),
처리 이력은 **공유 원장 하나**로 — 이중 매칭 없음.

장점: 크론·스케줄러 등록 불필요, 클로드를 쓰는 날에만 돎 — 사용자가 클로드를 켜는 행위 자체가 배치 트리거.
한계: 클로드를 안 켜는 날은 처리 지연 (다음 기동 때 소급 처리되므로 누락은 아님).

## 3. 진행 중 세션 무간섭 근거

1. **읽기 전용** — transcript는 읽기만. Claude의 JSONL append는 공유 읽기 허용이라 쓰기 락 충돌 없음
2. **자기 세션 제외** — 새로 켠 세션 transcript는 mtime 최신 + 자기 uuid 명시 제외
3. **다른 진행 중 세션** — mtime 30분 가드로 스킵. 30분 넘게 idle인 열린 세션은 읽혀도 무해, 이어가면 다음 스윕에서 upsert 갱신
4. **기동 지연 없음** — detach 스폰 후 hook 즉시 리턴
5. **원장/락은 스위퍼 전용 경로** — 클로드가 보는 파일 아님

### ⚠ 유일한 실전 함정 — `CLAUDE_CODE_*` env 누수
SessionStart hook의 자식 프로세스는 부모 클로드 세션의 환경변수를 물려받는다.
스위퍼가 Haiku 매칭을 `claude -p`로 돌리면 nested 마커가 새서 자식 클로드가 중첩 세션으로
오판·이상동작할 수 있음 (launcher-restarter에서 동일 문제로 6개 변수 스크럽한 실측 전례).
→ 스위퍼 시작부에서 `CLAUDE_CODE_*` 환경변수 제거, 또는 Haiku를 CLI 대신 **API 직접 호출**로 원천 회피.
