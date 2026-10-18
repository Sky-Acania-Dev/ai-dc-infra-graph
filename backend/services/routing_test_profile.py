"""Explicit LBB01 inventory test configuration. Reads never mutate infrastructure."""
from uuid import uuid4
from sqlalchemy import select
from backend.persistence.postgresql import routing_models as db
from backend.persistence.postgresql.models import Room
from backend.services import routing_configuration as config


def configure_hall_test(session, layout_uid):
    layout = session.scalar(select(db.RoutingLayout).where(db.RoutingLayout.uid == layout_uid).with_for_update())
    if not layout:
        raise config.RoutingNotFound('Routing layout was not found.')
    if session.get(Room, layout.room_uid).project_uid != 'LBB01' or layout.physical_hall_code != 'DH1':
        raise config.RoutingConfigurationError('The inventory test profile is limited to LBB01 DH1.')
    data = config.resolved_layout(session, layout_uid)
    layout.bottom_basket_elevation_in, layout.north_south_top_elevation_in = 98, 116
    created, openings = 0, 0
    for model, owners, key, records in (
        (db.RoutingPassageTier, [b for b in data['bands'] if b['kind'] == 'PASSAGE'], 'passage_band_uid', data['passage_tiers']),
        (db.RoutingCrossRouteTier, data['cross_routes'], 'cross_route_uid', data['cross_route_tiers']),
    ):
        for owner in owners:
            outer = owner.get('code') in ('NORTH', 'SOUTH')
            # Gap routes retain two layers for this test; no unconfirmed gap openings.
            heights = (98, 116) if outer or owner.get('kind') == 'SECTION_GAP' else (98, 110, 122)
            for tier, height in enumerate(heights, 1):
                previous = next((r for r in records if r[key] == owner['uid'] and r['tier'] == tier), None)
                row = session.get(model, previous['uid']) if previous else model(uid=str(uuid4()), routing_layout_uid=layout_uid, **{key: owner['uid']}, tier=tier, enabled=True)
                if not previous:
                    created += 1
                    row.pathway_type = 'BASKET_TRAY' if tier == 1 else 'LADDER_RACK'
                # Preserve an explicitly disabled pathway and existing pathway construction type.
                row.elevation_reference = 'BOTTOM_BASKET' if tier == 1 and row.pathway_type == 'BASKET_TRAY' else 'NORTH_SOUTH_TOP' if outer and tier == 2 else None
                row.elevation_in = None if row.elevation_reference else height
                session.add(row)
            if outer:
                for r in records:
                    if r[key] == owner['uid'] and r['tier'] == 3:
                        session.get(model, r['uid']).enabled = False
    session.flush()
    bands = {b['uid']: b for b in data['bands']}
    enabled_rows = {(r.cross_route_uid,r.tier) for r in session.scalars(select(db.RoutingCrossRouteTier).where(db.RoutingCrossRouteTier.routing_layout_uid == layout_uid,db.RoutingCrossRouteTier.enabled.is_(True)))}
    enabled_passages = {(r.passage_band_uid,r.tier) for r in session.scalars(select(db.RoutingPassageTier).where(db.RoutingPassageTier.routing_layout_uid == layout_uid,db.RoutingPassageTier.enabled.is_(True)))}
    for route in data['geometry']['cross_routes']:
        if route['kind'] != 'CABINET_COLD_AISLE' or not route['effective_enabled']:
            continue
        for band_uid in route['passage_band_uids']:
            if bands[band_uid]['code'] not in ('NORTH', 'SOUTH'):
                continue
            if (route['uid'],3) not in enabled_rows or (band_uid,2) not in enabled_passages:
                continue
            if any(v.get('cross_route_uid') == route['uid'] and v['passage_band_uid'] == band_uid and v['lower_tier'] == 2 and v['upper_tier'] == 3 for v in data['vertical_transitions']):
                continue
            # User-confirmed physical row-end openings. No T1-T2 holes are inferred.
            session.add(db.RoutingVerticalTransition(uid=str(uuid4()), routing_layout_uid=layout_uid,
                cross_route_uid=route['uid'], passage_band_uid=band_uid, station_in=route['station_in'], lower_tier=2, upper_tier=3,
                label=f"{bands[band_uid]['code'].title()} {route['display_label']} opening",
                notes='Confirmed row-end opening: upper row tier to upper outer passage tier. Station follows the row.', enabled=True))
            openings += 1
    session.flush()
    config.validate_layout(session, layout_uid)
    return dict(created_tier_count=created, created_opening_count=openings,
        notes='Rows/CENTRAL: 98/110/122 in AFF; NORTH/SOUTH: 98/116 in AFF. Gap routes use two test layers at 98/116 in. New upper pathways use LADDER_RACK as a test assumption; existing construction types and manual assignments are preserved.')
