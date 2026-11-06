import { test, expect } from "@playwright/test";

test("update feedback stays compact in a corner and disappears automatically", async ({
  page,
}) => {
  const book = {
    id: 1,
    title: "Livro",
    authors: ["Autor"],
    isbn: "",
    publisher: "",
    edition: "",
    year: "",
    language: "",
    cover_url: "",
    source: "",
    source_id: "",
    tags: [],
    copies: [],
    available: true,
    attribution_name: "",
    attribution_url: "",
  };
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = path.endsWith("/session")
      ? {
          user_id: 1,
          name: "Teste",
          email: "test@example.com",
          technical: false,
          library: "Casa",
          csrf: "test",
          avatar_url: "",
          catalog_view: "covers",
          cover_columns: 7,
        }
      : path.endsWith("/books")
        ? { items: [book], total: 1 }
        : path.endsWith("/books/1")
          ? book
          : [];
    return route.fulfill({ json });
  });
  await page.addInitScript(() =>
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: async () => {} },
    }),
  );
  await page.goto("/livros");
  await page.getByRole("link", { name: "Abrir Livro", exact: true }).click();
  await page.getByRole("button", { name: "Editar livro", exact: true }).click();
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .click();
  const toast = page.locator(".p-toast-message");
  await expect(toast).toContainText("Dados atualizados.");
  const box = (await toast.boundingBox())!;
  expect(box.x).toBeGreaterThan(850);
  expect(box.y).toBeGreaterThan(700);
  expect(box.height).toBeLessThan(90);
  await expect(toast).toHaveCount(0, { timeout: 6000 });
  await page.setViewportSize({ width: 393, height: 852 });

  await page.getByRole("button", { name: "Editar livro", exact: true }).click();
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .click();
  await expect(toast).toContainText("Dados atualizados.");
  const mobile = (await toast.boundingBox())!;
  expect(mobile.x).toBeGreaterThanOrEqual(10);
  expect(mobile.x + mobile.width).toBeLessThanOrEqual(383);
  expect(mobile.y).toBeGreaterThan(700);
  await page.screenshot({
    path: "../.superpowers/feedback-mobile.png",
    animations: "disabled",
  });
  await expect(toast).toHaveCount(0, { timeout: 6000 });
  await page.goto("/sobre");
  await page.getByRole("button", { name: "Copiar chave PIX" }).click();
  await expect(toast).toContainText("Chave PIX copiada.");
  await expect(
    page.locator(".readable p").filter({ hasText: "Chave PIX copiada." }),
  ).toHaveCount(0);
  await expect(toast).toHaveCount(0, { timeout: 6000 });
});
