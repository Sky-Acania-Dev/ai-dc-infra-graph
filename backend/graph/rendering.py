from __future__ import annotations

import html
from pathlib import Path

import networkx as nx

from backend.graph.cabinet_graph import load_cabinet_graph
from backend.persistence import TopologyDatabase, load_topology_database


DEFAULT_CABINET_GRAPH_IMAGE_PATH = Path("data/runtime/graphs/cabinet_graph.png")
DEFAULT_CABINET_LAYOUT_SVG_PATH = Path("data/runtime/graphs/cabinet_layout.svg")
DEFAULT_DISTANCE_SHELL_ORDER = ("root", "hop_1", "hop_2", "hop_3", "hop_4", "hop_5", "unreachable")


def render_cabinet_graph_png(
    graph_path: str | Path,
    output_path: str | Path = DEFAULT_CABINET_GRAPH_IMAGE_PATH,
    figure_size: tuple[int, int] = (24, 24),
    dpi: int = 220,
    label_distance_categories: set[str] | None = None,
) -> Path:
    # Import matplotlib lazily so non-visual API/server code does not require it at startup.
    import matplotlib.pyplot as plt

    graph = load_cabinet_graph(graph_path)
    labels_to_show = label_distance_categories or {"root", "hop_1"}
    position = distance_shell_layout(graph)
    edge_widths = [
        max(0.2, min(4.0, edge_data.get("total_cables", 1) / 40))
        for _, _, edge_data in graph.edges(data=True)
    ]
    node_colors = [_category_color(graph.nodes[node].get("visualization_category", "")) for node in graph.nodes]
    labels = {
        node: node
        for node, node_data in graph.nodes(data=True)
        if node_data.get("distance_category") in labels_to_show
    }

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=figure_size)
    nx.draw_networkx_edges(graph, position, width=edge_widths, alpha=0.2)
    nx.draw_networkx_nodes(graph, position, node_size=18, alpha=0.85, node_color=node_colors)
    nx.draw_networkx_labels(graph, position, labels=labels, font_size=6)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(output, dpi=dpi)
    plt.close()
    return output


def distance_shell_layout(graph: nx.Graph) -> dict[str, tuple[float, float]]:
    shells = [
        [
            node
            for node, node_data in graph.nodes(data=True)
            if node_data.get("distance_category") == distance_category
        ]
        for distance_category in DEFAULT_DISTANCE_SHELL_ORDER
    ]
    shells = [shell for shell in shells if shell]
    return nx.shell_layout(graph, nlist=shells)


def render_cabinet_layout_svg(
    database_path: str | Path,
    output_path: str | Path = DEFAULT_CABINET_LAYOUT_SVG_PATH,
    cell_width: int = 34,
    cell_height: int = 22,
    margin: int = 48,
    data_hall_id: str | None = None,
    label_stroke_color: str = "#D1D5DB",
    label_stroke_width: float = 0.75,
    color_context_text: bool = False,
) -> Path:
    database = load_topology_database(database_path)
    svg = cabinet_layout_svg(
        database,
        cell_width=cell_width,
        cell_height=cell_height,
        margin=margin,
        data_hall_id=data_hall_id,
        label_stroke_color=label_stroke_color,
        label_stroke_width=label_stroke_width,
        color_context_text=color_context_text,
    )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(svg, encoding="utf-8")
    return output


