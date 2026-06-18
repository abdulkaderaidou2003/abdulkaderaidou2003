import { storage } from "@/src/utils/storage";

const BASE = process.env.EXPO_PUBLIC_BACKEND_URL ?? "";
const TOKEN_KEY = "aidou.session_token";

async function getToken(): Promise<string | null> {
  const raw = await storage.secureGet<string>(TOKEN_KEY, "");
  return raw && raw.length > 0 ? raw : null;
}

export async function setToken(t: string): Promise<void> {
  await storage.secureSet(TOKEN_KEY, t);
}

export async function clearToken(): Promise<void> {
  await storage.secureRemove(TOKEN_KEY);
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  const resp = await fetch(`${BASE}/api${path}`, { ...options, headers });
  if (resp.status === 401) {
    await clearToken();
    throw new Error("unauthorized");
  }
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`API ${resp.status}: ${text}`);
  }
  return (await resp.json()) as T;
}

export async function streamChat(
  body: { assistant: string; session_id: string; message: string },
  onDelta: (s: string) => void,
  onDone: () => void,
  onError: (e: string) => void,
): Promise<void> {
  const token = await getToken();
  try {
    const resp = await fetch(`${BASE}/api/ai/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    });
    if (!resp.ok || !resp.body) {
      onError(`Server ${resp.status}`);
      return;
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() ?? "";
      for (const p of parts) {
        if (!p.startsWith("data:")) continue;
        const payload = p.slice(5).replace(/^ /, "");
        if (payload === "[done]") {
          onDone();
          return;
        }
        if (payload.startsWith("[error]")) {
          onError(payload);
          return;
        }
        onDelta(payload);
      }
    }
    onDone();
  } catch (e) {
    onError(String(e));
  }
}

export const API_BASE = BASE;
