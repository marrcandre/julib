import { test, expect, type Page } from "@playwright/test";

async function setMode(page: Page, name: string) {
  await page
    .getByRole("button", { name: "Visualização dos livros", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Visualização",
    exact: true,
  });
  await dialog.getByRole("button", { name, exact: true }).click();
  await dialog.getByRole("button", { name: "Close", exact: true }).click();
}
async function setColumns(page: Page, count: number) {
  await page
    .getByRole("button", { name: "Visualização dos livros", exact: true })
    .click();
  const slider = page.getByRole("slider", { name: "Livros por linha" });
  await slider.focus();
  await slider.press(count === 3 ? "Home" : "End");
  if (count === 9) await slider.press("ArrowLeft");
  await expect(slider).toHaveValue(String(count));
  await page
    .getByRole("dialog", { name: "Visualização", exact: true })
    .getByRole("button", { name: "Close", exact: true })
    .click();
}

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
    page_count: 320,
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
        user_id: 1,
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
  await expect(page.locator(".cover-status")).toHaveCount(1);
  await expect(page.locator(".cover-status")).toHaveAttribute(
    "aria-label",
    "Emprestado",
  );
  await expect(page.locator(".book-card--covers")).toHaveCount(6);
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
  await setColumns(page, 9);
  expect(preferences.cover_columns).toBe(7);
  await page.reload();
  expect(
    await page
      .locator(".book-grid")
      .evaluate(
        (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
      ),
  ).toBe(9);
  await expect(
    page.getByRole("button", { name: "Somente capas", exact: true }),
  ).not.toBeVisible();
  const search = page.getByRole("textbox", { name: "Buscar livros" });
  await page.clock.install();
  await page.clock.pauseAt(new Date());
  await search.fill("a");
  await search.fill("ab");
  await page.clock.fastForward(299);
  expect(queries).not.toContain("ab");
  await page.clock.fastForward(1);
  await expect.poll(() => queries.at(-1)).toBe("ab");
  await page.clock.resume();
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
    page.getByRole("link", { name: "Abrir Resultado recente", exact: true }),
  ).toBeVisible();
  await oldResponse;
  await expect(
    page.getByRole("link", { name: "Abrir Resultado recente", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Limpar busca" }).click();
  await expect(page.locator(".book-card")).toHaveCount(6);
  await expect(page.locator(".cover-status")).toHaveCount(1);
  await expect(page.locator(".cover-status")).toHaveAttribute(
    "aria-label",
    "Emprestado",
  );

  await setMode(page, "Cartões");

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
  await setMode(page, "Somente capas");
  await expect(page.locator(".book-info").first()).not.toBeVisible();
  for (const columns of [3, 10]) {
    await setColumns(page, columns);
    expect(preferences.cover_columns).toBe(7);
    expect(
      await page
        .locator(".book-grid")
        .evaluate(
          (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
        ),
    ).toBe(columns);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  }

  await page.screenshot({
    path: "../.superpowers/catalog-mobile-covers.png",
    fullPage: true,
    animations: "disabled",
  });
  await setMode(page, "Lista");
  await expect.poll(() => preferences.catalog_view).toBe("list");
  await expect(page.locator(".book-card--list")).toHaveCount(6);
  await page.screenshot({
    path: "../.superpowers/catalog-mobile-list.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.reload();
  await expect(page.locator(".book-card--list")).toHaveCount(6);
  await page
    .getByRole("link", { name: "Abrir Livro de teste 1", exact: true })
    .click();
  await expect(page).toHaveURL(/\/livros\/1/);
  await expect(
    page.getByRole("img", { name: "Capa do livro", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("320", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Trocar capa", exact: true }),
  ).not.toBeVisible();
  await page.getByRole("button", { name: "Editar livro pela capa" }).click();
  await expect(
    page
      .getByRole("button", { name: "Salvar alterações", exact: true })
      .first(),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Capa atual", exact: true }),
  ).toBeVisible();
  await expect(
    page
      .locator(".book-cover-controls")
      .getByRole("button", { name: "Trocar capa", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("spinbutton", { name: "Número de páginas" }),
  ).toHaveValue("320");
  await page.screenshot({
    path: "../.superpowers/catalog-editor.png",
    fullPage: true,
    animations: "disabled",
  });
});
