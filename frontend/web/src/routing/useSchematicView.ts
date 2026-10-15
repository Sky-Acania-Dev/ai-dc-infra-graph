import { useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";

export function useSchematicView(length: number, width: number) {
  const svgRef = useRef<SVGSVGElement>(null);
  const leftMargin = Math.max(160, length * 0.12);
  const fitted = { x: -leftMargin, y: -110, w: length + leftMargin + 160, h: width + 220 };
  const [view, setView] = useState(fitted);
  const [screenWidth, setScreenWidth] = useState(1200);
  const drag = useRef<{ x: number; y: number; origin: typeof view; moved: boolean } | null>(null);
  const suppressClick = useRef(false);
  const scale = Math.min(screenWidth / view.w, (svgRef.current?.clientHeight || 460) / view.h);
  useEffect(() => { setView(fitted); }, [length, width]);
  useEffect(() => {
    if (!svgRef.current) return;
    const observer = new ResizeObserver(entries => setScreenWidth(entries[0].contentRect.width));
    observer.observe(svgRef.current);
    return () => observer.disconnect();
  }, []);
  function point(clientX: number, clientY: number) {
    const svg = svgRef.current;
    const matrix = svg?.getScreenCTM();
    if (!svg || !matrix) return { x: 0, y: 0 };
    const p = svg.createSVGPoint(); p.x = clientX; p.y = clientY;
    return p.matrixTransform(matrix.inverse());
  }
  function zoom(factor: number, anchor = { x: view.x + view.w / 2, y: view.y + view.h / 2 }) {
    setView(v => {
      const w = Math.max(200, Math.min(fitted.w * 3, v.w * factor));
      const ratio = w / v.w;
      return { x: anchor.x - (anchor.x - v.x) * ratio, y: anchor.y - (anchor.y - v.y) * ratio, w, h: v.h * ratio };
    });
  }
  function pointerDown(event: ReactPointerEvent<SVGSVGElement>) {
    if (event.button !== 0 || (event.target as Element).closest('[data-selectable]')) return;
    drag.current = { x: event.clientX, y: event.clientY, origin: view, moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function pointerMove(event: ReactPointerEvent<SVGSVGElement>) {
    const d = drag.current;
    if (!d) return;
    const dx = event.clientX - d.x, dy = event.clientY - d.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) d.moved = true;
    if (d.moved) setView({ ...d.origin, x: d.origin.x - dx / scale, y: d.origin.y - dy / scale });
  }
  function pointerUp() { suppressClick.current = Boolean(drag.current?.moved); drag.current = null; }
  const focusSection = (start: number, end: number) => setView({ x: start - 200, y: -80, w: end - start + 400, h: width + 160 });
  return { svgRef, view, scale, zoom, point, focusSection, fit: () => setView(fitted), pointerDown, pointerMove, pointerUp, suppressClick };
}
