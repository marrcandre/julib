import { test, expect } from "@playwright/test";

for (const width of [320, 1280])
  test(`situations, sort preference and detail return ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 850 });
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    const book = {
      id: 58,
      title: "Livro de teste",
      authors: ["Autora"],
      isbn: "",
      publisher: "",
      edition: "",
      year: "",
      language: "",
      page_count: null,
      cover_url: "",
      source: "",
      source_id: "",
      tags: [],
      copies: [],
      available: false,
      is_desired: true,
      can_delete: true,
    };
    const requests: URL[] = [];
    await page.route("**/api/v1/**", (route) => {
      const url = new URL(route.request().url());
      let json: unknown = [];
      if (url.pathname.endsWith("/session"))
        json = {
          user_id: 1,
          name: "Teste",
          technical: false,
          library: "Biblioteca",
          csrf: "test",
          catalog_view: "covers",
          cover_columns: 7,
        };
      else if (url.pathname.endsWith("/books")) {
        requests.push(url);
        json = { items: [book], total: 1, page: 1, page_size: 24 };
      } else if (url.pathname.endsWith("/books/58")) json = book;
      return route.fulfill({ json });
    });
    await page.goto("/livros");
    await expect(
      page.getByRole("heading", { name: "Livros", exact: true }),
    ).toBeVisible();
    await expect(page.getByLabel("Coleção exibida")).toHaveCount(0);
    await expect
      .poll(() => requests.at(-1)?.searchParams.get("order"))
      .toBe("newest");
    await expect
      .poll(() => requests.at(-1)?.searchParams.get("statuses"))
      .toBe("available,loaned");
    await page.getByRole("button", { name: /^Filtros/ }).click();
    await page.screenshot({
      path: `../.superpowers/situations-filters-${width}.png`,
    });
    for (const name of ["Disponíveis", "Emprestados", "Desejados", "Perdidos"])
      await page.getByRole("checkbox", { name, exact: true }).click();
    await page
      .getByRole("button", { name: "Aplicar filtros", exact: true })
      .click();
    await expect
      .poll(() => requests.at(-1)?.searchParams.get("statuses"))
      .toBe("wishlist,lost");
    await page
      .getByRole("button", { name: "Ordenar livros", exact: true })
      .click();
    await page
      .getByRole("combobox", { name: "Ordenação dos livros", exact: true })
      .click();
    await page
      .getByRole("option", { name: "Título: A–Z", exact: true })
      .click();
    await expect
      .poll(() => requests.at(-1)?.searchParams.get("order"))
      .toBe("title_asc");
    const path = new URL(page.url()).search;
    await page
      .getByRole("link", { name: "Abrir Livro de teste", exact: true })
      .click();
    await page
      .getByRole("link", { name: "Voltar ao catálogo", exact: true })
      .click();
    await expect.poll(() => new URL(page.url()).search).toBe(path);
    if (width < 800)
      await page
        .getByRole("button", { name: "Abrir navegação", exact: true })
        .click();
    await page.getByRole("link", { name: "Livros", exact: true }).click();
    await expect
      .poll(() => requests.at(-1)?.searchParams.get("order"))
      .toBe("title_asc");
    await expect(page.locator(".p-drawer")).toHaveCount(0);
    await page.screenshot({
      path: `../.superpowers/situations-${width}.png`,
      animations: "disabled",
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(errors).toEqual([]);
  });
