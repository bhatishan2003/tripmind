import { ArrowLeft, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError, api } from "@/api/client";
import { DestinationInput } from "@/components/DestinationInput";
import { GenerationProgress } from "@/components/GenerationProgress";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { CURRENCIES, INTEREST_CHOICES, TRAVEL_STYLES } from "@/lib/constants";
import { titleCase, todayPlusDays } from "@/lib/format";
import type { TripCreatePayload } from "@/types";

export function NewTripPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();

  const [destination, setDestination] = useState("");
  const [startDate, setStartDate] = useState(todayPlusDays(30));
  const [endDate, setEndDate] = useState(todayPlusDays(33));
  const [budget, setBudget] = useState("2200");
  const [currency, setCurrency] = useState<string>(CURRENCIES[0]);
  const [travelers, setTravelers] = useState(2);
  const [style, setStyle] = useState<string>("balanced");
  const [interests, setInterests] = useState<string[]>(["culture", "food"]);
  const [customInterests, setCustomInterests] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const toggleInterest = (interest: string) => {
    setInterests((prev) =>
      prev.includes(interest)
        ? prev.filter((i) => i !== interest)
        : [...prev, interest],
    );
  };

  const validate = (): string | null => {
    if (!destination.trim()) return "Destination is required.";
    if (!budget || Number(budget) <= 0) return "Budget must be greater than 0.";
    if (endDate < startDate) return "End date must be on or after the start date.";
    const days =
      (new Date(`${endDate}T00:00:00`).getTime() -
        new Date(`${startDate}T00:00:00`).getTime()) /
      86_400_000;
    if (days > 60) return "Trips longer than 60 days aren't supported yet.";
    return null;
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const problem = validate();
    if (problem) {
      setError(problem);
      toast.warning(problem);
      return;
    }
    if (!token) return;
    setError(null);

    const allInterests = [
      ...interests,
      ...customInterests
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
    ];

    const payload: TripCreatePayload = {
      destination: destination.trim(),
      start_date: startDate,
      end_date: endDate,
      budget: String(budget),
      currency,
      travelers,
      travel_style: style,
      interests: [...new Set(allInterests)],
    };

    setSubmitting(true);
    try {
      const trip = await api.createTrip(token, payload);
      toast.success(`Trip to ${trip.destination} created!`);
      navigate(`/trips/${trip.id}`, { replace: true });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not create trip.";
      setError(message);
      toast.error(message);
      setSubmitting(false);
    }
  };

  if (submitting) {
    return (
      <div className="mx-auto max-w-2xl">
        <div className="card p-8">
          <GenerationProgress destination={destination.trim()} />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <Link to="/" className="btn-ghost -ml-2 mb-2">
          <ArrowLeft className="h-4 w-4" />
          Back to My Trips
        </Link>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
          Plan a new trip
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Tell us where and how you like to travel — we'll do the rest. Prefer to chat?{" "}
          <Link to="/chat" className="font-medium text-brand-600 hover:underline dark:text-brand-400">
            Ask the assistant
          </Link>
          .
        </p>
      </div>

      <form onSubmit={submit} className="card space-y-6 p-6">
        <div className="space-y-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-brand-100 text-xs text-brand-700 dark:bg-brand-950 dark:text-brand-300">
              1
            </span>
            Destination & dates
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="sm:col-span-2">
              <label className="label" htmlFor="destination">
                Destination <span className="text-rose-500">*</span>
              </label>
              <DestinationInput value={destination} onChange={setDestination} />
            </div>
            <div>
              <label className="label" htmlFor="startDate">
                Start date
              </label>
              <input
                id="startDate"
                type="date"
                className="input"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="label" htmlFor="endDate">
                End date
              </label>
              <input
                id="endDate"
                type="date"
                className="input"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                required
              />
            </div>
          </div>
        </div>

        <div className="space-y-4 border-t border-slate-100 pt-6 dark:border-slate-800">
          <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-brand-100 text-xs text-brand-700 dark:bg-brand-950 dark:text-brand-300">
              2
            </span>
            Budget, travelers & style
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="budget">
                Budget
              </label>
              <input
                id="budget"
                type="number"
                min={1}
                step="50"
                className="input"
                value={budget}
                onChange={(e) => setBudget(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="label" htmlFor="currency">
                Currency
              </label>
              <select
                id="currency"
                className="input"
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
              >
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="travelers">
                Travelers
              </label>
              <input
                id="travelers"
                type="number"
                min={1}
                max={50}
                className="input"
                value={travelers}
                onChange={(e) => setTravelers(Number(e.target.value))}
              />
            </div>
          </div>

          <div>
            <span className="label">Travel style</span>
            <div className="flex flex-wrap gap-2">
              {TRAVEL_STYLES.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setStyle(s)}
                  className={`rounded-xl border px-3.5 py-2 text-sm font-medium transition-all ${
                    style === s
                      ? "border-brand-500 bg-brand-50 text-brand-700 dark:border-brand-600 dark:bg-brand-950 dark:text-brand-300"
                      : "border-slate-200 text-slate-600 hover:border-slate-300 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  }`}
                >
                  {titleCase(s)}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4 border-t border-slate-100 pt-6 dark:border-slate-800">
          <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-brand-100 text-xs text-brand-700 dark:bg-brand-950 dark:text-brand-300">
              3
            </span>
            Interests
          </h2>
          <div className="flex flex-wrap gap-2">
            {INTEREST_CHOICES.map((interest) => {
              const active = interests.includes(interest);
              return (
                <button
                  key={interest}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleInterest(interest)}
                  className={`chip border px-3 py-1.5 transition-all ${
                    active
                      ? "border-brand-500 bg-brand-50 text-brand-700 dark:border-brand-600 dark:bg-brand-950 dark:text-brand-300"
                      : "border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  }`}
                >
                  {interest}
                </button>
              );
            })}
          </div>
          <div>
            <label className="label" htmlFor="customInterests">
              Other interests <span className="text-slate-400">(comma-separated)</span>
            </label>
            <input
              id="customInterests"
              className="input"
              value={customInterests}
              onChange={(e) => setCustomInterests(e.target.value)}
              placeholder="e.g. tea ceremonies, photography"
            />
          </div>
        </div>

        {error ? (
          <p
            role="alert"
            className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
          >
            {error}
          </p>
        ) : null}

        <div className="flex flex-col gap-3 border-t border-slate-100 pt-6 sm:flex-row sm:justify-end dark:border-slate-800">
          <Link to="/" className="btn-outline">
            Cancel
          </Link>
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? <Spinner /> : <Wand2 className="h-4 w-4" />}
            Create trip & generate itinerary
          </button>
        </div>
        <p className="flex items-center gap-1.5 text-xs text-slate-400">
          <Sparkles className="h-3.5 w-3.5" />
          Generation can take up to ~60 seconds when an LLM key is configured.
        </p>
      </form>
    </div>
  );
}
