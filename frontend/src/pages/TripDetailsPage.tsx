import {
  ArrowLeft,
  CalendarDays,
  ChevronDown,
  Code2,
  MapPin,
  Pencil,
  Printer,
  RefreshCw,
  Sparkles,
  Trash2,
  Users,
  Wallet,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError, api } from "@/api/client";
import { ConfirmDialog, Modal } from "@/components/Modal";
import { GenerationProgress } from "@/components/GenerationProgress";
import { ItineraryView } from "@/components/ItineraryView";
import { FullPageSpinner, Spinner } from "@/components/Spinner";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { INTEREST_CHOICES, TRAVEL_STYLES } from "@/lib/constants";
import { fmtDateRange, fmtMoney, titleCase } from "@/lib/format";
import type { Trip, TripUpdatePayload } from "@/types";

export function TripDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { token } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();

  const [trip, setTrip] = useState<Trip | null>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(
    async (silent = false) => {
      if (!token || !id) return;
      if (silent) setRefreshing(true);
      try {
        const data = await api.getTrip(token, id);
        setTrip(data);
        setNotFound(false);
      } catch (err) {
        if (!silent) {
          setNotFound(true);
          toast.error(err instanceof ApiError ? err.message : "Could not load trip.");
        }
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token, id, toast],
  );

  useEffect(() => {
    setLoading(true);
    setTrip(null);
    void load();
  }, [load]);

  const handleRegenerate = async () => {
    if (!token || !trip) return;
    setRegenerating(true);
    try {
      const updated = await api.regenerate(token, trip.id);
      setTrip(updated);
      toast.success("Itinerary regenerated!");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Regeneration failed.");
    } finally {
      setRegenerating(false);
    }
  };

  const handleDelete = async () => {
    if (!token || !trip) return;
    setDeleting(true);
    try {
      await api.deleteTrip(token, trip.id);
      toast.success("Trip deleted.");
      navigate("/", { replace: true });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Delete failed.");
      setDeleting(false);
    }
  };

  const handleExport = () => {
    setExporting(true);
    window.setTimeout(() => {
      window.print();
      setExporting(false);
    }, 150);
  };

  if (loading) return <FullPageSpinner label="Loading trip…" />;

  if (notFound || !trip) {
    return (
      <div className="card flex flex-col items-center gap-3 p-12 text-center">
        <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Trip not found
        </p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          It may have been deleted or you don't have access.
        </p>
        <Link to="/" className="btn-primary mt-2">
          <ArrowLeft className="h-4 w-4" />
          Back to My Trips
        </Link>
      </div>
    );
  }

  const meta = [
    { icon: CalendarDays, text: fmtDateRange(trip.start_date, trip.end_date) },
    { icon: Users, text: `${trip.travelers} traveler${trip.travelers === 1 ? "" : "s"}` },
    { icon: Wallet, text: fmtMoney(trip.budget, trip.currency) },
    { icon: Sparkles, text: titleCase(trip.travel_style) },
  ];

  return (
    <div className="space-y-6">
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <Link to="/" className="btn-ghost -ml-2">
          <ArrowLeft className="h-4 w-4" />
          My Trips
        </Link>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn-outline"
            onClick={() => load(true)}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </button>
          <button type="button" className="btn-outline" onClick={handleExport}>
            <Printer className="h-4 w-4" />
            Export / Print
          </button>
          <button type="button" className="btn-outline" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            Edit
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleRegenerate}
            disabled={regenerating}
          >
            {regenerating ? <Spinner /> : <Sparkles className="h-4 w-4" />}
            Regenerate
          </button>
          <button
            type="button"
            className="btn-danger"
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900 dark:text-slate-100">
            <MapPin className="h-6 w-6 text-brand-500" />
            {trip.destination}
          </h1>
          <span className="chip bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-300">
            {titleCase(trip.status)}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-slate-500 dark:text-slate-400">
          {meta.map(({ icon: Icon, text }) => (
            <span key={text} className="inline-flex items-center gap-1.5">
              <Icon className="h-4 w-4" />
              {text}
            </span>
          ))}
        </div>
        {trip.interests.length ? (
          <div className="flex flex-wrap gap-1.5">
            {trip.interests.map((interest) => (
              <span
                key={interest}
                className="chip bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
              >
                {interest}
              </span>
            ))}
          </div>
        ) : null}
      </header>

      {regenerating ? (
        <div className="no-print card p-8">
          <GenerationProgress destination={trip.destination} />
        </div>
      ) : (
        <ItineraryView trip={trip} forceExpanded={exporting} />
      )}

      <div className="no-print">
        <button
          type="button"
          onClick={() => setShowRaw((v) => !v)}
          className="flex w-full items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
          aria-expanded={showRaw}
        >
          <span className="inline-flex items-center gap-2">
            <Code2 className="h-4 w-4" />
            Raw API response
          </span>
          <ChevronDown
            className={`h-4 w-4 transition-transform ${showRaw ? "rotate-180" : ""}`}
          />
        </button>
        {showRaw ? (
          <pre className="mt-2 max-h-96 overflow-auto rounded-xl bg-slate-900 p-4 text-xs leading-relaxed text-slate-100">
            {JSON.stringify(trip, null, 2)}
          </pre>
        ) : null}
      </div>

      <EditTripModal
        open={editOpen}
        trip={trip}
        onClose={() => setEditOpen(false)}
        onSaved={(updated) => {
          setTrip(updated);
          setEditOpen(false);
        }}
      />

      <ConfirmDialog
        open={deleteOpen}
        title="Delete this trip?"
        message={`“${trip.destination}” and its itinerary will be permanently removed. This cannot be undone.`}
        confirmLabel={deleting ? "Deleting…" : "Yes, delete"}
        busy={deleting}
        onConfirm={handleDelete}
        onCancel={() => setDeleteOpen(false)}
      />
    </div>
  );
}

