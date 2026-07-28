"""정적 구조 진단 — 실행 없이 SKILL.md를 읽어 효과를 추산한다.

주의: 이것은 예측이지 측정이 아니다. 실측 Skill Lift를 대체하지 않으며,
용도는 (a) 실행 비용을 쓰기 전 스크리닝, (b) 명백한 구조 결함(트리거 모호,
검증 절차 부재 등) 조기 발견이다. 스킬 파일은 읽기만 하고 수정하지 않는다.

채점 항목 (가중 평균 → 0~100점):
- trigger        발동 조건이 구체적인가 (설명·트리거 문구·예시)
- steps          지침이 실행 가능한 단계로 쪼개져 있는가
- vagueness      모호어("잘", "적절히", "알아서" 등) 비율
- verification   자체 검증 절차가 있는가
- recovery       오류·실패 시 대응 지침이 있는가
- output_spec    산출물·형식 요구가 명시돼 있는가
- resources      동봉 자원(scripts/references/assets)과 본문 참조 일치
- overhead       분량(추정 토큰) — 길수록 매 실행 컨텍스트 비용
- constraints    constraints.json 존재 (커버리지 판정 가능 여부)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..registry import SkillPackage

# 모호어: 관측 가능한 행동으로 번역되지 않는 표현.
# 주의: 모든 패턴 집합은 한/영 대칭을 유지해야 한다 — 같은 내용의 스킬이
# 언어에 따라 다른 점수를 받으면 안 된다 (tests/test_static_lint.py의 동등성 테스트가 강제).
_VAGUE_PATTERNS = [
    # KR
    r"잘\s", r"적절히", r"적절한", r"알아서", r"필요에\s*따라", r"가능하면",
    r"상황에\s*맞게", r"유연하게", r"신중히", r"충분히",
    # EN
    r"\bproperly\b", r"\bappropriately\b", r"\bas\s+needed\b", r"\bif\s+necessary\b",
    r"\bas\s+appropriate\b", r"\bwhen\s+possible\b", r"\bflexibly\b", r"\bcarefully\b",
    r"\bideally\b", r"\bsufficiently\b",
]

# 검증 절차 증거 (KR | EN)
_VERIFY_RE = (
    r"검증|확인한\s*뒤|확인\s*후|재확인|채점|테스트를?\s*(돌|실행)|"
    r"\bverify|\bvalidat|\bself[- ]check\b|\bdouble[- ]check\b|\bconfirm\b|"
    r"\bensure\b|\brun\s+(the\s+)?tests?\b|\bassert\b"
)

# 오류·실패 대응 증거 (KR | EN)
_RECOVERY_RE = (
    r"실패\s*시|실패하면|오류|에러|안\s*되면|재시도|복구|"
    r"\berrors?\b|\bfail(s|ure|ed|ing)?\b|\bfallback\b|\bretry\b|\brecover|\btroubleshoot"
)

# 산출물·형식 증거 (KR | EN)
_OUTPUT_RE = (
    r"산출물|출력|결과\s*파일|파일명|형식|포맷|반환|작성한다|생성한다|저장한다|"
    r"\boutput\b|\bdeliverable\b|\bartifact\b|\bformat\b|\breturn\b|"
    r"\bproduce\b|\bgenerate\b|\bcreate\b|\bwrite\b|\bsave\b|\bfile\s*name\b"
)

_STEP_RE = re.compile(r"^\s*(\d+[.)]|[-*+])\s+\S", re.MULTILINE)


def _estimate_tokens(text: str) -> int:
    """한/영 혼합 대략 추정: ASCII ≈ 4자/토큰, 비ASCII ≈ 1.8자/토큰."""
    ascii_n = sum(1 for c in text if c.isascii())
    return int(ascii_n / 4 + (len(text) - ascii_n) / 1.8)


@dataclass
class CheckResult:
    check_id: str
    name: str
    weight: float
    score: float  # 0.0 ~ 1.0
    evidence: str
    advice: str = ""


@dataclass
class LintReport:
    skill_id: str
    version: str
    est_tokens: int
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        """가중 평균 0~100."""
        total_w = sum(c.weight for c in self.checks)
        if not total_w:
            return 0.0
        return round(100 * sum(c.score * c.weight for c in self.checks) / total_w, 1)

    @property
    def findings(self) -> list[CheckResult]:
        return [c for c in self.checks if c.score < 0.7 and c.advice]

    # SkillsBench 공개 집계(선별 스킬 평균 해결률 33.9%→50.5% ≈ 상대 +49%)를 상한 앵커로,
    # 구조 점수를 선형 스케일한 휴리스틱 추정. 검증된 예측 모델이 아니다.
    ANCHOR_UPLIFT = 0.49

    @property
    def est_efficiency_uplift(self) -> float:
        return round(self.total_score / 100 * self.ANCHOR_UPLIFT, 3)


def lint_skill(skill: SkillPackage) -> LintReport:
    md = skill.skill_md
    body = re.sub(r"^---\n.*?\n---\n", "", md, count=1, flags=re.DOTALL)  # frontmatter 분리
    frontmatter = md[: len(md) - len(body)]
    # 라벨: skills/<id>/<version> 구조 밖 경로도 지원 — frontmatter name 우선, 버전은 숫자형만
    name_m = re.search(r"^name:\s*(\S+)", frontmatter, re.MULTILINE)
    skill_id = name_m.group(1) if name_m else skill.skill_id
    version = skill.version if re.match(r"^\d", skill.version) else ""
    report = LintReport(skill_id, version, _estimate_tokens(md))
    add = report.checks.append

    # trigger — 발동 조건의 구체성
    has_desc = bool(re.search(r"^description:\s*\S", frontmatter, re.MULTILINE))
    trigger_section = bool(re.search(r"^#+.*(트리거|trigger|사용\s*시점|when to use)", md, re.IGNORECASE | re.MULTILINE))
    quoted_examples = len(re.findall(r"[\"“'‘][^\"”'’]{2,40}[\"”'’]", frontmatter))
    score = 0.0
    if has_desc or trigger_section:
        score = 0.6
        if quoted_examples >= 1 or trigger_section:
            score = 1.0
    add(CheckResult(
        "trigger", "발동 조건 구체성", 2.0, score,
        f"description={'있음' if has_desc else '없음'}, 트리거 섹션={'있음' if trigger_section else '없음'}, 예시 문구 {quoted_examples}개",
        "" if score >= 0.7 else "frontmatter description에 구체적 발동 문구(따옴표 예시)를 넣거나 트리거 섹션을 추가하라",
    ))

    # steps — 실행 가능한 단계 구조
    steps = len(_STEP_RE.findall(body))
    add(CheckResult(
        "steps", "단계화된 지침", 2.0, min(1.0, steps / 5),
        f"목록/번호 단계 {steps}개",
        "" if steps >= 4 else "지침을 번호 매긴 실행 단계로 쪼개라 — 산문 지침은 준수 판정이 어렵다",
    ))

    # vagueness — 모호어 밀도
    vague_hits = [m.group(0).strip() for p in _VAGUE_PATTERNS for m in re.finditer(p, body, re.IGNORECASE)]
    add(CheckResult(
        "vagueness", "모호어 밀도", 1.5, max(0.0, 1.0 - len(vague_hits) / 5),
        f"모호어 {len(vague_hits)}건: {', '.join(sorted(set(vague_hits))[:5]) or '없음'}",
        "" if len(vague_hits) <= 1 else "모호어를 관측 가능한 행동(무엇을, 어떤 기준으로)으로 바꿔라",
    ))

    # verification — 자체 검증 절차
    has_verify = bool(re.search(_VERIFY_RE, body, re.IGNORECASE))
    add(CheckResult(
        "verification", "자체 검증 절차", 2.0, 1.0 if has_verify else 0.0,
        "검증 지침 있음" if has_verify else "검증 지침 없음",
        "" if has_verify else "결과를 반환하기 전 검증하는 단계를 명시하라 — 검증 지침은 실측에서 성공률을 가르는 대표 요인",
    ))

    # recovery — 오류 대응
    has_recovery = bool(re.search(_RECOVERY_RE, body, re.IGNORECASE))
    add(CheckResult(
        "recovery", "오류·실패 대응", 1.0, 1.0 if has_recovery else 0.0,
        "오류 대응 지침 있음" if has_recovery else "오류 대응 지침 없음",
        "" if has_recovery else "대표 실패 상황과 복구 방법을 한 줄이라도 명시하라",
    ))

    # output_spec — 산출물 명시
    has_output = bool(re.search(_OUTPUT_RE, body, re.IGNORECASE))
    add(CheckResult(
        "output_spec", "산출물·형식 명시", 1.0, 1.0 if has_output else 0.0,
        "산출물 요구 있음" if has_output else "산출물 요구 없음",
        "" if has_output else "무엇을 어떤 형식으로 내야 완료인지 명시하라",
    ))

    # resources — 동봉 자원과 본문 참조 일치
    subdirs = [d for d in ("scripts", "references", "assets") if (skill.root / d).exists()]
    referenced = [d for d in ("scripts", "references", "assets") if re.search(rf"{d}/", body)]
    missing = [d for d in referenced if d not in subdirs]
    if missing:
        res_score, res_ev = 0.0, f"본문이 참조하지만 없는 디렉토리: {', '.join(missing)}"
        res_adv = "참조하는 동봉 자원이 실제로 존재하게 하라 (깨진 참조는 실행 실패 요인)"
    elif subdirs and not referenced:
        res_score, res_ev = 0.5, f"동봉 자원 {', '.join(subdirs)} 있으나 본문에서 참조 안 함"
        res_adv = "동봉 자원을 언제 쓰는지 본문에서 참조하라 — 참조 없는 자원은 로드만 되고 안 쓰인다"
    elif subdirs:
        res_score, res_ev, res_adv = 1.0, f"동봉·참조 일치: {', '.join(subdirs)}", ""
    else:
        res_score, res_ev, res_adv = 0.8, "동봉 자원 없음 (필수 아님)", ""
    add(CheckResult("resources", "동봉 자원 일치", 1.0, res_score, res_ev, res_adv))

    # overhead — 분량(매 실행 컨텍스트 비용)
    t = report.est_tokens
    if t <= 500:
        oh_score, oh_label = 1.0, "낮음"
    elif t <= 1500:
        oh_score, oh_label = 0.8, "보통"
    elif t <= 3000:
        oh_score, oh_label = 0.5, "높음"
    else:
        oh_score, oh_label = 0.2, "매우 높음"
    add(CheckResult(
        "overhead", "분량 오버헤드", 1.5, oh_score,
        f"추정 {t:,} 토큰 → 오버헤드 {oh_label}",
        "" if oh_score >= 0.7 else "매 실행마다 읽히는 비용이 크다 — 핵심 지침만 남기고 세부는 references/로 내려라",
    ))

    # constraints — 커버리지 판정 가능 여부
    n_constraints = len(skill.constraints)
    add(CheckResult(
        "constraints", "행동 제약 정의", 1.0, 1.0 if n_constraints else 0.0,
        f"constraints.json {n_constraints}개 제약" if n_constraints else "constraints.json 없음",
        "" if n_constraints else "constraints.json이 없으면 실측 시 지침 커버리지 판정이 불가하다",
    ))

    return report


def render_lint_markdown(report: LintReport) -> str:
    label = f"{report.skill_id}@{report.version}" if report.version else report.skill_id
    lines = [
        f"# Static Lint — {label}",
        "",
        f"## 결론",
        "",
        f"**추정 효율 상승: ≈ {report.est_efficiency_uplift:+.0%}** (휴리스틱 — 실측 아님)",
        f"(구조 점수 {report.total_score}/100 × 앵커 +{report.ANCHOR_UPLIFT:.0%}; "
        f"앵커 = SkillsBench 선별 스킬 평균 효과)",
        "",
        f"구조 품질 점수: {report.total_score}/100, 추정 {report.est_tokens:,} 토큰",
        "",
        "| 항목 | 가중치 | 점수 | 근거 |",
        "|---|---|---|---|",
    ]
    for c in report.checks:
        lines.append(f"| {c.name} | {c.weight:g} | {c.score:.2f} | {c.evidence} |")
    if report.findings:
        lines += ["", "## 개선 포인트", ""]
        for c in report.findings:
            lines.append(f"- **{c.name}**: {c.advice}")
    lines += [
        "",
        "> 이 점수는 실행 없이 문서 구조만 본 **추정**이다. 실제 효과(Skill Lift)와 다를 수 있으며,",
        "> 실측을 대체하지 않는다. 용도: 실행 전 스크리닝과 명백한 구조 결함 발견.",
    ]
    return "\n".join(lines)
