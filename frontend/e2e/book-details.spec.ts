import { test, expect } from "@playwright/test";

test("book has a private standalone URL, local cover draft and atomic edit with retry", async ({
  page,
  context,
}) => {
  const book = {
    id: 1,
    title: "1984",
    authors: ["George Orwell"],
    isbn: "9788535914849",
    publisher: "Companhia das Letras",
    edition: "1ª edição",
    year: "2009",
    language: "Português",
    page_count: 416,
    cover_url: "",
    source: "",
    source_id: "",
    tags: [],
    copies: [
      {
        id: 1,
        book_id: 1,
        number: 47,
        location_id: 1,
        acquired_on: "2020-08-15",
        state: "active",
        on_loan: false,
      },
    ],
    available: true,
    is_desired: false,
    can_delete: true,
    attribution_name: "",
    attribution_url: "",
  };
  let uploads = 0,
    writes = 0,
    fail = true;
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    let json: unknown = [];
    if (url.pathname.endsWith("/books/9999"))
      return route.fulfill({ status: 404, json: { detail: "Not Found" } });
    if (url.pathname.endsWith("/session"))
      json = {
        user_id: 1,
        name: "Teste",
        email: "test@example.com",
        technical: false,
        library: "Casa",
        csrf: "test",
        avatar_url: "",
        catalog_view: "covers",
        cover_columns: 7,
      };
    else if (url.pathname.endsWith("/locations"))
      json = [{ id: 1, name: "Escritório (Apto)", parent_id: null }];
    else if (url.pathname.endsWith("/books/1")) {
      if (route.request().method() === "PUT") {
        writes++;
        const data = route.request().postDataJSON();
        if (fail) {
          fail = false;
          return route.fulfill({
            status: 400,
            json: { detail: "Confira o ISBN." },
          });
        }
        Object.assign(book, data, {
          cover_url: "https://res.cloudinary.com/test/new.png",
        });
      }
      json = book;
    } else if (url.pathname.endsWith("/media/sign"))
      json = {
        cloud_name: "test",
        api_key: "test",
        signature: "test",
        timestamp: "1",
      };
    return route.fulfill({ json });
  });
  await page.route(
    "https://api.cloudinary.com/v1_1/test/image/upload",
    (route) => {
      uploads++;
      return route.fulfill({
        json: {
          public_id: "julib/1/new",
          secure_url: "https://res.cloudinary.com/test/new.png",
        },
      });
    },
  );
  await page.route("https://res.cloudinary.com/**", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="60" height="90"><rect width="60" height="90" fill="#053227"/></svg>',
    }),
  );
  await page.goto("/livros/1");
  await expect(
    page.getByRole("heading", { name: "1984", exact: true }),
  ).toBeVisible();
  await expect(page.getByText("416", { exact: true })).toBeVisible();
  await expect(page.getByText("9788535914849", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Histórico", exact: true }).click();
  await expect(
    page.getByText("Nenhum empréstimo registrado para este exemplar."),
  ).toBeVisible();
  const emptyCover = page.getByRole("button", {
    name: "Editar livro sem capa",
  });
  await expect(emptyCover.locator(".book-cover-pencil")).toBeVisible();
  await expect(emptyCover).toHaveAttribute("title", "Editar livro");
  await page.evaluate(() => window.scrollTo(0, 0));
  const initialCover = await emptyCover.boundingBox();
  await emptyCover.click();
  const editingCover = await page.locator(".book-cover-picker").boundingBox();
  expect(editingCover).toEqual(initialCover);
  const file = {
    name: "capa.png",
    mimeType: "image/png",
    buffer: Buffer.from(
      "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l2kAAAAASUVORK5CYII=",
      "base64",
    ),
  };
  await page.getByLabel("Título *", { exact: true }).fill("1984 revisado");
  const coverTrigger = page
    .getByRole("button", { name: "Trocar capa", exact: true })
    .filter({ has: page.locator(".book-detail-placeholder") });
  const chooserPromise = page.waitForEvent("filechooser");
  await coverTrigger.click();
  await (await chooserPromise).setFiles(file);
  await expect(
    page.getByRole("img", { name: "Prévia da capa selecionada" }),
  ).toBeVisible();
  const previewTrigger = page
    .getByRole("button", { name: "Trocar capa", exact: true })
    .filter({
      has: page.getByRole("img", { name: "Prévia da capa selecionada" }),
    });
  await previewTrigger.focus();
  const keyboardChooser = page.waitForEvent("filechooser");
  await page.keyboard.press("Enter");
  await (await keyboardChooser).setFiles(file);
  await page.setViewportSize({ width: 320, height: 852 });
  await expect(previewTrigger.locator(".book-cover-pencil")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Trocar capa", exact: true }),
  ).toHaveCount(2);
  await previewTrigger.focus();
  const spaceChooser = page.waitForEvent("filechooser");
  await page.keyboard.press("Space");
  await (await spaceChooser).setFiles(file);
  await page.screenshot({
    path: "/tmp/julib-cover-mobile.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.screenshot({
    path: "/tmp/julib-cover-desktop.png",
    fullPage: true,
  });
  expect(uploads).toBe(0);
  expect(writes).toBe(0);
  page.once("dialog", (dialog) => dialog.dismiss());
  await page
    .getByRole("link", { name: "Voltar ao catálogo", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Editar livro", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Cancelar", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "1984", exact: true }),
  ).toBeVisible();
  expect(uploads).toBe(0);
  await page.getByRole("button", { name: "Editar livro sem capa" }).click();
  await page.getByLabel("Título *", { exact: true }).fill("1984 revisado");
  await page.locator("input[type=file]").setInputFiles(file);
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .first()
    .click();
  await expect(page.getByRole("alert")).toContainText("Confira o ISBN.");
  expect(uploads).toBe(1);
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "1984 revisado", exact: true }),
  ).toBeVisible();
  expect(uploads).toBe(1);
  expect(writes).toBe(2);
  expect(page.url()).toContain("/livros/1");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "1984 revisado", exact: true }),
  ).toBeVisible();
  await page.setViewportSize({ width: 320, height: 852 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  const detailCover = page.getByRole("button", {
    name: "Editar livro pela capa",
  });
  await expect(detailCover.locator(".book-cover-pencil")).toBeVisible();
  await detailCover.focus();
  await expect(detailCover).toHaveCSS("outline-style", "solid");
  await page.screenshot({
    path: "/tmp/julib-detail-cover-mobile.png",
    fullPage: true,
  });
  const mobileCover = await detailCover.boundingBox();
  await page.keyboard.press("Enter");
  expect(await page.locator(".book-cover-picker").boundingBox()).toEqual(
    mobileCover,
  );
  await expect(
    page.getByRole("heading", { name: "Editar livro", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Cancelar", exact: true })
    .first()
    .click();
  await page.goto("/livros/9999");
  await expect(page.getByRole("alert")).toContainText(
    "Livro não encontrado ou sem acesso",
  );
  await expect(
    page.getByRole("heading", { name: "1984 revisado", exact: true }),
  ).not.toBeVisible();
});

test("catalog links open in another tab and return with filters, page and scroll", async ({
  page,
  context,
}) => {
  const item = (id: number) => ({
    id,
    title: "Livro " + id,
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
    attribution_name: "",
    attribution_url: "",
  });
  await context.route("**/api/v1/**", (route) => {
    const url = new URL(route.request().url());
    let json: unknown = [];
    if (url.pathname.endsWith("/session"))
      json = {
        user_id: 1,
        name: "Teste",
        email: "test@example.com",
        technical: false,
        library: "Casa",
        csrf: "test",
        avatar_url: "",
        catalog_view: "covers",
        cover_columns: 7,
      };
    else if (url.pathname.endsWith("/books"))
      json = {
        items: Array.from({ length: 24 }, (_, i) => item(i + 25)),
        total: 48,
      };
    else if (url.pathname.endsWith("/tags"))
      json = [{ id: 1, name: "Literatura" }];
    else if (/\/books\/\d+$/.test(url.pathname))
      json = item(Number(url.pathname.split("/").at(-1)));
    return route.fulfill({ json });
  });
  await page.setViewportSize({ width: 393, height: 600 });
  await page.goto("/livros?q=Livro&pagina=2&tag=1&lista=desejados");
  const link = page.getByRole("link", { name: "Abrir Livro 33", exact: true });
  await expect(link).toHaveAttribute("href", /\/livros\/33\?voltar=/);
  await link.scrollIntoViewIfNeeded();
  const [other] = await Promise.all([
    context.waitForEvent("page"),
    link.click({ modifiers: ["ControlOrMeta"] }),
  ]);
  await expect(
    other.getByRole("heading", { name: "Livro 33", exact: true }),
  ).toBeVisible();
  await other.reload();
  await expect(
    other.getByRole("heading", { name: "Livro 33", exact: true }),
  ).toBeVisible();
  await other.close();
  await expect(page).toHaveURL(/situacao=wishlist/);
  await link.scrollIntoViewIfNeeded();
  const scroll = await page.evaluate(() => window.scrollY);
  await link.click();
  await expect(
    page.getByRole("heading", { name: "Livro 33", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Voltar ao catálogo", exact: true })
    .click();
  await expect(page.getByLabel("Buscar livros")).toHaveValue("Livro");
  await expect(
    page.locator(".catalog-pagination [aria-current=page]"),
  ).toHaveText("2");
  await expect(
    page.getByRole("button", { name: "Remover filtro Literatura" }),
  ).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => window.scrollY))
    .toBeCloseTo(scroll, 0);
});

test("book and copy editing preserve returned loan history on the real API", async ({
  page,
  context,
}) => {
  const { readFileSync } = await import("node:fs");
  await context.addCookies([
    JSON.parse(readFileSync("../.superpowers/e2e-session.json", "utf8")),
  ]);
  const session = await (await page.request.get("/api/v1/session")).json();
  const headers = { "X-CSRFToken": session.csrf };
  const title = "Detalhes E2E " + Date.now();
  const registered = await page.request.post("/api/v1/registrations", {
    headers,
    data: {
      key: crypto.randomUUID(),
      book: { title, authors: ["Autora de teste"] },
    },
  });
  expect(registered.ok()).toBe(true);
  const { book_id, copy_id } = await registered.json();
  const locationName = "Local " + Date.now();
  const located = await page.request.post("/api/v1/locations", {
    headers,
    data: { name: locationName },
  });
  const location = await located.json();
  await page.goto("/livros/" + book_id);
  await page.getByRole("button", { name: "Editar livro sem capa" }).click();
  await expect(
    page.getByRole("heading", { name: "Editar livro", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Editora", { exact: true }).fill("Editora de teste");
  await page.getByRole("spinbutton", { name: "Número de páginas" }).fill("321");
  await page
    .getByRole("button", { name: "Salvar alterações", exact: true })
    .first()
    .click();
  await expect(
    page.getByText("Editora de teste", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("321", { exact: true })).toBeVisible();
  await page
    .getByRole("button", { name: "Editar exemplar", exact: true })
    .click();
  await page
    .getByRole("combobox", { name: "Sem localização", exact: true })
    .click();
  await page.getByRole("option", { name: locationName, exact: true }).click();
  await page
    .getByLabel("Data de aquisição", { exact: true })
    .fill("2019-05-20");
  await page
    .getByRole("button", { name: "Salvar exemplar", exact: true })
    .click();
  await expect(
    page.locator(".book-copy-info dd").filter({ hasText: locationName }),
  ).toBeVisible();
  const stored = await (
    await page.request.get("/api/v1/books/" + book_id)
  ).json();
  expect(stored.copies[0].acquired_on).toBe("2019-05-20");
  expect(stored.copies[0].location_id).toBe(location.id);
  const person = await (
    await page.request.post("/api/v1/people", {
      headers,
      data: { name: "Pessoa de teste", phone: "47999999999" },
    })
  ).json();
  const loan = await (
    await page.request.post("/api/v1/loans", {
      headers,
      data: { copy_id, person_id: person.id },
    })
  ).json();
  const returned = await page.request.post(
    "/api/v1/loans/" + loan.id + "/return",
    { headers, data: { returned_on: new Date().toISOString().slice(0, 10) } },
  );
  expect(returned.ok()).toBe(true);
  await page.reload();
  await page.getByRole("button", { name: "Histórico", exact: true }).click();
  await expect(
    page.getByText("Pessoa de teste", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Mais ações do livro", exact: true })
    .click();
  await expect(
    page.getByRole("menuitem", {
      name: "Exclusão bloqueada: há histórico de empréstimos",
      exact: true,
    }),
  ).toHaveAttribute("aria-disabled", "true");
  expect(
    (
      await page.request.delete("/api/v1/books/" + book_id, { headers })
    ).status(),
  ).toBe(400);
});

test("signed-out book deep link keeps its destination through Google login", async ({
  page,
}) => {
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({ status: 401, json: { detail: "Unauthorized" } }),
  );
  await page.goto("/livros/42");
  await expect(
    page.getByRole("link", { name: "Entrar com Google", exact: true }),
  ).toHaveAttribute("href", "/accounts/google/login/?next=%2Flivros%2F42");
});
