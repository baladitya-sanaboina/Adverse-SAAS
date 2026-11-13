import { Gauge, UserRound } from "lucide-react";

export const navigationItems = [
  { href: "/dashboard", label: "Dashboard", icon: Gauge },
  { href: "/profile", label: "Profile", icon: UserRound },
] as const;
