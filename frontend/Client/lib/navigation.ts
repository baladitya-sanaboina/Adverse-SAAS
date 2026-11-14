import { CalendarDays, Gauge, ReceiptText, UserRound } from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/calendar", label: "Content Calendar", icon: CalendarDays },
  { href: "/billing", label: "Billing", icon: ReceiptText },
  { href: "/profile", label: "Profile", icon: UserRound },
] as const;