def cabinet_layout_svg(
    database: TopologyDatabase,
    cell_width: int = 34,
    cell_height: int = 22,
    margin: int = 48,
    data_hall_id: str | None = None,
    label_stroke_color: str = "#D1D5DB",
    label_stroke_width: float = 0.75,
    color_context_text: bool = False,
) -> str:
    cabinets = [cabinet for cabinet in database.cabinets if cabinet.source_row is not None and cabinet.source_col is not None]
    if data_hall_id is not None:
        cabinets = [cabinet for cabinet in cabinets if cabinet.data_hall_id == data_hall_id]
    if not cabinets:
        raise ValueError("No cabinets with overhead source coordinates were found.")

    data_halls = sorted({cabinet.data_hall_id for cabinet in cabinets})
    layouts = {
        hall_id: _cabinet_grid_layout([cabinet for cabinet in cabinets if cabinet.data_hall_id == hall_id])
        for hall_id in data_halls
    }
    block_gap = 52
    hot_aisle_gap = 8
    cold_aisle_gap = 26
    panel_gap = 82
    max_block_count = max(max(position["block"] for _, position in layout) + 1 for layout in layouts.values())
    max_row_count = max(max(position["row"] for _, position in layout) + 1 for layout in layouts.values())
    panel_width = max_block_count * 10 * cell_width + (max_block_count - 1) * block_gap
    panel_height = _layout_y(max_row_count - 1, cell_height, hot_aisle_gap, cold_aisle_gap) + cell_height
    width = panel_width + margin * 2
    height = len(data_halls) * panel_height + (len(data_halls) - 1) * panel_gap + margin * 2 + 96

    parts = [_svg_header(width, height)]
    title = f"{data_hall_id} Cabinet Layout" if data_hall_id else "AI DC Infra Graph Cabinet Layout"
    parts.append(f'<text class="title" x="{margin}" y="28">{html.escape(title)}</text>')
    parts.append(f'<text class="subtitle" x="{margin}" y="48">10 cabinets per row; narrow gaps are hot aisles, wider gaps are cold aisles</text>')

    panel_top = margin + 26
    for hall_id in data_halls:
        parts.append(f'<text class="hall-label" x="{margin}" y="{panel_top - 10}">{html.escape(hall_id)}</text>')
        layout = layouts[hall_id]
        for cabinet, position in sorted(layout, key=lambda item: (item[1]["block"], item[1]["row"], item[1]["col"])):
            x = margin + position["block"] * (10 * cell_width + block_gap) + position["col"] * cell_width
            y = panel_top + _layout_y(position["row"], cell_height, hot_aisle_gap, cold_aisle_gap)
            parts.append(
                _cabinet_svg(
                    cabinet,
                    x,
                    y,
                    cell_width,
                    cell_height,
                    label_stroke_color=label_stroke_color,
                    label_stroke_width=label_stroke_width,
                    color_context_text=color_context_text,
                )
            )
        panel_top += panel_height + panel_gap

    legend_y = height - 58
    parts.extend(_legend(cabinets, margin, legend_y))
    parts.append("</svg>")
    return "\n".join(parts)


def _cabinet_svg(
    cabinet,
    x: int,
    y: int,
    cell_width: int,
    cell_height: int,
    label_stroke_color: str,
    label_stroke_width: float,
    color_context_text: bool,
) -> str:
    category = cabinet.category or "UNKNOWN"
    fill = _category_color(category)
    label_style = _label_style(
        fill,
        label_stroke_color=label_stroke_color,
        label_stroke_width=label_stroke_width,
        color_context_text=color_context_text,
    )
    uid = f"{cabinet.data_hall_id}:{cabinet.cabinet_id}"
    group = cabinet.cabinet_group or "Unassigned"
    tooltip = html.escape(
        f"{uid}\nCategory: {category}\nGroup: {group}\nSource: row {cabinet.source_row}, col {cabinet.source_col}"
    )
    cabinet_id = html.escape(cabinet.cabinet_id)
    label = html.escape(_short_label(category))
    return (
        f'<g class="cabinet-node">'
        f'<rect class="cabinet" x="{x}" y="{y}" width="{cell_width - 2}" height="{cell_height - 2}" fill="{fill}">'
        f"<title>{tooltip}</title>"
        f"</rect>"
        f'<text class="cabinet-label cabinet-id" x="{x + (cell_width - 2) / 2:.1f}" y="{y + 8}" style="{label_style}">{cabinet_id}</text>'
        f'<text class="cabinet-label cabinet-type" x="{x + (cell_width - 2) / 2:.1f}" y="{y + 17}" style="{label_style}">{label}</text>'
        f"</g>"
    )


def _cabinet_grid_layout(cabinets: list) -> list[tuple[object, dict[str, int]]]:
    layout = []
    source_rows = sorted({cabinet.source_row for cabinet in cabinets if cabinet.source_row is not None})
    for row_index, source_row in enumerate(source_rows):
        row_cabinets = sorted(
            [cabinet for cabinet in cabinets if cabinet.source_row == source_row],
            key=lambda cabinet: cabinet.source_col or 0,
        )
        for block_index, start in enumerate(range(0, len(row_cabinets), 10)):
            for col_index, cabinet in enumerate(row_cabinets[start : start + 10]):
                layout.append(
                    (
                        cabinet,
                        {
                            "block": block_index,
                            "row": row_index,
                            "col": col_index,
                        },
                    )
                )
    return layout


