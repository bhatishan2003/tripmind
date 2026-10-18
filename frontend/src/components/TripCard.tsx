import { ArrowRight, CalendarDays, MapPin, Users, Wallet } from "lucide-react";
import { Link } from "react-router-dom";

import { fmtDateRange, fmtMoney, titleCase, tripDays } from "@/lib/format";
import type { Trip } from "@/types";

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
  planned:
    "bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-300",
  completed:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  cancelled: "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300",
};

export function TripCard({ trip }: { trip: Trip }) {
  const estimated = trip.itinerary?.total_estimated_cost;
  const days = tripDays(trip.start_date, trip.end_date);

  return (
    <Link
      to={`/trips/${trip.id}`}
      className="card group block p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-300 hover:shadow-md dark:hover:border-brand-800"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <MapPin className="h-4 w-4 shrink-0 text-brand-500" />
            <h3 className="truncate text-lg font-semibold text-slate-900 group-hover:text-brand-700 dark:text-slate-100 dark:group-hover:text-brand-300">
              {trip.destination}
            </h3>
            <span
              className={`chip ${
                STATUS_STYLES[trip.status] ?? STATUS_STYLES.draft
              }`}
            >
              {titleCase(trip.status)}
            </span>
          </div>
          <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
            <span className="inline-flex items-center gap-1.5">
              <CalendarDays className="h-3.5 w-3.5" />
              {fmtDateRange(trip.start_date, trip.end_date)}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Users className="h-3.5 w-3.5" />
              {trip.travelers} traveler{trip.travelers === 1 ? "" : "s"}
            </span>
            <span>{titleCase(trip.travel_style)}</span>
            <span>{days} days</span>
          </div>
          {trip.interests.length ? (
            <div className="mt-2.5 flex flex-wrap gap-1.5">
              {trip.interests.slice(0, 5).map((interest) => (
                <span
                  key={interest}
                  className="chip bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                >
                  {interest}
                </span>
              ))}
              {trip.interests.length > 5 ? (
                <span className="chip text-slate-400">
                  +{trip.interests.length - 5}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className="flex items-center gap-6 sm:border-l sm:border-slate-100 sm:pl-6 dark:sm:border-slate-800">
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400">Budget</p>
            <p className="inline-flex items-center gap-1 font-semibold text-slate-900 dark:text-slate-100">
              <Wallet className="h-3.5 w-3.5 text-slate-400" />
              {fmtMoney(trip.budget, trip.currency)}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500 dark:text-slate-400">Est. cost</p>
            <p className="font-semibold text-slate-900 dark:text-slate-100">
              {estimated === undefined ? "—" : fmtMoney(estimated, trip.currency)}
            </p>
          </div>
          <span className="grid h-9 w-9 place-items-center rounded-full bg-slate-100 text-slate-500 transition-all group-hover:bg-brand-600 group-hover:text-white dark:bg-slate-800 dark:text-slate-400">
            <ArrowRight className="h-4 w-4" />
          </span>
        </div>
      </div>
    </Link>
  );
}
