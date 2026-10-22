import {
  LogOut,
  Menu,
  MessageCircle,
  Plane,
  PlusCircle,
  Server,
  Ticket,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { HealthBadge } from "@/components/HealthBadge";
import { ThemeToggle } from "@/components/ThemeToggle";
import { API_BASE_URL } from "@/lib/constants";
import { initials } from "@/lib/format";
import { useAuth } from "@/context/AuthContext";

const NAV = [
  { to: "/", label: "My Trips", icon: Ticket, end: true },
  { to: "/chat", label: "Chat", icon: MessageCircle, end: false },
  { to: "/trips/new", label: "New Trip", icon: PlusCircle, end: false },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const nav = (
    <nav className="flex flex-1 flex-col gap-1">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors ${
              isActive
                ? "bg-brand-50 text-brand-700 dark:bg-brand-950 dark:text-brand-300"
                : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
            }`
          }
        >
          <Icon className="h-4 w-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  );

  const sidebarInner = (
    <div className="flex h-full flex-col gap-6 p-5">
      <div className="flex items-center gap-3">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-600 text-white shadow-sm">
          <Plane className="h-5 w-5" />
        </span>
        <div>
          <p className="text-sm font-semibold leading-tight text-slate-900 dark:text-slate-100">
            AI Travel Planner
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">Chat + planner</p>
        </div>
      </div>

      {nav}

      <div className="space-y-3 border-t border-slate-200 pt-4 dark:border-slate-800">
        <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <Server className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate" title={API_BASE_URL}>
            {API_BASE_URL}
          </span>
        </div>
        <div className="flex items-center justify-between gap-2">
          <HealthBadge />
          <ThemeToggle />
        </div>
      </div>

      {user ? (
        <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 dark:border-slate-800 dark:bg-slate-900">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700 dark:bg-brand-950 dark:text-brand-300">
            {initials(user.full_name, user.email)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium text-slate-800 dark:text-slate-200">
              {user.full_name || user.email.split("@")[0]}
            </p>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">{user.email}</p>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            className="btn-ghost !p-1.5"
            title="Log out"
            aria-label="Log out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      ) : null}
    </div>
  );

  return (
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside className="no-print hidden w-72 shrink-0 border-r border-slate-200 bg-white/60 backdrop-blur lg:block dark:border-slate-800 dark:bg-slate-950/60">
        <div className="sticky top-0 h-screen">{sidebarInner}</div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div className="no-print fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
            onClick={() => setMobileOpen(false)}
            aria-hidden
          />
          <div className="absolute inset-y-0 left-0 w-72 border-r border-slate-200 bg-white animate-fade-in dark:border-slate-800 dark:bg-slate-950">
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="btn-ghost absolute right-3 top-3 !p-1.5"
              aria-label="Close menu"
            >
              <X className="h-4 w-4" />
            </button>
            {sidebarInner}
          </div>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-30 flex items-center gap-3 border-b border-slate-200 bg-white/80 px-4 py-3 backdrop-blur lg:hidden dark:border-slate-800 dark:bg-slate-950/80">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="btn-ghost !p-2"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
          <span className="flex items-center gap-2 font-semibold text-slate-900 dark:text-slate-100">
            <Plane className="h-4 w-4 text-brand-600" />
            AI Travel Planner
          </span>
          <div className="ml-auto flex items-center gap-2">
            <HealthBadge />
            <ThemeToggle />
          </div>
        </header>

        <main className="print-area mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 lg:py-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
