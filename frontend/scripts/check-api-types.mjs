// Fails when src/api/schema.d.ts is out of date with backend/openapi.json,
// so a contract change can't silently skip the frontend. Fix: `npm run gen:api`.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const out = join(mkdtempSync(join(tmpdir(), "fme-api-")), "schema.d.ts");
execFileSync("npx", ["openapi-typescript", "../backend/openapi.json", "-o", out], {
  stdio: "ignore",
});
if (readFileSync(out, "utf8") !== readFileSync("src/api/schema.d.ts", "utf8")) {
  console.error("src/api/schema.d.ts is stale: run `npm run gen:api` and commit the result.");
  process.exit(1);
}
console.log("API types match backend/openapi.json");
