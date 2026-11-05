import { test, expect } from "@playwright/test";

test("Brazilian ISBN results show provenance and preserve edition data", async ({
  page,
}) => {
  let query = "";
  await page.route("**/api/v1/**", (route) => {
    const url = new URL(route.request().url());
    let json: unknown = [];
    if (url.pathname.endsWith("/session"))
      json = {
        name: "Teste",
        email: "test@example.com",
        technical: false,
        library: "Teste",
        csrf: "test",
        avatar_url: "",
      };
    else if (url.pathname.endsWith("/books")) json = { items: [], total: 0 };
    else if (url.pathname.endsWith("/search")) {
      query = url.searchParams.get("q") || "";
      json = [
        {
          title: query === "9788570550156" ? "A MENSAGEM DE 2 TIMOTEO" : "Solo",
          authors: ["Autor"],
          isbn: query,
          source: "brasilapi",
          source_id: query,
          publisher: "Editora",
          page_count: query === "9786583581112" ? 656 : null,
          cover_url: "",
        },
      ];
    }
    return route.fulfill({ json });
  });
  await page.goto("/livros");
  for (const isbn of ["9788570550156", "9786583581112"]) {
    await page
      .getByRole("button", { name: "Adicionar livro", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    await dialog.getByRole("textbox", { name: "Buscar em APIs" }).fill(isbn);
    await dialog
      .getByRole("button", { name: "Buscar dados", exact: true })
      .click();
    await expect(
      dialog.getByRole("link", { name: "Fonte: BrasilAPI (CBL)" }),
    ).toBeVisible();
    await dialog.getByRole("button", { name: new RegExp(isbn) }).click();
    await expect(dialog.getByLabel("ISBN", { exact: true })).toHaveValue(isbn);
    await expect(
      dialog.getByRole("link", { name: "Fonte: BrasilAPI (CBL)" }),
    ).toBeVisible();
    if (isbn === "9786583581112")
      await expect(
        dialog.getByRole("spinbutton", { name: "Número de páginas" }),
      ).toHaveValue("656");
    await dialog.getByRole("button", { name: "Close", exact: true }).click();
  }
});
