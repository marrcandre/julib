import { it, expect, vi } from "vitest";
import { api } from "../src/api";
it("surfaces server validation errors without pretending save succeeded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: "Exemplar indisponível" }),
    }),
  );
  await expect(
    api("/loans", { method: "POST", body: JSON.stringify({}) }),
  ).rejects.toThrow("Exemplar indisponível");
});

it("does not claim nothing saved when a write response is lost", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network")));
  await expect(
    api("/registrations", { method: "POST", body: "{}" }),
  ).rejects.toThrow("Não foi possível confirmar");
});

it("sends the active route library with API requests", async () => {
  const originalPath = window.location.pathname;
  window.history.replaceState({}, "", "/bibliotecas/42/emprestimos");
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [],
  });
  vi.stubGlobal("fetch", fetchMock);

  await api("/loans");

  const init = fetchMock.mock.calls[0][1] as RequestInit;
  expect(new Headers(init.headers).get("X-Library-ID")).toBe("42");
  window.history.replaceState({}, "", originalPath);
});

it("keeps session and library creation requests unscoped", async () => {
  const originalPath = window.location.pathname;
  window.history.replaceState({}, "", "/bibliotecas/42/livros");
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
  });
  vi.stubGlobal("fetch", fetchMock);

  await api("/session");
  await api("/libraries", {
    method: "POST",
    body: "{}",
    headers: { "X-Library-ID": "99" },
  });

  for (const [, init] of fetchMock.mock.calls as [string, RequestInit?][]) {
    expect(new Headers(init?.headers).has("X-Library-ID")).toBe(false);
  }
  window.history.replaceState({}, "", originalPath);
});

it("does not reuse a library header outside a canonical library route", async () => {
  const originalPath = window.location.pathname;
  window.history.replaceState({}, "", "/bibliotecas/nao-valida/livros");
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => [],
  });
  vi.stubGlobal("fetch", fetchMock);

  await api("/books", { headers: { "X-Library-ID": "42" } });

  const init = fetchMock.mock.calls[0][1] as RequestInit;
  expect(new Headers(init.headers).has("X-Library-ID")).toBe(false);
  window.history.replaceState({}, "", originalPath);
});
