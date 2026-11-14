import { Gauge, ReceiptText, UserRound } from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/billing", label: "Billing", icon: ReceiptText },
  { href: "/profile", label: "Profile", icon: UserRound },
] as const;
