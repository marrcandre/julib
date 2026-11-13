import {
  situationOptions,
  defaultSituations,
  validOrder,
  type Situation,
  type CatalogOrder,
} from "./catalog-options";
import type { LocationQuery, LocationQueryRaw } from "vue-router";
export type CatalogState = {
  q: string;
  tag: number | null;
  location: number | null;
  statuses: Situation[];
  order: CatalogOrder;
  missing: boolean;
  page: number;
  pageSize: number;
};
const one = (v: LocationQuery[string]) => (Array.isArray(v) ? v[0] : v);
const id = (v: LocationQuery[string]) => {
  const n = Number(one(v));
  return Number.isSafeInteger(n) && n > 0 ? n : null;
};
export function readCatalogQuery(
  query: LocationQuery,
  fallback: CatalogOrder = "newest",
): CatalogState {
  return {
    q: one(query.q) || "",
    tag: id(query.tag),
    location: id(query.local),
    statuses:
      query.situacao !== undefined
        ? one(query.situacao) === "todos"
          ? []
          : (() => {
              const values = (one(query.situacao) || "").split(",");
              const selected = situationOptions
                .filter((o) => values.includes(o.value))
                .map((o) => o.value);
              return selected.length ? selected : [...defaultSituations];
            })()
        : one(query.lista) === "desejados"
          ? ["wishlist"]
          : one(query.disponivel) === "true"
            ? ["available"]
            : one(query.disponivel) === "false"
              ? ["loaned", "lost"]
              : [...defaultSituations],
    order: validOrder(one(query.ordem))
      ? (one(query.ordem) as CatalogOrder)
      : fallback,
    missing: one(query.sem_local) === "true",
    page: id(query.pagina) || 1,
    pageSize:
      id(query.por_pagina) && id(query.por_pagina)! <= 100
        ? id(query.por_pagina)!
        : 24,
  };
}
export function catalogQuery(s: CatalogState): LocationQueryRaw {
  return {
    q: s.q || undefined,
    tag: s.tag || undefined,
    local: s.location || undefined,
    situacao: s.statuses.length ? s.statuses.join(",") : "todos",
    ordem: s.order,
    sem_local: s.missing ? "true" : undefined,
    pagina: s.page > 1 ? s.page : undefined,
    por_pagina: s.pageSize,
  };
}
export function safeCatalogReturn(value: LocationQuery[string]): string {
  const text = one(value) || "";
  if (
    (!text.startsWith("/livros") && !text.startsWith("/bibliotecas/")) ||
    text.startsWith("//")
  )
    return "/livros";
  try {
    const url = new URL(text, "https://julib.invalid");
    return url.origin === "https://julib.invalid" &&
      (url.pathname === "/livros" ||
        /^\/bibliotecas\/-?\d+\/livros$/.test(url.pathname))
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
