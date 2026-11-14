// Copy of frontend/shared/production/privacy.tsx (the Client app cannot import shared/). Keep in sync.
"use client";

/*
 * Privacy eye for money (owner decisions 2026-11-14): amounts are hidden on every visit and shown
 * only after the eye is pressed, until the page is left. When the provider gets a `password`
 * (the Admin app), showing amounts first asks for it. Outside a <MoneyPrivacy> provider nothing
 * is hidden, so other pages are unaffected.
 *
 * This is a screen-privacy guard against people looking over a shoulder, not access control: the
 * server already decides who may see which amounts.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { Eye, EyeOff, LockKeyhole, X } from "lucide-react";
import "@/styles/privacy.css";

export const MASK = "••••";

type Privacy = { hidden: boolean; toggle: () => void };
const PrivacyContext = createContext<Privacy>({ hidden: false, toggle: () => {} });

export function MoneyPrivacy({ children, password }: { children: ReactNode; password?: string }) {
  const [hidden, setHidden] = useState(true);
  const [asking, setAsking] = useState(false);
  const toggle = useCallback(() => {
    if (hidden && password) setAsking(true);
    else setHidden((current) => !current);
  }, [hidden, password]);
  const value = useMemo(() => ({ hidden, toggle }), [hidden, toggle]);
  return (
    <PrivacyContext.Provider value={value}>
      {children}
      {asking && password && (
        <PasswordGate
          password={password}
          onClose={() => setAsking(false)}
          onUnlock={() => {
            setAsking(false);
            setHidden(false);
          }}
        />
      )}
    </PrivacyContext.Provider>
  );
}

function PasswordGate({
  password,
  onClose,
  onUnlock,
}: {
  password: string;
  onClose: () => void;
  onUnlock: () => void;
}) {
  const [value, setValue] = useState("");
  const [wrong, setWrong] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    input.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (value === password) onUnlock();
    else {
      setWrong(true);
      setValue("");
      input.current?.focus();
    }
  };

  return (
    <div
      className="privacy-gate"
      role="presentation"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <form
        className="privacy-gate-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="privacy-gate-title"
        onSubmit={submit}
      >
        <button type="button" className="privacy-gate-close" aria-label="Cancel" onClick={onClose}>
          <X aria-hidden="true" />
        </button>
        <span className="privacy-gate-icon" aria-hidden="true">
          <LockKeyhole />
        </span>
        <h2 id="privacy-gate-title">Show amounts</h2>
        <p>Enter the password to see the money on this page.</p>
        <input
          ref={input}
          type="password"
          inputMode="numeric"
          autoComplete="off"
          value={value}
          aria-label="Password"
          aria-invalid={wrong}
          placeholder="Password"
          onChange={(event) => {
            setValue(event.target.value);
            setWrong(false);
          }}
        />
        {wrong && <small role="alert">Wrong password. Try again.</small>}
        <div className="privacy-gate-actions">
          <button type="button" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="primary" disabled={!value}>
            Show
          </button>
        </div>
      </form>
    </div>
  );
}

export function useMoneyPrivacy(): Privacy {
  return useContext(PrivacyContext);
}

/** "₹1,23,921.00" -> "₹••••"; "-₹500" -> "-₹••••"; "₹1.5L" -> "₹••••". Other text is kept. */
export function maskMoney(text: string): string {
  return text.replace(/\d[\d,]*(?:\.\d+)?(?:\s?(?:K|L|Cr|M|B)\b)?/g, MASK);
}

/** Wraps a formatter so it returns masked text while amounts are hidden. */
export function usePrivateMoney<A extends unknown[]>(format: (...args: A) => string): (...args: A) => string {
  const { hidden } = useMoneyPrivacy();
  return useCallback((...args: A) => (hidden ? maskMoney(format(...args)) : format(...args)), [hidden, format]);
}

/** Masks any amount inside its text children while hidden. */
export function Private({ children }: { children: string }) {
  const { hidden } = useMoneyPrivacy();
  return <>{hidden ? maskMoney(children) : children}</>;
}

/** Eye button: same look as the app's secondary buttons. */
export function PrivacyToggle({ className = "management-secondary-action" }: { className?: string }) {
  const { hidden, toggle } = useMoneyPrivacy();
  return (
    <button
      type="button"
      className={className}
      onClick={toggle}
      aria-pressed={!hidden}
      title={hidden ? "Show amounts" : "Hide amounts"}
    >
      {hidden ? <Eye aria-hidden="true" /> : <EyeOff aria-hidden="true" />}
      {hidden ? "Show amounts" : "Hide amounts"}
    </button>
  );
}

/** Small icon-only eye to sit right next to an amount. */
export function AmountEye() {
  const { hidden, toggle } = useMoneyPrivacy();
  return (
    <button
      type="button"
      className="privacy-eye"
      onClick={toggle}
      aria-pressed={!hidden}
      aria-label={hidden ? "Show amounts" : "Hide amounts"}
      title={hidden ? "Show amounts" : "Hide amounts"}
    >
      {hidden ? <Eye aria-hidden="true" /> : <EyeOff aria-hidden="true" />}
    </button>
  );
}
