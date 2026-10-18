import { KeyRound, Plane, Sparkles, UserPlus } from "lucide-react";
import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Spinner } from "@/components/Spinner";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";

type Tab = "login" | "register";

export function LoginPage() {
  const { token, ready, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const [tab, setTab] = useState<Tab>("login");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("demo1234");
  const [fullName, setFullName] = useState("");
  const [confirm, setConfirm] = useState("");

  if (ready && token) {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from && from !== "/login" ? from : "/"} replace />;
  }

  const redirect = () => {
    const from = (location.state as { from?: string } | null)?.from;
    navigate(from && from !== "/login" ? from : "/", { replace: true });
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError("Email and password are required.");
      return;
    }
    if (tab === "register" && password !== confirm) {
      setError("Passwords do not match.");
      return;
    }

    setBusy(true);
    try {
      if (tab === "login") {
        await login(email.trim(), password);
        toast.success("Welcome back!");
      } else {
        await register(email.trim(), password, fullName.trim() || null);
        toast.success("Account created — you're signed in!");
      }
      redirect();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong.";
      setError(message);
      toast.error(message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative grid min-h-screen lg:grid-cols-2">
      <div className="absolute right-4 top-4 z-10">
        <ThemeToggle />
      </div>

      {/* Hero */}
      <div className="relative hidden overflow-hidden bg-gradient-to-br from-brand-600 via-brand-700 to-indigo-800 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="absolute -right-20 -top-20 h-72 w-72 rounded-full bg-white/10 blur-2xl" />
        <div className="absolute -bottom-24 -left-10 h-80 w-80 rounded-full bg-indigo-400/20 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-white/15 backdrop-blur">
            <Plane className="h-6 w-6" />
          </span>
          <span className="text-lg font-semibold">AI Travel Planner</span>
        </div>
        <div className="relative space-y-5">
          <h1 className="max-w-md text-4xl font-bold leading-tight">
            Plan unforgettable trips in seconds.
          </h1>
          <p className="max-w-md text-brand-100">
            Describe your destination, budget, and style — get a day-by-day itinerary
            with activities, meals, and cost estimates.
          </p>
          <ul className="space-y-2 text-sm text-brand-100">
            {[
              "LLM-generated or offline-template itineraries",
              "Budget-aware activity suggestions",
              "Edit, regenerate, and export with one click",
            ].map((item) => (
              <li key={item} className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 shrink-0" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-brand-200">FastAPI · React · Tailwind CSS</p>
      </div>

      {/* Form */}
      <div className="flex items-center justify-center px-5 py-12 sm:px-8">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <span className="inline-flex items-center gap-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
              <Plane className="h-5 w-5 text-brand-600" />
              AI Travel Planner
            </span>
          </div>

          <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            {tab === "login" ? "Welcome back" : "Create your account"}
          </h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {tab === "login"
              ? "Sign in to plan and manage your trips."
              : "Start planning your next adventure."}
          </p>

          <div className="mt-6 grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1 dark:bg-slate-800">
            {(
              [
                { id: "login", label: "Login", icon: KeyRound },
                { id: "register", label: "Register", icon: UserPlus },
              ] as const
            ).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => {
                  setTab(id);
                  setError(null);
                }}
                className={`inline-flex items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
                  tab === id
                    ? "bg-white text-slate-900 shadow-sm dark:bg-slate-950 dark:text-slate-100"
                    : "text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>

          <form onSubmit={submit} className="mt-6 space-y-4">
            {tab === "register" ? (
              <div>
                <label className="label" htmlFor="fullName">
                  Full name <span className="text-slate-400">(optional)</span>
                </label>
                <input
                  id="fullName"
                  className="input"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Ada Lovelace"
                  autoComplete="name"
                />
              </div>
            ) : null}

            <div>
              <label className="label" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </div>

            <div>
              <label className="label" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete={tab === "login" ? "current-password" : "new-password"}
                required
              />
            </div>

            {tab === "register" ? (
              <div>
                <label className="label" htmlFor="confirm">
                  Confirm password
                </label>
                <input
                  id="confirm"
                  type="password"
                  className="input"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="new-password"
                />
              </div>
            ) : null}

            {error ? (
              <p
                role="alert"
                className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
              >
                {error}
              </p>
            ) : null}

            <button type="submit" className="btn-primary w-full" disabled={busy}>
              {busy ? <Spinner /> : tab === "login" ? <KeyRound className="h-4 w-4" /> : <UserPlus className="h-4 w-4" />}
              {busy
                ? tab === "login"
                  ? "Signing in…"
                  : "Creating account…"
                : tab === "login"
                  ? "Sign in"
                  : "Create account"}
            </button>
          </form>

          {tab === "login" ? (
            <p className="mt-4 text-center text-xs text-slate-400">
              Demo credentials pre-filled (after seeding): demo@example.com / demo1234
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
