"use client";

import { FormEvent, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, Eye, EyeOff, Moon, SunMedium } from "lucide-react";
import { adverseBrand, getBrandLogo } from "@/lib/branding";
import { AuthCursor, Characters } from "@/components/auth/LoginRegisterPage";
import { ThemeLoader } from "@/components/loader/theme-loader";
import "@/styles/auth/base.css";
import "@/styles/auth/user-login.css";
import "@/styles/auth/auth-theme.css";
import "@/styles/auth/auth-interactive-v2.css";
import "@/styles/auth/loopless-purple-theme.css";
import "@/styles/invitation-acceptance.css";

type ThemeMode = "dark" | "light";
type InvitationDetails = {
  email: string;
  company_name: string;
  expires_at: string;
  role_code: "COMPANY_EMPLOYEE" | "COMPANY_CLIENT";
  login_url: string;
};
const THEME_STORAGE_KEY = "loopless-theme";

function passwordError(value: string) {
  if (!value) return "Password is required.";
  if (
    value.length < 12 ||
    !/[a-z]/.test(value) ||
    !/[A-Z]/.test(value) ||
    !/\d/.test(value) ||
    !/[^A-Za-z0-9]/.test(value)
  )
    return "Use 12+ characters with uppercase, lowercase, number and symbol.";
  return "";
}

