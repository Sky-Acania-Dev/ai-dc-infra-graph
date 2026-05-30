export function categoryColor(category: string): string {
  if (category.startsWith("T1-FE-")) return "#06B6D4";
  if (category.startsWith("T2-")) return "#FACC15";
  if (category.startsWith("T3-")) return "#F97316";
  if (category.startsWith("FCR-")) return "#0D9488";

  const palette: Record<string, string> = {
    "DPR-H1": "#0F766E",
    "DPR-H2": "#14B8A6",
    "HD-GB3c": "#EF4444",
    RES: "#9CA3AF",
    U: "#E5E7EB",
    "T0-RO-v1a": "#2563EB",
    "T0-RO-v2a": "#1D4ED8",
    "T0-RO-v2b": "#3B82F6",
    "T0-FE-v1a": "#7C3AED",
    "T1-RO-v1a": "#16A34A",
    "T1-RO-v1b": "#22C55E",
    "T1-RO-v3a": "#15803D",
    "STRG-v3a": "#0891B2",
    "CP5-v2a": "#0E7490",
    "BB-RES": "#64748B",
  };
  return palette[category] ?? "#374151";
}

export function labelColors(backgroundColor: string): { fill: string; stroke: string } {
  return brightness(backgroundColor) < 40 ? { fill: "#FFFFFF", stroke: "#111827" } : { fill: "#111827", stroke: "#D1D5DB" };
}

function brightness(color: string): number {
  let normalized = color.replace("#", "").trim();
  if (normalized.length === 3) {
    normalized = normalized.split("").map((channel) => channel + channel).join("");
  }
  if (normalized.length !== 6) return 100;

  const red = parseInt(normalized.slice(0, 2), 16);
  const green = parseInt(normalized.slice(2, 4), 16);
  const blue = parseInt(normalized.slice(4, 6), 16);
  return ((red * 0.299 + green * 0.587 + blue * 0.114) / 255) * 100;
}
