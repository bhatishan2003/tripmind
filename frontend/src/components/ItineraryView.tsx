import {
  Banknote,
  CalendarDays,
  ChevronDown,
  Clock,
  Compass,
  MapPin,
  StickyNote,
  Tag,
  UtensilsCrossed,
  Wallet,
} from "lucide-react";
import { useEffect, useState } from "react";

import { fmtDate, fmtMoney, titleCase } from "@/lib/format";
import type { Activity, DayPlan, Trip } from "@/types";

const CATEGORY_STYLES: Record<string, string> = {
  food: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  culture: "bg-violet-100 text-violet-700 dark:bg-violet-950 dark:text-violet-300",
  nature: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  nightlife: "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
  history: "bg-orange-100 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
  shopping: "bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300",
  sightseeing: "bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-300",
};

function categoryClass(category: string): string {
  return CATEGORY_STYLES[category?.toLowerCase()] ?? CATEGORY_STYLES.sightseeing;
}

function ActivityRow({ activity }: { activity: Activity }) {
  const meta = [
    activity.location ? { icon: MapPin, text: activity.location } : null,
    activity.category ? { icon: Tag, text: titleCase(activity.category) } : null,
    activity.cost_estimate
      ? { icon: Banknote, text: `~${fmtMoney(activity.cost_estimate)}` }
      : null,
  ].filter(Boolean) as { icon: typeof MapPin; text: string }[];

  return (
    <li className="relative pl-8">
      <span className="absolute left-0 top-1.5 grid h-6 w-6 place-items-center rounded-full border border-brand-200 bg-brand-50 text-[10px] font-semibold text-brand-700 dark:border-brand-900 dark:bg-brand-950 dark:text-brand-300">
        <Compass className="h-3 w-3" />
      </span>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-900 dark:text-slate-100">
          <Clock className="h-3.5 w-3.5 text-brand-500" />
          {activity.time || "—"}
        </span>
        <span className="text-sm font-medium text-slate-800 dark:text-slate-200">
          {activity.title}
        </span>
        {activity.category ? (
          <span className={`chip ${categoryClass(activity.category)}`}>
            {titleCase(activity.category)}
          </span>
        ) : null}
      </div>
      {activity.description ? (
        <p className="mt-1 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
          {activity.description}
        </p>
      ) : null}
      {meta.length ? (
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
          {meta.map(({ icon: Icon, text }) => (
            <span
              key={text}
              className="inline-flex items-center gap-1 text-xs text-slate-500 dark:text-slate-400"
            >
              <Icon className="h-3 w-3" />
              {text}
            </span>
          ))}
        </div>
      ) : null}
    </li>
  );
}

function DayBlock({
  day,
  open,
  onToggle,
}: {
  day: DayPlan;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="print-day card overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
      >
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-600 text-sm font-bold text-white">
          {day.day_number}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
            {day.theme || `Day ${day.day_number}`}
          </span>
          <span className="block text-xs text-slate-500 dark:text-slate-400">
            {fmtDate(day.date)} · {day.activities.length} activities
          </span>
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      <div
        className={`grid transition-all duration-300 ease-in-out ${
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="min-h-0 overflow-hidden">
          <div className="space-y-4 border-t border-slate-100 px-4 py-4 dark:border-slate-800">
            {day.notes ? (
              <p className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950/50 dark:text-amber-200">
                <StickyNote className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {day.notes}
              </p>
            ) : null}

            {day.activities.length ? (
              <ol className="relative space-y-4 before:absolute before:left-3 before:top-2 before:h-[calc(100%-1rem)] before:w-px before:bg-slate-200 dark:before:bg-slate-800">
                {day.activities.map((activity, i) => (
                  <ActivityRow key={`${activity.time}-${i}`} activity={activity} />
                ))}
              </ol>
            ) : (
              <p className="text-sm text-slate-500 dark:text-slate-400">
                No activities planned for this day.
              </p>
            )}

            {day.meals.length ? (
              <div className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-800/50">
                <UtensilsCrossed className="h-3.5 w-3.5 text-slate-500" />
                {day.meals.map((meal) => (
                  <span
                    key={meal}
                    className="chip bg-white text-slate-600 ring-1 ring-slate-200 dark:bg-slate-900 dark:text-slate-300 dark:ring-slate-700"
                  >
                    {meal}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ItineraryView({
  trip,
  forceExpanded = false,
}: {
  trip: Trip;
  forceExpanded?: boolean;
}) {
  const itinerary = trip.itinerary;
  const [openDays, setOpenDays] = useState<Set<number>>(new Set([1]));

  useEffect(() => {
    if (forceExpanded && itinerary) {
      setOpenDays(new Set(itinerary.days.map((d) => d.day_number)));
    }
  }, [forceExpanded, itinerary]);

  if (!itinerary) {
    return (
      <div className="card flex flex-col items-center gap-2 p-10 text-center">
        <Compass className="h-8 w-8 text-slate-300 dark:text-slate-600" />
        <p className="font-medium text-slate-700 dark:text-slate-200">No itinerary yet</p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Use “Regenerate itinerary” to generate a day-by-day plan.
        </p>
      </div>
    );
  }

  const toggleDay = (n: number) => {
    setOpenDays((prev) => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });
  };

  const metrics = [
    {
      icon: Wallet,
      label: "Est. total cost",
      value: fmtMoney(itinerary.total_estimated_cost, itinerary.currency || trip.currency),
    },
    { icon: Banknote, label: "Trip budget", value: fmtMoney(trip.budget, trip.currency) },
    { icon: CalendarDays, label: "Days", value: String(itinerary.days.length) },
  ];

  return (
    <div className="space-y-5">
      <div className="card space-y-3 p-5">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          <Compass className="h-4 w-4 text-brand-500" />
          Itinerary Summary
        </h2>
        <p className="text-sm leading-relaxed text-slate-700 dark:text-slate-300">
          {itinerary.summary || "—"}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {metrics.map(({ icon: Icon, label, value }) => (
          <div key={label} className="card flex items-center gap-3 p-4">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-950 dark:text-brand-400">
              <Icon className="h-5 w-5" />
            </span>
            <div>
              <p className="text-xs text-slate-500 dark:text-slate-400">{label}</p>
              <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">{value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-3">
        {itinerary.days.map((day) => (
          <DayBlock
            key={day.day_number}
            day={day}
            open={forceExpanded || openDays.has(day.day_number)}
            onToggle={() => toggleDay(day.day_number)}
          />
        ))}
      </div>
    </div>
  );
}
