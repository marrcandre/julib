export type ThemePreference = "light" | "dark";
export function applyTheme(preference: ThemePreference): void {
  document.documentElement.classList.toggle("dark", preference === "dark");
  localStorage.setItem("julib-theme", preference);
}
export function initialTheme(): ThemePreference {
  const stored = localStorage.getItem("julib-theme");
  if (stored === "light" || stored === "dark") return stored;
  return typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}
