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
  await expect(page).toHaveURL(/\/livros(?:\?.*)?$/);
  await expect(
    page.getByRole("button", { name: "Adicionar livro" }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Painel" })).toHaveCount(0);
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
  await expect(page.getByLabel("Subtítulo")).toHaveAttribute("maxlength", "500");
  await expect(page.getByLabel("Sinopse")).toHaveAttribute(
    "maxlength",
    "20000",
  );
  await expect(page.getByLabel("Categorias / Assuntos")).toHaveAttribute(
    "maxlength",
    "10049",
  );
  await page.getByLabel("Subtítulo").fill("Subtítulo cadastrado");
  await page.getByLabel("Sinopse").fill("Sinopse cadastrada manualmente.");
  await page
    .getByLabel("Categorias / Assuntos")
    .fill("História\nLiteratura");
  await page.getByRole("button", { name: "Salvar", exact: true }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(
    page.getByRole("link", { name: "Abrir " + title, exact: true }),
  ).toBeVisible();
  const libraryId = new URL(page.url()).pathname.split("/")[2];
  const catalog = await page.request.get(
    "/api/v1/books?q=" + encodeURIComponent(title),
    { headers: { "X-Library-ID": libraryId } },
  );
  const book = (await catalog.json()).items[0];
  expect(book.subtitle).toBe("Subtítulo cadastrado");
  expect(book.description).toBe("Sinopse cadastrada manualmente.");
  expect(book.subjects).toEqual(["História", "Literatura"]);
  await page.goto(`/livros/${book.id}`);
  await page.getByRole("button", { name: "Editar livro sem capa" }).click();
  await expect(page.getByLabel("Subtítulo")).toHaveValue("Subtítulo cadastrado");
  await expect(page.getByLabel("Descrição e sinopse")).toHaveValue(
    "Sinopse cadastrada manualmente.",
  );
  await expect(page.getByLabel("Assuntos bibliográficos")).toHaveValue(
    "História\nLiteratura",
  );
  await page.getByRole("button", { name: "Salvar alterações" }).first().click();
  await expect(page.getByRole("heading", { name: title })).toBeVisible();
  await page.goto("/livros");
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
    page.getByRole("button", { name: "Adicionar livro" }),
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
    page.getByRole("heading", {
      name: "Julib — Sua biblioteca, bem organizada",
    }),
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
  const libraryId = new URL(page.url()).pathname.split("/")[2];
  const response = await page.request.get(
    "/api/v1/books?q=" + encodeURIComponent(title),
    { headers: { "X-Library-ID": libraryId } },
  );
  const data = await response.json();
  expect(data.total).toBe(1);
  expect(data.items[0].copies).toHaveLength(1);
  expect(data.items[0].subtitle).toBe("");
  expect(data.items[0].description).toBe("");
  expect(data.items[0].subjects).toEqual([]);
});
