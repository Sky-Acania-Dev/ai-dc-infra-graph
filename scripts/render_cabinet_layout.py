from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.graph import DEFAULT_CABINET_LAYOUT_SVG_PATH, render_cabinet_layout_svg
from backend.persistence import DEFAULT_RUNTIME_DATABASE_PATH
from backend.persistence import load_topology_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the overhead cabinet layout as an SVG map.")
    parser.add_argument(
        "--database-path",
        default=str(DEFAULT_RUNTIME_DATABASE_PATH),
        help="Path to the loaded topology database JSON.",
    )
    parser.add_argument(
        "--output-path",
        default=str(DEFAULT_CABINET_LAYOUT_SVG_PATH),
        help="Path for the generated SVG file.",
    )
    parser.add_argument("--cell-width", type=int, default=34, help="Cabinet rectangle width.")
    parser.add_argument("--cell-height", type=int, default=22, help="Cabinet rectangle height.")
    parser.add_argument(
        "--label-stroke-color",
        default="#D1D5DB",
        help="SVG color used for cabinet label outlines when enabled.",
    )
    parser.add_argument(
        "--label-stroke-width",
        type=float,
        default=0.75,
        help="Cabinet label outline width in px. Use 0 to disable label outlines.",
    )
    parser.add_argument(
        "--color-context-text",
        action="store_true",
        help="Use white text and an inverted dark outline on cabinet colors with brightness below 40 percent.",
    )
    parser.add_argument(
        "--data-hall",
        default=None,
        help="Optional data hall id such as DH1. If omitted, one SVG is rendered per data hall.",
    )
    args = parser.parse_args()

    if args.data_hall:
        output = render_cabinet_layout_svg(
            database_path=args.database_path,
            output_path=args.output_path,
            cell_width=args.cell_width,
            cell_height=args.cell_height,
            data_hall_id=args.data_hall,
            label_stroke_color=args.label_stroke_color,
            label_stroke_width=args.label_stroke_width,
            color_context_text=args.color_context_text,
        )
        print(f"cabinet_layout_svg={output}")
        return

    database = load_topology_database(args.database_path)
    output_path = Path(args.output_path)
    for data_hall_id in sorted({cabinet.data_hall_id for cabinet in database.cabinets}):
        hall_output = output_path.with_name(f"{output_path.stem}_{data_hall_id}{output_path.suffix}")
        output = render_cabinet_layout_svg(
            database_path=args.database_path,
            output_path=hall_output,
            cell_width=args.cell_width,
            cell_height=args.cell_height,
            data_hall_id=data_hall_id,
            label_stroke_color=args.label_stroke_color,
            label_stroke_width=args.label_stroke_width,
            color_context_text=args.color_context_text,
        )
        print(f"cabinet_layout_svg={output}")


if __name__ == "__main__":
    main()
