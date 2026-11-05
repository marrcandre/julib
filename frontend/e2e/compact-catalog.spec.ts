import { test, expect, type Page } from "@playwright/test";

async function mockCatalog(
  page: Page,
  account: { id: number },
  state: {
    view: string;
    writes: unknown[];
    queries: string[];
    share: boolean;
    shareWrites: string[];
  },
) {
  await page.route("**/compact-cover.svg", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="150"><rect width="100" height="150" fill="#053227"/></svg>',
    }),
  );
  await page.route("**/api/v1/**", (route) => {
    const url = new URL(route.request().url()),
      method = route.request().method();
    let json: unknown = [];
    if (url.pathname.endsWith("/session"))
      json = {
        user_id: account.id,
        name: "Teste",
        email: "test@example.com",
        technical: false,
        library: "Casa",
        csrf: "test",
        avatar_url: "",
        catalog_view: state.view,
        cover_columns: 7,
      };
    else if (url.pathname.endsWith("/preferences/catalog")) {
      const body = route.request().postDataJSON();
      state.view = body.catalog_view;
      state.writes.push(body);
      json = body;
    } else if (url.pathname.endsWith("/books")) {
      state.queries.push(url.search);
      json = {
        total: 320,
        items: Array.from({ length: 12 }, (_, i) => ({
          id: i + 1,
          title: "Livro " + i,
          authors: ["Autor"],
          isbn: "",
          publisher: "",
          edition: "",
          year: "",
          language: "",
          cover_url: "/compact-cover.svg",
          source: "",
          source_id: "",
          tags: [],
          copies: [],
          available: true,
          attribution_name: "",
          attribution_url: "",
        })),
      };
    } else if (url.pathname.endsWith("/share/manage")) {
      if (method !== "GET") {
        state.shareWrites.push(method);
        state.share = method === "POST";
      }
      json =
        method === "POST"
          ? { token: "test-preview-token" }
          : { active: state.share };
    }
    return route.fulfill({ json });
  });
}

test("compact catalog prioritizes books and keeps density per account and device", async ({
  page,
  browser,
}) => {
  const state = {
      view: "covers",
      writes: [] as unknown[],
      queries: [] as string[],
      share: true,
      shareWrites: [] as string[],
    },
    account = { id: 1 };
  await mockCatalog(page, account, state);
  await page.setViewportSize({ width: 393, height: 852 });
  await page.goto("/livros");
  await expect(page.locator(".book-card")).toHaveCount(12);
  expect((await page.locator(".cover").first().boundingBox())!.y).toBeLessThan(
    250,
  );
  await expect(
    page.getByLabel("320 edições encontradas", { exact: true }),
  ).toHaveText("320");
  await expect(
    page.getByRole("button", { name: "Adicionar livro", exact: true }),
  ).toHaveText("");
  await expect(
    page.getByRole("combobox", { name: "Filtrar por tag" }),
  ).not.toBeVisible();
  await page.getByRole("button", { name: "Abrir navegação" }).click();
  await expect(
    page
      .getByRole("dialog")
      .getByRole("link", { name: "Empréstimos", exact: true }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await page
    .getByRole("button", { name: "Adicionar livro", exact: true })
    .click();
  await page.getByRole("menuitem", { name: "Cadastro manual" }).click();
  await expect(
    page.getByRole("dialog", { name: "Cadastrar livro", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await page.getByRole("button", { name: "Filtros", exact: true }).click();
  await expect
    .poll(async () => {
      const box = await page.getByRole("dialog").boundingBox();
      return Math.round(box!.y + box!.height);
    })
    .toBe(852);
  const before = state.queries.length;
  await page.getByLabel("Sem localização", { exact: true }).check();
  expect(state.queries).toHaveLength(before);
  await page.getByRole("button", { name: "Aplicar filtros" }).click();
  await expect
    .poll(() => state.queries.at(-1))
    .toContain("missing_location=true");
  await expect(
    page.getByRole("button", { name: "Filtros: 1 aplicados" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Remover filtro Sem localização" })
    .click();
  await page
    .getByRole("button", { name: "Visualização dos livros", exact: true })
    .click();
  await expect
    .poll(async () => {
      const box = await page.getByRole("dialog").boundingBox();
      return Math.round(box!.y + box!.height);
    })
    .toBe(852);
  const slider = page.getByRole("slider", { name: "Livros por linha" });
  await expect(slider).toHaveValue("4");
  await slider.focus();
  await page.keyboard.press("End");
  await expect(slider).toHaveValue("10");
  expect(state.writes).toHaveLength(0);
  await page.keyboard.press("Escape");
  await page.reload();
  expect(
    await page
      .locator(".book-grid")
      .evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
      ),
  ).toBe(10);
  const context = await browser.newContext({
    viewport: { width: 393, height: 852 },
  });
  const other = await context.newPage();
  await mockCatalog(other, { id: 1 }, state);
  await other.goto("/livros");
  await expect(other.locator(".book-card")).toHaveCount(12);
  expect(
    await other
      .locator(".book-grid")
      .evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
      ),
  ).toBe(4);
  await context.close();
  account.id = 2;
  await page.reload();
  await expect(page.locator(".book-card")).toHaveCount(12);
  expect(
    await page
      .locator(".book-grid")
      .evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
      ),
  ).toBe(4);
  await page.getByRole("button", { name: "Mais opções da biblioteca" }).click();
  await page.getByRole("menuitem", { name: "Compartilhar coleção" }).click();
  await expect(
    page.getByRole("button", { name: "Renovar link", exact: true }),
  ).toBeVisible();
  expect(state.shareWrites).toHaveLength(0);
  page.once("dialog", (dialog) => dialog.dismiss());
  await page.getByRole("button", { name: "Renovar link", exact: true }).click();
  expect(state.shareWrites).toHaveLength(0);
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Renovar link", exact: true }).click();
  await expect(
    page.getByRole("textbox", { name: "Link de consulta" }),
  ).toHaveValue(/test-preview-token$/);
  expect(state.shareWrites).toEqual(["POST"]);
  page.once("dialog", (dialog) => dialog.dismiss());
  await page
    .getByRole("button", { name: "Desativar link", exact: true })
    .click();
  expect(state.shareWrites).toEqual(["POST"]);
  page.once("dialog", (dialog) => dialog.accept());
  await page
    .getByRole("button", { name: "Desativar link", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Gerar link de consulta", exact: true }),
  ).toBeVisible();
  expect(state.shareWrites).toEqual(["POST", "DELETE"]);
  await expect(
    page.getByRole("textbox", { name: "Link de consulta" }),
  ).not.toBeVisible();
  await page
    .getByRole("dialog", { name: "Compartilhar coleção", exact: true })
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../.superpowers/compact-catalog-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
  account.id = 3;
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.reload();
  await expect(page.locator(".book-card")).toHaveCount(12);
  expect(
    await page
      .locator(".book-grid")
      .evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
      ),
  ).toBe(7);
  await page.screenshot({
    path: "../.superpowers/compact-catalog-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
});
