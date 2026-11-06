import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";

for (const width of [393, 1280])
  test(`wishlist acquisition, reclassification and permanent deletion on real API ${width}`, async ({
    page,
    context,
  }) => {
    await page.setViewportSize({ width, height: 852 });
    await context.addCookies([
      JSON.parse(readFileSync("../.superpowers/e2e-session.json", "utf-8")),
    ]);
    await page.goto("/livros");
    await page.getByLabel("Coleção exibida").selectOption("wishlist");
    await page
      .getByRole("button", { name: "Adicionar livro", exact: true })
      .click();
    await page.getByRole("menuitem", { name: "Cadastro manual" }).click();
    const title = "Desejado E2E " + Date.now();
    await page.getByLabel("Título *", { exact: true }).fill(title);
    await page.getByLabel("Autores *").fill("Autora de teste");
    await expect(page.getByLabel("Destino do cadastro")).toHaveValue(
      "wishlist",
    );
    await expect(
      page.getByText("Data de aquisição (opcional)"),
    ).not.toBeVisible();
    await page.getByRole("button", { name: "Salvar", exact: true }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    const open = page.getByRole("button", {
      name: "Abrir " + title,
      exact: true,
    });
    await expect(open).toBeVisible();
    await open.click();
    await expect(
      page.getByText("Este livro está nos seus desejados."),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Adicionar ao acervo", exact: true })
      .click();
    let dropped = false;
    await page.route("**/api/v1/registrations", async (route) => {
      if (!dropped) {
        dropped = true;
        await route.fetch();
        await route.abort("failed");
      } else await route.continue();
    });
    await page.getByRole("button", { name: "Confirmar aquisição" }).click();
    await expect(
      page
        .getByRole("dialog", { name: "Adicionar ao acervo", exact: true })
        .getByRole("alert"),
    ).toContainText("Não foi possível confirmar");
    await page.getByRole("button", { name: "Confirmar aquisição" }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.getByLabel("Coleção exibida").selectOption("collection");
    await page.getByLabel("Buscar no acervo").fill(title);
    await expect(open).toBeVisible();
    await page.screenshot({
      path: `../.superpowers/wishlist-catalog-${width}.png`,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await open.click();
    const acquired = await page.request.get(
      "/api/v1/books?scope=all&q=" + encodeURIComponent(title),
    );
    expect((await acquired.json()).items[0].copies).toHaveLength(1);
    page.once("dialog", (dialog) => dialog.accept());
    await page
      .getByRole("button", { name: "Mover para desejados", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await page.getByLabel("Coleção exibida").selectOption("wishlist");
    await open.click();
    await page
      .getByRole("button", { name: "Excluir definitivamente", exact: true })
      .click();
    await page.getByLabel("Digite EXCLUIR para confirmar").fill("EXCLUIR");
    await page
      .getByRole("button", {
        name: "Confirmar exclusão definitiva",
        exact: true,
      })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(open).not.toBeVisible();
    const response = await page.request.get(
      "/api/v1/books?scope=all&q=" + encodeURIComponent(title),
    );
    expect((await response.json()).total).toBe(0);
  });
