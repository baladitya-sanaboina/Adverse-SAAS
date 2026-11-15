"use client";

import { CallManager } from "@/components/chat/call-manager";
import { TopbarStatus } from "@/components/chat/topbar-status";
import { ChatLauncher } from "@/components/chat/chat-launcher";
import Link from "next/link";
import Image from "next/image";
import { usePathname, useRouter } from "next/navigation";
import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { LogOut, Moon, SunMedium } from "lucide-react";
import { getBrandLogo } from "@/lib/branding";
import { DashboardContentLoader } from "@/components/loader/dashboard-content-loader";
import { AppFooter, ErrorState, ShellActions } from "@/components/foundation/ui-foundation";
import { navigationItems } from "@/lib/navigation";
import { loadCurrentUser, logout } from "@/lib/auth/client";
import type { CurrentUser } from "@/lib/auth/types";
import { useCompanyBranding } from "@/components/branding/company-branding-provider";

type Theme = "light" | "dark";

function resolvePageTitle(pathname: string) {
  const navigationTitle = navigationItems.find((item) => item.href === pathname)?.label;
  if (navigationTitle) return navigationTitle;
  const errorTitles: Record<string, string> = {
    "/401": "Unauthorized",
    "/403": "Forbidden",
    "/404": "Page Not Found",
    "/500": "Server Error",
  };
  if (errorTitles[pathname]) return errorTitles[pathname];
  const segment = pathname.split("/").filter(Boolean).at(-1);
  return segment ? segment.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "Workspace";
}

function Sidebar({
  roleLabel,
  user,
  items,
  theme,
  collapsed,
  onCollapse,
  onNavigate,
  onLogout,
}: {
  roleLabel: string;
  user: CurrentUser | null;
  items: (typeof navigationItems)[number][];
  theme: Theme;
  collapsed: boolean;
  onCollapse: () => void;
  onNavigate: (event: ReactMouseEvent<HTMLAnchorElement>, href: string) => void;
  onLogout: () => void;
}) {
  const pathname = usePathname();
  const branding = useCompanyBranding();
  const accountName = user?.user.name ?? roleLabel;
  const accountRole = user?.role.name ?? roleLabel;
  const accountInitials = accountName
    .split(/\\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

  return (
    <aside className="dash-sidebar">
      <div className="dash-sidebar-logo">
        <Link
          href="/dashboard"
          className={`dash-logo ${branding.logo_url ? "has-company-logo" : "has-default-logo"}`}
          aria-label={`${branding.company_name} dashboard`}
        >
          <Image
            src={
              branding.logo_url
                ? `/api/company/branding/file?path=${encodeURIComponent(branding.logo_url)}`
                : getBrandLogo(theme, collapsed ? "orbit" : "wordmark")
            }
            alt={branding.company_name}
            width={collapsed ? 240 : 560}
            height={collapsed ? 240 : 236}
            priority
            unoptimized={Boolean(branding.logo_url)}
          />
        </Link>
        <button
          type="button"
          className="dash-collapse"
          onClick={onCollapse}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <svg viewBox="0 0 24 24">
            <path d="m15 18-6-6 6-6" />
          </svg>
        </button>
      </div>
      <nav className="dash-sidebar-body" aria-label="Dashboard navigation">
        <p className="dash-nav-label">Navigation</p>
        {items.map((item) => {
          const active = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              title={item.label}
              onClick={(event) => onNavigate(event, item.href)}
              className={`dash-nav-item${active ? " active" : ""}`}
            >
              <span className="dash-nav-icon">
                <Icon width={18} height={18} strokeWidth={1.8} aria-hidden="true" />
              </span>
              <span className="dash-nav-text">{item.label}</span>
              <span className="dash-nav-arrow" aria-hidden="true">
                ›
              </span>
            </Link>
          );
        })}
      </nav>
      <div className="dash-sidebar-footer" title={`${accountName} · ${accountRole}`}>
        <div className="dash-avatar">
          {user?.user.profile_image_url ? (
            <Image
              unoptimized
              width={38}
              height={38}
              style={{ objectFit: "cover", borderRadius: "inherit" }}
              src={`/api/profile/image?path=${encodeURIComponent(user.user.profile_image_url)}`}
              alt=""
            />
          ) : (
            accountInitials
          )}
        </div>
        <div className="dash-user-info">
          <div className="dash-user-name">{accountName}</div>
          <div className="dash-user-plan">{accountRole} · Active</div>
        </div>
        <button type="button" className="dash-logout" aria-label="Log out" onClick={onLogout}>
          <LogOut width={16} height={16} strokeWidth={1.9} aria-hidden="true" />
          <span>Log out</span>
        </button>
      </div>
    </aside>
  );
}