interface EditTripModalProps {
  open: boolean;
  trip: Trip;
  onClose: () => void;
  onSaved: (trip: Trip) => void;
}

function EditTripModal({ open, trip, onClose, onSaved }: EditTripModalProps) {
  const { token } = useAuth();
  const toast = useToast();
  const [destination, setDestination] = useState(trip.destination);
  const [budget, setBudget] = useState(String(trip.budget));
  const [travelers, setTravelers] = useState(trip.travelers);
  const [style, setStyle] = useState(trip.travel_style);
  const [interests, setInterests] = useState<string[]>(trip.interests);
  const [status, setStatus] = useState(trip.status);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setDestination(trip.destination);
    setBudget(String(trip.budget));
    setTravelers(trip.travelers);
    setStyle(trip.travel_style);
    setInterests(trip.interests);
    setStatus(trip.status);
  }, [open, trip]);

  const toggle = (interest: string) =>
    setInterests((prev) =>
      prev.includes(interest) ? prev.filter((i) => i !== interest) : [...prev, interest],
    );

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) return;

    const payload: TripUpdatePayload = {};
    if (destination.trim() && destination.trim() !== trip.destination)
      payload.destination = destination.trim();
    if (Number(budget) !== Number(trip.budget)) payload.budget = budget;
    if (travelers !== trip.travelers) payload.travelers = travelers;
    if (style !== trip.travel_style) payload.travel_style = style;
    if ([...interests].sort().join() !== [...trip.interests].sort().join())
      payload.interests = interests;
    if (status.trim() && status.trim() !== trip.status) payload.status = status.trim();

    if (Object.keys(payload).length === 0) {
      toast.info("No changes to save.");
      onClose();
      return;
    }

    setSaving(true);
    try {
      const updated = await api.updateTrip(token, trip.id, payload);
      toast.success("Trip updated. Regenerate to apply new constraints.");
      onSaved(updated);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Update failed.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Edit trip constraints"
      footer={
        <>
          <button type="button" className="btn-outline" onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button type="submit" form="edit-trip-form" className="btn-primary" disabled={saving}>
            {saving ? <Spinner /> : null}
            Save changes
          </button>
        </>
      }
    >
      <form id="edit-trip-form" onSubmit={save} className="space-y-4 text-left">
        <div>
          <label className="label" htmlFor="edit-destination">
            Destination
          </label>
          <input
            id="edit-destination"
            className="input"
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="edit-budget">
              Budget
            </label>
            <input
              id="edit-budget"
              type="number"
              min={0}
              step="50"
              className="input"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
          </div>
          <div>
            <label className="label" htmlFor="edit-travelers">
              Travelers
            </label>
            <input
              id="edit-travelers"
              type="number"
              min={1}
              max={50}
              className="input"
              value={travelers}
              onChange={(e) => setTravelers(Number(e.target.value))}
            />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="edit-style">
              Travel style
            </label>
            <select
              id="edit-style"
              className="input"
              value={style}
              onChange={(e) => setStyle(e.target.value)}
            >
              {TRAVEL_STYLES.map((s) => (
                <option key={s} value={s}>
                  {titleCase(s)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="edit-status">
              Status
            </label>
            <input
              id="edit-status"
              className="input"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              placeholder="draft / planned / completed"
            />
          </div>
        </div>
        <div>
          <span className="label">Interests</span>
          <div className="flex flex-wrap gap-1.5">
            {INTEREST_CHOICES.map((interest) => {
              const active = interests.includes(interest);
              return (
                <button
                  key={interest}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggle(interest)}
                  className={`chip border px-2.5 py-1 transition-all ${
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
        </div>
      </form>
    </Modal>
  );
}
