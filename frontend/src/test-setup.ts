import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// With Vitest globals disabled, Testing Library can't register its own cleanup,
// so unmount rendered components after each test explicitly.
afterEach(() => cleanup());
