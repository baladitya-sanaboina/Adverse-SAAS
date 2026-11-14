import { CalendarDays, Gauge, MessagesSquare, ReceiptText, UserRound } from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/calendar", label: "Content Calendar", icon: CalendarDays },
  { href: "/chat", label: "Chat", icon: MessagesSquare },
  { href: "/billing", label: "Billing", icon: ReceiptText },
  { href: "/profile", label: "Profile", icon: UserRound },
] as const;