def _layout_y(row_index: int, cell_height: int, hot_aisle_gap: int, cold_aisle_gap: int) -> int:
    y = 0
    for previous_row in range(row_index):
        y += cell_height
        y += hot_aisle_gap if previous_row % 2 == 0 else cold_aisle_gap
    return y


def _label_style(
    background_color: str,
    label_stroke_color: str,
    label_stroke_width: float,
    color_context_text: bool,
) -> str:
    text_color = "#111827"
    stroke_color = label_stroke_color
    if color_context_text and _hex_color_brightness(background_color) < 40:
        text_color = "#FFFFFF"
        stroke_color = "#111827"

    if label_stroke_width <= 0:
        return f"fill:{html.escape(text_color)};stroke:none;stroke-width:0;"

    return (
        f"fill:{html.escape(text_color)};"
        f"stroke:{html.escape(stroke_color)};"
        f"stroke-width:{label_stroke_width:g}px;"
    )


def _hex_color_brightness(color: str) -> float:
    normalized = color.strip().lstrip("#")
    if len(normalized) == 3:
        normalized = "".join(channel * 2 for channel in normalized)
    if len(normalized) != 6:
        return 100.0

    try:
        red = int(normalized[0:2], 16)
        green = int(normalized[2:4], 16)
        blue = int(normalized[4:6], 16)
    except ValueError:
        return 100.0
    return ((red * 0.299) + (green * 0.587) + (blue * 0.114)) / 255 * 100


def _svg_header(width: int, height: int) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<style>
  .title {{ font: 600 16px Arial, sans-serif; fill: #111827; }}
  .subtitle {{ font: 12px Arial, sans-serif; fill: #4B5563; }}
  .hall-label {{ font: 700 12px Arial, sans-serif; fill: #111827; }}
  .cabinet {{ stroke: #FFFFFF; stroke-width: 1; shape-rendering: crispEdges; }}
  .cabinet-node:hover .cabinet {{ stroke: #111827; stroke-width: 2; }}
  .cabinet-label {{ paint-order: stroke fill; text-anchor: middle; pointer-events: none; }}
  .cabinet-id {{ font: 700 7px Arial, sans-serif; }}
  .cabinet-type {{ font: 4px Arial, sans-serif; }}
  .legend-label {{ font: 9px Arial, sans-serif; fill: #111827; }}
  .legend-title {{ font: 700 10px Arial, sans-serif; fill: #111827; }}
</style>
<rect width="100%" height="100%" fill="#F8FAFC"/>'''


def _legend(cabinets: list, x: int, y: int) -> list[str]:
    categories = sorted({cabinet.category or "UNKNOWN" for cabinet in cabinets})
    parts = [f'<text class="legend-title" x="{x}" y="{y}">Categories</text>']
    cursor_x = x
    cursor_y = y + 16
    for category in categories:
        label = html.escape(category)
        fill = _category_color(category)
        parts.append(f'<rect x="{cursor_x}" y="{cursor_y - 9}" width="10" height="10" fill="{fill}" stroke="#FFFFFF"/>')
        parts.append(f'<text class="legend-label" x="{cursor_x + 14}" y="{cursor_y}">{label}</text>')
        cursor_x += max(64, len(category) * 6 + 28)
        if cursor_x > x + 880:
            cursor_x = x
            cursor_y += 16
    return parts


def _short_label(category: str) -> str:
    return category


def _category_color(category: str) -> str:
    if category.startswith("T1-FE-"):
        return "#06B6D4"
    if category.startswith("T2-"):
        return "#FACC15"
    if category.startswith("T3-"):
        return "#F97316"
    if category.startswith("FCR-"):
        return "#0D9488"

    palette = {
        "DPR-H1": "#0F766E",
        "DPR-H2": "#14B8A6",
        "HD-GB3c": "#EF4444",
        "RES": "#9CA3AF",
        "U": "#E5E7EB",
        "T0-RO-v1a": "#2563EB",
        "T0-FE-v1a": "#7C3AED",
        "T1-RO-v1a": "#16A34A",
        "T1-RO-v1b": "#22C55E",
        "T1-RO-v3a": "#15803D",
        "STRG-v3a": "#0891B2",
        "CP5-v2a": "#0E7490",
        "BB-RES": "#64748B",
    }
    return palette.get(category, "#374151")
