import {
  ChartNoAxesCombined,
  ClipboardList,
  Contact,
  Gauge,
  HandCoins,
  NotebookTabs,
  UsersRound,
  UserRound,
} from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/tasks", label: "My Tasks", icon: ClipboardList, module: "TASKS" },
  { href: "/earnings", label: "My Earnings", icon: HandCoins, module: "TASKS" },
  { href: "/sheets", label: "Payment Sheets", icon: NotebookTabs, module: "TASKS" },
  { href: "/employees", label: "Team", icon: UsersRound, module: "EMPLOYEES", feature: "EMPLOYEE_MANAGEMENT" },
  { href: "/clients", label: "Clients", icon: Contact, module: "CLIENTS", feature: "CLIENT_MANAGEMENT" },
  { href: "/crm", label: "CRM", icon: ChartNoAxesCombined, module: "CRM", feature: "CRM" },
  { href: "/profile", label: "Profile", icon: UserRound },
] as const;
