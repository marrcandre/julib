export const situationOptions = [
  { value: "available", label: "Disponíveis" },
  { value: "loaned", label: "Emprestados" },
  { value: "wishlist", label: "Desejados" },
  { value: "lost", label: "Perdidos" },
] as const;
export type Situation = (typeof situationOptions)[number]["value"];
export const defaultSituations: Situation[] = ["available", "loaned"];
export const orderOptions = [
  { value: "newest", label: "Inclusão: mais recentes" },
  { value: "oldest", label: "Inclusão: mais antigos" },
  { value: "title_asc", label: "Título: A–Z" },
  { value: "title_desc", label: "Título: Z–A" },
  { value: "author", label: "Autor: A–Z" },
  { value: "acquired_desc", label: "Aquisição: mais recentes" },
  { value: "acquired_asc", label: "Aquisição: mais antigas" },
  { value: "year_desc", label: "Publicação: mais recentes" },
  { value: "year_asc", label: "Publicação: mais antigas" },
] as const;
export type CatalogOrder = (typeof orderOptions)[number]["value"];
export function validOrder(value: unknown): value is CatalogOrder {
  return orderOptions.some((o) => o.value === value);
}
export function readCatalogOrder(userId?: number): CatalogOrder {
  try {
    const value = userId
      ? localStorage.getItem(`julib:catalog:order:${userId}`)
      : null;
    return validOrder(value) ? value : "newest";
  } catch {
    return "newest";
  }
}
export function writeCatalogOrder(
  userId: number | undefined,
  value: CatalogOrder,
) {
  try {
    if (userId) localStorage.setItem(`julib:catalog:order:${userId}`, value);
  } catch {
    /* Preference is optional. */
  }
}
