const valid = (value: number) =>
  Number.isInteger(value) && value >= 3 && value <= 10;
const key = (userId: number) => `julib:catalog:columns:${userId}`;

export function readCoverColumns(
  userId: number | undefined,
  mobile: boolean,
  storage?: Pick<Storage, "getItem">,
): number {
  const fallback = mobile ? 4 : 7;
  if (!userId) return fallback;
  try {
    const raw = (storage ?? window.localStorage).getItem(key(userId));
    const value = raw === null ? NaN : Number(raw);
    return valid(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

export function writeCoverColumns(
  userId: number | undefined,
  value: number,
  storage?: Pick<Storage, "setItem">,
): boolean {
  if (!userId || !valid(value)) return false;
  try {
    (storage ?? window.localStorage).setItem(key(userId), String(value));
    return true;
  } catch {
    return false;
  }
}
