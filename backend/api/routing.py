from __future__ import annotations

from contextlib import contextmanager
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, ProgrammingError

from backend.api.auth import AuthUser, current_user, require_manager
from backend.persistence.postgresql import routing_models as db
from backend.persistence.postgresql.session import session_factory
from backend.schemas.routing import InitializeInput, LayoutInput, PreviewInput, RoutePreview, RoutingGraph
from backend.services import routing_configuration as config
from backend.services.routing_graph import derive_graph
from backend.services.routing_pathfinding import NoRoutingPath, preview_route
from backend.schemas.routing_manual import ManualBatchInput, ManualPreviewInput
from backend.services.routing_manual_routes import RoutingRouteConflict, preview_manual_route, update_manual_batch, initialize_test_tiers

router = APIRouter(prefix='/routing', tags=['routing'])


@contextmanager
def routing_session():
    try:
        with session_factory()(autoflush=False) as session, session.begin():
            yield session
    except config.RoutingNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except RoutingRouteConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except (config.RoutingConfigurationError, NoRoutingPath) as exc:
        raise HTTPException(422, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_context=False)) from exc
    except IntegrityError as exc:
        raise HTTPException(409, 'Routing configuration conflicts with an existing record or dimension constraint.') from exc
    except ProgrammingError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '42P01':
            raise HTTPException(503, 'Routing database tables are unavailable. Apply the Alembic migrations first.') from exc
        raise


@router.get('/layouts')
def list_layouts(project_uid: str = 'LBB01', building_id: str = 'A', hall_code: str = 'DH1', user: AuthUser = Depends(current_user)):
    with routing_session() as session:
        row = config.find_layout(session, project_uid, building_id, hall_code)
        return [config.record(row)] if row else []


@router.post('/initialize-lbb01')
def initialize(request: InitializeInput, user: AuthUser = Depends(current_user)):
    require_manager(user)
    with routing_session() as session:
        return config.initialize_lbb01(session, request.building_id)


@router.post('/layouts')
def create_layout(request: LayoutInput, user: AuthUser = Depends(current_user)):
    require_manager(user)
    with routing_session() as session:
        return config.resolved_layout(session, config.create_layout(session, request.model_dump()).uid)


@router.get('/layouts/{layout_uid}')
def get_resolved_layout(layout_uid: str, user: AuthUser = Depends(current_user)):
    with routing_session() as session:
        return config.resolved_layout(session, layout_uid)


@router.patch('/layouts/{layout_uid}')
def update_layout(layout_uid: str, request: dict, user: AuthUser = Depends(current_user)):
    require_manager(user)
    with routing_session() as session:
        return config.update_layout(session, layout_uid, request)


@router.delete('/layouts/{layout_uid}', status_code=204)
def delete_layout(layout_uid: str, user: AuthUser = Depends(current_user)):
    require_manager(user)
    with routing_session() as session:
        session.delete(config.get_layout(session, layout_uid))


@router.get('/layouts/{layout_uid}/graph', response_model=RoutingGraph)
def get_graph(layout_uid: str, user: AuthUser = Depends(current_user)):
    with routing_session() as session:
        return derive_graph(config.snapshot(session, layout_uid))


@router.get('/layouts/{layout_uid}/placement-sources')
def get_placement_sources(layout_uid: str, user: AuthUser = Depends(current_user)):
    from backend.services.routing_sections import placement_sources
    with routing_session() as session:
        return placement_sources(session, config.get_layout(session, layout_uid))


@router.post('/layouts/{layout_uid}/route-preview', response_model=RoutePreview)
def route_preview(layout_uid: str, request: PreviewInput, user: AuthUser = Depends(current_user)):
    with routing_session() as session:
        data = config.resolved_layout(session, layout_uid)
        return preview_route(derive_graph(data), data, request.start_node_id, request.end_node_id)


@router.get('/layouts/{layout_uid}/bundle-placements/{placement_uid}/cables')
def get_placement_cables(layout_uid: str, placement_uid: str, user: AuthUser = Depends(current_user)):
    from backend.services.routing_cables import placement_cables
    with routing_session() as session:
        return placement_cables(session, layout_uid, placement_uid)


