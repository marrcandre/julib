import type { components } from "./generated/schema";
export type Tag = components["schemas"]["TagOut"];
export type Location = components["schemas"]["LocationOut"];
export type Copy = components["schemas"]["CopyOut"];
export type Book = components["schemas"]["BookOut"];
export type Person = components["schemas"]["PersonOut"];
export type Loan = components["schemas"]["LoanOut"];
export type Session = components["schemas"]["SessionOut"];
export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
  }
}
let csrf = "";
export function setCsrf(token: string) {
  csrf = token;
}
export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET")
    headers.set("X-CSRFToken", csrf);
  let response: Response;
  try {
    response = await fetch("/api/v1" + path, {
      ...options,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      "Não foi possível confirmar o resultado. Reconecte e tente novamente; uma gravação pode ter sido concluída.",
    );
  }
  const data = await response
    .json()
    .catch(() => ({ detail: "Resposta inesperada do servidor." }));
  if (!response.ok) {
    if (response.status === 401)
      throw new Error("Entre com sua conta Google para continuar.");
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : "Confira os campos informados e tente novamente.",
      response.status,
    );
  }
  return data as T;
}
export const post = <T = unknown>(path: string, body: unknown = {}) =>
  api<T>(path, { method: "POST", body: JSON.stringify(body) });
export function locationLabel(
  locations: Location[],
  id: number | null,
): string {
  if (!id) return "Sem localização";
  const loc = locations.find((l) => l.id === id);
  return loc
    ? (loc.parent_id ? locationLabel(locations, loc.parent_id) + " → " : "") +
        loc.name
    : "Sem localização";
}
export const today = () =>
  new Date().toLocaleDateString("en-CA", { timeZone: "America/Sao_Paulo" });
