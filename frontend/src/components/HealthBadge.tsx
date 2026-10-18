import { Activity, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { API_BASE_URL, api } from "@/api/client";
import { Spinner } from "@/components/Spinner";

type Status = "loading" | "online" | "offline";

export function HealthBadge() {
  const [status, setStatus] = useState<Status>("loading");

  const check = useCallback(async () => {
    setStatus("loading");
    try {
      await api.health();
      setStatus("online");
    } catch {
      setStatus("offline");
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  const dot =
    status === "online"
      ? "bg-emerald-500"
      : status === "offline"
        ? "bg-rose-500"
        : "bg-amber-500";

  return (
    <button
      type="button"
      onClick={check}
      title={`Backend: ${API_BASE_URL}`}
      className="group inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/70 px-2.5 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-300 dark:hover:bg-slate-800"
    >
      {status === "loading" ? (
        <Spinner className="h-3 w-3 text-amber-500" />
      ) : (
        <span className="relative flex h-2 w-2">
          <span className={`absolute inline-flex h-full w-full rounded-full ${dot} opacity-60 ${status === "online" ? "animate-ping" : ""}`} />
          <span className={`relative inline-flex h-2 w-2 rounded-full ${dot}`} />
        </span>
      )}
      <Activity className="h-3 w-3" />
      <span className="hidden sm:inline">
        {status === "online" ? "API online" : status === "offline" ? "API offline" : "Checking…"}
      </span>
      <RefreshCw className="h-3 w-3 opacity-0 transition-opacity group-hover:opacity-60" />
    </button>
  );
}
