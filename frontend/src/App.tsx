import { NavLink, Route, Routes } from "react-router-dom";

import { BackendStatus } from "./components/BackendStatus";
import { FitPage } from "./pages/FitPage";
import { LeaderboardPage } from "./pages/LeaderboardPage";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded px-3 py-1.5 text-sm font-medium focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600 ${
    isActive ? "bg-blue-700 text-white" : "text-slate-700 hover:bg-slate-100"
  }`;

/** frontend-spec §3: top navigation with Leaderboard (home) and Fit for my app. */
export function App() {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="border-b border-slate-200">
        <nav aria-label="Main" className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-3">
          <span className="font-semibold">Frontier Model Evaluator</span>
          <div className="flex gap-2">
            <NavLink to="/" end className={navClass}>
              Leaderboard
            </NavLink>
            <NavLink to="/fit" className={navClass}>
              Fit for my app
            </NavLink>
          </div>
        </nav>
      </header>
      <main className="mx-auto max-w-6xl space-y-6 px-6 py-6">
        <Routes>
          <Route path="/" element={<LeaderboardPage />} />
          <Route path="/fit" element={<FitPage />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Routes>
      </main>
      {import.meta.env.DEV && (
        <footer className="mx-auto max-w-6xl px-6 pb-6 text-sm">
          <BackendStatus />
        </footer>
      )}
    </div>
  );
}
