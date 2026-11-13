import {
  ChartNoAxesCombined,
  Contact,
  Gauge,
  UsersRound,
  UserRound,
} from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/employees", label: "Team", icon: UsersRound, module: "EMPLOYEES", feature: "EMPLOYEE_MANAGEMENT" },
  { href: "/clients", label: "Clients", icon: Contact, module: "CLIENTS", feature: "CLIENT_MANAGEMENT" },
  { href: "/crm", label: "CRM", icon: ChartNoAxesCombined, module: "CRM", feature: "CRM" },
  { href: "/profile", label: "Profile", icon: UserRound },
] as const;
