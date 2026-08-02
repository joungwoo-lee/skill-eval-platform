# 세션 → 업무 매칭 트리거 설계

아바타 효율성 구조(→ [avatar-overview-map.html](avatar-overview-map.html) · [avatar-structure-map.html](avatar-structure-map.html))에서
"세션 종료 시 Haiku가 세션 내용을 읽어 역할·업무에 매칭하고 효율계수 η를 산정"하는 작업을
**언제, 무엇을 읽어** 수행할지에 대한 설계 정리.

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

## 2. 트리거 후보와 한계

### SessionEnd hook — 단독 사용 불가
- 발화 조건 = 정상 종료(exit, `/clear`, logout)뿐
- **방치(터미널 열어둔 채 이탈), 창 강제 종료, 크래시, PC 절전 → 안 걸림**. 실사용에선 방치가 흔해 누락 큼
- 걸리면 즉시 확정하는 조기 트리거로만 활용

### Stop hook + idle 판정 (실시간형 정답)
1. Stop hook은 **매 턴 응답 완료마다** 발화 → 방치해도 "마지막 턴 완료" 기록은 남음
   (인터랙티브 transcript는 종료 시점 flush라 라이브 tail 불가 — 2.1.177 실측. 권위를 Stop hook에 두는 이유)
2. Stop에서는 `{uuid, transcript_path, 시각}`만 터치파일/큐에 기록 (매번 Haiku 돌리면 과도)
3. 스위퍼가 주기적으로 "마지막 Stop 후 T시간(예: 2h) 무활동 + mtime 정지" 세션을 종료로 간주 → Haiku 매칭
4. resume 대비: 매칭 결과를 **세션 uuid 기준 upsert** — 재개되면 다음 idle 판정 때 재매칭·갱신

### 야간 배치 (최소 구현형)
```powershell
$since = (Get-Content state.json | ConvertFrom-Json).lastRun   # 마지막 실행 시각
Get-ChildItem "$env:USERPROFILE\.claude\projects" -Recurse -Filter *.jsonl |
  Where-Object { $_.LastWriteTime -gt $since }
```
- "당일" 대신 **"마지막 실행 시각 이후"** 기준 — 스케줄 하루 빠져도 자동 보정, 자정 걸친 세션 누락 없음
- 밤엔 대부분 idle → flush 미완 문제 거의 없음. mtime 최근 30분 이내(진행 중)는 스킵해 다음 밤 처리
- 파일별 마지막 처리 오프셋 저장 → 증분 읽기
- 트레이드오프: 매칭 최대 하루 지연. 일 단위 대시보드면 충분

### SessionStart 스위퍼 (클로드 켤 때 밀린 것 처리)
- SessionStart hook(matcher `startup`)에서 스위퍼 스크립트를 **detach 스폰 후 즉시 리턴**
  (hook이 안 끝나면 세션 기동이 블록됨 → `Start-Process -WindowStyle Hidden` 필수)
- 스위퍼: `mtime < 세션 시작 시각` AND 처리 원장(ledger)에 없는 uuid만 골라 매칭 → 원장 기록

```json
"hooks": {
  "SessionStart": [{
    "matcher": "startup",
    "hooks": [{ "type": "command",
      "command": "powershell -Command \"Start-Process powershell -WindowStyle Hidden -ArgumentList '-File C:\\Users\\joung\\sweep-transcripts.ps1'\"" }]
  }]
}
```

필수 가드 3개:
1. **락파일 단일 인스턴스** — 세션 동시 다발 기동 시 스위퍼 중복 방지
2. **스로틀** — 마지막 스윕 후 N시간 경과 시에만 실행 (원장에 lastSweep 기록)
3. **진행 중 세션 제외** — mtime 최근 30분 이내 스킵 + 자기 자신 uuid 제외

장점: 크론 등록 불필요, 클로드를 쓰는 날에만 돎. 한계: 안 켜는 날 지연 → 야간 배치와 병용 시 상호 보완(원장 공유로 이중처리 없음).

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

## 4. 권장 조합

| 구성 | 역할 |
|---|---|
| Stop hook | 마지막 활동 시각 기록 (이벤트 신호) |
| idle 스위퍼 (주기) | "마지막 Stop 후 T시간 무활동" 세션 종료 판정 → Haiku 매칭 |
| SessionStart 스위퍼 | 클로드 기동 시 밀린 미처리 transcript 소급 처리 |
| 야간 배치 | 훅 누락·크래시 보정 스윕 (최후 안전망) |
| SessionEnd hook | 걸리면 즉시 확정하는 조기 트리거 (보너스) |

공통 원칙: 결과는 **세션 uuid 기준 upsert**, 처리 이력은 **공유 원장(ledger)** 하나로 — 어떤 경로로 처리되든 이중 매칭 없음.
