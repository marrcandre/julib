import { test, expect } from "@playwright/test";
test("uploaded cover has no optional badge and Google data credit stays with bibliographic fields", async ({
  page,
}) => {
  const book = {
    id: 313,
    title: "Livro com capa própria",
    authors: ["Autora"],
    isbn: "",
    publisher: "Editora",
    edition: "",
    year: "2020",
    language: "pt",
    page_count: 100,
    cover_url: "/own-cover.svg",
    source: "openlibrary",
    source_id: "/works/OL1W",
    tags: [],
    copies: [],
    available: false,
    is_desired: false,
    can_delete: true,
    attribution_name: "",
    attribution_url: "",
    metadata_attribution_name: "",
    metadata_attribution_url: "",
  };
  await page.route("**/own-cover.svg", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="60" height="90"><rect width="60" height="90" fill="#053227"/></svg>',
    }),
  );
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    const json = path.endsWith("/session")
      ? {
          user_id: 1,
          name: "Teste",
          email: "test@example.com",
          library: "Casa",
          technical: false,
          csrf: "test",
          avatar_url: "",
        }
      : path.endsWith("/books/313")
        ? book
        : [];
    return route.fulfill({ json });
  });
  await page.goto("/livros/313");
  await expect(
    page.getByRole("img", { name: "Capa do livro", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".source-attribution")).toHaveCount(0);
  await page.getByRole("button", { name: "Editar livro", exact: true }).click();
  await expect(page.locator(".source-attribution")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Cancelar", exact: true })
    .first()
    .click();
  book.source = "google";
  book.source_id = "metadata";
  book.metadata_attribution_name = "Google Books";
  book.metadata_attribution_url = "https://books.google.com/books?id=metadata";
  await page.reload();
  await expect(
    page.getByRole("link", {
      name: "Fonte dos dados: Google Books",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.locator(".book-detail-figure .source-attribution"),
  ).toHaveCount(0);
  await expect(
    page.locator(".book-detail-facts .source-attribution"),
  ).toHaveCount(1);
  await page.setViewportSize({ width: 320, height: 852 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
