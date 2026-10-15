/** V1 dimensions are integer inches; formatting never changes the model. */
export function formatInches(value: number): string {
  if (!Number.isSafeInteger(value)) throw new Error("Dimension must be integer inches.");
  return `${value < 0 ? "−" : ""}${Math.floor(Math.abs(value) / 12)}'-${Math.abs(value) % 12}"`;
}
export function parseInches(text: string): number {
  const normalized = text.trim().replace(/[′’]/g, "'").replace(/[″“”]/g, '"');
  const plain = /^(\d+)\s*(?:in|inches|")?$/.exec(normalized);
  if (plain) {
    const value = Number(plain[1]);
    if (!Number.isSafeInteger(value)) throw new Error("Dimension is too large.");
    return value;
  }
  const feet = /^(\d+)\s*(?:'|ft)\s*(?:-?\s*(\d+)\s*(?:"|in)?)?$/.exec(normalized);
  if (!feet || Number(feet[2] ?? 0) >= 12) throw new Error("Enter integer inches or feet/inches, for example 34 or 2'-10\".");
  const result = Number(feet[1]) * 12 + Number(feet[2] ?? 0);
  if (!Number.isSafeInteger(result)) throw new Error("Dimension is too large.");
  return result;
}
