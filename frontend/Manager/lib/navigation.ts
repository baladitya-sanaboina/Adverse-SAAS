import {
  CalendarClock,
  CalendarDays,
  CalendarRange,
  ChartNoAxesCombined,
  ClipboardList,
  Contact,
  Gauge,
  HandCoins,
  Mail,
  MessagesSquare,
  NotebookTabs,
  UserRound,
  UsersRound,
} from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/tasks", label: "My Tasks", icon: ClipboardList, module: "TASKS" },
  { href: "/earnings", label: "My Earnings", icon: HandCoins, module: "TASKS" },
  { href: "/sheets", label: "Payment Sheets", icon: NotebookTabs, module: "TASKS" },
  { href: "/calendar", label: "Work Calendar", icon: CalendarDays },
  // Content calendars of the clients the admin gave access to (owner request 2026-11-26).
  { href: "/content-calendar", label: "Content Calendar", icon: CalendarRange },
  { href: "/chat", label: "Chat", icon: MessagesSquare },
  // Mail opens in its own tab (owner request 2026-11-15).
  { href: "/mail", label: "Mail", icon: Mail, newTab: true },
  // Events, meetings, deadlines and todos (owner request 2026-11-15).
  { href: "/agenda", label: "Calendar", icon: CalendarClock },
  { href: "/employees", label: "Team", icon: UsersRound, module: "EMPLOYEES", feature: "EMPLOYEE_MANAGEMENT" },
  { href: "/clients", label: "Clients", icon: Contact, module: "CLIENTS", feature: "CLIENT_MANAGEMENT" },
  { href: "/crm", label: "CRM", icon: ChartNoAxesCombined, module: "CRM", feature: "CRM" },
  { href: "/profile", label: "Profile", icon: UserRound },
] as const;
