export type PageToken = number | "left" | "right";
export type PagePreferences = { rows: number; listSize: number };
export function pageTokens(
  current: number,
  total: number,
  compact: boolean,
): PageToken[] {
  if (total <= 1) return [1];
  const visible = new Set<number>([1, total]);
  const radius = compact ? 0 : 2;
  for (
    let i = Math.max(1, current - radius);
    i <= Math.min(total, current + radius);
    i++
  )
    visible.add(i);
  if (compact && current <= 2)
    for (let i = 1; i <= Math.min(3, total); i++) visible.add(i);
  if (compact && current >= total - 1)
    for (let i = Math.max(1, total - 2); i <= total; i++) visible.add(i);
  const result: PageToken[] = [];
  for (const value of [...visible].sort((a, b) => a - b)) {
    const previous = result.at(-1);
    if (typeof previous === "number" && value - previous > 1) {
      if (value - previous === 2) result.push(previous + 1);
      else result.push(value <= current ? "left" : "right");
    }
    result.push(value);
  }
  return result;
}
export const pageForOffset = (offset: number, size: number) =>
  Math.floor(Math.max(0, offset) / size) + 1;
export function sizeForLayout(
  view: string,
  rows: number,
  columns: number,
  mobile: boolean,
  listSize: number,
): number {
  return view === "list"
    ? listSize
    : rows * (view === "covers" ? columns : mobile ? 3 : 5);
}
export function readPagePreferences(userId?: number): PagePreferences {
  try {
    const data = JSON.parse(
      userId
        ? localStorage.getItem(`julib:catalog:pagination:${userId}`) || "null"
        : "null",
    );
    return {
      rows: [3, 5, 8, 10].includes(data?.rows) ? data.rows : 5,
      listSize: [24, 48, 96].includes(data?.listSize) ? data.listSize : 24,
    };
  } catch {
    return { rows: 5, listSize: 24 };
  }
}
export function savePagePreferences(
  userId: number | undefined,
  value: PagePreferences,
) {
  try {
    if (userId)
      localStorage.setItem(
        `julib:catalog:pagination:${userId}`,
        JSON.stringify(value),
      );
  } catch {
    /* Use this visit's choice when storage is unavailable. */
  }
}
