"""Atomic, optimistic-versioned manual routes for actual pilot rack-pair/type groups."""
from uuid import uuid4
from sqlalchemy import select

from backend.persistence.postgresql.routing_models import RoutingLayout, RoutingManualCableRoute
from backend.services.routing_cable_review import review_context
from backend.services.routing_configuration import RoutingConfigurationError, RoutingNotFound
from backend.services.routing_manual_paths import manual_preview, validate_chain, chain_legs


def initialize_test_tiers(session, layout_uid):
    """Explicit, idempotent T1 fixture configuration. Never called by reads or suggestions."""
    from backend.services import routing_configuration as config
    review_context(session, layout_uid)  # enforce pilot hall and actual 40-cabinet scope
    data = config.resolved_layout(session, layout_uid)
    created = 0
    for resource, owners, owner_key, records in (
        ('passage-tiers', [b for b in data['bands'] if b['kind'] == 'PASSAGE'], 'passage_band_uid', data['passage_tiers']),
        ('cross-route-tiers', data['cross_routes'], 'cross_route_uid', data['cross_route_tiers']),
    ):
        existing = {r[owner_key] for r in records if r['tier'] == 1}
        for owner in owners:
            if owner['uid'] not in existing:
                config.save_resource(session, layout_uid, resource, {owner_key: owner['uid'], 'tier': 1, 'pathway_type': 'BASKET_TRAY'})
                created += 1
    return dict(created_tier_count=created, review=review_context(session, layout_uid)[0])


class RoutingRouteConflict(RoutingConfigurationError):
    pass


def check_topology(review, revision):
    if revision is not None and revision != review['topology_revision']:
        raise RoutingRouteConflict('Pathways changed while this route was being edited. Reload the cable review and rebuild the draft.')


def preview_manual_route(session, layout_uid, request):
    review, planner = review_context(session, layout_uid, request.scope)
    check_topology(review, request.topology_revision)
    group = next((g for g in review['groups'] if g['uid'] == request.group_uid), None)
    if not group:
        raise RoutingNotFound('The cable group is not in the current test-row inventory.')
    return manual_preview(planner, group, request.prefix_segment_ids, request.start_tier, request.end_tier)


def update_manual_batch(session, layout_uid, request, user_uid, reset=False):
    # Serialize batch updates, including two simultaneous inserts of the same new assignment.
    layout = session.scalar(select(RoutingLayout).where(RoutingLayout.uid == layout_uid).with_for_update())
    if not layout:
        raise RoutingNotFound('Routing layout was not found.')
    review, planner = review_context(session, layout_uid, request.scope)
    check_topology(review, request.topology_revision)
    groups = {g['uid']: g for g in review['groups']}
    saved = {(r.source_cabinet_uid, r.destination_cabinet_uid, r.cable_type): r for r in session.scalars(
        select(RoutingManualCableRoute).where(RoutingManualCableRoute.routing_layout_uid == layout_uid).with_for_update())}
    changes = []
    # Validate every member before any mutation: a batch cannot partly succeed.
    for item in request.groups:
        group = groups.get(item.group_uid)
        if not group:
            raise RoutingNotFound('A selected cable group is no longer in the current test-row inventory.')
        key = group['source_cabinet_uid'], group['destination_cabinet_uid'], group['cable_type']
        row = saved.get(key)
        if (row.version if row else None) != item.expected_version:
            raise RoutingRouteConflict('A manual route changed in another session. Reload before applying this batch.')
        legs = None
        if not reset:
            points, _ = validate_chain(planner, key[0], key[1], item.segment_ids, complete=True, start_tier=item.start_tier, end_tier=item.end_tier)
            legs = chain_legs(planner, points, item.segment_ids)
            if not legs:
                raise RoutingConfigurationError('A manual route must contain a nonempty complete segment chain.')
        changes.append((row, key, legs, item.start_tier, item.end_tier))
    for row, key, legs, start_tier, end_tier in changes:
        if reset:
            if row: session.delete(row)
        else:
            if not row:
                row = RoutingManualCableRoute(uid=str(uuid4()), routing_layout_uid=layout_uid,
                    source_cabinet_uid=key[0], destination_cabinet_uid=key[1], cable_type=key[2], revision=0)
                session.add(row)
            row.legs, row.version, row.revision = legs, str(uuid4()), row.revision + 1
            row.start_tier, row.end_tier = start_tier, end_tier
            row.updated_by, row.notes = user_uid, request.notes
    session.flush()
    return dict(updated_group_uids=[g.group_uid for g in request.groups], review=review_context(session, layout_uid, request.scope)[0])
