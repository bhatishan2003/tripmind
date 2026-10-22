import { BookOpen, Bot, MessageCircle, Plus, Send, Sparkles, Square, User } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, api, streamChat } from "@/api/client";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import type { ChatMessage } from "@/types";

const STORAGE_KEY = "atp-chat-conversation";

const SUGGESTIONS = [
  "Plan a 5-day Goa trip for 2 people, around INR 40k",
  "Where should I stay in Kyoto for a first visit?",
  "Suggest a budget-friendly food day in Barcelona",
  "Make day 3 of my trip cheaper",
];

let tempId = 0;
const nextTempId = () => `temp-${Date.now()}-${++tempId}`;

export function ChatPane() {
  const { token } = useAuth();
  const toast = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [title, setTitle] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (!token) return;
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return;

    let active = true;
    setLoadingHistory(true);
    api
      .getChat(token, saved)
      .then((conversation) => {
        if (!active) return;
        setConversationId(conversation.id);
        setTitle(conversation.title ?? null);
        setMessages(conversation.messages);
      })
      .catch(() => {
        if (active) localStorage.removeItem(STORAGE_KEY);
      })
      .finally(() => {
        if (active) setLoadingHistory(false);
      });

    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: streaming ? "auto" : "smooth",
      block: "end",
    });
  }, [messages, streaming]);

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const newChat = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    localStorage.removeItem(STORAGE_KEY);
    setMessages([]);
    setConversationId(null);
    setTitle(null);
    setError(null);
    setInput("");
    setStreaming(false);
    textareaRef.current?.focus();
  }, []);

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || !token || streaming) return;

      setInput("");
      setError(null);

      const userId = nextTempId();
      const assistantId = nextTempId();
      const now = new Date().toISOString();
      const userPlaceholder: ChatMessage = {
        id: userId,
        conversation_id: conversationId ?? "",
        role: "user",
        content: message,
        sources: [],
        created_at: now,
      };
      const assistantPlaceholder: ChatMessage = {
        id: assistantId,
        conversation_id: conversationId ?? "",
        role: "assistant",
        content: "",
        sources: [],
        created_at: now,
      };
      setMessages((prev) => [...prev, userPlaceholder, assistantPlaceholder]);
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        await streamChat(
          token,
          { message, conversation_id: conversationId },
          {
            onMeta: (meta) => {
              setConversationId(meta.conversation_id);
              localStorage.setItem(STORAGE_KEY, meta.conversation_id);
              setMessages((prev) =>
                prev.map((item) => (item.id === userId ? meta.user_message : item)),
              );
            },
            onDelta: (delta) => {
              setMessages((prev) =>
                prev.map((item) =>
                  item.id === assistantId ? { ...item, content: item.content + delta } : item,
                ),
              );
            },
            onDone: (done) => {
              setConversationId(done.conversation_id);
              localStorage.setItem(STORAGE_KEY, done.conversation_id);
              setTitle((current) => current ?? message.slice(0, 60));
              setMessages((prev) =>
                prev.map((item) => (item.id === assistantId ? done.message : item)),
              );
            },
            onError: (detail) => {
              setError(detail);
              toast.error(detail);
              setMessages((prev) =>
                prev.filter((item) => !(item.id === assistantId && !item.content.trim())),
              );
            },
          },
          controller.signal,
        );
      } catch (err) {
        if (!controller.signal.aborted) {
          const detail = err instanceof ApiError ? err.message : "Could not reach the assistant.";
          setError(detail);
          toast.error(detail);
          setMessages((prev) =>
            prev.filter((item) => !(item.id === assistantId && !item.content.trim())),
          );
        }
      } finally {
        if (abortRef.current === controller) abortRef.current = null;
        setStreaming(false);
      }
    },
    [token, streaming, conversationId, toast],
  );

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  };

  const canSend = input.trim().length > 0 && !streaming;

  return (
    <section className="card flex min-h-0 flex-1 flex-col overflow-hidden">
      <header className="flex items-center gap-3 border-b border-slate-200 px-4 py-3 dark:border-slate-800">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-600 text-white shadow-sm">
          <Sparkles className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
            {title || "Travel assistant"}
          </p>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">
            {conversationId ? "Conversation saved" : "New conversation"}
          </p>
        </div>
        <button
          type="button"
          onClick={newChat}
          className="btn-outline !px-3 !py-1.5 text-xs"
          disabled={messages.length === 0 && !conversationId}
        >
          <Plus className="h-3.5 w-3.5" />
          New chat
        </button>
      </header>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-6">
        {loadingHistory ? (
          <div className="flex h-full items-center justify-center gap-2 text-sm text-slate-500 dark:text-slate-400">
            <Spinner className="h-5 w-5 text-brand-500" />
            Loading conversation…
          </div>
        ) : messages.length === 0 ? (
          <EmptyState
            onPick={(suggestion) => {
              setInput(suggestion);
              textareaRef.current?.focus();
            }}
          />
        ) : (
          messages.map((message) => (
            <MessageBubble
              key={message.id}
              message={message}
              live={streaming && message.role === "assistant" && !message.content}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-200 px-4 py-3 dark:border-slate-800 sm:px-6">
        {error ? (
          <p
            role="alert"
            className="mb-2 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300"
          >
            {error}
          </p>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void send(input);
          }}
        >
          <div className="relative">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={onKeyDown}
              disabled={streaming || loadingHistory}
              placeholder="Ask about a destination, budget, or itinerary idea…"
              className="input max-h-40 min-h-[3.25rem] resize-none py-3 pr-14 leading-relaxed disabled:opacity-60"
              aria-label="Chat message"
            />
            {streaming ? (
              <button
                type="button"
                onClick={stop}
                className="btn-outline absolute bottom-2 right-2 !p-2"
                title="Stop generating"
                aria-label="Stop generating"
              >
                <Square className="h-4 w-4" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!canSend}
                className="btn-primary absolute bottom-2 right-2 !p-2"
                title="Send message"
                aria-label="Send message"
              >
                <Send className="h-4 w-4" />
              </button>
            )}
          </div>
          <p className="mt-2 text-xs text-slate-400">
            Enter to send · Shift+Enter for a new line. The assistant can make mistakes — verify
            prices and opening hours.
          </p>
        </form>
      </div>
    </section>
  );
}

function EmptyState({ onPick }: { onPick: (suggestion: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-5 py-10 text-center">
      <span className="grid h-14 w-14 place-items-center rounded-2xl bg-brand-50 text-brand-600 dark:bg-brand-950 dark:text-brand-300">
        <MessageCircle className="h-7 w-7" />
      </span>
      <div className="max-w-md space-y-1">
        <p className="text-lg font-semibold text-slate-900 dark:text-slate-100">
          Plan your next trip by chatting
        </p>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Ask about destinations, neighbourhoods, budgets, or refine an itinerary. Replies stream
          in live and the conversation is saved.
        </p>
      </div>
      <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            onClick={() => onPick(suggestion)}
            className="rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-left text-sm text-slate-600 transition-colors hover:border-brand-300 hover:bg-brand-50/50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:border-brand-700 dark:hover:bg-brand-950/40"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ message, live }: { message: ChatMessage; live: boolean }) {
  const isUser = message.role === "user";
  const Icon = isUser ? User : Bot;

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      <span
        className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full ${
          isUser
            ? "bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
            : "bg-brand-100 text-brand-700 dark:bg-brand-950 dark:text-brand-300"
        }`}
      >
        <Icon className="h-4 w-4" />
      </span>

      <div className={`min-w-0 max-w-[min(100%,42rem)] ${isUser ? "text-right" : ""}`}>
        <div
          className={`inline-block whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-left text-sm leading-relaxed ${
            isUser
              ? "bg-brand-600 text-white"
              : "border border-slate-200 bg-white text-slate-700 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          }`}
        >
          {message.content}
          {live ? (
            <span className="ml-0.5 inline-flex items-center gap-1 align-middle">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400 [animation-delay:150ms]" />
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400 [animation-delay:300ms]" />
            </span>
          ) : null}
        </div>

        {message.sources.length > 0 ? (
          <div className="mt-2 space-y-1.5 text-left">
            <p className="flex items-center gap-1.5 text-xs font-medium text-slate-400">
              <BookOpen className="h-3.5 w-3.5" />
              Sources
            </p>
            {message.sources.map((source) => (
              <div
                key={`${message.id}-${source.source_uri}`}
                className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/60"
              >
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300">
                  {source.title}
                </p>
                {source.snippet ? (
                  <p className="mt-0.5 text-xs leading-snug text-slate-500 dark:text-slate-400">
                    {source.snippet}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
