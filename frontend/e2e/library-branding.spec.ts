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
    await expect(page.getByRole("link", { name: "Painel" })).toHaveCount(0);
    if (width > 800)
      await expect(page.getByRole("link", { name: "Livros" })).toBeVisible();
    const brand = page.locator(".brand");
    await expect(brand).toHaveText(name);
    await expect(brand).toHaveAttribute("title", name);
    await expect(page).toHaveTitle(`Locais | ${name}`);
    await expect(page.locator("footer")).toContainText("Powered by Julib");
    await expect(page.locator("footer")).not.toContainText(
      "Sua biblioteca, bem organizada",
    );
    await page.locator(".account summary").click();
    await expect(page.locator(".account-menu")).toContainText("Julib v0.2.0");
    await expect(page.locator(".copyright")).toContainText("v0.2.0");
    await expect(page.getByRole("radio", { name: "Claro" })).toBeVisible();
    await expect(page.getByRole("radio", { name: "Escuro" })).toBeVisible();
    await expect(page.getByRole("radio")).toHaveCount(2);
    await page.getByRole("radio", { name: "Claro" }).check();
    await expect(page.locator("html")).not.toHaveClass(/dark/);
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem("julib-theme")))
      .toBe("light");
    await page.getByRole("radio", { name: "Claro" }).focus();
    await page.keyboard.press("ArrowRight");
    await expect(page.getByRole("radio", { name: "Escuro" })).toBeChecked();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem("julib-theme")))
      .toBe("dark");
    await page.reload();
    await expect(page.locator("html")).toHaveClass(/dark/);
    await page.locator(".account summary").click();
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
      await expect(
        page.getByRole("dialog").getByRole("link", { name: "Painel" }),
      ).toHaveCount(0);
      await expect(
        page.getByRole("dialog").getByRole("link", { name: "Livros" }),
      ).toBeVisible();
      await page.keyboard.press("Escape");
    }
    await page.goto("/colecao/amigos");
    await expect(brand).toHaveText("Biblioteca dos amigos");
    await expect(page).toHaveTitle("Coleção | Biblioteca dos amigos");
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
  await expect(page).toHaveURL(/\/livros$/);
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
