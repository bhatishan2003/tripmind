import { API_BASE_URL } from "@/lib/constants";
import type {
  ChatConversation,
  ChatConversationSummary,
  ChatRequestPayload,
  ChatStreamDone,
  ChatStreamMeta,
  ChatTurn,
  DestinationDetail,
  DestinationSummary,
  Trip,
  TripCreatePayload,
  TripUpdatePayload,
  User,
} from "@/types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const PREFIX = "/api/v1";

function extractDetail(body: unknown): string {
  if (typeof body === "string" && body) return body;
  if (body && typeof body === "object") {
    const detail = (body as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          if (d && typeof d === "object" && "msg" in d) {
            const loc = (d as { loc?: unknown[] }).loc;
            const where = Array.isArray(loc) ? loc.slice(1).join(".") : "";
            return where ? `${where}: ${(d as { msg: string }).msg}` : (d as { msg: string }).msg;
          }
          return JSON.stringify(d);
        })
        .join("; ");
    }
    if (detail && typeof detail === "object") return JSON.stringify(detail);
  }
  return "Request failed";
}

interface RequestOptions {
  method?: string;
  token?: string | null;
  body?: unknown;
  timeoutMs?: number;
  signal?: AbortSignal;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", token, body, timeoutMs = 30_000, signal } = opts;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  if (signal) {
    signal.addEventListener("abort", () => controller.abort(), { once: true });
  }

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  try {
    const resp = await fetch(`${API_BASE_URL}${PREFIX}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    if (resp.status === 204) return undefined as T;

    const text = await resp.text();
    const data = text ? safeJson(text) : undefined;

    if (!resp.ok) {
      throw new ApiError(extractDetail(data ?? resp.statusText), resp.status);
    }
    return data as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError("Request timed out. The backend may be unreachable.", 0);
    }
    throw new ApiError(
      "Network error — is the backend running and reachable?",
      0,
    );
  } finally {
    clearTimeout(timer);
  }
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export interface HealthStatus {
  status: string;
  app: string;
  environment: string;
}

export const api = {
  health: async (): Promise<HealthStatus> => {
    let resp: Response;
    try {
      resp = await fetch(`${API_BASE_URL}/health`);
    } catch {
      throw new ApiError("Network error — is the backend running and reachable?", 0);
    }
    if (!resp.ok) throw new ApiError(`Health check failed (${resp.status})`, resp.status);
    return (await resp.json()) as HealthStatus;
  },

  register: (email: string, password: string, full_name?: string | null) =>
    request<User>("/auth/register", {
      method: "POST",
      body: { email, password, full_name: full_name || null },
    }),

  login: async (email: string, password: string): Promise<string> => {
    const data = await request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: { email, password },
    });
    return data.access_token;
  },

  me: (token: string) => request<User>("/auth/me", { token }),

  listTrips: (token: string, limit = 50, offset = 0) =>
    request<Trip[]>(`/trips?limit=${limit}&offset=${offset}`, { token }),

  createTrip: (token: string, payload: TripCreatePayload) =>
    request<Trip>("/trips", { method: "POST", token, body: payload, timeoutMs: 120_000 }),

  getTrip: (token: string, id: string) => request<Trip>(`/trips/${id}`, { token }),

  updateTrip: (token: string, id: string, payload: TripUpdatePayload) =>
    request<Trip>(`/trips/${id}`, { method: "PATCH", token, body: payload }),

  deleteTrip: (token: string, id: string) =>
    request<void>(`/trips/${id}`, { method: "DELETE", token }),

  regenerate: (token: string, id: string) =>
    request<Trip>(`/trips/${id}/generate`, { method: "POST", token, timeoutMs: 120_000 }),

  searchDestinations: (token: string, q: string, limit = 8) =>
    request<DestinationSummary[]>(
      `/destinations/search?q=${encodeURIComponent(q)}&limit=${limit}`,
      { token, timeoutMs: 10_000 },
    ),

  getDestination: (token: string, name: string) =>
    request<DestinationDetail>(`/destinations/${encodeURIComponent(name)}`, {
      token,
      timeoutMs: 10_000,
    }),

  sendChat: (token: string, payload: ChatRequestPayload) =>
    request<ChatTurn>("/chat", {
      method: "POST",
      token,
      body: payload,
      timeoutMs: 60_000,
    }),

  listChats: (token: string, limit = 100, offset = 0) =>
    request<ChatConversationSummary[]>(`/chat?limit=${limit}&offset=${offset}`, {
      token,
      timeoutMs: 15_000,
    }),

  getChat: (token: string, conversationId: string) =>
    request<ChatConversation>(`/chat/${conversationId}`, { token }),

  deleteChat: (token: string, conversationId: string) =>
    request<void>(`/chat/${conversationId}`, { method: "DELETE", token }),
};

export interface ChatStreamHandlers {
  onMeta?: (meta: ChatStreamMeta) => void;
  onDelta?: (text: string) => void;
  onDone?: (done: ChatStreamDone) => void;
  onError?: (message: string) => void;
}

export async function streamChat(
  token: string,
  payload: ChatRequestPayload,
  handlers: ChatStreamHandlers = {},
  signal?: AbortSignal,
): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE_URL}${PREFIX}/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return;
    throw new ApiError("Network error — is the backend running and reachable?", 0);
  }

  if (!resp.ok) {
    const text = await resp.text();
    throw new ApiError(extractDetail(text ? safeJson(text) : resp.statusText), resp.status);
  }
  if (!resp.body) {
    throw new ApiError("This browser does not support streaming responses.", 0);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (block: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (!line || line.startsWith(":")) continue;
      const colon = line.indexOf(":");
      const field = colon === -1 ? line : line.slice(0, colon);
      let value = colon === -1 ? "" : line.slice(colon + 1);
      if (value.startsWith(" ")) value = value.slice(1);
      if (field === "event") event = value;
      else if (field === "data") dataLines.push(value);
    }
    if (!dataLines.length) return;

    let data: unknown;
    try {
      data = JSON.parse(dataLines.join("\n"));
    } catch {
      return;
    }

    if (event === "meta") {
      handlers.onMeta?.(data as ChatStreamMeta);
    } else if (event === "delta") {
      const text = (data as { text?: unknown }).text;
      if (typeof text === "string") handlers.onDelta?.(text);
    } else if (event === "done") {
      handlers.onDone?.(data as ChatStreamDone);
    } else if (event === "error") {
      const detail = (data as { detail?: unknown }).detail;
      handlers.onError?.(typeof detail === "string" ? detail : "Chat stream failed.");
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
      let split = buffer.indexOf("\n\n");
      while (split !== -1) {
        const block = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        if (block.trim()) dispatch(block);
        split = buffer.indexOf("\n\n");
      }
    }
    buffer += decoder.decode().replace(/\r\n/g, "\n");
    if (buffer.trim()) dispatch(buffer);
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") return;
    throw new ApiError("The chat stream was interrupted.", 0);
  } finally {
    reader.releaseLock();
  }
}

export { API_BASE_URL };
