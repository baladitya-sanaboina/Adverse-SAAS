// Payment sheets overview (owner request 2026-11-14): GET /company/finance/sheets, Admin only.
import type { SheetLine } from "@loopless-shared/production/payment-sheets";

export type SheetStatus = "OVER" | "USED_UP" | "NEAR" | "OK";

export type PaymentSheetRow = {
  index: number;
  start: string;
  end: string | null;
  paid: string;
  carried_in: string;
  used: string;
  left: string;
  items: number;
  ran_out_on: string | null;
  lines: SheetLine[];
};

export type SheetOwner = {
  kind: "MANAGER" | "CLIENT";
  id: string;
  name: string;
  code: string;
  status: SheetStatus;
  left: string;
  pot: string;
  percent_used: number;
  ran_out_on: string | null;
  sheets: PaymentSheetRow[];
};

export type SheetsOverview = { currency: string; managers: SheetOwner[]; clients: SheetOwner[] };

export const STATUS_TEXT: Record<SheetStatus, string> = {
  OVER: "Needs top-up",
  USED_UP: "Used up",
  NEAR: "Running low",
  OK: "OK",
};

/** One line saying where the current sheet stands, e.g. "₹200 left of ₹10,300 · 98% used". */
export function ownerLine(
  owner: SheetOwner,
  money: (value: string | number, currency?: string) => string,
  currency: string,
) {
  const left = Number(owner.left);
  if (left < 0) return `Over by ${money(-left, currency)}`;
  return `${money(left, currency)} left of ${money(owner.pot, currency)} · ${Math.round(owner.percent_used)}% used`;
}
