import type { LocationQuery, LocationQueryRaw } from "vue-router";
export type CatalogState = {
  q: string;
  tag: number | null;
  location: number | null;
  available: boolean | null;
  missing: boolean;
  page: number;
  scope: "collection" | "wishlist";
};
const one = (v: LocationQuery[string]) => (Array.isArray(v) ? v[0] : v);
const id = (v: LocationQuery[string]) => {
  const n = Number(one(v));
  return Number.isSafeInteger(n) && n > 0 ? n : null;
};
export function readCatalogQuery(query: LocationQuery): CatalogState {
  return {
    q: one(query.q) || "",
    tag: id(query.tag),
    location: id(query.local),
    available:
      one(query.disponivel) === "true"
        ? true
        : one(query.disponivel) === "false"
          ? false
          : null,
    missing: one(query.sem_local) === "true",
    page: id(query.pagina) || 1,
    scope: one(query.lista) === "desejados" ? "wishlist" : "collection",
  };
}
export function catalogQuery(s: CatalogState): LocationQueryRaw {
  return {
    q: s.q || undefined,
    tag: s.tag || undefined,
    local: s.location || undefined,
    disponivel: s.available === null ? undefined : String(s.available),
    sem_local: s.missing ? "true" : undefined,
    pagina: s.page > 1 ? s.page : undefined,
    lista: s.scope === "wishlist" ? "desejados" : undefined,
  };
}
export function safeCatalogReturn(value: LocationQuery[string]): string {
  const text = one(value) || "";
  if (!text.startsWith("/livros") || text.startsWith("//")) return "/livros";
  try {
    const url = new URL(text, "https://julib.invalid");
    return url.origin === "https://julib.invalid" && url.pathname === "/livros"
      ? url.pathname + url.search
      : "/livros";
  } catch {
    return "/livros";
  }
}
const positions = new Map<string, number>();
export function saveCatalogPosition(path: string) {
  positions.set(path, window.scrollY);
}
export function catalogPosition(path: string) {
  return positions.get(path) || 0;
}
