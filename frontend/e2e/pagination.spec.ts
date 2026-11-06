import { test, expect } from "@playwright/test";

for (const width of [393, 1280])
  test(`numbered pages and per-device rows ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    let preferences = { catalog_view: "covers", cover_columns: 7 };
    const queries: URL[] = [];
    const book = (id: number) => ({
      id,
      title: `Livro ${id}`,
      authors: ["Autora"],
      isbn: "",
      publisher: "",
      edition: "",
      year: "2020",
      language: "pt",
      page_count: null,
      cover_url: "",
      source: "",
      source_id: "",
      tags: [],
      copies: [],
      available: true,
      is_desired: false,
      can_delete: true,
    });
    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      let json: unknown = [];
      if (url.pathname.endsWith("/session"))
        json = {
          user_id: 1,
          name: "Teste",
          technical: false,
          library: "Casa",
          csrf: "test",
          ...preferences,
        };
      else if (url.pathname.endsWith("/preferences/catalog")) {
        preferences = route.request().postDataJSON();
        json = preferences;
      } else if (url.pathname.endsWith("/books")) {
        queries.push(url);
        const total = url.searchParams.get("q") === "um" ? 1 : 322;
        const size = Number(url.searchParams.get("page_size") || 24),
          n = Math.min(
            Number(url.searchParams.get("page") || 1),
            Math.ceil(total / size),
          );
        const offset = (n - 1) * size;
        json = {
          items: Array.from(
            { length: Math.min(size, total - offset) },
            (_, i) => book(offset + i + 1),
          ),
          total,
          page: n,
          page_size: size,
        };
      } else if (/\/books\/\d+$/.test(url.pathname))
        json = book(Number(url.pathname.split("/").at(-1)));
      return route.fulfill({ json });
    });
    await page.goto("/livros?q=Livro&ordem=title_asc");
    const initial = width < 800 ? 20 : 35;
    await expect(page.locator(".catalog-item")).toHaveCount(initial);
    await expect(
      page.getByText(`1–${initial} de 322 livros`, { exact: true }),
    ).toBeVisible();
    const contrast = await page
      .locator(".catalog-page-links a")
      .first()
      .evaluate((el) => {
        const luminance = (color: string) => {
          const values = color
            .match(/[\d.]+/g)!
            .slice(0, 3)
            .map(Number)
            .map((v) => {
              const c = v / 255;
              return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
            });
          return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
        };
        const ink = luminance(getComputedStyle(el).color),
          bg = luminance(
            getComputedStyle(document.documentElement).backgroundColor,
          );
        return (Math.max(ink, bg) + 0.05) / (Math.min(ink, bg) + 0.05);
      });
    expect(contrast).toBeGreaterThanOrEqual(4.5);
    const last = Math.ceil(322 / initial);
    await page
      .getByRole("link", { name: `Ir para página ${last}`, exact: true })
      .click();
    await expect(
      page.locator('.catalog-pagination [aria-current="page"]'),
    ).toHaveText(String(last));
    await expect(
      page.getByLabel("Próxima página", { exact: true }),
    ).toHaveAttribute("aria-disabled", "true");
    await expect
      .poll(() => queries.at(-1)?.searchParams.get("q"))
      .toBe("Livro");
    await page
      .getByRole("link", { name: "Ir para página 1", exact: true })
      .click();
    await page.goBack();
    await expect(
      page.locator('.catalog-pagination [aria-current="page"]'),
    ).toHaveText(String(last));
    await page.goForward();
    await expect(
      page.locator('.catalog-pagination [aria-current="page"]'),
    ).toHaveText("1");
    await page.locator(".catalog-pagination").screenshot({
      path: `../.superpowers/pager-${width}.png`,
      animations: "disabled",
    });
    const url = new URL(page.url()).search;
    await page
      .getByRole("link", { name: "Abrir Livro 1", exact: true })
      .click();
    await page
      .getByRole("link", { name: "Voltar ao catálogo", exact: true })
      .click();
    await expect.poll(() => new URL(page.url()).search).toBe(url);
    await page
      .getByRole("button", { name: "Visualização dos livros", exact: true })
      .click();
    await page
      .getByRole("combobox", { name: "Linhas por página", exact: true })
      .click();
    await page.getByRole("option", { name: "8", exact: true }).click();
    const expanded = width < 800 ? 32 : 56;
    await expect(page.locator(".catalog-item")).toHaveCount(expanded);
    await page
      .getByRole("dialog", { name: "Visualização", exact: true })
      .getByRole("button", { name: "Close", exact: true })
      .click();
    await page.reload();
    await expect(page.locator(".catalog-item")).toHaveCount(expanded);
    await page
      .getByRole("button", { name: "Visualização dos livros", exact: true })
      .click();
    await page.getByRole("button", { name: "Cartões", exact: true }).click();
    const cards = width < 800 ? 24 : 40;
    await expect(page.locator(".catalog-item")).toHaveCount(cards);
    await expect
      .poll(() =>
        page
          .locator(".book-grid")
          .evaluate(
            (el) => getComputedStyle(el).gridTemplateColumns.split(" ").length,
          ),
      )
      .toBe(width < 800 ? 3 : 5);
    await page.getByRole("button", { name: "Lista", exact: true }).click();
    await page
      .getByRole("combobox", { name: "Livros por página", exact: true })
      .click();
    await page.getByRole("option", { name: "48", exact: true }).click();
    await expect(page.locator(".catalog-item")).toHaveCount(48);
    await page
      .getByRole("dialog", { name: "Visualização", exact: true })
      .getByRole("button", { name: "Close", exact: true })
      .click();
    await page
      .getByRole("link", { name: "Ir para página 2", exact: true })
      .click();
    await page
      .getByRole("textbox", { name: "Buscar livros", exact: true })
      .fill("um");
    await expect(page.locator(".catalog-item")).toHaveCount(1);
    await expect(
      page.getByRole("navigation", {
        name: "Paginação dos livros",
        exact: true,
      }),
    ).toHaveCount(0);
    await expect(
      page.getByText("1–1 de 1 livro", { exact: true }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Limpar busca", exact: true })
      .click();
    await expect(page.locator(".catalog-item")).toHaveCount(48);
    await page.screenshot({
      path: `../.superpowers/pagination-${width}.png`,
      animations: "disabled",
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(errors).toEqual([]);
  });

test("density and viewport resize keep a reference book on the recalculated page", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  const book = (id: number) => ({
    id,
    title: `Livro ${id}`,
    authors: ["Autora"],
    isbn: "",
    publisher: "",
    edition: "",
    year: "",
    language: "",
    cover_url: "",
    tags: [],
    copies: [],
    available: true,
  });
  await page.route("**/api/v1/**", (route) => {
    const u = new URL(route.request().url());
    let json: unknown = [];
    if (u.pathname.endsWith("/session"))
      json = {
        user_id: 2,
        name: "Teste",
        technical: false,
        library: "Casa",
        csrf: "test",
        catalog_view: "covers",
        cover_columns: 7,
      };
    else if (u.pathname.endsWith("/books")) {
      const size = Number(u.searchParams.get("page_size")),
        n = Number(u.searchParams.get("page"));
      json = {
        items: Array.from({ length: size }, (_, i) =>
          book((n - 1) * size + i + 1),
        ),
        total: 1000,
        page: n,
        page_size: size,
      };
    } else if (u.pathname.endsWith("/preferences/catalog"))
      json = route.request().postDataJSON();
    return route.fulfill({ json });
  });
  await page.goto("/livros?pagina=3&por_pagina=35");
  await expect(
    page.getByRole("link", { name: "Abrir Livro 71", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Visualização dos livros", exact: true })
    .click();
  await page
    .getByRole("slider", { name: "Livros por linha", exact: true })
    .fill("10");
  await expect(page.locator(".catalog-item")).toHaveCount(50);
  await expect(
    page.locator('.catalog-pagination [aria-current="page"]'),
  ).toHaveText("2");
  await expect(
    page.getByRole("link", { name: "Abrir Livro 71", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Cartões", exact: true }).click();
  await page
    .getByRole("dialog", { name: "Visualização", exact: true })
    .getByRole("button", { name: "Close", exact: true })
    .click();
  const first = Number(
    await page.locator(".catalog-item").first().getAttribute("data-book-id"),
  );
  await page.setViewportSize({ width: 393, height: 900 });
  await expect(page.locator(".catalog-item")).toHaveCount(15);
  await expect(
    page.getByRole("link", { name: `Abrir Livro ${first}`, exact: true }),
  ).toBeVisible();
});
