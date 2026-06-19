type ViewerScaleSliderProps<T extends string> = {
  label: string;
  steps: Array<{ value: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
};

export function ViewerScaleSlider<T extends string>({ label, steps, value, onChange }: ViewerScaleSliderProps<T>) {
  const currentIndex = Math.max(0, steps.findIndex((step) => step.value === value));
  const currentLabel = steps[currentIndex]?.label ?? label;

  return (
    <div className="viewer-scale-slider" role="group" aria-label={label}>
      <span>{currentLabel}</span>
      <input
        aria-label={label}
        max={steps.length - 1}
        min={0}
        onChange={(event) => onChange(steps[Number(event.target.value)]?.value ?? value)}
        step={1}
        type="range"
        value={currentIndex}
      />
      <div className="viewer-scale-ticks" aria-hidden="true">
        {steps.map((step, index) => {
          const left = steps.length <= 1 ? 0 : (index / (steps.length - 1)) * 100;
          return (
            <span
              className={index === currentIndex ? "is-active" : ""}
              key={step.value}
              style={{ left: `${left}%` }}
              title={step.label}
            />
          );
        })}
      </div>
    </div>
  );
}

