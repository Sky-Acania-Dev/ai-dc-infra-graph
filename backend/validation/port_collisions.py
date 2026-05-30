from __future__ import annotations

from collections import Counter
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
    breakout_ports: dict[str, BreakoutFanoutRule] = {}
    breakout_slot_ports: dict[str, set[str]] = {}
    rules = breakout_rules or DEFAULT_BREAKOUT_RULES

    for row in rows:
        _track_side(
            row=row,
            side_prefix="a",
            port_uid=_row_value(row, "a_port_uid"),
            breakout_loc_cab_ru=_row_value(row, "a_breakout_loc_cab_ru"),
            breakout_slot_port=_row_value(row, "a_breakout_slot_port"),
            connection_counts=connection_counts,
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
            connection_counts=connection_counts,
            breakout_ports=breakout_ports,
            breakout_slot_ports=breakout_slot_ports,
            breakout_rules=rules,
        )

    return _connection_findings(connection_counts, breakout_ports, breakout_slot_ports)


def _track_side(
    row: Any,
    side_prefix: str,
    port_uid: str,
    breakout_loc_cab_ru: str,
    breakout_slot_port: str,
    connection_counts: Counter[str],
    breakout_ports: dict[str, BreakoutFanoutRule],
    breakout_slot_ports: dict[str, set[str]],
    breakout_rules: list[BreakoutFanoutRule],
) -> None:
    if not port_uid:
        return

    connection_counts[port_uid] += 1
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
            findings.append(
                PortConnectionFinding(
                    port_uid=port_uid,
                    count=count,
                    message=f"Port has {count} cable connections; only breakout rows may fan out.",
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


def _row_value(row: Any, key: str) -> str:
    if isinstance(row, dict):
        return str(row.get(key, "") or "")
    return str(getattr(row, key, "") or "")
