import { test, expect } from "@playwright/test";

test("catalog supports responsive cards, covers, list and current edit cover", async ({
  page,
}) => {
  let preferences = { catalog_view: "covers", cover_columns: 7 };
  const queries: string[] = [];
  const books = Array.from({ length: 6 }, (_, i) => ({
    id: i + 1,
    title: `Livro de teste ${i + 1}`,
    authors: ["Autora de teste"],
    isbn: "",
    publisher: "Editora",
    edition: "",
    year: "2025",
    language: "pt",
    cover_url: i === 5 ? "" : "/test-cover.svg",
    source: "",
    source_id: "",
    tags: [],
    attribution_name: "",
    attribution_url: "",
    available: i !== 1,
    copies: [
      {
        id: i + 1,
        book_id: i + 1,
        number: 1,
        state: "active",
        on_loan: i === 1,
        location_id: null,
        acquired_on: "2026-11-01",
      },
    ],
  }));
  await page.route("**/test-cover.svg", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="150"><rect width="100" height="150" fill="#053227"/></svg>',
    }),
  );
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let json: unknown = [];
    if (path.endsWith("/session"))
      json = {
        name: "Teste",
        email: "test@example.com",
        technical: false,
        library: "Teste",
        csrf: "test",
        avatar_url: "",
        ...preferences,
      };
    else if (path.endsWith("/preferences/catalog")) {
      preferences = route.request().postDataJSON();
      json = preferences;
    } else if (path.endsWith("/books")) {
      const query = new URL(route.request().url()).searchParams.get("q") || "";
      queries.push(query);
      if (query === "antigo")
        await new Promise((resolve) => setTimeout(resolve, 1000));
      const items = ["antigo", "recente"].includes(query)
        ? [{ ...books[0], title: "Resultado " + query }]
        : books;
      json = { items, total: items.length };
    } else if (path.match(/\/books\/\d+$/))
      json = books[Number(path.split("/").pop()) - 1];
    return route.fulfill({ json });
  });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/livros");
  await expect(page.locator(".book-card")).toHaveCount(6);
  await expect(
    page.getByRole("button", { name: "Somente capas", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  expect(
    await page
      .locator(".book-grid")
      .evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
      ),
  ).toBe(7);
  await page.screenshot({
    path: "../.superpowers/catalog-default-seven.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("combobox", { name: "Capas por linha no desktop" })
    .click();
  await page.getByRole("option", { name: "9", exact: true }).click();
  await expect.poll(() => preferences.cover_columns).toBe(9);
  await page.reload();
  expect(
    await page
      .locator(".book-grid")
      .evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
      ),
  ).toBe(9);
  const search = page.getByRole("textbox", { name: "Buscar no acervo" });
  await search.fill("a");
  await search.fill("ab");
  await expect.poll(() => queries.at(-1)).toBe("ab");
  expect(queries).not.toContain("a");
  await page.getByRole("button", { name: "Limpar busca" }).click();
  await expect(search).toHaveValue("");
  await expect.poll(() => queries.at(-1)).toBe("");
  const oldResponse = page.waitForResponse(
    (response) => new URL(response.url()).searchParams.get("q") === "antigo",
  );
  const oldRequest = page.waitForRequest(
    (request) => new URL(request.url()).searchParams.get("q") === "antigo",
  );
  await search.fill("antigo");
  await oldRequest;
  await search.fill("recente");
  await expect(
    page.getByRole("button", { name: "Abrir Resultado recente", exact: true }),
  ).toBeVisible();
  await oldResponse;
  await expect(
    page.getByRole("button", { name: "Abrir Resultado recente", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Limpar busca" }).click();
  await expect(page.locator(".book-card")).toHaveCount(6);

  await page.getByRole("button", { name: "Cartões", exact: true }).click();

  expect(
    await page
      .locator(".book-grid")
      .evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
      ),
  ).toBe(5);
  await expect(
    page.locator(".book-title").getByLabel("Emprestado"),
  ).toBeVisible();
  await page.screenshot({
    path: "../.superpowers/catalog-desktop.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 393, height: 852 });
  expect(
    await page
      .locator(".book-grid")
      .evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
      ),
  ).toBe(3);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "../.superpowers/catalog-mobile-cards.png",
    fullPage: true,
    animations: "disabled",
  });
  await page
    .getByRole("button", { name: "Somente capas", exact: true })
    .click();
  await expect(page.locator(".book-info").first()).not.toBeVisible();
  await page.screenshot({
    path: "../.superpowers/catalog-mobile-covers.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Lista", exact: true }).click();
  await expect(page.locator(".book-card--list")).toHaveCount(6);
  await page.screenshot({
    path: "../.superpowers/catalog-mobile-list.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Lista", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await page
    .getByRole("button", { name: "Abrir Livro de teste 1", exact: true })
    .click();
  await expect(
    page.getByRole("dialog").getByRole("img", { name: "Capa do livro" }),
  ).toBeVisible();
  const uploadBox = await page.locator(".cover-upload").boundingBox();
  const coverBox = await page
    .getByRole("dialog")
    .getByRole("img", { name: "Capa do livro" })
    .boundingBox();
  expect(uploadBox!.x + uploadBox!.width).toBeLessThanOrEqual(coverBox!.x);
  await page.screenshot({
    path: "../.superpowers/catalog-detail-cover.png",
    fullPage: false,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "Editar dados", exact: true }).click();
  const editor = page.getByRole("dialog", {
    name: "Editar livro",
    exact: true,
  });
  await expect(editor.getByRole("img", { name: "Capa atual" })).toBeVisible();
  await page.screenshot({
    path: "../.superpowers/catalog-editor.png",
    fullPage: false,
    animations: "disabled",
  });
});
