"use client";

/*
 * Privacy eye for money on dashboards (owner decision 2026-11-14): amounts are hidden on every
 * visit and shown only after the eye is pressed, until the page is left. Outside a <MoneyPrivacy>
 * provider nothing is hidden, so other pages are unaffected.
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { Eye, EyeOff } from "lucide-react";

export const MASK = "••••";

type Privacy = { hidden: boolean; toggle: () => void };
const PrivacyContext = createContext<Privacy>({ hidden: false, toggle: () => {} });

export function MoneyPrivacy({ children }: { children: ReactNode }) {
  const [hidden, setHidden] = useState(true);
  const toggle = useCallback(() => setHidden((current) => !current), []);
  const value = useMemo(() => ({ hidden, toggle }), [hidden, toggle]);
  return <PrivacyContext.Provider value={value}>{children}</PrivacyContext.Provider>;
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
