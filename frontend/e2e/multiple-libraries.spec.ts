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
