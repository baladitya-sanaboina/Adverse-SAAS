"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { Eye, EyeOff, Moon, SunMedium } from "lucide-react";
import { adverseBrand, getBrandLogo } from "@/lib/branding";
import { ThemeLoader } from "@/components/loader/theme-loader";
import { AuthApiError, login as authenticate } from "@/lib/auth/client";
import { authConfig } from "@/lib/auth/config";
import "@/styles/auth/base.css";
import "@/styles/auth/user-login.css";
import "@/styles/auth/auth-theme.css";
import "@/styles/auth/auth-interactive-v2.css";
import "@/styles/auth/loopless-purple-theme.css";

type AuthMode = "login" | "register";
type ThemeMode = "dark" | "light";

const THEME_STORAGE_KEY = "loopless-theme";
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function validatePassword(value: string): string {
  if (!value) return "Password is required.";
  if (value.length < 12) return "Use at least 12 characters.";
  if (!/[a-z]/.test(value)) return "Include at least one lowercase letter.";
  if (!/[A-Z]/.test(value)) return "Include at least one uppercase letter.";
  if (!/\d/.test(value)) return "Include at least one number.";
  if (!/[^A-Za-z0-9]/.test(value)) return "Include at least one symbol.";
  return "";
}

function validateEmail(value: string): string {
  if (!value.trim()) return "Email is required.";
  if (!EMAIL_PATTERN.test(value.trim())) return "Enter a valid email address.";
  return "";
}

// After signing in from a meet link, go back to that call. Only /call/<code> paths are
// followed, so the login page cannot be used to send people to another site.
function afterLogin(): string {
  const next = new URLSearchParams(window.location.search).get("next") ?? "";
  return /^\/call\/[a-z-]{3,16}(\?kind=(AUDIO|VIDEO))?$/i.test(next) ? next : "/dashboard";
}

export function AuthCursor() {
  const cursor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const move = (event: MouseEvent) => {
      if (!cursor.current) return;
      cursor.current.style.transform = `translate3d(${event.clientX}px, ${event.clientY}px, 0)`;
      cursor.current.dataset.visible = "true";
    };
    window.addEventListener("mousemove", move, { passive: true });
    return () => window.removeEventListener("mousemove", move);
  }, []);

  return (
    <div className="auth-cursor" ref={cursor} aria-hidden="true">
      <svg viewBox="0 0 24 24">
        <path d="M2 2 10.5 22l3-8.5L22 10.5 2 2Z" />
      </svg>
    </div>
  );
}

function Face({ darkEyes = false }: { darkEyes?: boolean }) {
  return (
    <div className={`character-face ${darkEyes ? "dark-eyes" : ""}`}>
      <i>
        <b />
      </i>
      <i>
        <b />
      </i>
    </div>
  );
}

export function Characters({
  lookingAway,
  focused,
  celebrate,
  register,
}: {
  lookingAway: boolean;
  focused: string | null;
  pulse: number;
  celebrate: boolean;
  register: boolean;
}) {
  return (
    <div
      className={`user-characters original-interaction ${lookingAway ? "looking-away" : ""} ${celebrate ? "celebrate" : ""} ${register ? "registering" : ""} ${focused ? "is-focused" : ""}`}
    >
      <div className="login-character blue-character">
        <Face />
      </div>
      <div className="login-character orange-character">
        <Face darkEyes />
        <span className="character-mouth" />
      </div>
      <div className="login-character black-character">
        <Face />
      </div>
      <div className="login-character yellow-character">
        <span className="character-beak" />
        <Face darkEyes />
      </div>
    </div>
  );
}

