import {
  Banknote,
  CalendarClock,
  CalendarDays,
  CalendarRange,
  ChartNoAxesCombined,
  ClipboardList,
  Contact,
  Gauge,
  Mail,
  MessagesSquare,
  UserRound,
} from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/tasks", label: "My Tasks", icon: ClipboardList, module: "TASKS" },
  { href: "/salary", label: "My Salary", icon: Banknote, module: "TASKS" },
  { href: "/calendar", label: "Work Calendar", icon: CalendarDays },
  // Content calendars of the clients the admin gave access to (owner request 2026-11-26).
  { href: "/content-calendar", label: "Content Calendar", icon: CalendarRange },
  { href: "/chat", label: "Chat", icon: MessagesSquare },
  // Mail opens in its own tab (owner request 2026-11-15).
  { href: "/mail", label: "Mail", icon: Mail, newTab: true },
  // Events, meetings, deadlines and todos (owner request 2026-11-15).
  { href: "/agenda", label: "Calendar", icon: CalendarClock },
  { href: "/clients", label: "Clients", icon: Contact, module: "CLIENTS", feature: "CLIENT_MANAGEMENT" },
  { href: "/crm", label: "CRM", icon: ChartNoAxesCombined, module: "CRM", feature: "CRM" },
  { href: "/profile", label: "Profile", icon: UserRound },
] as const;
