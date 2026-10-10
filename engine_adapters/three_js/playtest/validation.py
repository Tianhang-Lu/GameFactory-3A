"""Stable slice validation records for three.js playtests.

The recorder produces runtime evidence; this module decides which evidence is
still trustworthy after a design or dependency change. It has no browser or
engine dependencies, so a ledger can be checked in CI before a browser is
available.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


LEDGER_SCHEMA = "a3game.playtest_validation.v1"
RESULTS = {"pass", "fail", "blocked"}
EVIDENCE_STATES = {"current", "stale"}
CHANGE_KINDS = {
    "presentation", "asset", "asset_behavior", "mechanic", "contract",
    "state", "entry_conditions", "exit_conditions", "checkpoint", "branch",
    "screen", "task",
}


def _text(value: Any, field_name: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{field_name} must be a non-empty string")
    return result


def _ids(value: Any, field_name: str, *, required: bool = False) -> list[str]:
    if value is None:
        values: list[Any] = []
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        raise ValueError(f"{field_name} must be an array of stable IDs")
    result = [_text(item, field_name) for item in values]
    if len(result) != len(set(result)):
        raise ValueError(f"{field_name} contains duplicate IDs")
    if required and not result:
        raise ValueError(f"{field_name} must not be empty")
    return result


def _list(value: Any, field_name: str, *, required: bool = False) -> list[Any]:
    if value is None:
        result: list[Any] = []
    elif isinstance(value, list):
        result = list(value)
    else:
        raise ValueError(f"{field_name} must be an array")
    if required and not result:
        raise ValueError(f"{field_name} must not be empty")
    return result


@dataclass(frozen=True)
class TestableSlice:
    """An independently recoverable and observable gameplay flow."""

    id: str
    chapter_id: str
    requirement_ids: list[str] = field(default_factory=list)
    beat_ids: list[str] = field(default_factory=list)
    entry_conditions: list[Any] = field(default_factory=list)
    checkpoint: Any = None
    operations: list[Any] = field(default_factory=list)
    expected_transitions: list[Any] = field(default_factory=list)
    exit_conditions: list[Any] = field(default_factory=list)
    task_refs: list[str] = field(default_factory=list)
    asset_refs: list[str] = field(default_factory=list)
    screen_refs: list[str] = field(default_factory=list)
    acceptance: list[Any] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    output_state_ids: list[str] = field(default_factory=list)
    branch_id: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "TestableSlice":
        if not isinstance(raw, Mapping):
            raise ValueError("slice must be an object")
        if "checkpoint" not in raw or raw.get("checkpoint") is None:
            raise ValueError("slice.checkpoint is required")
        return cls(
            id=_text(raw.get("id"), "slice.id"),
            chapter_id=_text(raw.get("chapter_id"), "slice.chapter_id"),
            requirement_ids=_ids(raw.get("requirement_ids"), "slice.requirement_ids"),
            beat_ids=_ids(raw.get("beat_ids"), "slice.beat_ids"),
            entry_conditions=_list(raw.get("entry_conditions"), "slice.entry_conditions"),
            checkpoint=raw.get("checkpoint"),
            operations=_list(raw.get("operations"), "slice.operations", required=True),
            expected_transitions=_list(raw.get("expected_transitions"), "slice.expected_transitions"),
            exit_conditions=_list(raw.get("exit_conditions"), "slice.exit_conditions"),
            task_refs=_ids(raw.get("task_refs"), "slice.task_refs"),
            asset_refs=_ids(raw.get("asset_refs"), "slice.asset_refs"),
            screen_refs=_ids(raw.get("screen_refs"), "slice.screen_refs"),
            acceptance=_list(raw.get("acceptance"), "slice.acceptance", required=True),
            depends_on=_ids(raw.get("depends_on"), "slice.depends_on"),
            output_state_ids=_ids(raw.get("output_state_ids"), "slice.output_state_ids"),
            branch_id=(str(raw["branch_id"]).strip() if raw.get("branch_id") else None),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "chapter_id": self.chapter_id,
            "requirement_ids": list(self.requirement_ids), "beat_ids": list(self.beat_ids),
            "entry_conditions": list(self.entry_conditions), "checkpoint": self.checkpoint,
            "operations": list(self.operations), "expected_transitions": list(self.expected_transitions),
            "exit_conditions": list(self.exit_conditions), "task_refs": list(self.task_refs),
            "asset_refs": list(self.asset_refs), "screen_refs": list(self.screen_refs),
            "acceptance": list(self.acceptance), "depends_on": list(self.depends_on),
            "output_state_ids": list(self.output_state_ids), "branch_id": self.branch_id,
        }


@dataclass
class ValidationRecord:
    validation_id: str
    slice_id: str
    chapter_id: str
    design_revision: str
    dependency_refs: list[str]
    covered_requirement_ids: list[str]
    covered_beat_ids: list[str]
    entry_checkpoint: Any
    operations_exercised: list[Any]
    result: str
    evidence: list[Any]
    finding: str = ""
    owning_task: str = ""
    evidence_state: str = "current"
    stale_reason: str = ""
    branch_id: str | None = None

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "ValidationRecord":
        if not isinstance(raw, Mapping):
            raise ValueError("validation must be an object")
        result = _text(raw.get("result"), "validation.result").lower()
        if result not in RESULTS:
            raise ValueError("validation.result must be pass, fail, or blocked")
        state = str(raw.get("evidence_state") or raw.get("status") or "current").lower()
        if state not in EVIDENCE_STATES:
            raise ValueError("validation.evidence_state must be current or stale")
        return cls(
            validation_id=_text(raw.get("validation_id"), "validation.validation_id"),
            slice_id=_text(raw.get("slice_id"), "validation.slice_id"),
            chapter_id=_text(raw.get("chapter_id"), "validation.chapter_id"),
            design_revision=_text(raw.get("design_revision"), "validation.design_revision"),
            dependency_refs=_ids(raw.get("dependency_refs"), "validation.dependency_refs", required=True),
            covered_requirement_ids=_ids(raw.get("covered_requirement_ids"), "validation.covered_requirement_ids"),
            covered_beat_ids=_ids(raw.get("covered_beat_ids"), "validation.covered_beat_ids"),
            entry_checkpoint=raw.get("entry_checkpoint"),
            operations_exercised=_list(raw.get("operations_exercised"), "validation.operations_exercised"),
            result=result, evidence=_list(raw.get("evidence"), "validation.evidence", required=True),
            finding=str(raw.get("finding") or ""), owning_task=str(raw.get("owning_task") or ""),
            evidence_state=state, stale_reason=str(raw.get("stale_reason") or ""),
            branch_id=(str(raw["branch_id"]).strip() if raw.get("branch_id") else None),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id, "slice_id": self.slice_id,
            "chapter_id": self.chapter_id, "design_revision": self.design_revision,
            "dependency_refs": list(self.dependency_refs),
            "covered_requirement_ids": list(self.covered_requirement_ids),
            "covered_beat_ids": list(self.covered_beat_ids),
            "entry_checkpoint": self.entry_checkpoint,
            "operations_exercised": list(self.operations_exercised), "result": self.result,
            "evidence": list(self.evidence), "finding": self.finding,
            "owning_task": self.owning_task, "evidence_state": self.evidence_state,
            "stale_reason": self.stale_reason, "branch_id": self.branch_id,
        }


class ValidationLedger:
    """Persist slices and validation evidence without changing task state."""

    def __init__(
        self,
        *,
        design_revision: str = "",
        slices: Iterable[TestableSlice] = (),
        validations: Iterable[ValidationRecord] = (),
    ) -> None:
        self.design_revision = str(design_revision or "")
        self.slices: dict[str, TestableSlice] = {}
        self.validations: dict[str, ValidationRecord] = {}
        for item in slices:
            self.add_slice(item)
        for item in validations:
            self.add_validation(item)

    @classmethod
    def load(cls, path: str | Path) -> "ValidationLedger":
        source = Path(path).expanduser().resolve(strict=True)
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping) or raw.get("schema_version") != LEDGER_SCHEMA:
            raise ValueError(f"Unsupported validation ledger: {source}")
        return cls(
            design_revision=str(raw.get("design_revision") or ""),
            slices=(TestableSlice.from_dict(item) for item in raw.get("slices", [])),
            validations=(ValidationRecord.from_dict(item) for item in raw.get("validations", [])),
        )

    def add_slice(self, item: TestableSlice | Mapping[str, Any]) -> TestableSlice:
        value = item if isinstance(item, TestableSlice) else TestableSlice.from_dict(item)
        existing = self.slices.get(value.id)
        if existing and existing != value:
            raise ValueError(f"slice ID already exists with different content: {value.id}")
        self.slices[value.id] = value
        return value

    def add_validation(self, item: ValidationRecord | Mapping[str, Any]) -> ValidationRecord:
        value = item if isinstance(item, ValidationRecord) else ValidationRecord.from_dict(item)
        if value.slice_id not in self.slices:
            raise ValueError(f"validation references unknown slice: {value.slice_id}")
        existing = self.validations.get(value.validation_id)
        if existing and existing.to_dict() != value.to_dict():
            raise ValueError(f"validation ID already exists: {value.validation_id}")
        self.validations[value.validation_id] = value
        return value

    def update_design_revision(self, revision: str) -> list[str]:
        """Switch revisions and stale every pass based on the previous revision."""
        value = _text(revision, "design_revision")
        stale: list[str] = []
        if self.design_revision != value or any(
            record.design_revision != value for record in self.validations.values()
        ):
            for record in self.validations.values():
                if record.design_revision != value and record.evidence_state != "stale":
                    record.evidence_state = "stale"
                    record.stale_reason = f"design revision changed to {value}"
                    stale.append(record.validation_id)
        self.design_revision = value
        return stale

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LEDGER_SCHEMA,
            "design_revision": self.design_revision,
            "slices": [item.to_dict() for item in self.slices.values()],
            "validations": [item.to_dict() for item in self.validations.values()],
        }

    def save(self, path: str | Path) -> Path:
        destination = Path(path).expanduser().resolve(strict=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
        return destination

    @staticmethod
    def _change_parts(changes: Mapping[str, Any] | Iterable[str]) -> tuple[set[str], set[str]]:
        if isinstance(changes, Mapping):
            kind = str(changes.get("kind") or "task").lower()
            if kind not in CHANGE_KINDS:
                raise ValueError(f"unknown change kind: {kind}")
            values = changes.get("refs", changes.get("ids", changes.get("id", [])))
            if isinstance(values, str):
                refs = {values}
            else:
                refs = {str(item) for item in (values or []) if str(item)}
            return refs, {kind}
        return {str(item) for item in changes if str(item)}, {"task"}

    def impacted_slice_ids(self, changes: Mapping[str, Any] | Iterable[str]) -> list[str]:
        """Return the smallest slice set affected by one change descriptor."""
        refs, kinds = self._change_parts(changes)
        direct: set[str] = set()
        for slice_id, item in self.slices.items():
            owned = set(item.task_refs) | set(item.asset_refs) | set(item.screen_refs)
            owned |= set(item.requirement_ids) | set(item.beat_ids)
            if item.branch_id:
                owned.add(item.branch_id)
            if refs & owned:
                direct.add(slice_id)
            if "asset" in kinds or "asset_behavior" in kinds:
                if refs & set(item.asset_refs):
                    direct.add(slice_id)
            if "mechanic" in kinds or "task" in kinds or "contract" in kinds:
                if refs & set(item.task_refs):
                    direct.add(slice_id)

        propagate = bool(kinds & {
            "asset_behavior", "mechanic", "contract", "state", "entry_conditions",
            "exit_conditions", "checkpoint", "branch",
        })
        if not propagate:
            return [item.id for item in self.slices.values() if item.id in direct]

        affected = set(direct)
        changed = True
        while changed:
            changed = False
            produced = {
                state
                for slice_id in affected
                for state in self.slices[slice_id].output_state_ids
            }
            for slice_id, item in self.slices.items():
                if slice_id in affected:
                    continue
                entry_ids = {
                    str(condition.get("id"))
                    for condition in item.entry_conditions
                    if isinstance(condition, Mapping) and condition.get("id")
                }
                if set(item.depends_on) & affected or entry_ids & produced:
                    affected.add(slice_id)
                    changed = True
        return [item.id for item in self.slices.values() if item.id in affected]

    def select_regression(self, changes: Mapping[str, Any] | Iterable[str]) -> list[str]:
        """Alias used by callers planning the minimum regression set."""
        return self.impacted_slice_ids(changes)

    def invalidate(self, changes: Mapping[str, Any] | Iterable[str], *, reason: str = "dependency changed") -> list[str]:
        """Alias for marking existing evidence stale after a changed input."""
        return self.mark_stale(changes, reason=reason)

    def mark_stale(
        self,
        changes: Mapping[str, Any] | Iterable[str],
        *,
        reason: str = "dependency changed",
    ) -> list[str]:
        stale_slices = set(self.impacted_slice_ids(changes))
        stale_ids: list[str] = []
        for record in self.validations.values():
            if record.slice_id in stale_slices and record.evidence_state != "stale":
                record.evidence_state = "stale"
                record.stale_reason = reason
                stale_ids.append(record.validation_id)
        return stale_ids

    def current_passes(self, *, design_revision: str | None = None) -> list[ValidationRecord]:
        revision = design_revision if design_revision is not None else self.design_revision
        return [
            item for item in self.validations.values()
            if item.result == "pass" and item.evidence_state == "current"
            and (not revision or item.design_revision == revision)
        ]


def load_slice(value: TestableSlice | Mapping[str, Any] | str | Path) -> TestableSlice:
    if isinstance(value, TestableSlice):
        return value
    if isinstance(value, (str, Path)):
        raw = json.loads(Path(value).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
        return TestableSlice.from_dict(raw)
    return TestableSlice.from_dict(value)


__all__ = [
    "EVIDENCE_STATES", "LEDGER_SCHEMA", "RESULTS", "TestableSlice",
    "ValidationLedger", "ValidationRecord", "load_slice",
]



