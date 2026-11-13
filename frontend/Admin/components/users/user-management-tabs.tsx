"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { MailPlus, UserRoundCog } from "lucide-react";
import "@/styles/user-management-tabs.css";

const tabs = [
  {
    href: "/company/invitations",
    label: "Invitations",
    icon: MailPlus,
  },
  {
    href: "/company/users",
    label: "User assignments",
    icon: UserRoundCog,
  },
] as const;

export function UserManagementTabs() {
  const pathname = usePathname();

  return (
    <nav className="user-management-tabs" aria-label="Users and invitations">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const active = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={active ? "active" : ""}
            aria-current={active ? "page" : undefined}
          >
            <Icon aria-hidden="true" />
            <strong>{tab.label}</strong>
          </Link>
        );
      })}
    </nav>
  );
}
