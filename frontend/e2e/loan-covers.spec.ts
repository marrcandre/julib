import { test, expect } from "@playwright/test";

test("loan covers appear in loans with safe missing-image fallback", async ({
  page,
}) => {
  const base = {
    id: 1,
    copy_id: 1,
    copy_number: 1,
    title: "Livro com capa",
    person_id: 1,
    person_name: "Pessoa de teste",
    started_on: "2026-11-01",
    due_on: "2026-12-01",
    returned_on: null,
    state: "open",
    overdue: false,
    cover_url: "/loan-cover.svg",
    attribution_name: "Open Library",
    attribution_url: "https://openlibrary.org",
  };
  const loans = [
    base,
    {
      ...base,
      id: 2,
      title: "Sem imagem",
      cover_url: "",
      attribution_name: "",
      attribution_url: "",
    },
    {
      ...base,
      id: 3,
      title: "Imagem indisponível",
      cover_url: "/missing-cover.png",
      attribution_name: "",
      attribution_url: "",
    },
  ];
  await page.route("**/loan-cover.svg", (route) =>
    route.fulfill({
      contentType: "image/svg+xml",
      body: '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="150"><rect width="100" height="150" fill="#053227"/></svg>',
    }),
  );
  await page.route("**/missing-cover.png", (route) =>
    route.fulfill({ status: 404 }),
  );
  const requestedPaths: string[] = [];
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    requestedPaths.push(path);
    const json = path.endsWith("/session")
      ? {
          user_id: 1,
          name: "Teste",
          email: "test@example.com",
          technical: false,
          library: "Teste",
          csrf: "test",
          avatar_url: "",
        }
      : path.endsWith("/loans")
        ? loans
        : [];
    return route.fulfill({ json });
  });
  for (const width of [1280, 393]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/emprestimos");
    await expect(
      page.getByRole("img", { name: "Capa de Livro com capa", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("img", { name: "Sem capa: Sem imagem", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("img", {
        name: "Sem capa: Imagem indisponível",
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("link", { name: "Fonte: Open Library" }),
    ).not.toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    expect(requestedPaths.some((path) => path.endsWith("/dashboard"))).toBe(
      false,
    );
    await page.screenshot({
      path: `../.superpowers/loans-${width}-page.png`,
      fullPage: true,
      animations: "disabled",
    });
  }
});
