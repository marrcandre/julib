import { describe, it, expect, vi, beforeEach } from "vitest";
import { resolveTheme, applyTheme } from "../src/theme";
describe("theme", () => {
  beforeEach(() => localStorage.clear());
  it("uses system, with dark fallback", () => {
    expect(resolveTheme("system", undefined)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("light", true)).toBe("light");
  });
  it("persists manual preference", () => {
    applyTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("julib-theme")).toBe("dark");
  });
});
