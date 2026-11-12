import { test, expect } from "@playwright/test";

test("technical account updates shared library name and reactive title", async ({
  page,
}) => {
  let currentName = "Casa";
  let sessionCalls = 0;
  await page.route("**/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/session")) {
      sessionCalls++;
      return route.fulfill({
        json: {
          user_id: 1,
          name: "Marco",
          email: "marco@example.com",
          technical: true,
          library: currentName,
          csrf: "test",
          avatar_url: "",
        },
      });
    }
    if (path.endsWith("/library/name")) {
      const payload = route.request().postDataJSON() as { name: string };
      currentName = payload.name.trim();
      return route.fulfill({ json: { name: currentName } });
    }
    return route.fulfill({ json: [] });
  });
  await page.goto("/livros");
  await expect(page).toHaveTitle("Livros | Casa");
  await page.locator(".account summary").click();
  await page.getByRole("link", { name: "Configurações" }).click();
  await expect(
    page.getByRole("heading", { name: "Configurações" }),
  ).toBeVisible();
  await expect(page).toHaveTitle("Configurações | Casa");
  await page.getByLabel("Nome da biblioteca").fill("Biblioteca Siloé");
  await page.getByRole("button", { name: "Salvar" }).click();
  await expect(page.getByRole("status")).toHaveText("Nome atualizado.");
  await expect(page.locator(".brand")).toHaveText("Biblioteca Siloé");
  await expect(page).toHaveTitle("Configurações | Biblioteca Siloé");
  await expect.poll(() => currentName).toBe("Biblioteca Siloé");
  expect(sessionCalls).toBe(1);
});

test("regular member cannot open settings", async ({ page }) => {
  await page.route("**/api/v1/**", (route) => {
    const path = new URL(route.request().url()).pathname;
    return route.fulfill({
      json: path.endsWith("/session")
        ? {
            user_id: 2,
            name: "Ju",
            email: "ju@example.com",
            technical: false,
            library: "Casa",
            csrf: "test",
            avatar_url: "",
          }
        : [],
    });
  });
  await page.goto("/configuracoes");
  await expect(page).toHaveURL(/\/livros(?:\?.*)?$/);
  await expect(
    page.getByRole("heading", { name: "Configurações" }),
  ).toHaveCount(0);
});
