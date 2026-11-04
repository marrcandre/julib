export type ThemePreference = "system" | "light" | "dark";
export function resolveTheme(
  preference: ThemePreference,
  systemDark?: boolean,
): "light" | "dark" {
  return preference === "system"
    ? systemDark === false
      ? "light"
      : "dark"
    : preference;
}
export function applyTheme(preference: ThemePreference): void {
  let dark: boolean | undefined;
  if (typeof window.matchMedia === "function") {
    if (window.matchMedia("(prefers-color-scheme: dark)").matches) dark = true;
    else if (window.matchMedia("(prefers-color-scheme: light)").matches)
      dark = false;
  }
  document.documentElement.classList.toggle(
    "dark",
    resolveTheme(preference, dark) === "dark",
  );
  localStorage.setItem("julib-theme", preference);
}
export function initialTheme(): ThemePreference {
  const stored = localStorage.getItem("julib-theme");
  if (stored === "light" || stored === "dark") return stored;
  return typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}
