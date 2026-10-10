import { BackendStatus } from "./components/BackendStatus";

export function App() {
  return (
    <main className="mx-auto max-w-3xl space-y-4 p-8">
      <h1 className="text-2xl font-semibold text-slate-900">Frontier Model Evaluator</h1>
      <p className="text-slate-600">Phase 0 placeholder. Screens arrive in Phase 4.</p>
      <BackendStatus />
    </main>
  );
}
