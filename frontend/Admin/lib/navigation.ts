import {
  ChartNoAxesCombined,
  Contact,
  Gauge,
  Settings,
  UserRound,
  UsersRound,
} from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  {
    href: "/employees",
    label: "Employees",
    icon: UsersRound,
    module: "EMPLOYEES",
    feature: "EMPLOYEE_MANAGEMENT",
  },
  { href: "/clients", label: "Clients", icon: Contact, module: "CLIENTS", feature: "CLIENT_MANAGEMENT" },
  { href: "/crm", label: "CRM", icon: ChartNoAxesCombined, module: "CRM", feature: "CRM" },
  { href: "/profile", label: "My Profile", icon: UserRound },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;