export function InvitationAcceptancePage({ token }: { token: string }) {
  const router = useRouter();
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [themeReady, setThemeReady] = useState(false);
  const [details, setDetails] = useState<InvitationDetails | null>(null);
  const [validating, setValidating] = useState(Boolean(token));
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [focused, setFocused] = useState<string | null>(null);
  const [pulse, setPulse] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState(token ? "" : "Invitation token is missing.");
  const [saving, setSaving] = useState(false);
  const [accepted, setAccepted] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const saved = localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === "dark" || saved === "light") {
        setTheme(saved);
        document.documentElement.dataset.looplessTheme = saved;
        document.documentElement.classList.toggle("dark", saved === "dark");
      }
      setThemeReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!token) {
      return;
    }
    const controller = new AbortController();
    void fetch(`/api/company/invitations/validate?token=${encodeURIComponent(token)}`, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail ?? "Invitation is invalid or has expired.");
        setDetails(data);
      })
      .catch((error: Error) => {
        if (error.name !== "AbortError") {
          setMessage(error.message);
        }
      })
      .finally(() => setValidating(false));
    return () => controller.abort();
  }, [token]);

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem(THEME_STORAGE_KEY, next);
    document.documentElement.dataset.looplessTheme = next;
    document.documentElement.classList.toggle("dark", next === "dark");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const nextErrors = {
      name: name.trim().length < 2 ? "Enter your full name." : "",
      password: passwordError(password),
      confirmation: !confirmation
        ? "Confirm password is required."
        : confirmation !== password
          ? "Passwords do not match."
          : "",
    };
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;
    setSaving(true);
    setMessage("");
    try {
      const response = await fetch("/api/company/invitations/accept", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, name: name.trim(), password, confirm_password: confirmation }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail ?? "Unable to accept this invitation.");
      if (data && typeof data === "object" && "login_url" in data && typeof data.login_url === "string") {
        setDetails((current) =>
          current
            ? {
                ...current,
                login_url: data.login_url,
                role_code: data.role_code === "COMPANY_CLIENT" ? "COMPANY_CLIENT" : current.role_code,
              }
            : current,
        );
      }
      setAccepted(true);
      setMessage(data.message);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Invitation service is unavailable.");
    } finally {
      setSaving(false);
    }
  }

  if (!themeReady) return <ThemeLoader />;

  const continueHref = details?.login_url ?? "/login";
  const continueLabel =
    details?.role_code === "COMPANY_CLIENT"
      ? "Continue to client login"
      : details?.role_code === "COMPANY_EMPLOYEE"
        ? "Continue to employee login"
        : "Continue to login";

  return (
    <main className={`interactive-auth ${theme}`}>
      <AuthCursor />
      <button className="auth-theme" type="button" onClick={toggleTheme} aria-label="Toggle theme">
        {theme === "dark" ? <SunMedium /> : <Moon />}
      </button>
      <button className="auth-exit" type="button" onClick={() => router.push("/login")}>
        <ArrowLeft /> Back
      </button>
      <div className="interactive-card invitation-acceptance-card">
        <section className="character-pane">
          <Link href="/login">
            <span className="brand-logo-wide">
              <Image src={getBrandLogo(theme, "wordmark")} alt={adverseBrand.name} width={560} height={236} priority />
            </span>
          </Link>
          <Characters
            lookingAway={!showPassword && focused === "password"}
            focused={focused}
            pulse={pulse}
            celebrate={accepted}
            register
          />
          <p>Your secure invitation is tied to one company and one email address.</p>
        </section>
        <section className="interactive-form recovery-form invitation-acceptance-form">
          <div className="auth-logo">
            <Image src={getBrandLogo(theme, "orbit")} alt={adverseBrand.name} width={240} height={240} priority />
          </div>
          <h1>{accepted ? `Welcome to ${adverseBrand.name}` : "Accept invitation"}</h1>
          <p>
            {accepted
              ? `Your ${details?.company_name ?? "company"} account is ready.`
              : details
                ? `Create your account for ${details.company_name}.`
                : "Validating your secure invitation link…"}
          </p>
          {validating ? (
            <div className="invitation-validation-state">
              <i /> Validating invitation…
            </div>
          ) : accepted ? (
            <div className="invitation-success">
              <CheckCircle2 />
              <strong>Account created successfully</strong>
              <span>{message}</span>
              <a className="interactive-submit" href={continueHref}>
                {continueLabel}
              </a>
            </div>
          ) : details ? (
            <form className="auth-form-transition" onSubmit={submit} noValidate>
              <label>
                Email
                <input type="email" value={details.email} readOnly aria-readonly="true" />
              </label>
              <label>
                Full name
                <input
                  value={name}
                  placeholder="Your full name"
                  aria-invalid={Boolean(errors.name)}
                  onFocus={() => setFocused("name")}
                  onBlur={() => setFocused(null)}
                  onChange={(event) => {
                    setName(event.target.value);
                    setPulse((value) => value + 1);
                    setErrors((current) => ({
                      ...current,
                      name: event.target.value.trim().length < 2 ? "Enter your full name." : "",
                    }));
                  }}
                />
                {errors.name && <small className="auth-field-error">{errors.name}</small>}
              </label>
              <label>
                Password
                <span>
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    placeholder="••••••••••••"
                    aria-invalid={Boolean(errors.password)}
                    onFocus={() => setFocused("password")}
                    onBlur={() => setFocused(null)}
                    onChange={(event) => {
                      setPassword(event.target.value);
                      setPulse((value) => value + 1);
                      setErrors((current) => ({
                        ...current,
                        password: passwordError(event.target.value),
                        confirmation:
                          confirmation && confirmation !== event.target.value ? "Passwords do not match." : "",
                      }));
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((value) => !value)}
                    aria-label={showPassword ? "Hide passwords" : "Show passwords"}
                  >
                    {showPassword ? <EyeOff /> : <Eye />}
                  </button>
                </span>
                {errors.password && <small className="auth-field-error">{errors.password}</small>}
              </label>
              <label>
                Confirm password
                <input
                  type={showPassword ? "text" : "password"}
                  value={confirmation}
                  placeholder="••••••••••••"
                  aria-invalid={Boolean(errors.confirmation)}
                  onFocus={() => setFocused("password")}
                  onBlur={() => setFocused(null)}
                  onChange={(event) => {
                    setConfirmation(event.target.value);
                    setPulse((value) => value + 1);
                    setErrors((current) => ({
                      ...current,
                      confirmation: !event.target.value
                        ? "Confirm password is required."
                        : event.target.value === password
                          ? ""
                          : "Passwords do not match.",
                    }));
                  }}
                />
                {errors.confirmation && <small className="auth-field-error">{errors.confirmation}</small>}
              </label>
              {message && <div className="interactive-error">{message}</div>}
              <button className="interactive-submit" disabled={saving}>
                {saving && <i className="recovery-spinner" />}
                {saving ? "Creating account…" : "Create account"}
              </button>
            </form>
          ) : (
            <div className="interactive-error" role="alert">
              {message}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
