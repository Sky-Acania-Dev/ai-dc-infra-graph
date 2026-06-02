type ProgressCircleProps = {
  percent: number;
  size?: number;
  label?: string;
};

export function ProgressCircle({ percent, size = 22, label }: ProgressCircleProps) {
  const radius = size / 2 - 2;
  const center = size / 2;
  const clamped = Math.min(100, Math.max(0, percent));
  const angle = (clamped / 100) * 360;
  const largeArc = angle > 180 ? 1 : 0;
  const end = polarToCartesian(center, center, radius, angle);
  const path =
    clamped >= 100
      ? `M ${center} ${center - radius} A ${radius} ${radius} 0 1 1 ${center - 0.01} ${center - radius} Z`
      : `M ${center} ${center} L ${center} ${center - radius} A ${radius} ${radius} 0 ${largeArc} 1 ${end.x} ${end.y} Z`;

  return (
    <svg className="progress-circle" width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label={label}>
      <circle cx={center} cy={center} r={radius} />
      {clamped > 0 ? <path d={path} fill={progressColor(clamped)} /> : null}
    </svg>
  );
}

function progressColor(percent: number): string {
  if (percent < 25) return "#ef4444";
  if (percent < 50) return "#f97316";
  if (percent < 75) return "#eab308";
  return "#22c55e";
}

function polarToCartesian(centerX: number, centerY: number, radius: number, angleDegrees: number) {
  const angleRadians = ((angleDegrees - 90) * Math.PI) / 180.0;
  return {
    x: centerX + radius * Math.cos(angleRadians),
    y: centerY + radius * Math.sin(angleRadians),
  };
}
