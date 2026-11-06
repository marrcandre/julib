import { it, expect } from "vitest";
import {
  pageTokens,
  pageForOffset,
  sizeForLayout,
  readPagePreferences,
  savePagePreferences,
} from "../src/pagination";
it("uses short windows with endpoints and ellipses", () => {
  expect(pageTokens(7, 14, false)).toEqual([
    1,
    "left",
    5,
    6,
    7,
    8,
    9,
    "right",
    14,
  ]);
  expect(pageTokens(7, 14, true)).toEqual([1, "left", 7, "right", 14]);
  expect(pageTokens(1, 3, true)).toEqual([1, 2, 3]);
  expect(pageTokens(14, 14, true)).toEqual([1, "left", 12, 13, 14]);
});
it("keeps the reference book on the recalculated page", () => {
  expect(pageForOffset(48, 35)).toBe(2);
  expect(pageForOffset(70, 20)).toBe(4);
  expect(sizeForLayout("covers", 5, 7, false, 24)).toBe(35);
  expect(sizeForLayout("covers", 10, 10, true, 24)).toBe(100);
  expect(sizeForLayout("cards", 5, 7, true, 24)).toBe(15);
  expect(sizeForLayout("cards", 5, 7, false, 24)).toBe(25);
  expect(sizeForLayout("list", 5, 7, false, 96)).toBe(96);
});
it("keeps valid row and list preferences per account and tolerates corrupt storage", () => {
  localStorage.clear();
  expect(readPagePreferences(1)).toEqual({ rows: 5, listSize: 24 });
  savePagePreferences(1, { rows: 8, listSize: 48 });
  expect(readPagePreferences(1)).toEqual({ rows: 8, listSize: 48 });
  expect(readPagePreferences(2)).toEqual({ rows: 5, listSize: 24 });
  localStorage.setItem(
    "julib:catalog:pagination:1",
    '{"rows":999,"listSize":-1}',
  );
  expect(readPagePreferences(1)).toEqual({ rows: 5, listSize: 24 });
});
