import { test, expect } from "@playwright/test";

test("creation invite removes its token before prepare and creates an admin library", async ({
  page,
}) => {
  let urlAtPrepare = "";
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({
      json: {
        user_id: 40,
        name: "Convidada",
        email: "convidada@example.com",
        catalog_view: "covers",
        cover_columns: 7,
        avatar_url: "",
        technical: false,
        can_create_libraries: false,
        libraries: [],
        library: null,
        csrf: "csrf-test",
      },
    }),
  );
  await page.route("**/api/v1/csrf", (route) => route.fulfill({ json: { csrf: "csrf-test" } }));
  await page.route("**/api/v1/library-creation-invites/prepare", async (route) => {
    urlAtPrepare = page.url();
    await route.fulfill({ json: { pending: true, email: "", expires_at: "2026-11-24T12:00:00Z" } });
  });
  await page.route("**/api/v1/libraries/from-invite", async (route) => {
    await route.fulfill({ json: { id: 77, name: "Biblioteca E2E", role: "admin" } });
  });

  await page.goto("/convites/criar#creation-secret-for-test");
  await expect(page.getByRole("heading", { name: "Crie sua biblioteca" })).toBeVisible();
  expect(urlAtPrepare).not.toContain("creation-secret-for-test");
  await expect(page).toHaveURL(/\/convites\/criar$/);
  await page.getByLabel("Nome da biblioteca").fill("Biblioteca E2E");
  await page.getByRole("button", { name: "Criar biblioteca" }).click();

  await expect(page).toHaveURL(/\/bibliotecas\/77\/livros(?:\?.*)?$/);
  await expect(page).toHaveTitle("Livros | Biblioteca E2E");
});
