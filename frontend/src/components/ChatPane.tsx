import {
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  Copy,
  History,
  MessageCircle,
  Plus,
  Send,
  Sparkles,
  Square,
  User,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { ApiError, api, streamChat } from "@/api/client";
import { ChatHistory } from "@/components/ChatHistory";
import { ConfirmDialog } from "@/components/Modal";
import { Spinner } from "@/components/Spinner";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import type { ChatConversationSummary, ChatMessage } from "@/types";

const STORAGE_KEY = "atp-chat-conversation";

const SUGGESTIONS = [
  "Plan a 5-day Goa trip for 2 people, around INR 40k",
  "Where should I stay in Kyoto for a first visit?",
  "Suggest a budget-friendly food day in Barcelona",
  "Make day 3 of my trip cheaper",
];

const markdownComponents: Components = {
  h1: ({ children }) => (
    <h2 className="mb-2 mt-5 text-lg font-semibold leading-snug first:mt-0">{children}</h2>
  ),
  h2: ({ children }) => (
    <h3 className="mb-2 mt-5 text-base font-semibold leading-snug first:mt-0">{children}</h3>
  ),
  h3: ({ children }) => (
    <h4 className="mb-1.5 mt-4 text-sm font-semibold leading-snug first:mt-0">{children}</h4>
  ),
  h4: ({ children }) => (
    <h5 className="mb-1.5 mt-3 text-sm font-semibold leading-snug first:mt-0">{children}</h5>
  ),
  p: ({ children }) => <p className="mb-2.5 leading-relaxed last:mb-0">{children}</p>,
  strong: ({ children }) => (
    <strong className="font-semibold text-slate-900 dark:text-slate-100">{children}</strong>
  ),
  em: ({ children }) => <em className="italic">{children}</em>,
  del: ({ children }) => <del className="line-through opacity-70">{children}</del>,
  ul: ({ children }) => <ul className="mb-2.5 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>,
  ol: ({ children }) => (
    <ol className="mb-2.5 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed [&>p]:mb-1">{children}</li>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-medium text-brand-600 underline decoration-brand-300 underline-offset-2 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2.5 border-l-2 border-brand-300 bg-brand-50/60 px-3 py-2 text-slate-600 dark:border-brand-700 dark:bg-brand-950/30 dark:text-slate-300">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-slate-200 dark:border-slate-800" />,
  code: ({ className, children }) =>
    className ? (
      <code className={`font-mono text-xs ${className}`}>{children}</code>
    ) : (
      <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] text-slate-800 dark:bg-slate-800 dark:text-slate-200">
        {children}
      </code>
    ),
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-xl bg-slate-900 p-3 text-xs leading-relaxed text-slate-100 [&_code]:bg-transparent [&_code]:p-0 [&_code]:text-inherit">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
      <table className="min-w-full border-collapse text-left text-xs sm:text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-slate-50 text-slate-700 dark:bg-slate-800/70 dark:text-slate-200">
      {children}
    </thead>
  ),
  tbody: ({ children }) => (
    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">{children}</tbody>
  ),
  tr: ({ children }) => <tr className="align-top">{children}</tr>,
  th: ({ children }) => (
    <th className="whitespace-nowrap px-3 py-2 font-semibold">{children}</th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-slate-600 dark:text-slate-300">{children}</td>
  ),
};

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
  const [conversations, setConversations] = useState<ChatConversationSummary[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ChatConversationSummary | null>(null);
  const [deleting, setDeleting] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const streamSeqRef = useRef(0);
  const openSeqRef = useRef(0);

  const loadConversations = useCallback(async () => {
    if (!token) return;
    setLoadingConversations(true);
    try {
      setConversations(await api.listChats(token));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not load chat history.");
    } finally {
      setLoadingConversations(false);
    }
  }, [token, toast]);

  useEffect(() => {
    if (!token) return;
    void loadConversations();

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
        if (active) {
          localStorage.removeItem(STORAGE_KEY);
          setConversationId(null);
        }
      })
      .finally(() => {
        if (active) setLoadingHistory(false);
      });

    return () => {
      active = false;
    };
  }, [token, loadConversations]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: streaming ? "auto" : "smooth",
      block: "end",
    });
  }, [messages, streaming]);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [input]);

  const cancelStream = useCallback(() => {
    streamSeqRef.current += 1;
    abortRef.current?.abort();
    abortRef.current = null;
    setStreaming(false);
  }, []);

  const stop = useCallback(() => {
    cancelStream();
  }, [cancelStream]);

  const resetConversation = useCallback(() => {
    cancelStream();
    openSeqRef.current += 1;
    localStorage.removeItem(STORAGE_KEY);
    setMessages([]);
    setConversationId(null);
    setTitle(null);
    setError(null);
    setInput("");
  }, [cancelStream]);

  const newChat = useCallback(() => {
    resetConversation();
    setHistoryOpen(false);
    textareaRef.current?.focus();
  }, [resetConversation]);

  const openConversation = useCallback(
    async (id: string) => {
      if (!token) return;
      setHistoryOpen(false);
      if (id === conversationId) return;

      cancelStream();
      const seq = ++openSeqRef.current;
      setConversationId(id);
      setTitle(conversations.find((item) => item.id === id)?.title ?? null);
      setMessages([]);
      setError(null);
      setLoadingHistory(true);
      localStorage.setItem(STORAGE_KEY, id);

      try {
        const conversation = await api.getChat(token, id);
        if (seq !== openSeqRef.current) return;
        setTitle(conversation.title ?? null);
        setMessages(conversation.messages);
      } catch (err) {
        if (seq !== openSeqRef.current) return;
        localStorage.removeItem(STORAGE_KEY);
        setConversationId(null);
        setMessages([]);
        toast.error(err instanceof ApiError ? err.message : "Could not load this conversation.");
      } finally {
        if (seq === openSeqRef.current) setLoadingHistory(false);
      }
    },
    [token, conversationId, conversations, cancelStream, toast],
  );

  const confirmDelete = useCallback(async () => {
    if (!token || !deleteTarget) return;
    setDeleting(true);
    try {
      await api.deleteChat(token, deleteTarget.id);
      setConversations((prev) => prev.filter((item) => item.id !== deleteTarget.id));
      if (deleteTarget.id === conversationId) resetConversation();
      toast.success("Chat deleted.");
      setDeleteTarget(null);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not delete this chat.");
    } finally {
      setDeleting(false);
    }
  }, [token, deleteTarget, conversationId, resetConversation, toast]);

  const send = useCallback(
    async (text: string) => {
      const message = text.trim();
      if (!message || !token || streaming) return;

      const streamId = ++streamSeqRef.current;
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
              if (streamSeqRef.current !== streamId) return;
              setConversationId(meta.conversation_id);
              localStorage.setItem(STORAGE_KEY, meta.conversation_id);
              setMessages((prev) =>
                prev.map((item) => (item.id === userId ? meta.user_message : item)),
              );
              setConversations((prev) => {
                const existing = prev.find((item) => item.id === meta.conversation_id);
                const summary: ChatConversationSummary = {
                  id: meta.conversation_id,
                  title: existing?.title ?? message.slice(0, 60),
                  trip_id: existing?.trip_id ?? null,
                  created_at: existing?.created_at ?? meta.user_message.created_at,
                  updated_at: meta.user_message.created_at,
                  last_message: message,
                  last_role: "user",
                  message_count: (existing?.message_count ?? 0) + 1,
                };
                return [summary, ...prev.filter((item) => item.id !== meta.conversation_id)];
              });
            },
            onDelta: (delta) => {
              if (streamSeqRef.current !== streamId) return;
              setMessages((prev) =>
                prev.map((item) =>
                  item.id === assistantId ? { ...item, content: item.content + delta } : item,
                ),
              );
            },
            onDone: (done) => {
              if (streamSeqRef.current !== streamId) return;
              setConversationId(done.conversation_id);
              localStorage.setItem(STORAGE_KEY, done.conversation_id);
              setTitle((current) => current ?? message.slice(0, 60));
              setMessages((prev) =>
                prev.map((item) => (item.id === assistantId ? done.message : item)),
              );
              setConversations((prev) => {
                const existing = prev.find((item) => item.id === done.conversation_id);
                const summary: ChatConversationSummary = {
                  id: done.conversation_id,
                  title: existing?.title ?? message.slice(0, 60),
                  trip_id: existing?.trip_id ?? null,
                  created_at: existing?.created_at ?? done.message.created_at,
                  updated_at: done.message.created_at,
                  last_message: done.message.content,
                  last_role: "assistant",
                  message_count: (existing?.message_count ?? 0) + 1,
                };
                return [summary, ...prev.filter((item) => item.id !== done.conversation_id)];
              });
              void loadConversations();
            },
            onError: (detail) => {
              if (streamSeqRef.current !== streamId) return;
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
        if (streamSeqRef.current === streamId && !controller.signal.aborted) {
          const detail = err instanceof ApiError ? err.message : "Could not reach the assistant.";
          setError(detail);
          toast.error(detail);
          setMessages((prev) =>
            prev.filter((item) => !(item.id === assistantId && !item.content.trim())),
          );
        }
      } finally {
        if (streamSeqRef.current === streamId) {
          abortRef.current = null;
          setStreaming(false);
        }
      }
    },
    [token, streaming, conversationId, toast, loadConversations],
  );

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing) return;
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  };

  const canSend = input.trim().length > 0 && !streaming;

  return (
    <div className="flex min-h-0 flex-1 gap-4">
      <aside className="card hidden w-64 shrink-0 flex-col p-3 lg:flex xl:w-72">
        <ChatHistory
          conversations={conversations}
          activeId={conversationId}
          loading={loadingConversations}
          onSelect={(id) => void openConversation(id)}
          onNew={newChat}
          onDelete={setDeleteTarget}
        />
      </aside>

      {historyOpen ? (
        <div className="no-print fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
            onClick={() => setHistoryOpen(false)}
            aria-hidden
          />
          <div className="absolute inset-y-0 left-0 w-80 max-w-[85vw] border-r border-slate-200 bg-white p-4 shadow-xl animate-fade-in dark:border-slate-800 dark:bg-slate-950">
            <ChatHistory
              conversations={conversations}
              activeId={conversationId}
              loading={loadingConversations}
              onSelect={(id) => void openConversation(id)}
              onNew={newChat}
              onDelete={setDeleteTarget}
              onClose={() => setHistoryOpen(false)}
            />
          </div>
        </div>
      ) : null}

      <section className="card flex min-h-0 flex-1 flex-col overflow-hidden">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white/70 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/70">
          <button
            type="button"
            onClick={() => setHistoryOpen(true)}
            className="btn-ghost !p-2 lg:hidden"
            title="Chat history"
            aria-label="Open chat history"
          >
            <History className="h-4 w-4" />
          </button>
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-600 text-white shadow-sm">
            <Sparkles className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
              {title || "Travel assistant"}
            </p>
            <p className="truncate text-xs text-slate-500 dark:text-slate-400">
              {streaming
                ? "Streaming response…"
                : conversationId
                  ? "Conversation saved"
                  : "New conversation"}
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

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-4 py-5 sm:px-6">
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
                streaming={streaming && message.role === "assistant"}
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

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete this chat?"
        message={`“${deleteTarget?.title || "New conversation"}” and all of its messages will be permanently removed.`}
        confirmLabel={deleting ? "Deleting…" : "Delete chat"}
        busy={deleting}
        onConfirm={() => void confirmDelete()}
        onCancel={() => {
          if (!deleting) setDeleteTarget(null);
        }}
      />
    </div>
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

function MessageBubble({
  message,
  streaming,
}: {
  message: ChatMessage;
  streaming: boolean;
}) {
  const isUser = message.role === "user";
  const Icon = isUser ? User : Bot;
  const toast = useToast();
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Could not copy this reply.");
    }
  };

  const time = new Date(message.created_at).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

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

      <div
        className={`min-w-0 ${
          isUser ? "max-w-[min(100%,34rem)] text-right" : "w-full max-w-[min(100%,52rem)]"
        }`}
      >
        <div
          className={`rounded-2xl px-4 py-3 text-left text-sm leading-relaxed ${
            isUser
              ? "inline-block bg-brand-600 text-white shadow-sm"
              : "border border-slate-200 bg-white text-slate-700 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : message.content ? (
            <div className="min-w-0">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                {message.content}
              </ReactMarkdown>
            </div>
          ) : null}

          {streaming ? (
            message.content ? (
              <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-brand-400 align-middle" />
            ) : (
              <span className="inline-flex items-center gap-1 align-middle">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400 [animation-delay:150ms]" />
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-400 [animation-delay:300ms]" />
              </span>
            )
          ) : null}
        </div>

        <div
          className={`mt-1.5 flex items-center gap-2 text-[11px] text-slate-400 ${
            isUser ? "justify-end" : ""
          }`}
        >
          <span>{time}</span>
          {!isUser && message.content && !streaming ? (
            <button
              type="button"
              onClick={() => void copy()}
              className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 transition-colors hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
              aria-label="Copy reply"
            >
              {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
              {copied ? "Copied" : "Copy"}
            </button>
          ) : null}
        </div>

        {message.sources.length > 0 ? (
          <details className="group mt-1 text-left">
            <summary className="inline-flex cursor-pointer select-none items-center gap-1.5 text-xs font-medium text-slate-400 transition-colors hover:text-slate-600 dark:hover:text-slate-200">
              <BookOpen className="h-3.5 w-3.5" />
              {message.sources.length} source{message.sources.length === 1 ? "" : "s"}
              <ChevronDown className="h-3 w-3 transition-transform group-open:rotate-180" />
            </summary>
            <div className="mt-1.5 space-y-1.5">
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
          </details>
        ) : null}
      </div>
    </div>
  );
}
