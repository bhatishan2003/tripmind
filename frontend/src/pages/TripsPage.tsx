import { ArrowUpDown, PlusCircle, RefreshCw, Search, Ticket } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, api } from "@/api/client";
import { TripCardSkeleton } from "@/components/Spinner";
import { TripCard } from "@/components/TripCard";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import type { Trip } from "@/types";

type SortKey = "recent" | "destination" | "start_date";

export function TripsPage() {
  const { token, user } = useAuth();
  const toast = useToast();
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("recent");

  const load = useCallback(
    async (silent = false) => {
      if (!token) return;
      if (silent) setRefreshing(true);
      else setLoading(true);
      try {
        const data = await api.listTrips(token);
        setTrips(data);
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Could not load trips.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token, toast],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? trips.filter(
          (t) =>
            t.destination.toLowerCase().includes(q) ||
            t.interests.some((i) => i.toLowerCase().includes(q)),
        )
      : trips;
    return [...filtered].sort((a, b) => {
      if (sort === "destination") return a.destination.localeCompare(b.destination);
      if (sort === "start_date") return a.start_date.localeCompare(b.start_date);
      return b.created_at.localeCompare(a.created_at);
    });
  }, [trips, query, sort]);

  const firstName = user?.full_name?.split(" ")[0] || user?.email.split("@")[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            My Trips
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {loading
              ? "Loading your trips…"
              : `Hi ${firstName} — you have ${trips.length} trip${trips.length === 1 ? "" : "s"}.`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => load(true)}
            className="btn-outline"
            disabled={refreshing}
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            <span className="hidden sm:inline">Refresh</span>
          </button>
          <Link to="/trips/new" className="btn-primary">
            <PlusCircle className="h-4 w-4" />
            Plan new trip
          </Link>
        </div>
      </div>

      {trips.length > 0 || loading ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              className="input pl-9"
              placeholder="Filter by destination or interest…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Filter trips"
            />
          </div>
          <label className="inline-flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <ArrowUpDown className="h-4 w-4" />
            <span className="sr-only sm:not-sr-only">Sort</span>
            <select
              className="input !w-auto !py-2"
              value={sort}
              onChange={(e) => setSort(e.target.value as SortKey)}
              aria-label="Sort trips"
            >
              <option value="recent">Most recent</option>
              <option value="start_date">Start date</option>
              <option value="destination">Destination</option>
            </select>
          </label>
        </div>
      ) : null}

      {loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <TripCardSkeleton key={i} />
          ))}
        </div>
      ) : visible.length ? (
        <div className="space-y-3">
          {visible.map((trip) => (
            <TripCard key={trip.id} trip={trip} />
          ))}
        </div>
      ) : trips.length ? (
        <div className="card flex flex-col items-center gap-2 p-10 text-center">
          <Search className="h-8 w-8 text-slate-300 dark:text-slate-600" />
          <p className="font-medium text-slate-700 dark:text-slate-200">
            No trips match “{query}”
          </p>
          <button type="button" className="btn-ghost mt-1" onClick={() => setQuery("")}>
            Clear filter
          </button>
        </div>
      ) : (
        <div className="card flex flex-col items-center gap-3 p-12 text-center">
          <span className="grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-500 dark:bg-brand-950 dark:text-brand-400">
            <Ticket className="h-7 w-7" />
          </span>
          <div>
            <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
              No trips yet
            </p>
            <p className="mt-0.5 text-sm text-slate-500 dark:text-slate-400">
              Create your first itinerary — it only takes a moment.
            </p>
          </div>
          <Link to="/trips/new" className="btn-primary mt-1">
            <PlusCircle className="h-4 w-4" />
            Plan your first trip
          </Link>
        </div>
      )}
    </div>
  );
}
