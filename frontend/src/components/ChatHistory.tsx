import { MessageSquare, Plus, Search, Trash2, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Skeleton } from "@/components/Spinner";
import type { ChatConversationSummary } from "@/types";

interface ChatHistoryProps {
  conversations: ChatConversationSummary[];
  activeId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (conversation: ChatConversationSummary) => void;
  onClose?: () => void;
}

const GROUP_ORDER = ["Today", "Yesterday", "Previous 7 days", "Previous 30 days", "Older"] as const;

export function ChatHistory({
  conversations,
  activeId,
  loading,
  onSelect,
  onNew,
  onDelete,
  onClose,
}: ChatHistoryProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return conversations;
    return conversations.filter((conversation) => {
      const haystack = `${conversation.title ?? ""} ${conversation.last_message ?? ""}`.toLowerCase();
      return haystack.includes(q);
    });
  }, [conversations, query]);

  const groups = useMemo(() => {
    const buckets = new Map<string, ChatConversationSummary[]>();
    for (const conversation of filtered) {
      const label = groupFor(conversation.updated_at);
      const bucket = buckets.get(label) ?? [];
      bucket.push(conversation);
      buckets.set(label, bucket);
    }
    return GROUP_ORDER.filter((label) => buckets.has(label)).map((label) => ({
      label,
      items: buckets.get(label) ?? [],
    }));
  }, [filtered]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">Chats</p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {conversations.length} saved conversation{conversations.length === 1 ? "" : "s"}
          </p>
        </div>
        <button
          type="button"
          onClick={onNew}
          className="btn-primary !p-2"
          title="New chat"
          aria-label="New chat"
        >
          <Plus className="h-4 w-4" />
        </button>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="btn-ghost !p-2 lg:hidden"
            title="Close history"
            aria-label="Close history"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </div>

      <div className="relative mt-3">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          className="input !py-2 pl-8 text-xs"
          placeholder="Search chats…"
          aria-label="Search chats"
        />
      </div>

      <div className="mt-2 min-h-0 flex-1 overflow-y-auto pr-1">
        {loading ? (
          <div className="space-y-2 pt-2">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="space-y-1.5 px-2 py-2">
                <Skeleton className="h-3.5 w-3/4" />
                <Skeleton className="h-2.5 w-full" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-4 pb-8 text-center">
            <MessageSquare className="h-7 w-7 text-slate-300 dark:text-slate-600" />
            <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
              {query ? "No matching chats" : "No chats yet"}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {query
                ? "Try a different search."
                : "Start a conversation and it will appear here."}
            </p>
          </div>
        ) : (
          groups.map(({ label, items }) => (
            <div key={label} className="pb-1">
              <p className="px-2 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                {label}
              </p>
              {items.map((conversation) => {
                const active = conversation.id === activeId;
                const title = conversation.title || "New conversation";
                return (
                  <div
                    key={conversation.id}
                    className={`group flex items-center rounded-xl transition-colors ${
                      active
                        ? "bg-brand-50 dark:bg-brand-950/60"
                        : "hover:bg-slate-100 dark:hover:bg-slate-800/60"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onSelect(conversation.id)}
                      className="min-w-0 flex-1 px-3 py-2.5 text-left"
                      aria-current={active ? "page" : undefined}
                    >
                      <div className="flex items-baseline gap-2">
                        <p
                          className={`min-w-0 flex-1 truncate text-sm ${
                            active
                              ? "font-semibold text-brand-700 dark:text-brand-300"
                              : "font-medium text-slate-700 dark:text-slate-200"
                          }`}
                        >
                          {title}
                        </p>
                        <span className="shrink-0 text-[10px] text-slate-400">
                          {relativeTime(conversation.updated_at)}
                        </span>
                      </div>
                      <p className="mt-0.5 truncate text-[11px] text-slate-500 dark:text-slate-400">
                        {previewOf(conversation)}
                      </p>
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(conversation)}
                      className="mr-1 rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600 focus-visible:opacity-100 lg:opacity-0 lg:group-hover:opacity-100 dark:hover:bg-rose-950/40 dark:hover:text-rose-300"
                      title="Delete chat"
                      aria-label={`Delete ${title}`}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function previewOf(conversation: ChatConversationSummary): string | null {
  if (!conversation.last_message) {
    return `${conversation.message_count} message${conversation.message_count === 1 ? "" : "s"}`;
  }
  return stripMarkdown(conversation.last_message);
}

function stripMarkdown(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " code ")
    .replace(/[#>*_`~|]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function groupFor(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Older";
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const days = Math.round((startOfToday - startOfDate) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days <= 7) return "Previous 7 days";
  if (days <= 30) return "Previous 30 days";
  return "Older";
}

function relativeTime(value: string): string {
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  if (diff < 60_000) return "now";
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h`;
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)}d`;
  return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
