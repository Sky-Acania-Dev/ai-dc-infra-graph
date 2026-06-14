import { useRef, type MouseEvent, type PointerEvent } from "react";

const POINTER_HOLD_THRESHOLD_MS = 250;
const TOUCH_HOLD_THRESHOLD_MS = 150;
const MOVE_THRESHOLD_PX = 14;

type PanState = {
  pointerId: number;
  startX: number;
  startY: number;
  scrollLeft: number;
  scrollTop: number;
  startedAt: number;
  holdThresholdMs: number;
  didDrag: boolean;
};

export function useDragPan<T extends HTMLElement>() {
  const elementRef = useRef<T | null>(null);
  const stateRef = useRef<PanState | null>(null);

  function clearDrag() {
    elementRef.current?.classList.remove("is-drag-panning");
    stateRef.current = null;
  }

  return {
    ref: elementRef,
    onClickCapture: (event: MouseEvent<T>) => {
      const state = stateRef.current;
      if (state?.didDrag) {
        event.preventDefault();
        event.stopPropagation();
      }
      clearDrag();
    },
    onPointerCancel: clearDrag,
    onPointerDown: (event: PointerEvent<T>) => {
      if (event.button !== 0 || isNativeInteractive(event.target)) return;
      const element = elementRef.current;
      if (!element) return;
      stateRef.current = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        scrollLeft: element.scrollLeft,
        scrollTop: element.scrollTop,
        startedAt: window.performance.now(),
        holdThresholdMs: event.pointerType === "mouse" ? POINTER_HOLD_THRESHOLD_MS : TOUCH_HOLD_THRESHOLD_MS,
        didDrag: false,
      };
    },
    onPointerMove: (event: PointerEvent<T>) => {
      const state = stateRef.current;
      const element = elementRef.current;
      if (!state || !element || state.pointerId !== event.pointerId) return;

      const dx = event.clientX - state.startX;
      const dy = event.clientY - state.startY;
      const distance = Math.hypot(dx, dy);
      const heldLongEnough = window.performance.now() - state.startedAt >= state.holdThresholdMs;
      if (!state.didDrag && !heldLongEnough && distance < MOVE_THRESHOLD_PX) return;

      state.didDrag = true;
      if (!element.hasPointerCapture(event.pointerId)) {
        element.setPointerCapture(event.pointerId);
      }
      element.classList.add("is-drag-panning");
      element.scrollLeft = state.scrollLeft - dx;
      element.scrollTop = state.scrollTop - dy;
      event.preventDefault();
    },
    onPointerUp: (event: PointerEvent<T>) => {
      const element = elementRef.current;
      if (element?.hasPointerCapture(event.pointerId)) {
        element.releasePointerCapture(event.pointerId);
      }
      if (!stateRef.current?.didDrag) clearDrag();
    },
  };
}

function isNativeInteractive(target: EventTarget): boolean {
  return target instanceof Element && Boolean(target.closest("button,input,select,textarea,a"));
}
