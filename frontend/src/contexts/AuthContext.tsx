import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Platform } from "react-native";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";

import { apiFetch, clearToken, setToken } from "@/src/api/client";
import { storage } from "@/src/utils/storage";

const TOKEN_KEY = "aidou.session_token";

export interface User {
  user_id: string;
  email: string;
  name: string;
  picture?: string;
  company_ids: string[];
  active_company_id: string;
  role: string;
}

interface AuthCtx {
  user: User | null;
  loading: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>({
  user: null,
  loading: true,
  signIn: async () => undefined,
  signOut: async () => undefined,
  refresh: async () => undefined,
});

export function useAuth() {
  return useContext(Ctx);
}

function extractSessionId(url: string | null): string | null {
  if (!url) return null;
  // hash: #session_id=...
  const hashMatch = url.match(/#session_id=([^&]+)/);
  if (hashMatch) return decodeURIComponent(hashMatch[1]);
  const queryMatch = url.match(/[?&]session_id=([^&]+)/);
  if (queryMatch) return decodeURIComponent(queryMatch[1]);
  return null;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await apiFetch<{ user: User }>("/auth/me");
      setUser(data.user);
    } catch {
      setUser(null);
    }
  }, []);

  const exchangeSessionId = useCallback(async (sessionId: string) => {
    try {
      const resp = await fetch(
        "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
        { headers: { "X-Session-ID": sessionId } },
      );
      if (!resp.ok) return;
      const data = await resp.json();
      const token: string = data.session_token;
      // Hand to backend to create local session
      const create = await fetch(
        `${process.env.EXPO_PUBLIC_BACKEND_URL ?? ""}/api/auth/session`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_token: token }),
        },
      );
      if (!create.ok) return;
      const body = await create.json();
      await setToken(body.session_token);
      setUser(body.user as User);
    } catch (e) {
      console.warn("exchangeSessionId failed", e);
    }
  }, []);

  const signIn = useCallback(async () => {
    let redirectUrl: string;
    if (Platform.OS === "web") {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      redirectUrl = (globalThis as any).window?.location?.origin + "/";
    } else {
      redirectUrl = Linking.createURL("auth");
    }
    const authUrl = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;

    if (Platform.OS === "web") {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (globalThis as any).window.location.href = authUrl;
      return;
    }

    const result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUrl);
    if (result.type !== "success" || !result.url) return;
    const sid = extractSessionId(result.url);
    if (sid) await exchangeSessionId(sid);
  }, [exchangeSessionId]);

  const signOut = useCallback(async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch {}
    await clearToken();
    setUser(null);
  }, []);

  // Mount: handle web session_id in URL + check existing session
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (Platform.OS === "web") {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const w = (globalThis as any).window;
        if (w?.location) {
          const sid = extractSessionId(w.location.hash) || extractSessionId(w.location.search);
          if (sid) {
            await exchangeSessionId(sid);
            try {
              w.history.replaceState(null, "", w.location.pathname);
            } catch {}
            if (!cancelled) setLoading(false);
            return;
          }
        }
      } else {
        // Cold start mobile
        try {
          const initial = await Linking.getInitialURL();
          const sid = extractSessionId(initial);
          if (sid) {
            await exchangeSessionId(sid);
            if (!cancelled) setLoading(false);
            return;
          }
        } catch {}
      }
      // Skip API call if we don't have a token at all
      const existing = await storage.secureGet<string>(TOKEN_KEY, "");
      if (existing && existing.length > 0) {
        await refresh();
      }
      if (!cancelled) {
        console.log("[Auth] init done; loading=false");
        setLoading(false);
      }
    })();

    let sub: { remove: () => void } | undefined;
    if (Platform.OS !== "web") {
      sub = Linking.addEventListener("url", async (event) => {
        const sid = extractSessionId(event.url);
        if (sid) await exchangeSessionId(sid);
      });
    }
    return () => {
      cancelled = true;
      sub?.remove();
    };
  }, [exchangeSessionId, refresh]);

  const value = useMemo<AuthCtx>(
    () => ({ user, loading, signIn, signOut, refresh }),
    [user, loading, signIn, signOut, refresh],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
