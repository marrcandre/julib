import { test, expect } from "@playwright/test";

// Real decoder integration uses a synthetic camera fixture, enabled explicitly.
test("camera reads ISBN automatically without saving or overwriting selected data", async ({
  page,
}) => {
  test.skip(
    !process.env.CAMERA_FIXTURE,
    "Requires synthetic camera launch configuration",
  );
  const searches: string[] = [];
  const writes: string[] = [];
  await page.route("**/api/v1/**", (route) => {
    const url = new URL(route.request().url());
    // Enrichment accepts a candidate payload but performs no database writes.
    if (
      route.request().method() !== "GET" &&
      !url.pathname.endsWith("/search/enrich")
    )
      writes.push(url.pathname);
    let json: unknown = [];
    if (url.pathname.endsWith("/session"))
      json = {
        user_id: 1,
        name: "Teste",
        email: "test@example.com",
        technical: false,
        library: "Teste",
        csrf: "test",
        avatar_url: "",
      };
    else if (url.pathname.endsWith("/books")) json = { items: [], total: 0 };
    else if (url.pathname.endsWith("/search")) {
      searches.push(url.searchParams.get("q") || "");
      json = [
        {
          title: "O Hobbit",
          authors: ["Tolkien"],
          isbn: "9780261102217",
          source: "google",
          source_id: "test",
          page_count: 320,
        },
      ];
    }
    return route.fulfill({ json });
  });
  await page.goto("/livros");
  await page
    .getByRole("button", { name: "Adicionar livro", exact: true })
    .click();
  await page.getByRole("menuitem", { name: "Escanear ISBN" }).click();
  await expect.poll(() => searches.length).toBe(1);
  expect(searches[0]).toBe("isbn:9780261102217");
  expect(writes).toHaveLength(0);
  await page.getByRole("button", { name: /O Hobbit.*Tolkien/ }).click();
  const title = page.getByLabel("Título *", { exact: true });
  await title.fill("Título revisado");
  await page.waitForTimeout(1200);
  expect(searches).toHaveLength(1);
  await expect(title).toHaveValue("Título revisado");
  await expect(
    page.getByRole("spinbutton", { name: "Número de páginas" }),
  ).toHaveValue("320");
  expect(writes).toHaveLength(0);
  await page
    .getByRole("button", { name: "Ler outro código", exact: true })
    .click();
  await expect.poll(() => searches.length).toBe(2);
  expect(writes).toHaveLength(0);
  await page.getByRole("button", { name: /O Hobbit.*Tolkien/ }).click();
  await page
    .getByRole("button", { name: "Salvar e continuar", exact: true })
    .click();
  await expect
    .poll(() => writes.filter((path) => path.endsWith("/registrations")).length)
    .toBe(1);
  await expect(title).toHaveValue("");
  const video = await page.locator("video").elementHandle();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await expect
    .poll(() =>
      video!.evaluate(
        (v: HTMLVideoElement) =>
          !v.srcObject ||
          (v.srcObject as MediaStream)
            .getTracks()
            .every((t) => t.readyState === "ended"),
      ),
    )
    .toBe(true);
});

test("camera permission denial keeps manual registration available", async ({
  page,
}) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = () =>
      Promise.reject(new DOMException("Denied", "NotAllowedError"));
  });
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({
      json: new URL(route.request().url()).pathname.endsWith("/session")
        ? {
            user_id: 1,
            name: "Teste",
            email: "test@example.com",
            technical: false,
            library: "Teste",
            csrf: "test",
            avatar_url: "",
          }
        : new URL(route.request().url()).pathname.endsWith("/books")
          ? { items: [], total: 0 }
          : [],
    }),
  );
  await page.goto("/livros");
  await page
    .getByRole("button", { name: "Adicionar livro", exact: true })
    .click();
  await page.getByRole("menuitem", { name: "Escanear ISBN" }).click();
  await expect(page.getByRole("dialog").getByRole("alert")).toContainText(
    "Permita o acesso ou digite o ISBN",
  );
  await expect(page.locator("video")).toHaveCount(0);
  await expect(page.getByLabel("Título *", { exact: true })).toBeEditable();
});

test("closing while camera permission is pending stops the late stream", async ({
  page,
}) => {
  test.skip(
    !process.env.CAMERA_FIXTURE,
    "Requires synthetic camera launch configuration",
  );
  await page.addInitScript(() => {
    const original = navigator.mediaDevices.getUserMedia.bind(
      navigator.mediaDevices,
    );
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      await new Promise((resolve) => setTimeout(resolve, 500));
      const stream = await original(constraints);
      (
        window as unknown as { cameraTestTracks: MediaStreamTrack[] }
      ).cameraTestTracks = stream.getTracks();
      return stream;
    };
  });
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({
      json: new URL(route.request().url()).pathname.endsWith("/session")
        ? {
            user_id: 1,
            name: "Teste",
            email: "test@example.com",
            technical: false,
            library: "Teste",
            csrf: "test",
            avatar_url: "",
          }
        : new URL(route.request().url()).pathname.endsWith("/books")
          ? { items: [], total: 0 }
          : [],
    }),
  );
  await page.goto("/livros");
  await page
    .getByRole("button", { name: "Adicionar livro", exact: true })
    .click();
  await page.getByRole("menuitem", { name: "Escanear ISBN" }).click();
  await expect(page.locator("video")).toHaveCount(1);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close", exact: true })
    .click();
  await expect
    .poll(() =>
      page.evaluate(() => {
        const tracks = (
          window as unknown as { cameraTestTracks?: MediaStreamTrack[] }
        ).cameraTestTracks;
        return (
          !!tracks?.length && tracks.every((t) => t.readyState === "ended")
        );
      }),
    )
    .toBe(true);
});
