// Typed client for the demo API (api-contract-spec). Types are generated from
// backend/openapi.json (`npm run gen:api`), so contract drift is a compile error.
import type { components } from "./schema";

export type Schemas = components["schemas"];
export type Leaderboard = Schemas["Leaderboard"];
export type LeaderboardRow = Schemas["LeaderboardRow"];
export type ScoreCell = Schemas["ScoreCell"];
export type ModelDetail = Schemas["ModelDetail"];
export type UsageRecord = Schemas["UsageRecord"];
export type Defect = Schemas["DefectOut"];
export type DefectList = Schemas["DefectList"];
export type ResultSummary = Schemas["ResultSummary"];
export type ResultDetail = Schemas["ResultDetail"];
export type Profile = Schemas["ProfileOut"];
export type FitResponse = Schemas["FitResponse"];
export type Verdict = Schemas["VerdictOut"];

// Locally Vite proxies /api to the backend. The deployed build sets VITE_API_BASE_URL
// to the Render API's origin (D-13).
const ORIGIN = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
export const API_BASE = `${ORIGIN}/api/v1`;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    let detail = `The server responded with HTTP ${response.status}.`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep the generic message
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  return entries.length ? `?${new URLSearchParams(entries.map(([k, v]) => [k, String(v)]))}` : "";
}

export interface HealthResponse {
  status: string;
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResponse>("/health", { signal }),
  leaderboard: (p: { tier?: string; category?: string }, signal?: AbortSignal) =>
    request<Leaderboard>(`/leaderboard${query(p)}`, { signal }),
  model: (key: string, signal?: AbortSignal) =>
    request<ModelDetail>(`/models/${encodeURIComponent(key)}`, { signal }),
  defects: (
    key: string,
    p: { severity?: string; type?: string; tier?: string; category?: string; status?: string },
    signal?: AbortSignal,
  ) => request<DefectList>(`/models/${encodeURIComponent(key)}/defects${query(p)}`, { signal }),
  results: (key: string, signal?: AbortSignal) =>
    request<ResultSummary[]>(`/models/${encodeURIComponent(key)}/results`, { signal }),
  result: (id: number, signal?: AbortSignal) => request<ResultDetail>(`/results/${id}`, { signal }),
  templates: (signal?: AbortSignal) => request<Profile[]>("/profile-templates", { signal }),
  fit: (profileId: string) =>
    request<FitResponse>("/fit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId }),
    }),
};

// Kept for the Phase 0 placeholder test and BackendStatus component.
export const getHealth = api.health;
