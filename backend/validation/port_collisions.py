from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

from pydantic import BaseModel


class PortConnectionFinding(BaseModel):
    port_uid: str
    count: int
    message: str


def detect_port_collisions(rows: Iterable[Any]) -> list[PortConnectionFinding]:
    connection_counts: Counter[str] = Counter()
    breakout_ports: set[str] = set()
    breakout_slot_ports: dict[str, set[str]] = {}

    for row in rows:
        _track_side(
            port_uid=_row_value(row, "a_port_uid"),
            breakout_loc_cab_ru=_row_value(row, "a_breakout_loc_cab_ru"),
            breakout_slot_port=_row_value(row, "a_breakout_slot_port"),
            connection_counts=connection_counts,
            breakout_ports=breakout_ports,
            breakout_slot_ports=breakout_slot_ports,
        )
        _track_side(
            port_uid=_row_value(row, "z_port_uid"),
            breakout_loc_cab_ru=_row_value(row, "z_breakout_loc_cab_ru"),
            breakout_slot_port=_row_value(row, "z_breakout_slot_port"),
            connection_counts=connection_counts,
            breakout_ports=breakout_ports,
            breakout_slot_ports=breakout_slot_ports,
        )

    return _connection_findings(connection_counts, breakout_ports, breakout_slot_ports)


def _track_side(
    port_uid: str,
    breakout_loc_cab_ru: str,
    breakout_slot_port: str,
    connection_counts: Counter[str],
    breakout_ports: set[str],
    breakout_slot_ports: dict[str, set[str]],
) -> None:
    if not port_uid:
        return

    connection_counts[port_uid] += 1
    if not breakout_loc_cab_ru and not breakout_slot_port:
        return

    breakout_ports.add(port_uid)
    if breakout_slot_port:
        breakout_slot_ports.setdefault(port_uid, set()).add(f"{breakout_loc_cab_ru}:{breakout_slot_port}")


def _connection_findings(
    connection_counts: Counter[str],
    breakout_ports: set[str],
    breakout_slot_ports: dict[str, set[str]],
) -> list[PortConnectionFinding]:
    findings: list[PortConnectionFinding] = []
    for port_uid, count in sorted(connection_counts.items()):
        if port_uid in breakout_ports:
            unique_breakouts = len(breakout_slot_ports.get(port_uid, set()))
            if unique_breakouts and unique_breakouts < count:
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


def _row_value(row: Any, key: str) -> str:
    if isinstance(row, dict):
        return str(row.get(key, "") or "")
    return str(getattr(row, key, "") or "")
