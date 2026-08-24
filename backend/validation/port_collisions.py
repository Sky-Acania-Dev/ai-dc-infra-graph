from __future__ import annotations

from collections import Counter
import re
from typing import Any, Iterable

from pydantic import BaseModel


class PortConnectionFinding(BaseModel):
    port_uid: str
    count: int
    message: str


class BreakoutFanoutRule(BaseModel):
    name: str = "MPO to dual LC breakout"
    max_child_connections: int = 4
    require_unique_breakout_slot_port: bool = True
    cable_type_contains: str = ""
    optic_contains: str = ""


DEFAULT_BREAKOUT_RULES = [
    BreakoutFanoutRule(),
]


def detect_port_collisions(
    rows: Iterable[Any],
    breakout_rules: list[BreakoutFanoutRule] | None = None,
) -> list[PortConnectionFinding]:
    connection_counts: Counter[str] = Counter()
    shuffle_counts: Counter[str] = Counter()
    shuffle_fanout_limits: dict[str, int] = {}
    breakout_ports: dict[str, BreakoutFanoutRule] = {}
    breakout_slot_ports: dict[str, set[str]] = {}
    rules = breakout_rules or DEFAULT_BREAKOUT_RULES

    for row in rows:
        shuffle_fanout_limit = _shuffle_fanout_limit(row)
        _track_side(
            row=row,
            side_prefix="a",
            port_uid=_row_value(row, "a_port_uid"),
            breakout_loc_cab_ru=_row_value(row, "a_breakout_loc_cab_ru"),
            breakout_slot_port=_row_value(row, "a_breakout_slot_port"),
            shuffle_fanout_limit=shuffle_fanout_limit,
            connection_counts=connection_counts,
            shuffle_counts=shuffle_counts,
            shuffle_fanout_limits=shuffle_fanout_limits,
            breakout_ports=breakout_ports,
            breakout_slot_ports=breakout_slot_ports,
            breakout_rules=rules,
        )
        _track_side(
            row=row,
            side_prefix="z",
            port_uid=_row_value(row, "z_port_uid"),
            breakout_loc_cab_ru=_row_value(row, "z_breakout_loc_cab_ru"),
            breakout_slot_port=_row_value(row, "z_breakout_slot_port"),
            shuffle_fanout_limit=shuffle_fanout_limit,
            connection_counts=connection_counts,
            shuffle_counts=shuffle_counts,
            shuffle_fanout_limits=shuffle_fanout_limits,
            breakout_ports=breakout_ports,
            breakout_slot_ports=breakout_slot_ports,
            breakout_rules=rules,
        )

    return _connection_findings(
        connection_counts,
        shuffle_counts,
        shuffle_fanout_limits,
        breakout_ports,
        breakout_slot_ports,
    )


def _track_side(
    row: Any,
    side_prefix: str,
    port_uid: str,
    breakout_loc_cab_ru: str,
    breakout_slot_port: str,
    shuffle_fanout_limit: int | None,
    connection_counts: Counter[str],
    shuffle_counts: Counter[str],
    shuffle_fanout_limits: dict[str, int],
    breakout_ports: dict[str, BreakoutFanoutRule],
    breakout_slot_ports: dict[str, set[str]],
    breakout_rules: list[BreakoutFanoutRule],
) -> None:
    if not port_uid:
        return

    connection_counts[port_uid] += 1
    if shuffle_fanout_limit is not None:
        shuffle_counts[port_uid] += 1
        current_limit = shuffle_fanout_limits.get(port_uid)
        shuffle_fanout_limits[port_uid] = (
            shuffle_fanout_limit if current_limit is None else min(current_limit, shuffle_fanout_limit)
        )
    if not breakout_loc_cab_ru and not breakout_slot_port:
        return

    rule = _matching_breakout_rule(row, side_prefix, breakout_rules)
    if rule is None:
        return

    breakout_ports[port_uid] = rule
    if breakout_slot_port:
        breakout_slot_ports.setdefault(port_uid, set()).add(f"{breakout_loc_cab_ru}:{breakout_slot_port}")


def _connection_findings(
    connection_counts: Counter[str],
    shuffle_counts: Counter[str],
    shuffle_fanout_limits: dict[str, int],
    breakout_ports: dict[str, BreakoutFanoutRule],
    breakout_slot_ports: dict[str, set[str]],
) -> list[PortConnectionFinding]:
    findings: list[PortConnectionFinding] = []
    for port_uid, count in sorted(connection_counts.items()):
        if port_uid in breakout_ports:
            rule = breakout_ports[port_uid]
            unique_breakouts = len(breakout_slot_ports.get(port_uid, set()))
            if count > rule.max_child_connections:
                findings.append(
                    PortConnectionFinding(
                        port_uid=port_uid,
                        count=count,
                        message=(
                            f"Breakout port has {count} cable connections; rule '{rule.name}' allows "
                            f"{rule.max_child_connections}."
                        ),
                    )
                )
            if rule.require_unique_breakout_slot_port and unique_breakouts and unique_breakouts < count:
                findings.append(
                    PortConnectionFinding(
                        port_uid=port_uid,
                        count=count,
                        message=(
                            f"Breakout port has {count} cable connections but only "
                            f"{unique_breakouts} unique breakout slot/port values."
                        ),
                    )
                )
            continue

        if count > 1:
            shuffle_count = shuffle_counts.get(port_uid, 0)
            shuffle_fanout_limit = shuffle_fanout_limits.get(port_uid, 0)
            if shuffle_count == count and count <= shuffle_fanout_limit:
                continue

            findings.append(
                PortConnectionFinding(
                    port_uid=port_uid,
                    count=count,
                    message=(
                        f"Port has {count} cable connections; only breakout or MPO 2x2/4x4 shuffle rows may fan out."
                    ),
                )
            )
    return findings


def _matching_breakout_rule(
    row: Any,
    side_prefix: str,
    breakout_rules: list[BreakoutFanoutRule],
) -> BreakoutFanoutRule | None:
    for rule in breakout_rules:
        cable_type_matches = _contains_if_configured(_row_value(row, "cable_type"), rule.cable_type_contains)
        optic_matches = _contains_if_configured(_row_value(row, f"{side_prefix}_optic"), rule.optic_contains)
        if cable_type_matches and optic_matches:
            return rule
    return None


def _contains_if_configured(value: str, expected: str) -> bool:
    if not expected:
        return True
    return expected.upper() in value.upper()


def _shuffle_fanout_limit(row: Any) -> int | None:
    cable_type = _row_value(row, "cable_type")
    if _matches_mpo_shuffle(cable_type, "2", "2"):
        return 2
    if _matches_mpo_shuffle(cable_type, "4", "4"):
        return 16
    return None


def _matches_mpo_shuffle(cable_type: str, source_count: str, destination_count: str) -> bool:
    pattern = rf"\bMPO\w*\b.*\b{source_count}\s*[Xx]\s*{destination_count}\b"
    return re.search(pattern, cable_type, flags=re.IGNORECASE) is not None


def _row_value(row: Any, key: str) -> str:
    if isinstance(row, dict):
        return str(row.get(key, "") or "")
    return str(getattr(row, key, "") or "")