function Topbar({
  title,
  role,
  user,
  onThemeChange,
  onMenu,
}: {
  title: string;
  role: string;
  user: CurrentUser | null;
  onThemeChange?: (theme: Theme) => void;
  onMenu: () => void;
}) {
  const branding = useCompanyBranding();
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const saved = localStorage.getItem("loopless-theme");
    const frame = window.requestAnimationFrame(() => {
      if (saved === "light" || saved === "dark") setTheme(saved);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    onThemeChange?.(theme);
  }, [onThemeChange, theme]);

  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    onThemeChange?.(next);
    document.documentElement.classList.toggle("dark", next === "dark");
    document.documentElement.dataset.looplessTheme = next;
    localStorage.setItem("loopless-theme", next);
  }

  return (
    <header className="dash-topbar">
      <div className="dash-topbar-nav">
        <button type="button" className="dash-menu-button" onClick={onMenu} aria-label="Open navigation menu">
          <span />
          <span />
          <span />
        </button>
        <Link
          href="/dashboard"
          className={`dash-mobile-brand ${branding.logo_url ? "has-company-logo" : "has-default-logo"}`}
          aria-label={`${branding.company_name} dashboard`}
        >
          <Image
            src={
              branding.logo_url
                ? `/api/company/branding/file?path=${encodeURIComponent(branding.logo_url)}`
                : getBrandLogo(theme, "orbit")
            }
            alt={branding.company_name}
            width={240}
            height={240}
            priority
            unoptimized={Boolean(branding.logo_url)}
          />
        </Link>
        <div className="dash-breadcrumb" aria-label="Breadcrumb">
          <Link href="/dashboard" className="dash-breadcrumb-home" aria-label="Dashboard home">
            <svg viewBox="0 0 24 24">
              <path d="M3 10.5 12 3l9 7.5V21h-6v-6h-6v6H3V10.5Z" />
            </svg>
          </Link>
          <span>/</span>
          {title === "Dashboard" ? (
            <strong aria-current="page">Dashboard</strong>
          ) : (
            <>
              <Link href="/dashboard">Dashboard</Link>
              <span>/</span>
              <strong aria-current="page">{title}</strong>
            </>
          )}
        </div>
      </div>
      <div className="dash-topbar-controls">
        <TopbarStatus />
        <button
          type="button"
          className={`dash-theme-switch ${theme}`}
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
        >
          <span className="dash-theme-icon sun">
            <SunMedium
              width={14}
              height={14}
              strokeWidth={1.8}
              style={{ display: "block", margin: "auto" }}
              aria-hidden="true"
            />
          </span>
          <span className="dash-theme-icon moon">
            <Moon
              width={14}
              height={14}
              strokeWidth={1.8}
              style={{ display: "block", margin: "auto" }}
              aria-hidden="true"
            />
          </span>
          <span className="dash-theme-knob" />
        </button>
        <ShellActions role={role} userName={user?.user.name ?? role} profileImageUrl={user?.user.profile_image_url} />
      </div>
    </header>
  );
}

