"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Eye, EyeOff, Moon, SunMedium } from "lucide-react";
import { adverseBrand, getBrandLogo } from "@/lib/branding";
import { AuthCursor, Characters } from "./LoginRegisterPage";
import { ThemeLoader } from "@/components/loader/theme-loader";
import "@/styles/auth/base.css";
import "@/styles/auth/user-login.css";
import "@/styles/auth/auth-theme.css";
import "@/styles/auth/auth-interactive-v2.css";
import "@/styles/auth/loopless-purple-theme.css";

type RecoveryMode = "forgot" | "reset";
type ThemeMode = "dark" | "light";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const THEME_STORAGE_KEY = "loopless-theme";

function passwordError(value: string): string {
  if (!value) return "Password is required.";
  if (value.length < 12) return "Use at least 12 characters.";
  if (!/[a-z]/.test(value)) return "Include at least one lowercase letter.";
  if (!/[A-Z]/.test(value)) return "Include at least one uppercase letter.";
  if (!/\d/.test(value)) return "Include at least one number.";
  if (!/[^A-Za-z0-9]/.test(value)) return "Include at least one symbol.";
  return "";
}

export default function PasswordRecoveryPage({
  mode,
  token = "",
  email: initialEmail = "",
}: {
  mode: RecoveryMode;
  token?: string;
  email?: string;
}) {
  const router = useRouter();
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [themeReady, setThemeReady] = useState(false);
  const [email, setEmail] = useState(initialEmail);
  const [otp, setOtp] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [show, setShow] = useState(false);
  const [focused, setFocused] = useState<string | null>(null);
  const [pulse, setPulse] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(false);

  const title = useMemo(() => {
    if (mode === "forgot") return "Forgot password";
    return token ? "Reset your password" : "Verify reset code";
  }, [mode, token]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      try {
        const savedTheme = localStorage.getItem(THEME_STORAGE_KEY);
        if (savedTheme === "light" || savedTheme === "dark") {
          setTheme(savedTheme);
          document.documentElement.dataset.looplessTheme = savedTheme;
          document.documentElement.classList.toggle("dark", savedTheme === "dark");
        }
      } catch {
        /* Storage may be disabled. */
      }
      setThemeReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  function toggleTheme() {
    const nextTheme = theme === "dark" ? "light" : "dark";
    setTheme(nextTheme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch {
      /* Storage may be disabled. */
    }
    document.documentElement.dataset.looplessTheme = nextTheme;
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setFailed(false);
    const nextErrors: Record<string, string> = {};
    if (mode === "forgot") {
      if (!email.trim()) nextErrors.email = "Email is required.";
      else if (!EMAIL_PATTERN.test(email.trim())) nextErrors.email = "Enter a valid email address.";
    } else {
      if (!token) {
        if (!email.trim()) nextErrors.email = "Email is required.";
        else if (!EMAIL_PATTERN.test(email.trim())) nextErrors.email = "Enter a valid email address.";
        if (!otp.trim()) nextErrors.otp = "OTP is required.";
      }
      nextErrors.password = passwordError(password);
      if (!confirmation) nextErrors.confirmation = "Confirm password is required.";
      else if (confirmation !== password) nextErrors.confirmation = "Passwords do not match.";
    }
    setErrors(nextErrors);
    if (Object.values(nextErrors).some(Boolean)) return;

    setLoading(true);
    try {
      const response = await fetch(`/api/auth/${mode === "forgot" ? "forgot-password" : "reset-password"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          mode === "forgot"
            ? { email: email.trim() }
            : token
              ? { token, new_password: password, confirm_password: confirmation }
              : { email: email.trim(), otp: otp.trim(), new_password: password, confirm_password: confirmation },
        ),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail ?? "Password recovery request failed.");
      setMessage(data.message);
      if (mode === "forgot") {
        window.setTimeout(() => router.replace(`/reset-password?email=${encodeURIComponent(email.trim())}`), 700);
      } else {
        setPassword("");
        setConfirmation("");
        window.setTimeout(() => router.replace("/login"), 1100);
      }
    } catch (error) {
      setFailed(true);
      setMessage(error instanceof Error ? error.message : "Unable to connect to the password recovery service.");
    } finally {
      setLoading(false);
    }
  }

  if (!themeReady) return <ThemeLoader />;

  return (
    <main className={`interactive-auth ${theme}`}>
      <AuthCursor />
      <button className="auth-theme" type="button" onClick={toggleTheme} aria-label="Toggle theme">
        {theme === "dark" ? <SunMedium aria-hidden="true" /> : <Moon aria-hidden="true" />}
      </button>
      <button className="auth-exit" type="button" onClick={() => router.push("/login")}>
        <ArrowLeft /> Back
      </button>

      <div className="interactive-card">
        <section className="character-pane">
          <Link href="/login">
            <span className="brand-logo-wide">
              <Image src={getBrandLogo(theme, "wordmark")} alt={adverseBrand.name} width={560} height={236} priority />
            </span>
          </Link>
          <Characters
            lookingAway={!show && focused === "password"}
            focused={focused}
            pulse={pulse}
            celebrate={!failed && Boolean(message)}
            register={false}
          />
          <p>
            {mode === "forgot"
              ? "We will send a secure one-time code to your inbox."
              : "Enter the code from your email and choose a new password."}
          </p>
        </section>

        <section className="interactive-form">
          <div className="auth-logo">
            <Image src={getBrandLogo(theme, "orbit")} alt={adverseBrand.name} width={240} height={240} priority />
          </div>
          <h1>{title}</h1>
          <p>
            {mode === "forgot"
              ? "Request a reset code for your account."
              : "Complete the reset flow securely with OTP."}
          </p>

          <form className="auth-form-transition" onSubmit={submit} noValidate>
            <label>
              Email
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                readOnly={Boolean(initialEmail) && mode === "reset" && !token}
                aria-invalid={Boolean(errors.email)}
                onFocus={() => setFocused("email")}
                onBlur={() => setFocused(null)}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setPulse((current) => current + 1);
                  setErrors((current) => ({ ...current, email: "" }));
                }}
              />
              {errors.email && <small className="auth-field-error">{errors.email}</small>}
            </label>

            {mode === "reset" && !token && (
              <label>
                OTP code
                <input
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="123456"
                  value={otp}
                  aria-invalid={Boolean(errors.otp)}
                  onFocus={() => setFocused("otp")}
                  onBlur={() => setFocused(null)}
                  onChange={(event) => {
                    setOtp(event.target.value.replace(/\D/g, "").slice(0, 6));
                    setErrors((current) => ({ ...current, otp: "" }));
                  }}
                />
                {errors.otp && <small className="auth-field-error">{errors.otp}</small>}
              </label>
            )}

            {mode === "reset" && (
              <>
                <label>
                  New password
                  <span className="auth-password">
                    <input
                      minLength={12}
                      type={show ? "text" : "password"}
                      placeholder="••••••••••••"
                      value={password}
                      aria-invalid={Boolean(errors.password)}
                      onFocus={() => setFocused("password")}
                      onBlur={() => setFocused(null)}
                      onChange={(event) => {
                        setPassword(event.target.value);
                        setErrors((current) => ({ ...current, password: passwordError(event.target.value) }));
                        setPulse((current) => current + 1);
                      }}
                    />
                    <button
                      type="button"
                      onPointerDown={(event) => event.preventDefault()}
                      onClick={() => setShow(!show)}
                      aria-label={show ? "Hide password" : "Show password"}
                    >
                      {show ? <EyeOff /> : <Eye />}
                    </button>
                  </span>
                  {errors.password && <small className="auth-field-error">{errors.password}</small>}
                </label>

                <label>
                  Confirm password
                  <input
                    minLength={12}
                    type={show ? "text" : "password"}
                    placeholder="••••••••••••"
                    value={confirmation}
                    aria-invalid={Boolean(errors.confirmation)}
                    onFocus={() => setFocused("confirmation")}
                    onBlur={() => setFocused(null)}
                    onChange={(event) => {
                      setConfirmation(event.target.value);
                      setErrors((current) => ({
                        ...current,
                        confirmation: !event.target.value
                          ? "Confirm password is required."
                          : event.target.value !== password
                            ? "Passwords do not match."
                            : "",
                      }));
                    }}
                  />
                  {errors.confirmation && <small className="auth-field-error">{errors.confirmation}</small>}
                </label>
              </>
            )}

            {message && (
              <div className={failed ? "interactive-error" : "recovery-success"} role="status">
                {message}
              </div>
            )}

            <button className="interactive-submit" disabled={loading}>
              {loading ? "Please wait..." : mode === "forgot" ? "Send OTP" : "Reset password"}
            </button>
          </form>
          <p className="guest-copy">
            <Link href="/login">Back to login</Link>
          </p>
        </section>
      </div>
    </main>
  );
}
