import { Sparkles } from "lucide-react";

import { ChatPane } from "@/components/ChatPane";

export function ChatPage() {
  return (
    <div className="flex h-[calc(100dvh-8.5rem)] min-h-[32rem] flex-col gap-4 lg:h-[calc(100dvh-7rem)]">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold text-slate-900 dark:text-slate-100">
          <Sparkles className="h-5 w-5 text-brand-500" />
          Travel assistant
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Chat through a trip idea — answers stream live and are saved to your account.
        </p>
      </div>
      <ChatPane />
    </div>
  );
}
