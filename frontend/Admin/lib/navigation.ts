import {
  ChartColumn,
  ChartNoAxesCombined,
  ClipboardList,
  Contact,
  Gauge,
  NotebookTabs,
  ReceiptText,
  Settings,
  UserRound,
  UsersRound,
  Wallet,
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
  { href: "/tasks", label: "Tasks", icon: ClipboardList, module: "TASKS", feature: "TASKS" },
  // Admin-only money pages: gated by role permission, not by the subscription plan.
  { href: "/payments", label: "Payments", icon: Wallet, module: "FINANCE" },
  { href: "/sheets", label: "Payment Sheets", icon: NotebookTabs, module: "FINANCE" },
  { href: "/invoices", label: "Invoices", icon: ReceiptText, module: "FINANCE" },
  { href: "/reports", label: "Reports", icon: ChartColumn, module: "REPORTS" },
  { href: "/crm", label: "CRM", icon: ChartNoAxesCombined, module: "CRM", feature: "CRM" },
  { href: "/profile", label: "My Profile", icon: UserRound },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;
