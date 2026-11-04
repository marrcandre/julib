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
