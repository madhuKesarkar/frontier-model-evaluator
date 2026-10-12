import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// Runs on the seeded synthetic demo run: demo-claude and demo-gpt, 18 tasks each.
// demo-gpt has planted defects, including two S1s on the complex Tool Use task.

async function expectNoSeriousA11yViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const serious = results.violations.filter(
    (v) => v.impact === "serious" || v.impact === "critical",
  );
  expect(serious.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}

test("FE-AC-01: each model shows a 1-5 score for each of the six categories", async ({ page }) => {
  await page.goto("/");
  const rows = page.locator("tbody tr");
  await expect(rows).toHaveCount(2); // two providers in the demo (D-17)
  for (const row of await rows.all()) {
    const cells = row.locator("td[data-category]");
    await expect(cells).toHaveCount(6);
    for (const text of await cells.allInnerTexts()) {
      const score = Number(text.trim());
      expect(score).toBeGreaterThanOrEqual(1);
      expect(score).toBeLessThanOrEqual(5);
    }
  }
});

test("FE-AC-02: clicking a model row opens its detail screen within 2 seconds", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByTestId("row-demo-gpt")).toBeVisible();
  const started = Date.now();
  await page.getByTestId("row-demo-gpt").locator("td").first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Demo GPT (synthetic)" })).toBeVisible();
  await expect(page.getByTestId("token-panel")).toBeVisible();
  expect(Date.now() - started).toBeLessThan(2000);
  await expect(page).toHaveURL(/\/models\/demo-gpt$/);
});

test("FE-AC-03: filtering defects by S1 and Complex shows only matches and updates the count", async ({
  page,
}) => {
  await page.goto("/models/demo-gpt");
  const count = page.getByTestId("defect-count");
  await expect(count).toHaveText("6 defects found");

  await page.getByLabel("Severity").selectOption("S1");
  await page.getByLabel("Tier", { exact: true }).selectOption("complex");

  await expect(count).toHaveText("2 defects match these filters");
  const items = page.getByTestId("defect");
  await expect(items).toHaveCount(2);
  for (const item of await items.all()) {
    await expect(item).toContainText("S1 Critical");
    await expect(item).toContainText("Complex");
  }
});

test("FE-AC-16: an expanded defect shows its evidence and links to the full result", async ({
  page,
}) => {
  await page.goto("/models/demo-gpt");
  const defect = page.getByTestId("defect").filter({ hasText: "LC-S-01" });
  await defect.getByRole("button").click();
  await expect(defect.getByRole("button")).toHaveAttribute("aria-expanded", "true");
  for (const label of ["Expected", "Actual", "Prompt excerpt", "Response excerpt"]) {
    await expect(defect.getByText(label, { exact: true })).toBeVisible();
  }
  await expect(defect).toContainText("NOT_IN_DOCUMENT");
  await expect(defect).toContainText("The lab manager");
  await expect(defect.getByText("Severity")).toBeVisible();
  await expect(defect.getByText("Source")).toBeVisible();
  await expect(defect.getByText("Status")).toBeVisible();

  await defect.getByRole("link", { name: /full result/ }).click();
  await expect(page).toHaveURL(/\/results\/\d+$/);
  await expect(page.getByRole("heading", { name: "Prompt" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Response" })).toBeVisible();
  await expect(page.getByText("✗ Failed")).toBeVisible();
});

test("FE-AC-07: home → Check fit → template shows a verdict with reasons for every model (≤ 3 clicks)", async ({
  page,
}) => {
  await page.goto("/");
  let clicks = 0;
  await page.getByRole("link", { name: "Check fit for my app" }).click();
  clicks++;
  await page.getByRole("button", { name: "Customer support chatbot" }).click();
  clicks++;
  expect(clicks).toBeLessThanOrEqual(3);

  for (const key of ["demo-claude", "demo-gpt"]) {
    const card = page.getByTestId(`verdict-${key}`);
    await expect(card).toBeVisible();
    await expect(card.getByRole("heading", { name: "Why" })).toBeVisible();
    await expect(card.locator("li")).not.toHaveCount(0);
  }
  // D-18: an open S1 in a must-have category blocks the recommendation.
  await expect(page.getByTestId("verdict-demo-gpt")).toContainText("Not recommended");
  await expect(page.getByTestId("verdict-demo-gpt")).toContainText("S1 defect in must-have");
});

test("FE-AC-13: a failed API request shows a plain-language error and Retry recovers", async ({
  page,
}) => {
  let fail = true;
  await page.route("**/api/v1/leaderboard*", (route) =>
    fail
      ? route.fulfill({ status: 503, json: { detail: "Database not set up yet" } })
      : route.fallback(),
  );
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Database not set up yet");
  fail = false;
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByTestId("row-demo-gpt")).toBeVisible();
});

test("FE-AC-13: a failed fit request keeps the chosen template and Retry recovers", async ({
  page,
}) => {
  let fail = true;
  await page.route("**/api/v1/fit", (route) =>
    fail ? route.fulfill({ status: 500, json: { detail: "Fit failed" } }) : route.fallback(),
  );
  await page.goto("/fit");
  const template = page.getByRole("button", { name: "Code assistant" });
  await template.click();
  await expect(page.getByRole("alert")).toContainText("Fit failed");
  await expect(template).toHaveAttribute("aria-pressed", "true");
  fail = false;
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByTestId("verdict-demo-claude")).toBeVisible();
});

test("FE-AC-14: main screens have no serious or critical WCAG 2.1 AA violations", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByTestId("row-demo-gpt")).toBeVisible();
  await expectNoSeriousA11yViolations(page);

  await page.goto("/models/demo-gpt");
  await expect(page.getByTestId("token-panel")).toBeVisible();
  await page.getByTestId("defect").first().getByRole("button").click();
  await expectNoSeriousA11yViolations(page);

  await page.getByRole("link", { name: /full result/ }).click();
  await expect(page.getByRole("heading", { name: "Response" })).toBeVisible();
  await expectNoSeriousA11yViolations(page);

  await page.goto("/fit");
  await page.getByRole("button", { name: "Test-case generation tool" }).click();
  await expect(page.getByTestId("verdict-demo-gpt")).toBeVisible();
  await expectNoSeriousA11yViolations(page);
});

test("FE-AC-14: the main journeys work with the keyboard alone", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("row-demo-gpt")).toBeVisible();

  // Leaderboard → model, via Tab + Enter on the model link.
  const modelLink = page.getByRole("link", { name: "Demo GPT (synthetic)" });
  for (
    let i = 0;
    i < 40 && !(await modelLink.evaluate((el) => el === document.activeElement));
    i++
  ) {
    await page.keyboard.press("Tab");
  }
  await expect(modelLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/models\/demo-gpt$/);

  // Expand a defect with the keyboard.
  const toggle = page.getByTestId("defect").first().getByRole("button");
  await toggle.focus();
  await page.keyboard.press("Enter");
  await expect(toggle).toHaveAttribute("aria-expanded", "true");

  // Fit: nav link → template button → verdicts.
  await page.getByRole("link", { name: "Fit for my app" }).focus();
  await page.keyboard.press("Enter");
  const template = page.getByRole("button", { name: "Code assistant" });
  await template.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("verdict-demo-claude")).toBeVisible();
});
