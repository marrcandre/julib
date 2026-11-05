import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
test("catalog, location and loan roundtrip on real API", async ({
  page,
  context,
}) => {
  await context.addCookies([
    JSON.parse(readFileSync("../.superpowers/e2e-session.json", "utf-8")),
  ]);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Olá, e2e." })).toBeVisible();
  await page.getByRole("link", { name: "Locais", exact: true }).click();
  await page.getByRole("button", { name: "Novo local" }).click();
  await page.getByLabel("Nome *").fill("Estante E2E " + Date.now());
  await page.getByRole("button", { name: "Salvar local" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("link", { name: "Livros", exact: true }).click();
  await page.getByRole("button", { name: "Adicionar livro" }).click();
  await page.getByRole("menuitem", { name: "Cadastro manual" }).click();
  const title = "Livro E2E " + Date.now();
  await page.getByLabel("Título *", { exact: true }).fill(title);
  await page.getByLabel("Autores *").fill("Autora de teste");
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("button", { name: "Abrir " + title, exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Empréstimos", exact: true }).click();
  await page
    .getByRole("button", { name: "Cadastrar pessoa", exact: true })
    .click();
  const friend = "Amiga E2E " + Date.now();
  await page.getByLabel("Nome *", { exact: true }).fill(friend);
  await page.getByLabel("Telefone *", { exact: true }).fill("47999999999");
  await page.getByRole("button", { name: "Salvar pessoa" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button", { name: "Novo empréstimo" }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByText("Exemplar disponível *")).toBeVisible();
  const modal = page.getByRole("dialog");
  await modal.getByRole("combobox").nth(0).click();
  await page.getByRole("option", { name: friend, exact: true }).click();
  await modal.getByRole("combobox").nth(1).click();
  await page.getByRole("option", { name: new RegExp(title) }).click();
  await page.getByRole("button", { name: "Registrar empréstimo" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const row = page.locator(".loan-row").filter({ hasText: title });
  await expect(row).toContainText(friend);
  await row.getByRole("button", { name: "Devolver", exact: true }).click();
  await page.getByRole("button", { name: "Confirmar devolução" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(row).not.toBeVisible();
  await page.goto("/");
  await expect(
    page.getByText("Exemplares no acervo", { exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../.superpowers/julib-desktop.png",
    fullPage: true,
  });
});
test("mobile layout and theme preference", async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 852 });
  await page.goto("/sobre");
  await expect(
    page.getByRole("heading", { name: "Uma biblioteca cheia de histórias." }),
  ).toBeVisible();
  await page.screenshot({
    path: "../.superpowers/julib-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await expect(
    page.getByText("Dons Espirituais", { exact: true }),
  ).toBeVisible();
});

test("lost registration response can be retried without duplicating a copy", async ({
  page,
  context,
}) => {
  await context.addCookies([
    JSON.parse(readFileSync("../.superpowers/e2e-session.json", "utf-8")),
  ]);
  let dropped = false;
  await page.route("**/api/v1/registrations", async (route) => {
    if (!dropped) {
      dropped = true;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await page.goto("/livros?novo=1");
  const title = "Retry E2E " + Date.now();
  await page.getByLabel("Título *", { exact: true }).fill(title);
  await page.getByLabel("Autores *").fill("Autora de teste");
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "Não foi possível confirmar",
  );
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  const response = await page.request.get(
    "/api/v1/books?q=" + encodeURIComponent(title),
  );
  const data = await response.json();
  expect(data.total).toBe(1);
  expect(data.items[0].copies).toHaveLength(1);
});
