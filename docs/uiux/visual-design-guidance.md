# Visual Design Guidance

This project uses color and frame styles to communicate entity state before relying on text. Keep map, table, and detail-panel states aligned so the same color means the same workflow state across the application.

## Theme Direction

White and dark modes will be implemented later. Until then, new UI should avoid hard-coding assumptions that prevent theme tokens from replacing raw colors.

Hatch colors should render at 25% opacity over either white or black backgrounds.

Text over color hatches, such as cabinet labels inside map boxes, should use 90% black or 90% white, opposite the current background. Faded text should use 50% gray in both modes.

Color text should keep the same hue scheme across modes, with 40% brightness in white mode and 60% brightness in dark mode.

## State Colors

Green means good status, validated status, added element, or forward progress.

Red means bad status, validation error, removed element, or regress caused by bad work.

Cyan means active or powered status, currently-added element, or currently-added progress.

Purple means modified status, currently-removed element, or currently-removed progress.

Orange means currently selected or viewed status. It is also used for major decision buttons that require user attention and risk management.

## Cabinet Map Frames

The last-clicked cabinet uses the same rounded-frame geometry and thickness as the active frame, rendered as a top-layer orange overlay so there is no gap between the active and last-clicked frames.

Selected or active cabinets use normal color with a moderately thick black rounded frame in light mode, and a moderately thick white rounded frame when dark mode is implemented. In group mode, this means cabinets already inside the selected group. Neighbor styling must not override this active frame. Cabinet number text should be bolded further for selected cabinets.

Graph neighbors of selected or active cabinets use a simple square black frame that sits flush with the cabinet box, with no gap and no rounded corners. Show a black count dot with a white number for connected active cabinets. If a cabinet is also active or selected, omit the graph-neighbor frame and keep only the count dot.

Added selection uses faded cabinet fill with a thin cyan rounded frame. The frame itself should not fade.

Graph neighbors of added selection use faded cabinet fill with a thin square black frame. The frame itself should not fade. Show a gray count dot with a white number. If the same cabinet is already a graph neighbor of active cabinets, keep the active-neighbor square black frame and show the added count in cyan alongside the active count.

Removed selection uses normal color with a medium purple rounded frame, overriding the normal active-cabinet cyan frame.

Graph neighbors lost by removed selection use dashed thin square black frames. If the neighbor is completely lost, it is faded. If only the connected-active count is reduced, keep normal color, use the dashed thin black frame, and show the remaining active count in purple inside the black count dot. If a cabinet is also active or selected, omit the graph-neighbor frame and keep the selected/active frame.
Data-hall selector buttons should use an orange accent background and show a small black circular count badge when graph neighbors exist in another data hall. The badge count is the number of graph-neighbor cabinets in that data hall.
Connection count dots should render above cabinet frames, including selected and last-clicked frames.