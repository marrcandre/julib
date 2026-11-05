export function canonicalIsbn(raw: string): string {
  const value = raw.replace(/[\s-]/g, "").toUpperCase();
  if (/^\d{9}[\dX]$/.test(value)) {
    const sum = [...value].reduce(
      (total, c, i) => total + (10 - i) * (c === "X" ? 10 : Number(c)),
      0,
    );
    if (sum % 11 === 0) {
      const base = "978" + value.slice(0, 9);
      const check =
        (10 -
          ([...base].reduce(
            (total, c, i) => total + Number(c) * (i % 2 ? 3 : 1),
            0,
          ) %
            10)) %
        10;
      return base + check;
    }
  }
  return value;
}

export function isbnFromBarcode(raw: string): string | null {
  const isbn = canonicalIsbn(raw);
  if (!/^97[89]\d{10}$/.test(isbn)) return null;
  const sum = [...isbn].reduce(
    (total, digit, i) => total + Number(digit) * (i % 2 ? 3 : 1),
    0,
  );
  return sum % 10 === 0 ? isbn : null;
}