export function DashboardShell({ children, roleLabel }: { children: ReactNode; roleLabel: string }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  // Chat is full screen (owner request 2026-11-14): entering it collapses the sidebar (it can
  // still be opened), and leaving it restores the sidebar if chat collapsed it.
  const chatMode = pathname === "/chat";
  const chatCollapsed = useRef(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [navigating, setNavigating] = useState(false);
  const [theme, setTheme] = useState<Theme>("dark");
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const navigationTimer = useRef<number | null>(null);
  const finishTimer = useRef<number | null>(null);
  const title = resolvePageTitle(pathname);
  const allowedModules = new Set(currentUser?.permissions.map((permission) => permission.module) ?? []);
  const enabledFeatures = (currentUser?.company?.subscription_features ?? {}) as Record<string, boolean>;
  const hasModuleAccess = (item: (typeof navigationItems)[number]) =>
    !("module" in item) || allowedModules.has(String(item.module));
  const hasPlanAccess = (item: (typeof navigationItems)[number]) =>
    !("feature" in item) || enabledFeatures[String(item.feature)] === true;
  const items = navigationItems.filter((item) => hasModuleAccess(item) && hasPlanAccess(item));
  const requestedItem = navigationItems.find((item) => item.href === pathname);
  const subscriptionDenied = Boolean(requestedItem && !hasPlanAccess(requestedItem));
  const permissionDenied = Boolean(requestedItem && !hasModuleAccess(requestedItem));
  const displayRole = currentUser?.role.name ?? roleLabel;

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (chatMode) {
        setCollapsed((current) => {
          chatCollapsed.current = !current;
          return true;
        });
      } else if (chatCollapsed.current) {
        chatCollapsed.current = false;
        setCollapsed(false);
      }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [chatMode]);

  useEffect(() => {
    let active = true;
    void loadCurrentUser()
      .then((user) => {
        if (active) setCurrentUser(user);
      })
      .catch(() => {
        if (active) router.replace("/login");
      })
      .finally(() => {
        if (active) setAuthLoading(false);
      });
    return () => {
      active = false;
    };
  }, [router]);

  useEffect(() => {
    const updateProfileImage = (event: Event) => {
      const profileImageUrl = (event as CustomEvent<string>).detail;
      setCurrentUser((current) =>
        current ? { ...current, user: { ...current.user, profile_image_url: profileImageUrl } } : current,
      );
    };
    window.addEventListener("loopless-profile-image-updated", updateProfileImage);
    return () => window.removeEventListener("loopless-profile-image-updated", updateProfileImage);
  }, []);

  useEffect(
    () => () => {
      if (navigationTimer.current) window.clearTimeout(navigationTimer.current);
      if (finishTimer.current) window.clearTimeout(finishTimer.current);
    },
    [],
  );

  function handleNavigation(event: ReactMouseEvent<HTMLAnchorElement>, href: string) {
    setMobileOpen(false);
    if (pathname === href) return;
    event.preventDefault();
    if (navigating) return;

    setNavigating(true);
    navigationTimer.current = window.setTimeout(() => {
      router.push(href);
      window.scrollTo({ top: 0, behavior: "smooth" });
      finishTimer.current = window.setTimeout(() => setNavigating(false), 250);
    }, 1800);
  }

  async function handleLogout() {
    setNavigating(true);
    await logout();
    router.replace("/login");
    router.refresh();
  }

  if (authLoading) return <DashboardContentLoader />;

  return (
    <div
      className={`dash-shell${collapsed ? " is-collapsed" : ""}${mobileOpen ? " is-mobile-open" : ""}${chatMode ? " is-chat" : ""}`}
    >
      <Sidebar
        roleLabel={displayRole}
        user={currentUser}
        items={items}
        theme={theme}
        collapsed={collapsed}
        onCollapse={() => setCollapsed((value) => !value)}
        onNavigate={handleNavigation}
        onLogout={() => void handleLogout()}
      />
      <button
        type="button"
        className="dash-backdrop"
        aria-label="Close navigation"
        onClick={() => setMobileOpen(false)}
      />
      <div className="dash-main">
        <Topbar
          title={title}
          role={displayRole}
          user={currentUser}
          onThemeChange={setTheme}
          onMenu={() => setMobileOpen(true)}
        />
        <main>
          {navigating ? (
            <DashboardContentLoader />
          ) : subscriptionDenied ? (
            <ErrorState code="403" title="Feature not available on your current plan" />
          ) : permissionDenied ? (
            <ErrorState code="403" title="You do not have permission to access this module" />
          ) : (
            children
          )}
        </main>
        <AppFooter role={displayRole} />
      </div>
      {!chatMode && <ChatLauncher />}
      <CallManager />
    </div>
  );
}
