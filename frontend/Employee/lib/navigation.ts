import { Banknote, ChartNoAxesCombined, ClipboardList, Contact, Gauge, UserRound } from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/tasks", label: "My Tasks", icon: ClipboardList, module: "TASKS" },
  { href: "/salary", label: "My Salary", icon: Banknote, module: "TASKS" },
  { href: "/clients", label: "Clients", icon: Contact, module: "CLIENTS", feature: "CLIENT_MANAGEMENT" },
  { href: "/crm", label: "CRM", icon: ChartNoAxesCombined, module: "CRM", feature: "CRM" },
  { href: "/profile", label: "Profile", icon: UserRound },
] as const;
