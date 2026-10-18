import { API_BASE_URL } from "@/lib/constants";
import type {
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
};

export { API_BASE_URL };
