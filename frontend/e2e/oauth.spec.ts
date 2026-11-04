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
