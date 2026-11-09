import { test, expect } from "@playwright/test";
for (const width of [393, 1280])
  test(`enriched registration and compact catalog credits ${width}`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    const base = {
      title: "1984",
      authors: ["George Orwell"],
      isbn: "9788535914849",
      source: "google",
      source_id: "google-volume",
      publisher: "",
      year: "",
      language: "pt",
      page_count: null,
      cover_url: "",
      provenance: { title: { source: "google", source_id: "google-volume" } },
    };
    const enriched = {
      ...base,
      publisher: "Companhia",
      year: "2009",
      page_count: 416,
      cover_url: "https://covers.openlibrary.org/b/id/999-L.jpg?default=false",
      provenance: {
        ...base.provenance,
        page_count: { source: "openlibrary", source_id: "ISBN:9788535914849" },
        cover_url: {
          source: "openlibrary",
          source_id: "ISBN:9788535914849",
          url: "https://covers.openlibrary.org/b/id/999-L.jpg?default=false",
        },
      },
      metadata_attribution_name: "Google Books",
      metadata_attribution_url:
        "https://books.google.com/books?id=google-volume",
      attribution_name: "",
      attribution_url: "",
    };
    let saved = false,
      payload: Record<string, any> | undefined;
    await page.route("**/b/id/999-L.jpg*", (route) =>
      route.fulfill({
        contentType: "image/svg+xml",
        body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="150"><rect width="100" height="150" fill="#074534"/></svg>',
      }),
    );
    await page.route("**/api/v1/**", (route) => {
      const url = new URL(route.request().url());
      let json: unknown = [];
      if (url.pathname.endsWith("/session"))
        json = {
          user_id: 1,
          name: "Teste",
          library: "Casa",
          technical: false,
          csrf: "test",
          catalog_view: "covers",
          cover_columns: 7,
        };
      else if (url.pathname.endsWith("/search/enrich")) json = enriched;
      else if (url.pathname.endsWith("/search")) json = [base];
      else if (url.pathname.endsWith("/registrations")) {
        payload = route.request().postDataJSON();
        saved = true;
        json = { book_id: 58, copy_id: 1, number: 1 };
      } else if (url.pathname.endsWith("/books"))
        json = {
          items: saved
            ? [
                {
                  ...enriched,
                  id: 58,
                  tags: [],
                  copies: [],
                  available: true,
                  is_desired: false,
                  can_delete: true,
                },
              ]
            : [],
          total: saved ? 1 : 0,
        };
      else if (url.pathname.endsWith("/books/58"))
        json = {
          ...enriched,
          id: 58,
          tags: [],
          copies: [],
          available: true,
          is_desired: false,
          can_delete: true,
        };
      return route.fulfill({ json });
    });
    await page.goto("/livros");
    await page
      .getByRole("button", { name: "Adicionar livro", exact: true })
      .click();
    await page
      .getByRole("menuitem", { name: "Buscar livro", exact: true })
      .click();
    await page
      .getByRole("textbox", { name: "Buscar em APIs", exact: true })
      .fill("1984");
    await page
      .getByRole("button", { name: "Buscar dados", exact: true })
      .click();
    await page.getByRole("button", { name: /1984.*George Orwell/ }).click();
    await expect(
      page.getByRole("spinbutton", { name: "Número de páginas" }),
    ).toHaveValue("416");
    await expect(
      page.getByRole("img", { name: "Capa atual", exact: true }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Salvar", exact: true }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(payload?.book.provenance.page_count.source).toBe("openlibrary");
    await expect(page.locator(".catalog-item .source-attribution")).toHaveCount(
      0,
    );
    await expect(page.locator(".book-credit-compact a")).toHaveCount(1);
    await expect(page.locator(".catalog-google-credit img")).toHaveCount(1);
    await expect(
      page.getByText("Dados bibliográficos:", { exact: true }),
    ).toHaveCount(0);
    await page.screenshot({
      path: `../.superpowers/enriched-catalog-${width}.png`,
      animations: "disabled",
    });
    await page.getByRole("link", { name: "Abrir 1984", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Fontes dos dados", exact: true }),
    ).toBeVisible();
    await expect(page.locator(".book-source-details")).toContainText(
      "Open Library",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });

test("late enrichment never overwrites a manual draft", async ({ page }) => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => (release = resolve));
  const candidate = {
    title: "Título inicial",
    authors: ["Autor"],
    isbn: "9788535914849",
    source: "google",
    source_id: "test",
  };
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let json: unknown = [];
    if (path.endsWith("/session"))
      json = {
        user_id: 1,
        name: "Teste",
        library: "Casa",
        technical: false,
        csrf: "test",
      };
    else if (path.endsWith("/books")) json = { items: [], total: 0 };
    else if (path.endsWith("/search")) json = [candidate];
    else if (path.endsWith("/search/enrich")) {
      await gate;
      json = { ...candidate, title: "Título remoto", publisher: "Remoto" };
    }
    return route.fulfill({ json });
  });
  await page.goto("/livros");
  await page
    .getByRole("button", { name: "Adicionar livro", exact: true })
    .click();
  await page
    .getByRole("menuitem", { name: "Buscar livro", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "Buscar em APIs", exact: true })
    .fill("Livro");
  await page.getByRole("button", { name: "Buscar dados", exact: true }).click();
  await page.getByRole("button", { name: /Título inicial/ }).click();
  await page.getByLabel("Título *", { exact: true }).fill("Minha correção");
  release();
  await expect(
    page.getByText("Complementando dados e procurando capa…"),
  ).toHaveCount(0);
  await expect(page.getByLabel("Título *", { exact: true })).toHaveValue(
    "Minha correção",
  );
  await expect(page.getByLabel("Editora", { exact: true })).toHaveValue("");
});
