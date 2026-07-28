"""데이터 모델과 SQLite 저장소 (PLAN.md §14).

계획서는 PostgreSQL을 권장하지만 MVP는 SQLite 단일 파일로 시작한다.
테이블 스키마는 §14의 주요 테이블을 그대로 따른다.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# 평가 조건 (PLAN.md §7)
CONDITIONS = ("C0_NO_SKILL", "C1_FORCED_SKILL", "C2_AUTO_DISCOVERY")

# 커버리지 판정 (PLAN.md §11.2)
VERDICTS = ("NOT_APPLICABLE", "COVERED_PASS", "COVERED_FAIL", "UNJUDGEABLE")

# 실패 원인 분류 (PLAN.md §12)
FAILURE_TYPES = (
    "ROUTING_FAILURE",
    "SKILL_DEFECT",
    "INSTRUCTION_NONCOMPLIANCE",
    "TOOL_FAILURE",
    "MODEL_CAPABILITY_FAILURE",
    "VERIFIER_OR_TASK_DEFECT",
)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class TrajectoryEvent:
    """Trace Collector가 수집하는 단일 이벤트 (PLAN.md §5)."""

    timestamp: float
    event_type: str  # model_call | tool_call | file_change | skill_loaded | error | note
    tool_name: str = ""
    detail: str = ""

    def as_text(self) -> str:
        """제약 매칭용 평문 표현."""
        return f"{self.event_type} {self.tool_name} {self.detail}"


@dataclass
class RunResult:
    """runs 테이블 한 행 + 궤적."""

    run_id: str
    experiment_id: str
    condition: str
    task_id: str
    skill_id: str | None
    skill_version: str | None
    model: str
    repeat_index: int
    started_at: float = 0.0
    finished_at: float = 0.0
    success: bool = False
    score: float = 0.0
    tokens: int = 0
    cost: float = 0.0
    wall_time: float = 0.0
    skill_was_loaded: bool = False
    verifier_error: str = ""
    trajectory: list[TrajectoryEvent] = field(default_factory=list)
    constraint_verdicts: dict[str, str] = field(default_factory=dict)
    failure_type: str | None = None
    failure_rationale: str = ""


@dataclass
class ExperimentSpec:
    """experiments 테이블 한 행."""

    experiment_id: str
    task_id: str
    skill_id: str | None
    skill_version: str | None
    condition: str
    model: str
    harness: str
    seed: int
    repeats: int
    limits: dict[str, Any] = field(default_factory=dict)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
  skill_id TEXT, version TEXT, git_commit TEXT, metadata TEXT, created_at REAL,
  PRIMARY KEY (skill_id, version)
);
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY, domain TEXT, type TEXT, source TEXT, difficulty_features TEXT
);
CREATE TABLE IF NOT EXISTS experiments (
  experiment_id TEXT PRIMARY KEY, skill_id TEXT, skill_version TEXT, task_id TEXT,
  condition TEXT, model TEXT, harness TEXT, seed INTEGER, repeats INTEGER, limits TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, experiment_id TEXT, condition TEXT, task_id TEXT,
  skill_id TEXT, skill_version TEXT, model TEXT, repeat_index INTEGER,
  started_at REAL, finished_at REAL, success INTEGER, score REAL,
  tokens INTEGER, cost REAL, wall_time REAL, skill_was_loaded INTEGER,
  verifier_error TEXT
);
CREATE TABLE IF NOT EXISTS trajectory_events (
  run_id TEXT, timestamp REAL, event_type TEXT, tool_name TEXT,
  input_hash TEXT, output_hash TEXT, artifact_uri TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS skill_constraints (
  skill_id TEXT, version TEXT, constraint_id TEXT, condition TEXT,
  required_action TEXT, forbidden_action TEXT, evidence_rule TEXT,
  PRIMARY KEY (skill_id, version, constraint_id)
);
CREATE TABLE IF NOT EXISTS constraint_results (
  run_id TEXT, constraint_id TEXT, verdict TEXT, evidence_uri TEXT
);
CREATE TABLE IF NOT EXISTS failure_attributions (
  run_id TEXT PRIMARY KEY, failure_type TEXT, confidence REAL, rationale TEXT
);
"""


class Store:
    """실험·런·궤적·판정 결과 저장소."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def save_experiment(self, spec: ExperimentSpec) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                spec.experiment_id, spec.skill_id, spec.skill_version, spec.task_id,
                spec.condition, spec.model, spec.harness, spec.seed, spec.repeats,
                json.dumps(spec.limits),
            ),
        )
        self.conn.commit()

    def save_run(self, run: RunResult) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run.run_id, run.experiment_id, run.condition, run.task_id,
                run.skill_id, run.skill_version, run.model, run.repeat_index,
                run.started_at, run.finished_at, int(run.success), run.score,
                run.tokens, run.cost, run.wall_time, int(run.skill_was_loaded),
                run.verifier_error,
            ),
        )
        self.conn.executemany(
            "INSERT INTO trajectory_events VALUES (?,?,?,?,?,?,?,?)",
            [
                (run.run_id, ev.timestamp, ev.event_type, ev.tool_name, "", "", "", ev.detail)
                for ev in run.trajectory
            ],
        )
        self.conn.executemany(
            "INSERT INTO constraint_results VALUES (?,?,?,?)",
            [(run.run_id, cid, verdict, "") for cid, verdict in run.constraint_verdicts.items()],
        )
        if run.failure_type:
            self.conn.execute(
                "INSERT OR REPLACE INTO failure_attributions VALUES (?,?,?,?)",
                (run.run_id, run.failure_type, 1.0, run.failure_rationale),
            )
        self.conn.commit()

    def load_runs(self, condition: str | None = None, task_id: str | None = None) -> list[dict]:
        q = "SELECT * FROM runs WHERE 1=1"
        params: list[Any] = []
        if condition:
            q += " AND condition = ?"
            params.append(condition)
        if task_id:
            q += " AND task_id = ?"
            params.append(task_id)
        cur = self.conn.execute(q, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def load_constraint_results(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM constraint_results")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def load_failures(self) -> list[dict]:
        cur = self.conn.execute("SELECT * FROM failure_attributions")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
