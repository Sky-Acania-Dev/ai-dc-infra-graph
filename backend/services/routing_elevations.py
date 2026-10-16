"""Measured hall references are separate from explicit tier availability and numbering."""


def tier_elevation(layout, record):
    reference = record.get('elevation_reference')
    if reference == 'BOTTOM_BASKET':
        return layout.get('bottom_basket_elevation_in')
    if reference == 'NORTH_SOUTH_TOP':
        return layout.get('north_south_top_elevation_in')
    return record['elevation_in']


def validate_elevations(data):
    layout = data['layout']
    bottom, top = (layout.get(k) for k in ('bottom_basket_elevation_in', 'north_south_top_elevation_in'))
    if bottom is not None and top is not None and top <= bottom:
        raise ValueError('The NORTH/SOUTH top reference must be above the bottom basket reference.')
    bands = {b['uid']: b for b in data['bands']}
    for kind, records, owner in (('passage', data['passage_tiers'], 'passage_band_uid'), ('cross', data['cross_route_tiers'], 'cross_route_uid')):
        for record in records:
            reference = record.get('elevation_reference')
            if reference and record['elevation_in'] is not None:
                raise ValueError('Choose a measured elevation reference or an explicit elevation, not both.')
            if reference == 'BOTTOM_BASKET' and (record['tier'] != 1 or record['pathway_type'] != 'BASKET_TRAY'):
                raise ValueError('The bottom basket reference applies to Tier 1 basket trays only.')
            if reference == 'NORTH_SOUTH_TOP':
                if kind != 'passage' or bands[record[owner]]['code'] not in ('NORTH', 'SOUTH') or record['tier'] == 1:
                    raise ValueError('The top reference applies only to an explicitly designated upper tier on NORTH/SOUTH passages.')
                if record['enabled'] and any(r[owner] == record[owner] and r['enabled'] and r['tier'] > record['tier'] for r in records):
                    raise ValueError('Only the highest enabled tier on this passage can be designated as its top tier.')


def resolve_elevations(data):
    for record in data['passage_tiers'] + data['cross_route_tiers']:
        record['effective_elevation_in'] = tier_elevation(data['layout'], record)
