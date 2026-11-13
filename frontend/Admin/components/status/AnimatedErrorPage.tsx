"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Moon, SunMedium } from "lucide-react";
import { ThemeLoader } from "@/components/loader/theme-loader";
import "@/styles/auth/base.css";
import "@/styles/auth/user-login.css";
import "@/styles/auth/auth-theme.css";
import "@/styles/auth/auth-interactive-v2.css";
import "@/styles/auth/loopless-purple-theme.css";

type ThemeMode = "dark" | "light";

const THEME_STORAGE_KEY = "loopless-theme";

export function AnimatedErrorPage() {
  const router = useRouter();
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [themeReady, setThemeReady] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      let initialTheme: ThemeMode = "dark";
      try {
        initialTheme = localStorage.getItem(THEME_STORAGE_KEY) === "light" ? "light" : "dark";
      } catch {
        /* Storage may be disabled. */
      }
      setTheme(initialTheme);
      document.documentElement.dataset.looplessTheme = initialTheme;
      document.documentElement.classList.toggle("dark", initialTheme === "dark");
      setThemeReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  function toggleTheme() {
    setTheme((currentTheme) => {
      const nextTheme: ThemeMode = currentTheme === "dark" ? "light" : "dark";
      try {
        localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
      } catch {
        /* Storage may be disabled. */
      }
      document.documentElement.dataset.looplessTheme = nextTheme;
      document.documentElement.classList.toggle("dark", nextTheme === "dark");
      return nextTheme;
    });
  }

  if (!themeReady) return <ThemeLoader />;

  return (
    <main className={`interactive-auth ${theme} account-disabled-page`}>
      <button className="auth-theme" type="button" onClick={toggleTheme} aria-label="Toggle theme">
        {theme === "dark" ? <SunMedium aria-hidden="true" /> : <Moon aria-hidden="true" />}
      </button>
      <section className="account-restricted-state" role="alert" aria-labelledby="not-found-title">
        <strong className="account-restricted-code" aria-hidden="true">
          404
        </strong>
        <div className="account-restricted-animation" aria-hidden="true" />
        <div className="account-restricted-content">
          <span className="account-restricted-label">404 · Page not found</span>
          <h1 id="not-found-title">Looks like you&apos;re lost</h1>
          <p>The page you are looking for is unavailable or may have been moved.</p>
        </div>
        <button type="button" onClick={() => router.push("/")}>
          <ArrowLeft /> Back to home
        </button>
      </section>
    </main>
  );
}
