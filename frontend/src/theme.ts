import { useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "p2w-theme";
const META_COLORS: Record<Theme, string> = { light: "#f7f8f2", dark: "#111613" };
const listeners = new Set<() => void>();

function current(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", META_COLORS[theme]);
  listeners.forEach((listener) => listener());
}

export function setTheme(theme: Theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage may be unavailable (private mode); the choice still applies for this visit.
  }
  apply(theme);
}

// Follow the OS setting until the user picks a theme explicitly.
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
  let saved: string | null = null;
  try {
    saved = localStorage.getItem(STORAGE_KEY);
  } catch {
    // ignore
  }
  if (!saved) apply(event.matches ? "dark" : "light");
});

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, current);
}
