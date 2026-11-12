import { test, expect } from "@playwright/test";

for (const width of [320, 800, 1280]) {
  test(`library identity and compact footer ${width}`, async ({ page }) => {
    const name =
      "Biblioteca de Ju e Marco — Literatura, histórias e descobertas compartilhadas";
    await page.setViewportSize({ width, height: 900 });
    await page.route("**/api/v1/**", (route) => {
      const path = new URL(route.request().url()).pathname;
      return route.fulfill({
        json: path.endsWith("/session")
          ? {
              user_id: 1,
              name: "Ju",
              email: "ju@example.com",
              library: name,
              technical: false,
              csrf: "test",
              avatar_url: "",
            }
          : path.includes("/public/")
            ? { name: "Biblioteca dos amigos", items: [], total: 0 }
            : [],
      });
    });
    await page.goto("/locais");
    const brand = page.locator(".brand");
    await expect(brand).toHaveText(name);
    await expect(brand).toHaveAttribute("title", name);
    await expect(page.locator("footer")).toContainText("Powered by Julib");
    await expect(page.locator("footer")).not.toContainText(
      "Sua biblioteca, bem organizada",
    );
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `/tmp/julib-brand-${width}.png`,
      fullPage: true,
    });
    if (width <= 800) {
      await page.getByRole("button", { name: "Abrir navegação" }).click();
      await expect(page.getByRole("dialog")).toContainText(name);
      await page.keyboard.press("Escape");
    }
    await page.goto("/colecao/amigos");
    await expect(brand).toHaveText("Biblioteca dos amigos");
    await page
      .locator("footer")
      .getByRole("link", { name: "Sobre", exact: true })
      .click();
    await expect(brand).toHaveText(name);
    await expect(
      page.getByRole("heading", {
        name: "Julib — Sua biblioteca, bem organizada",
      }),
    ).toBeVisible();
    await expect(page.locator("main")).toContainText(
      "Um lugar para cada livro. Mais histórias para compartilhar.",
    );
  });
}

test("signed-out identity and invalid public link use Julib", async ({
  page,
}) => {
  await page.route("**/api/v1/**", (route) =>
    route.request().url().includes("/public/amigos/")
      ? route.fulfill({
          json: { name: "Biblioteca dos amigos", items: [], total: 0 },
        })
      : route.fulfill({
          status: 401,
          json: { detail: "Entre com sua conta Google." },
        }),
  );
  await page.goto("/");
  await expect(page.locator(".brand")).toHaveText("Julib");
  await page.goto("/colecao/amigos");
  await expect(page.locator(".brand")).toHaveText("Biblioteca dos amigos");
  await page
    .locator("footer")
    .getByRole("link", { name: "Sobre", exact: true })
    .click();
  await expect(page.locator(".brand")).toHaveText("Julib");
  await page.goto("/colecao/invalida");
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.locator(".brand")).toHaveText("Julib");
});
