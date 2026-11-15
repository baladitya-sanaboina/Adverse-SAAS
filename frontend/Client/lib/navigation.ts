import { CalendarDays, Gauge, Mail, MessagesSquare, ReceiptText, UserRound } from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/calendar", label: "Content Calendar", icon: CalendarDays },
  { href: "/chat", label: "Chat", icon: MessagesSquare },
  // Mail opens in its own tab (owner request 2026-11-15).
  { href: "/mail", label: "Mail", icon: Mail, newTab: true },
  { href: "/billing", label: "Billing", icon: ReceiptText },
  { href: "/profile", label: "Profile", icon: UserRound },
] as const;
