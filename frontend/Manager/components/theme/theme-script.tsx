const themeInitializer = `
  try {
    var theme = localStorage.getItem("loopless-theme");
    if (theme !== "light" && theme !== "dark") theme = "dark";
    document.documentElement.dataset.looplessTheme = theme;
    document.documentElement.classList.toggle("dark", theme === "dark");
  } catch (_) {
    document.documentElement.dataset.looplessTheme = "dark";
    document.documentElement.classList.add("dark");
  }
`;

export function ThemeScript() {
  return <script dangerouslySetInnerHTML={{ __html: themeInitializer }} />;
}
