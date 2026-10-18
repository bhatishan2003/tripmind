import { BookOpen, Loader2, MapPin, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { api } from "@/api/client";
import { useAuth } from "@/context/AuthContext";
import type { DestinationSummary } from "@/types";

interface DestinationInputProps {
  value: string;
  onChange: (value: string) => void;
}

export function DestinationInput({ value, onChange }: DestinationInputProps) {
  const { token } = useAuth();
  const [suggestions, setSuggestions] = useState<DestinationSummary[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const justSelected = useRef(false);

  useEffect(() => {
    const query = value.trim();
    if (!token || query.length < 1 || justSelected.current) {
      justSelected.current = false;
      setSuggestions([]);
      return;
    }
    let active = true;
    setLoading(true);
    const timer = window.setTimeout(async () => {
      try {
        const results = await api.searchDestinations(token, query);
        if (active) {
          setSuggestions(results);
          setOpen(true);
        }
      } catch {
        if (active) setSuggestions([]);
      } finally {
        if (active) setLoading(false);
      }
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [value, token]);

  useEffect(() => {
    const onClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  const select = (destination: string) => {
    justSelected.current = true;
    onChange(destination);
    setOpen(false);
    setSuggestions([]);
  };

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <MapPin className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input
          id="destination"
          className="input pl-9 pr-9"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => suggestions.length && setOpen(true)}
          placeholder="e.g. Kyoto, Japan"
          autoComplete="off"
          autoFocus
          required
        />
        {loading ? (
          <Loader2 className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-brand-500" />
        ) : (
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-300 dark:text-slate-600" />
        )}
      </div>

      {open && suggestions.length ? (
        <ul className="absolute z-20 mt-1 w-full overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg animate-fade-in dark:border-slate-700 dark:bg-slate-900">
          <li className="flex items-center gap-1.5 border-b border-slate-100 px-3 py-1.5 text-[11px] uppercase tracking-wide text-slate-400 dark:border-slate-800">
            <BookOpen className="h-3 w-3" />
            From the knowledge base
          </li>
          {suggestions.map((s) => (
            <li key={s.destination}>
              <button
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => select(s.destination)}
                className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition-colors hover:bg-brand-50 dark:hover:bg-slate-800"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <MapPin className="h-3.5 w-3.5 shrink-0 text-brand-500" />
                  <span className="truncate font-medium text-slate-800 dark:text-slate-200">
                    {s.destination}
                  </span>
                  {s.categories.slice(0, 2).map((c) => (
                    <span
                      key={c}
                      className="chip hidden bg-slate-100 text-slate-500 sm:inline-flex dark:bg-slate-800 dark:text-slate-400"
                    >
                      {c}
                    </span>
                  ))}
                </span>
                <span className="shrink-0 text-xs text-slate-400">
                  {s.document_count} doc{s.document_count === 1 ? "" : "s"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
