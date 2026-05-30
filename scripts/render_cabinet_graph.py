from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.graph import DEFAULT_CABINET_GRAPH_IMAGE_PATH, DEFAULT_CABINET_GRAPH_PATH, render_cabinet_graph_png


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a cabinet graph PNG for quick inspection.")
    parser.add_argument("--graph-path", default=str(DEFAULT_CABINET_GRAPH_PATH))
    parser.add_argument("--output-path", default=str(DEFAULT_CABINET_GRAPH_IMAGE_PATH))
    parser.add_argument("--dpi", type=int, default=220)
    args = parser.parse_args()

    output_path = render_cabinet_graph_png(
        graph_path=args.graph_path,
        output_path=args.output_path,
        dpi=args.dpi,
    )
    print(f"cabinet_graph_image={output_path}")


if __name__ == "__main__":
    main()
