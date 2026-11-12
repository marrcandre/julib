import { test, expect } from "@playwright/test";

test("OAuth callback keeps the public frontend origin through the development proxy", async ({ request }) => {
  const base = "http://127.0.0.1:5173";
  const page = await request.get("/accounts/google/login/");
  expect(page.status()).toBe(200);
  const match = (await page.text()).match(/name="csrfmiddlewaretoken" value="([^"]+)"/);
  expect(match).not.toBeNull();
  const response = await request.post("/accounts/google/login/", {
    form: { csrfmiddlewaretoken: match![1] },
    headers: { Origin: base, Referer: base + "/accounts/google/login/" },
    maxRedirects: 0,
  });
  expect(response.status()).toBe(302);
  const target = new URL(response.headers()["location"]);
  expect(target.hostname).toBe("accounts.google.com");
  expect(target.searchParams.get("redirect_uri")).toBe(base + "/accounts/google/login/callback/");
  expect(Boolean(target.searchParams.get("state"))).toBe(true);
});

test("browser submits the Google confirmation with a trusted origin", async ({ page }) => {
  await page.route("https://accounts.google.com/**", route => route.fulfill({ body: "Google authorization reached" }));
  await page.goto("/accounts/google/login/");
  const submission = page.waitForRequest(request => request.method() === "POST" && new URL(request.url()).pathname === "/accounts/google/login/");
  await page.locator('form[method="post"] button[type="submit"]').click();
  const request = await submission;
  expect(request.headers()["origin"]).toBe("http://127.0.0.1:5173");
  await expect(page).toHaveURL(/^https:\/\/accounts\.google\.com\//);
});

test("saved theme is applied on Google login without a separate control", async ({ page }) => {
  await page.setViewportSize({ width: 393, height: 852 });
  await page.emulateMedia({ colorScheme: "light" });
  await page.addInitScript(() => localStorage.setItem("julib-theme", "dark"));
  await page.goto("/accounts/google/login/");
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(page.locator(".theme-toggle")).toHaveCount(0);
  await expect(page.locator(".auth-card")).toBeVisible();
  expect(await page.locator(".auth-card").evaluate(el => getComputedStyle(el).borderRadius)).toBe("20px");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await expect.poll(() => page.evaluate(() => localStorage.getItem("julib-theme"))).toBe("dark");
});

test("header shows the Google photo and falls back to initials on image failure", async ({ page }) => {
  await page.route("**/api/v1/session", route => route.fulfill({ json: {
    name: "Pessoa Teste", email: "test@example.com", technical: false,
    library: "Teste", csrf: "test", avatar_url: "https://lh3.googleusercontent.com/avatar-test",
  } }));
  await page.route("https://lh3.googleusercontent.com/avatar-test", route => route.fulfill({
    contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36"><circle cx="18" cy="18" r="18" fill="green"/></svg>',
  }));
  await page.goto("/sobre");
  await expect(page.locator(".avatar-photo")).toBeVisible();
  expect(await page.locator(".avatar-photo").evaluate((el: HTMLImageElement) => el.complete && el.naturalWidth > 0)).toBe(true);
  await page.route("https://lh3.googleusercontent.com/avatar-test", route => route.abort());
  await page.reload();
  await expect(page.locator(".avatar")).toHaveText("PE");
});
