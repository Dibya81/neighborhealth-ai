import useSWR, { SWRConfiguration } from "swr";

export const API_URL = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";
const TOKEN_KEY = "nh.token";

export function getToken(): string | null {
  try { return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch { /* storage unavailable (private mode); stay signed in for this tab only */ }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach NeighborHealth right now. Check your connection and try again.");
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail.map((d: { msg: string }) => d.msg).join(", ") : msg;
    } catch { /* not JSON */ }
    if (res.status === 401) setToken(null);
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

export function useApi<T>(path: string | null, config?: SWRConfiguration) {
  return useSWR<T>(path, (p: string) => api<T>(p), { revalidateOnFocus: false, ...config });
}

let sessionId: string | null = null;
export function track(name: string, props?: Record<string, string | number>) {
  if (typeof window === "undefined") return;
  sessionId ??= Math.random().toString(36).slice(2, 12);
  api("/v2/events", { method: "POST", body: JSON.stringify({ name, props, session_id: sessionId }) }).catch(() => {});
}
