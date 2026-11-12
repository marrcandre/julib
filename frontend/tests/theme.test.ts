import { describe, it, expect, vi, beforeEach } from "vitest";
import { initialTheme, applyTheme } from "../src/theme";
describe("theme", () => {
  beforeEach(() => localStorage.clear());
  it("resolves the operating system preference to a concrete initial theme", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    expect(initialTheme()).toBe("light");
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
    expect(initialTheme()).toBe("dark");
    vi.unstubAllGlobals();
  });
  it("restores only saved light or dark preferences", () => {
    localStorage.setItem("julib-theme", "light");
    expect(initialTheme()).toBe("light");
    localStorage.setItem("julib-theme", "system");
    expect(initialTheme()).toBe("dark");
  });
  it("persists manual preference", () => {
    applyTheme("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("julib-theme")).toBe("dark");
  });
});
