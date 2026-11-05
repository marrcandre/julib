import { it, expect, beforeEach } from "vitest";
import {
  readCoverColumns,
  writeCoverColumns,
} from "../src/catalog-preferences";

beforeEach(() => localStorage.clear());
it("keeps density in this browser separately for each account", () => {
  expect(readCoverColumns(1, true)).toBe(4);
  expect(readCoverColumns(1, false)).toBe(7);
  expect(writeCoverColumns(1, 9)).toBe(true);
  expect(readCoverColumns(1, true)).toBe(9);
  expect(readCoverColumns(2, true)).toBe(4);
  expect(readCoverColumns(1, false)).toBe(9);
  localStorage.clear(); // Another browser/device has no shared local preference.
  expect(readCoverColumns(1, true)).toBe(4);
});
it("rejects corrupt/out-of-range preferences and tolerates unavailable storage", () => {
  for (const value of [2, 11, 4.5, NaN])
    expect(writeCoverColumns(1, value)).toBe(false);
  expect(writeCoverColumns(undefined, 5)).toBe(false);
  const unavailable = {
    getItem() {
      throw Error("blocked");
    },
    setItem() {
      throw Error("blocked");
    },
  };
  expect(readCoverColumns(1, true, unavailable)).toBe(4);
  expect(writeCoverColumns(1, 5, unavailable)).toBe(false);
});
