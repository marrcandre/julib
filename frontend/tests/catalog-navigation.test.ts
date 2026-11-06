import { it, expect } from "vitest";
import {
  safeCatalogReturn,
  readCatalogQuery,
  catalogQuery,
} from "../src/catalog-navigation";
it("keeps return navigation inside the private catalog", () => {
  expect(safeCatalogReturn("/livros?q=Orwell&pagina=2")).toBe(
    "/livros?q=Orwell&pagina=2",
  );
  for (const path of [
    "https://example.com",
    "//example.com",
    "/livros/123",
    "/livros-malicioso",
    "/livros\\\\example.com",
    null,
  ])
    expect(safeCatalogReturn(path)).toBe("/livros");
});
it("restores wishlist filters and pagination without accepting invalid IDs", () => {
  const state = readCatalogQuery({
    q: "Orwell",
    tag: "3",
    local: "bad",
    pagina: "2",
    lista: "desejados",
    disponivel: "false",
    sem_local: "true",
  });
  expect(state).toEqual({
    q: "Orwell",
    tag: 3,
    location: null,
    page: 2,
    pageSize: 24,
    statuses: ["wishlist"],
    order: "newest",
    missing: true,
  });
  expect(catalogQuery(state)).toMatchObject({
    q: "Orwell",
    tag: 3,
    pagina: 2,
    situacao: "wishlist",
    ordem: "newest",
  });
});

it("roundtrips multiple situations and ordering", () => {
  const state = readCatalogQuery({
    situacao: "lost,wishlist",
    ordem: "acquired_asc",
    pagina: "3",
  });
  expect(state.statuses).toEqual(["wishlist", "lost"]);
  expect(state.order).toBe("acquired_asc");
  expect(readCatalogQuery(catalogQuery(state) as never)).toEqual(state);
  expect(
    readCatalogQuery({ situacao: "invalid", ordem: "invalid" }).statuses,
  ).toEqual(["available", "loaned"]);
});

it("keeps the effective size in return links without accepting unbounded sizes", () => {
  const state = readCatalogQuery({ pagina: "3", por_pagina: "35" });
  expect(readCatalogQuery(catalogQuery(state) as never)).toEqual(state);
  expect(readCatalogQuery({ por_pagina: "9999" }).pageSize).toBe(24);
});