@router.get('/layouts/{layout_uid}/cable-review')
def get_cable_review(layout_uid: str, scope: Literal['pilot', 'hall'] = 'pilot', user: AuthUser = Depends(current_user)):
    from backend.services.routing_cable_review import cable_review
    with routing_session() as session:
        result = cable_review(session, layout_uid, scope)
        return JSONResponse(result) if scope == 'hall' else result


@router.post('/layouts/{layout_uid}/inventory-test-profile')
def configure_inventory_test(layout_uid: str, user: AuthUser = Depends(current_user)):
    require_manager(user)
    from backend.services.routing_test_profile import configure_hall_test
    with routing_session() as session:
        return configure_hall_test(session, layout_uid)


@router.post('/layouts/{layout_uid}/manual-route-preview')
def manual_route_preview(layout_uid: str, request: ManualPreviewInput, user: AuthUser = Depends(current_user)):
    with routing_session() as session:
        return preview_manual_route(session, layout_uid, request)


@router.get('/layouts/{layout_uid}/manual-routes')
def list_manual_routes(layout_uid: str, user: AuthUser = Depends(current_user)):
    with routing_session() as session:
        config.get_layout(session, layout_uid)
        return [config.record(row) for row in session.scalars(select(db.RoutingManualCableRoute)
            .where(db.RoutingManualCableRoute.routing_layout_uid == layout_uid).order_by(db.RoutingManualCableRoute.uid))]


@router.post('/layouts/{layout_uid}/manual-routes/test-tiers')
def manual_test_tiers(layout_uid: str, user: AuthUser = Depends(current_user)):
    require_manager(user)
    with routing_session() as session:
        return initialize_test_tiers(session, layout_uid)


@router.post('/layouts/{layout_uid}/manual-routes/batch')
def save_manual_routes(layout_uid: str, request: ManualBatchInput, user: AuthUser = Depends(current_user)):
    require_manager(user)
    with routing_session() as session:
        return update_manual_batch(session, layout_uid, request, user.uid)


@router.post('/layouts/{layout_uid}/manual-routes/reset')
def reset_manual_routes(layout_uid: str, request: ManualBatchInput, user: AuthUser = Depends(current_user)):
    require_manager(user)
    with routing_session() as session:
        return update_manual_batch(session, layout_uid, request, user.uid, reset=True)


@router.get('/layouts/{layout_uid}/{resource}')
def list_resources(layout_uid: str, resource: str, user: AuthUser = Depends(current_user)):
    with routing_session() as session:
        config.get_layout(session, layout_uid)
        model, _ = config.resource_type(resource)
        return [config.record(row) for row in session.scalars(select(model).where(model.routing_layout_uid == layout_uid).order_by(model.uid))]


@router.get('/layouts/{layout_uid}/{resource}/{uid}')
def get_resource(layout_uid: str, resource: str, uid: str, user: AuthUser = Depends(current_user)):
    with routing_session() as session:
        config.get_layout(session, layout_uid)
        model, _ = config.resource_type(resource)
        row = session.get(model, uid)
        if row is None or row.routing_layout_uid != layout_uid:
            raise config.RoutingNotFound('Routing record was not found in this layout.')
        return config.record(row)


@router.post('/layouts/{layout_uid}/{resource}')
def create_resource(layout_uid: str, resource: str, request: dict, user: AuthUser = Depends(current_user)):
    require_manager(user)
    with routing_session() as session:
        return config.save_resource(session, layout_uid, resource, request)


@router.patch('/layouts/{layout_uid}/{resource}/{uid}')
def update_resource(layout_uid: str, resource: str, uid: str, request: dict, user: AuthUser = Depends(current_user)):
    require_manager(user)
    with routing_session() as session:
        return config.save_resource(session, layout_uid, resource, request, uid)


@router.delete('/layouts/{layout_uid}/{resource}/{uid}', status_code=204)
def delete_resource(layout_uid: str, resource: str, uid: str, user: AuthUser = Depends(current_user)):
    require_manager(user)
    with routing_session() as session:
        config.delete_resource(session, layout_uid, resource, uid)
