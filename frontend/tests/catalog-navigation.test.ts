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
    scope: "wishlist",
    available: false,
    missing: true,
  });
  expect(catalogQuery(state)).toMatchObject({
    q: "Orwell",
    tag: 3,
    pagina: 2,
    lista: "desejados",
    disponivel: "false",
  });
});
