"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, Clock3, MailCheck, Moon, SunMedium, XCircle } from "lucide-react";
import { adverseBrand, getBrandLogo } from "@/lib/branding";
import { AuthCursor, Characters } from "./LoginRegisterPage";
import { ThemeLoader } from "@/components/loader/theme-loader";

type VerificationState = "waiting" | "verifying" | "success" | "failed" | "expired";
type ThemeMode = "dark" | "light";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const THEME_STORAGE_KEY = "loopless-theme";

export default function EmailVerificationPage({
  token,
  email: initialEmail = "",
  verificationOtp = "",
}: {
  token?: string;
  email?: string;
  verificationOtp?: string;
}) {
  const router = useRouter();
  const hasAutoVerification = Boolean(token || (initialEmail && verificationOtp));
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [themeReady, setThemeReady] = useState(false);
  const [state, setState] = useState<VerificationState>(hasAutoVerification ? "verifying" : "waiting");
  const [message, setMessage] = useState(
    hasAutoVerification
      ? "Verifying your secure link…"
      : "We sent a 6-digit verification code to your email. Enter it below to activate your account.",
  );
  const [email, setEmail] = useState(initialEmail);
  const [otp, setOtp] = useState("");
  const [emailError, setEmailError] = useState("");
  const [otpError, setOtpError] = useState("");
  const [focused, setFocused] = useState<string | null>(null);
  const [pulse, setPulse] = useState(0);
  const [sending, setSending] = useState(false);
  const verifiedToken = useRef("");

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

  useEffect(() => {
    const autoVerificationKey = token
      ? `token:${token}`
      : initialEmail && verificationOtp
        ? `otp:${initialEmail}:${verificationOtp}`
        : "";
    if (!autoVerificationKey || verifiedToken.current === autoVerificationKey) return;
    verifiedToken.current = autoVerificationKey;
    void (async () => {
      const response = token
        ? await fetch(`/api/auth/verify-email?token=${encodeURIComponent(token)}`, { cache: "no-store" })
        : await fetch("/api/auth/verify-email", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: initialEmail.trim(), otp: verificationOtp.trim() }),
          });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setState(data.code === "VERIFICATION_TOKEN_EXPIRED" ? "expired" : "failed");
        throw new Error(data.detail ?? "Email verification failed.");
      }
      setState("success");
      setMessage(data.message);
    })().catch((error: Error) => setMessage(error.message));
  }, [token, initialEmail, verificationOtp]);

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

  async function verify(event: FormEvent) {
    event.preventDefault();
    const normalized = email.trim();
    const nextEmailError = !normalized
      ? "Email is required."
      : !EMAIL_PATTERN.test(normalized)
        ? "Enter a valid email address."
        : "";
    const nextOtpError = !otp.trim() ? "OTP is required." : otp.trim().length !== 6 ? "Enter the 6-digit code." : "";
    setEmailError(nextEmailError);
    setOtpError(nextOtpError);
    if (nextEmailError || nextOtpError) return;

    setSending(true);
    setState("verifying");
    try {
      const response = await fetch("/api/auth/verify-email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: normalized, otp: otp.trim() }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail ?? "Unable to verify your email.");
      setState("success");
      setMessage(data.message);
    } catch (error) {
      setState("failed");
      setMessage(error instanceof Error ? error.message : "Email verification service is unavailable.");
    } finally {
      setSending(false);
    }
  }

  async function resend(event: FormEvent) {
    event.preventDefault();
    const normalized = email.trim();
    const validation = !normalized
      ? "Email is required."
      : !EMAIL_PATTERN.test(normalized)
        ? "Enter a valid email address."
        : "";
    setEmailError(validation);
    if (validation) return;
    setSending(true);
    try {
      const response = await fetch("/api/auth/resend-verification", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: normalized }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail ?? "Unable to resend verification code.");
      setState("waiting");
      setMessage(data.message);
    } catch (error) {
      setState("failed");
      setMessage(error instanceof Error ? error.message : "Email verification service is unavailable.");
    } finally {
      setSending(false);
    }
  }

  if (!themeReady) return <ThemeLoader />;

  const Icon =
    state === "success" ? CheckCircle2 : state === "expired" ? Clock3 : state === "failed" ? XCircle : MailCheck;
  const title =
    state === "success"
      ? "Email verified!"
      : state === "expired"
        ? "Code expired"
        : state === "failed"
          ? "Verification failed"
          : state === "verifying"
            ? "Verifying email"
            : "Verify your email";
  const canResend = state === "waiting" || state === "failed" || state === "expired";

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
          <Characters lookingAway={false} focused={focused} pulse={pulse} celebrate={state === "success"} register={false} />
          <p>The little team keeps your workspace access private.</p>
        </section>

        <section className="interactive-form">
          <div className="auth-logo">
            <Image src={getBrandLogo(theme, "orbit")} alt={adverseBrand.name} width={240} height={240} priority />
          </div>
          <h1>{title}</h1>
          <p>{message}</p>

          <div className="auth-switch login" aria-label="Email verification">
            <button type="button" className="active">
              Verify email
            </button>
          </div>

          {state === "verifying" && (
            <div className="recovery-success">
              <Icon size={16} /> Verifying your account…
            </div>
          )}

          {!token && state !== "success" && (
            <form className="auth-form-transition" onSubmit={verify} noValidate>
              <label>
                Email
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  readOnly={Boolean(initialEmail)}
                  aria-invalid={Boolean(emailError)}
                  onFocus={() => setFocused("email")}
                  onBlur={() => setFocused(null)}
                  onChange={(event) => {
                    const value = event.target.value;
                    setEmail(value);
                    setPulse((current) => current + 1);
                    setEmailError("");
                  }}
                />
                {emailError && <small className="auth-field-error">{emailError}</small>}
              </label>

              <label>
                OTP code
                <input
                  inputMode="numeric"
                  maxLength={6}
                  placeholder="123456"
                  value={otp}
                  aria-invalid={Boolean(otpError)}
                  onFocus={() => setFocused("otp")}
                  onBlur={() => setFocused(null)}
                  onChange={(event) => {
                    setOtp(event.target.value.replace(/\D/g, "").slice(0, 6));
                    setPulse((current) => current + 1);
                    setOtpError("");
                  }}
                />
                {otpError && <small className="auth-field-error">{otpError}</small>}
              </label>

              {state === "failed" && <div className="interactive-error">{message}</div>}
              <button className="interactive-submit" disabled={sending}>
                {sending ? "Verifying…" : "Verify email"}
              </button>
            </form>
          )}

          {canResend && !token && (
            <form className="auth-form-transition" onSubmit={resend} noValidate>
              <button className="interactive-submit" disabled={sending}>
                {sending ? "Sending…" : "Resend verification code"}
              </button>
            </form>
          )}
          {state === "success" && (
            <div className="recovery-success" role="status">
              <Icon size={16} /> Your account is active.
            </div>
          )}
          <p className="guest-copy">
            <Link href="/login">Back to login</Link>
          </p>
        </section>
      </div>
    </main>
  );
}
