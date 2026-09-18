import type { Invoice, PayRail } from "./basePay";
import type { ArchiveRow, Brief, SessionUser, Watch } from "./types";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(path, { ...init, headers, credentials: "include" });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status}`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export type CreatedWatch = Watch & { webhook_secret?: string };

export type OpsFunnelStep = {
  id: string;
  label: string;
  count: number;
  of_top_pct: number;
  of_prev_pct: number;
};

export type OpsDashboard = {
  as_of: string;
  window_days: number;
  kpis: {
    workspaces: number;
    users: number;
    watches: number;
    watches_active: number;
    runs_completed: number;
    runs_completed_30d: number;
    briefs: number;
    cogs_usd_30d: number;
    usdc_paid_30d: number;
    usdc_paid: number;
    invoices_pending: number;
    grants_unredeemed: number;
    push_devices: number;
  };
  funnel: OpsFunnelStep[];
  series: { days: string[]; runs: number[]; invoices: number[]; paid: number[]; cogs_usd: number[] };
  plans: { plan: string; workspaces: number }[];
  evidence: { status: string; count: number }[];
  delivery: { channel: string; ok: number; fail: number }[];
  by_sku: { sku: string; count: number; cogs_usd: number }[];
  workspaces: {
    id: string;
    name: string;
    plan: string;
    expired: boolean;
    email: string;
    users: number;
    watches: number;
    runs: number;
    cogs_usd: number;
    push_devices: number;
    created_at: string | null;
    plan_expires_at: string | null;
    last_run_at: string | null;
  }[];
  recent_runs: {
    id: string;
    workspace: string;
    status: string;
    evidence_status: string;
    alerted: boolean;
    cogs_usd: number;
    started_at: string | null;
  }[];
  recent_invoices: {
    id: string;
    plan: string;
    status: string;
    amount_usdc: number;
    created_at: string | null;
    paid_at: string | null;
  }[];
};

export const api = {
  health: () =>
    request<{
      ok: boolean;
      hub_mode: string;
      pay_mode?: string;
      demo?: boolean;
      desk_mode?: string;
    }>("/api/public/health"),
  status: () => request<Record<string, unknown>>("/api/public/status"),
  sampleBrief: () => request<Brief>("/api/public/sample-brief"),
  publicBrief: (token: string) => request<Brief>(`/api/public/briefs/${token}`),
  payStatus: () => request<PayRail>("/api/public/pay/status"),
  createOrder: (plan: string, payment_method: string) =>
    request<Invoice>("/api/public/pay/orders", {
      method: "POST",
      body: JSON.stringify({ plan, payment_method }),
    }),
  createInvoice: (plan: string) =>
    request<Invoice>("/api/public/pay/invoices", { method: "POST", body: JSON.stringify({ plan }) }),
  payInvoice: (id: string) => request<Invoice>(`/api/public/pay/invoices/${id}`),
  confirmInvoice: (id: string, tx_hash: string) =>
    request<Invoice>(`/api/public/pay/invoices/${id}/confirm`, {
      method: "POST",
      body: JSON.stringify({ tx_hash }),
    }),
  simulateInvoice: (id: string) =>
    request<Invoice>(`/api/public/pay/invoices/${id}/simulate`, { method: "POST" }),
  login: (email: string, password: string) =>
    request<{ access_token: string; user: SessionUser }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  redeem: (desk_key: string) =>
    request<{ access_token: string; user: SessionUser }>("/api/auth/redeem", {
      method: "POST",
      body: JSON.stringify({ desk_key }),
    }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  me: () => request<SessionUser>("/api/auth/me"),
  watches: () => request<Watch[]>("/api/watches"),
  createWatch: (body: Record<string, unknown>) =>
    request<CreatedWatch>("/api/watches", { method: "POST", body: JSON.stringify(body) }),
  watch: (id: string) => request<Watch>(`/api/watches/${id}`),
  runWatch: (id: string) =>
    request<{ run_id: string; brief_id: string | null; status: string; evidence_status: string; alerted: boolean }>(
      `/api/watches/${id}/run`,
      { method: "POST" },
    ),
  watchRuns: (id: string) => request<ArchiveRow[]>(`/api/watches/${id}/runs`),
  archive: () => request<ArchiveRow[]>("/api/archive"),
  brief: (id: string) => request<Brief>(`/api/briefs/${id}`),
  usage: () => request<Record<string, unknown>>("/api/billing/usage"),
  pushStatus: () => request<{ enabled: boolean; public_key: string; subscribed: boolean }>("/api/push/status"),
  pushSubscribe: (body: { endpoint: string; keys: { p256dh: string; auth: string } }) =>
    request<{ ok: boolean; subscribed: boolean }>("/api/push/subscribe", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  pushUnsubscribe: (body: { endpoint: string; keys: { p256dh: string; auth: string } }) =>
    request<{ ok: boolean; subscribed: boolean }>("/api/push/subscribe", {
      method: "DELETE",
      body: JSON.stringify(body),
    }),
  opsMe: () => request<{ ok: boolean; role: string }>("/api/ops/me"),
  opsLogin: (secret: string) =>
    request<{ ok: boolean }>("/api/ops/login", { method: "POST", body: JSON.stringify({ secret }) }),
  opsLogout: () => request<{ ok: boolean }>("/api/ops/logout", { method: "POST" }),
  opsDashboard: () => request<OpsDashboard>("/api/ops/dashboard"),
  async citePack(id: string) {
    const response = await fetch(`/api/briefs/${id}/cite-pack`, { credentials: "include" });
    if (!response.ok) throw new Error(await response.text());
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `emberline_${id}_cite.zip`;
    link.click();
    URL.revokeObjectURL(url);
  },
};
