import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

test("create and switch libraries without changing another tab", async ({
  page,
  context,
}) => {
  await context.addCookies([
    JSON.parse(
      readFileSync(
        process.env.E2E_SESSION_PATH ?? "../.superpowers/e2e-session.json",
        "utf-8",
      ),
    ),
  ]);
  const response = await page.request.get("/api/v1/libraries");
  const before: { id: number; name: string }[] = await response.json();
  const original = before[0];
  expect(original).toBeTruthy();

  await page.goto("/");
  await expect(page.locator(".library-switcher > summary")).toBeVisible();
  await page.locator(".library-switcher > summary").click();
  await page.getByRole("menuitem", { name: "Nova biblioteca" }).click();
  const libraryName = `Biblioteca E2E ${Date.now()}`;
  await page.getByLabel("Nome da biblioteca").fill(libraryName);
  await page.getByRole("button", { name: "Criar biblioteca" }).click();
  await expect(page).toHaveURL(/\/bibliotecas\/\d+\/livros(?:\?.*)?$/);
  await expect(page).toHaveTitle(`Livros | ${libraryName}`);

  const after: { id: number; name: string }[] = await (
    await page.request.get("/api/v1/libraries")
  ).json();
  const created = after.find((library) => library.name === libraryName);
  expect(created).toBeTruthy();
  const secondTab = await context.newPage();
  await secondTab.goto(`/bibliotecas/${created!.id}/livros`);
  await expect(secondTab).toHaveTitle(`Livros | ${libraryName}`);

  await page.locator(".brand").click();
  await page
    .getByRole("menuitemradio", { name: original.name, exact: true })
    .click();
  await expect(page).toHaveURL(
    new RegExp(`/bibliotecas/${original.id}/livros(?:\\?.*)?$`),
  );
  await expect(page).toHaveTitle(`Livros | ${original.name || "Julib"}`);
  await expect(secondTab).toHaveURL(
    new RegExp(`/bibliotecas/${created!.id}/livros(?:\\?.*)?$`),
  );
  await expect(secondTab).toHaveTitle(`Livros | ${libraryName}`);
});

test("library administrators can issue a one-time invite link", async ({ page, context }) => {
  await context.addCookies([
    JSON.parse(readFileSync(process.env.E2E_SESSION_PATH ?? "../.superpowers/e2e-session.json", "utf-8")),
  ]);
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "share", {
      configurable: true,
      value: async (payload: ShareData) => {
        (window as Window & { sharedInvite?: string }).sharedInvite = payload.url;
      },
    });
  });
  const libraries: { id: number; name: string; role: string }[] = await (
    await page.request.get("/api/v1/libraries")
  ).json();
  const adminLibrary = libraries.find((library) => library.role === "admin");
  expect(adminLibrary).toBeTruthy();

  await page.goto(`/bibliotecas/${adminLibrary!.id}/membros`);
  await expect(page.getByRole("heading", { name: "Membros e convites" })).toBeVisible();
  await page.getByRole("button", { name: "Criar link de convite" }).click();
  await expect.poll(() => page.evaluate(() => (window as Window & { sharedInvite?: string }).sharedInvite)).toMatch(/\/convites\/aceitar#[\w-]+$/);
  await expect(page.getByText(/Link compartilhado/)).toBeVisible();
});

test("invite token is removed from the address before the API request", async ({ page }) => {
  let requestUrl = "";
  await page.route("**/api/v1/csrf", (route) => route.fulfill({ json: { csrf: "csrf-test" } }));
  await page.route("**/api/v1/invites/prepare", async (route) => {
    requestUrl = page.url();
    await route.fulfill({ json: { pending: true, library_name: "Biblioteca de teste" } });
  });

  await page.goto("/convites/aceitar#invite-secret-for-test");
  await expect(page.getByRole("heading", { name: "Você foi convidado" })).toBeVisible();
  expect(requestUrl).not.toContain("invite-secret-for-test");
  await expect(page).toHaveURL(/\/convites\/aceitar$/);
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain("invite-secret-for-test");
});
