import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { GENERATION_STEPS } from "@/lib/constants";

export function GenerationProgress({ destination }: { destination?: string }) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setStep((s) => (s < GENERATION_STEPS.length - 1 ? s + 1 : s));
    }, 3500);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <div className="flex flex-col items-center justify-center gap-5 py-16 text-center">
      <div className="relative grid h-16 w-16 place-items-center">
        <span className="absolute inset-0 animate-ping rounded-full bg-brand-400/30" />
        <span className="absolute inset-1 rounded-full border-2 border-dashed border-brand-400/60 animate-spin-slow" />
        <span className="relative grid h-11 w-11 place-items-center rounded-full bg-brand-600 text-white shadow-lg">
          <Sparkles className="h-5 w-5" />
        </span>
      </div>

      <div className="space-y-1">
        <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Crafting your {destination ? `${destination} ` : ""}itinerary
        </p>
        <p className="h-5 text-sm text-slate-500 transition-all dark:text-slate-400">
          {GENERATION_STEPS[step]}
        </p>
      </div>

      <div className="relative h-1.5 w-64 max-w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <span className="absolute inset-y-0 rounded-full bg-brand-500 animate-progress-slide" />
      </div>

      <p className="text-xs text-slate-400">This can take up to ~60 seconds with an LLM key.</p>
    </div>
  );
}