export default function LoginRegisterPage({ initialMode = "login" }: { initialMode?: AuthMode }) {
  const router = useRouter();
  const [mode, setMode] = useState<AuthMode>(authConfig.signupEnabled ? initialMode : "login");
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [themeReady, setThemeReady] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [remember, setRemember] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");
  const [focused, setFocused] = useState<string | null>(null);
  const [pulse, setPulse] = useState(0);
  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
    companyName: "",
    companyCode: "",
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const signupEnabled = authConfig.signupEnabled;
  const registerCopy = useMemo(() => authConfig.signupDescription, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
        if (savedTheme === "light" || savedTheme === "dark") {
          setTheme(savedTheme);
          document.documentElement.dataset.looplessTheme = savedTheme;
          document.documentElement.classList.toggle("dark", savedTheme === "dark");
        }
        const rememberedEmail = localStorage.getItem("loopless-remembered-email") || "";
        if (rememberedEmail) {
          setForm((currentForm) => ({ ...currentForm, email: rememberedEmail }));
          setRemember(true);
        }
      } catch {
        /* Storage may be disabled. */
      }
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

  function changeMode(nextMode: AuthMode) {
    if (!signupEnabled && nextMode === "register") {
      setMode("login");
      setError(authConfig.signupDisabledMessage);
      router.push("/login");
      return;
    }

    setMode(nextMode);
    setShowPassword(false);
    setShowConfirm(false);
    setSuccess(false);
    setError("");
    setFieldErrors({});
    router.push(nextMode === "login" ? "/login" : "/register");
  }

  function validateRegisterFields() {
    const nextErrors: Record<string, string> = {
      name: !form.name.trim() ? "Name is required." : form.name.trim().length < 2 ? "Use at least 2 characters." : "",
      email: validateEmail(form.email),
      password: validatePassword(form.password),
      confirmPassword: !form.confirmPassword
        ? "Confirm your password."
        : form.confirmPassword !== form.password
          ? "Passwords do not match."
          : "",
      companyName: authConfig.requiresCompanyName && !form.companyName.trim() ? "Company name is required." : "",
      companyCode: authConfig.requiresCompanyCode && !form.companyCode.trim() ? "Company code is required." : "",
    };
    return nextErrors;
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (mode === "register" && !signupEnabled) {
      setError(authConfig.signupDisabledMessage);
      return;
    }

    const nextErrors =
      mode === "login"
        ? { email: validateEmail(form.email), password: form.password ? "" : "Password is required." }
        : validateRegisterFields();
    setFieldErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;

    try {
      if (remember) localStorage.setItem("loopless-remembered-email", form.email.trim());
      else localStorage.removeItem("loopless-remembered-email");
    } catch {
      /* Storage may be disabled. */
    }

    setLoading(true);
    try {
      if (mode === "login") {
        await authenticate(form.email.trim(), form.password);
        setSuccess(true);
        window.setTimeout(() => router.replace(afterLogin()), 650);
      } else {
        const response = await fetch("/api/auth/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            role: authConfig.signupRole,
            name: form.name.trim(),
            email: form.email.trim(),
            password: form.password,
            confirm_password: form.confirmPassword,
            company_name: authConfig.requiresCompanyName ? form.companyName.trim() : undefined,
            company_code: authConfig.requiresCompanyCode ? form.companyCode.trim().toUpperCase() : undefined,
          }),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail ?? "Unable to create your account.");
        setSuccess(true);
        window.setTimeout(() => router.replace(`/verify-email?email=${encodeURIComponent(form.email.trim())}`), 700);
      }
    } catch (submissionError) {
      if (
        submissionError instanceof AuthApiError &&
        ["USER_INACTIVE", "COMPANY_INACTIVE", "ACTOR_INACTIVE", "MAINTENANCE_MODE"].includes(submissionError.code ?? "")
      ) {
        setError(
          submissionError.code === "MAINTENANCE_MODE"
            ? submissionError.message
            : "Your access is currently unavailable. Please contact your administrator.",
        );
      } else {
        setError(submissionError instanceof Error ? submissionError.message : "Unable to continue.");
      }
      setSuccess(false);
    } finally {
      setLoading(false);
    }
  }

  if (!themeReady) {
    return <ThemeLoader />;
  }

  return (
    <main className={`interactive-auth ${theme}`}>
      <AuthCursor />
      <button className="auth-theme" type="button" onClick={toggleTheme} aria-label="Toggle theme">
        {theme === "dark" ? <SunMedium aria-hidden="true" /> : <Moon aria-hidden="true" />}
      </button>

      <div className="interactive-card">
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
            celebrate={success}
            register={mode === "register"}
          />
          <p>{mode === "login" ? `${authConfig.roleLabel} access for your Adverse workspace.` : registerCopy}</p>
        </section>

        <section className="interactive-form">
          <div className="auth-logo">
            <Image src={getBrandLogo(theme, "orbit")} alt={adverseBrand.name} width={240} height={240} priority />
          </div>
          <h1>
            {mode === "login" ? `Welcome back, ${authConfig.roleLabel}` : `Create your ${authConfig.roleLabel} account`}
          </h1>
          <p>
            {mode === "login"
              ? "Sign in to continue to your dashboard."
              : "Fill in the details below. We will send a one-time verification code to your email."}
          </p>

          <div className={`auth-switch ${mode}`} role="tablist" aria-label="Account access">
            <button
              type="button"
              role="tab"
              aria-selected={mode === "login"}
              className={mode === "login" ? "active" : ""}
              onClick={() => changeMode("login")}
            >
              Log in
            </button>
            {signupEnabled ? (
              <button
                type="button"
                role="tab"
                aria-selected={mode === "register"}
                className={mode === "register" ? "active" : ""}
                onClick={() => changeMode("register")}
              >
                Sign up
              </button>
            ) : null}
          </div>

          <form key={mode} className="auth-form-transition" onSubmit={submit} noValidate>
            {mode === "register" && (
              <label>
                Name
                <input
                  required
                  minLength={2}
                  placeholder="Your name"
                  value={form.name}
                  onFocus={() => setFocused("name")}
                  onBlur={() => setFocused(null)}
                  onChange={(event) => {
                    setForm({ ...form, name: event.target.value });
                    setPulse((value) => value + 1);
                  }}
                />
                {fieldErrors.name && <small className="auth-field-error">{fieldErrors.name}</small>}
              </label>
            )}

            {mode === "register" && authConfig.requiresCompanyName && (
              <label>
                Company name
                <input
                  placeholder="Acme Operations"
                  value={form.companyName}
                  onFocus={() => setFocused("companyName")}
                  onBlur={() => setFocused(null)}
                  onChange={(event) => setForm({ ...form, companyName: event.target.value })}
                />
                {fieldErrors.companyName && <small className="auth-field-error">{fieldErrors.companyName}</small>}
              </label>
            )}

            {mode === "register" && authConfig.requiresCompanyCode && (
              <label>
                Company code
                <input
                  placeholder="ACME_OPS"
                  value={form.companyCode}
                  onFocus={() => setFocused("companyCode")}
                  onBlur={() => setFocused(null)}
                  onChange={(event) =>
                    setForm({ ...form, companyCode: event.target.value.toUpperCase().replace(/\s+/g, "_") })
                  }
                />
                {fieldErrors.companyCode && <small className="auth-field-error">{fieldErrors.companyCode}</small>}
              </label>
            )}

            <label>
              Email
              <input
                type="email"
                placeholder="Your Gmail or Adverse ID"
                value={form.email}
                aria-invalid={Boolean(fieldErrors.email)}
                onFocus={() => setFocused("email")}
                onBlur={() => setFocused(null)}
                onChange={(event) => {
                  setForm({ ...form, email: event.target.value });
                  setFieldErrors((current) => ({ ...current, email: validateEmail(event.target.value) }));
                  setError("");
                  setPulse((value) => value + 1);
                }}
              />
              {fieldErrors.email && <small className="auth-field-error">{fieldErrors.email}</small>}
            </label>

            <label>
              Password
              <span className="auth-password">
                <input
                  minLength={8}
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••••••"
                  value={form.password}
                  aria-invalid={Boolean(fieldErrors.password)}
                  onFocus={() => setFocused("password")}
                  onBlur={() => setFocused(null)}
                  onChange={(event) => {
                    setForm({ ...form, password: event.target.value });
                    if (mode === "register") {
                      setFieldErrors((current) => ({ ...current, password: validatePassword(event.target.value) }));
                    }
                    setError("");
                    setPulse((value) => value + 1);
                  }}
                />
                <button
                  type="button"
                  onPointerDown={(event) => event.preventDefault()}
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff /> : <Eye />}
                </button>
              </span>
              {fieldErrors.password && <small className="auth-field-error">{fieldErrors.password}</small>}
            </label>

            {mode === "register" && (
              <label>
                Confirm password
                <span className="auth-password">
                  <input
                    minLength={8}
                    type={showConfirm ? "text" : "password"}
                    placeholder="••••••••••••"
                    value={form.confirmPassword}
                    aria-invalid={Boolean(fieldErrors.confirmPassword)}
                    onFocus={() => setFocused("confirmPassword")}
                    onBlur={() => setFocused(null)}
                    onChange={(event) => {
                      setForm({ ...form, confirmPassword: event.target.value });
                      setFieldErrors((current) => ({
                        ...current,
                        confirmPassword: !event.target.value
                          ? "Confirm your password."
                          : event.target.value !== form.password
                            ? "Passwords do not match."
                            : "",
                      }));
                    }}
                  />
                  <button
                    type="button"
                    onPointerDown={(event) => event.preventDefault()}
                    onClick={() => setShowConfirm(!showConfirm)}
                    aria-label={showConfirm ? "Hide confirmation password" : "Show confirmation password"}
                  >
                    {showConfirm ? <EyeOff /> : <Eye />}
                  </button>
                </span>
                {fieldErrors.confirmPassword && (
                  <small className="auth-field-error">{fieldErrors.confirmPassword}</small>
                )}
              </label>
            )}

            {mode === "login" && (
              <div className="login-options-row">
                <label className="remember-row">
                  <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
                  <i />
                  <span>Remember my email on this device</span>
                </label>
                <Link href="/forgot-password">Forgot password?</Link>
              </div>
            )}

            {error && (
              <div className="interactive-error" role="alert">
                {error}
              </div>
            )}

            <button className={`interactive-submit ${success ? "success" : ""}`} type="submit" disabled={loading}>
              {success
                ? mode === "login"
                  ? "Welcome!"
                  : "OTP sent"
                : loading
                  ? "Loading..."
                  : mode === "login"
                    ? "Log in"
                    : "Create account"}
            </button>
          </form>
          <p className="guest-copy">
            {mode === "login" ? (
              signupEnabled ? (
                <>
                  New here?{" "}
                  <button type="button" onClick={() => changeMode("register")}>
                    Create account
                  </button>
                </>
              ) : (
                <>Need access? Contact your administrator.</>
              )
            ) : (
              <Link href="/login">Back to login</Link>
            )}
          </p>
        </section>
      </div>
    </main>
  );
}
