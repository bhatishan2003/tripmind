import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { api } from "@/api/client";
import type { User } from "@/types";

const TOKEN_KEY = "atp-token";

interface AuthContextValue {
  token: string | null;
  user: User | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (
    email: string,
    password: string,
    fullName?: string | null,
  ) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  );
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    async function restore() {
      const stored = localStorage.getItem(TOKEN_KEY);
      if (!stored) {
        setReady(true);
        return;
      }
      try {
        const me = await api.me(stored);
        if (!active) return;
        setToken(stored);
        setUser(me);
      } catch {
        if (!active) return;
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setUser(null);
      } finally {
        if (active) setReady(true);
      }
    }
    void restore();
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const accessToken = await api.login(email, password);
    const me = await api.me(accessToken);
    localStorage.setItem(TOKEN_KEY, accessToken);
    setToken(accessToken);
    setUser(me);
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName?: string | null) => {
      await api.register(email, password, fullName ?? null);
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ token, user, ready, login, register, logout }),
    [token, user, ready, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
