// Base path for the local backend (api-contract-spec §1). Requests are same-origin;
// Vite's dev server proxies /api to http://127.0.0.1:8000.
export const API_BASE = "/api/v1";

export interface HealthResponse {
  status: string;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/health`, { signal });
  if (!response.ok) {
    throw new Error(`Backend responded with HTTP ${response.status}`);
  }
  return (await response.json()) as HealthResponse;
}
