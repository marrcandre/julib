import { beforeEach, expect, it, vi } from "vitest";
import { readCatalogOrder, writeCatalogOrder } from "../src/catalog-options";
import { readCatalogQuery } from "../src/catalog-navigation";
beforeEach(() => localStorage.clear());
it("remembers ordering separately by account and respects explicit URLs", () => {
  expect(readCatalogOrder(1)).toBe("newest");
  writeCatalogOrder(1, "title_asc");
  expect(readCatalogOrder(1)).toBe("title_asc");
  expect(readCatalogOrder(2)).toBe("newest");
  expect(readCatalogQuery({}, readCatalogOrder(1)).order).toBe("title_asc");
  expect(readCatalogQuery({ ordem: "oldest" }, readCatalogOrder(1)).order).toBe(
    "oldest",
  );
});
it("handles unavailable or corrupt preference storage", () => {
  localStorage.setItem("julib:catalog:order:1", "invalid");
  expect(readCatalogOrder(1)).toBe("newest");
  const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw Error("blocked");
  });
  expect(readCatalogOrder(1)).toBe("newest");
  spy.mockRestore();
});
