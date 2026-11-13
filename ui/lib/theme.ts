// Shared by the theme toggle (client) and the inline no-flash script in app/layout.tsx (server).
// Keep this module free of client-only imports so layout.tsx can read the script string.
export const THEME_STORAGE_KEY = "echo-theme";

// Runs before first paint. Sets data-theme only for an explicit light or dark choice; "system" leaves it unset.
// Authored here as a constant string; it contains no user input.
export const THEME_INIT_SCRIPT = `(function () {
  try {
    var choice = localStorage.getItem("${THEME_STORAGE_KEY}");
    if (choice === "light" || choice === "dark") {
      document.documentElement.setAttribute("data-theme", choice);
    }
  } catch (error) {
    // Storage can be blocked; fall back to the system theme.
  }
})();`;
