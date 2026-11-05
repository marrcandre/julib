import { test, expect } from "@playwright/test";

test("catalog supports responsive cards, covers, list and current edit cover", async ({
  page,
}) => {
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
  await page.route("**/api/v1/**", (route) => {
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
      };
    else if (path.endsWith("/books"))
      json = { items: books, total: books.length };
    else if (path.match(/\/books\/\d+$/))
      json = books[Number(path.split("/").pop()) - 1];
    return route.fulfill({ json });
  });
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/livros");
  await expect(page.locator(".book-card")).toHaveCount(6);
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
