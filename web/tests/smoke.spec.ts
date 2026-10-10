import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  // This suite never needs a provider credential, remote resource, or a paid call.
  await page.route("**/api/backend/**", (route) => route.fulfill({
    status: 503,
    contentType: "application/json",
    body: JSON.stringify({ detail: "API disconnected for this offline browser test." }),
  }));
});

test("the story, navigation and field guide remain readable with motion disabled", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("A matter");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await expect(page.locator("[data-counter='1196860']")).toHaveText("1,196,860");
  const guide = page.getByRole("button", { name: "Field guide", exact: true });
  await guide.click();
  await expect(page.locator(".field-guide-dialog")).toBeVisible();
  await expect(page.locator(".glossary")).toContainText("Probability dilution");
  await page.keyboard.press("Escape");
  await expect(page.locator(".field-guide-dialog")).not.toBeVisible();
  await expect(guide).toBeFocused();
  await page.getByRole("link", { name: "Enter the observatory", exact: true }).click();
  await expect(page).toHaveURL(/\/observatory$/);
  expect(errors).toEqual([]);
});

test("all 2,000 encounters remain selectable and empty filters clear the inspector", async ({ page }) => {
  await page.goto("/observatory");
  const picker = page.getByLabel("Jump to any filtered encounter");
  await expect(picker.locator("option")).toHaveCount(2001);
  await page.getByRole("button", { name: /Inspect highest/ }).click();
  await expect(picker).not.toHaveValue("");
  const selected = await picker.inputValue();
  expect(selected).toContain("TRACSS");
  await page.getByLabel("Maximum miss distance in kilometers").fill("0");
  await expect(picker.locator("option")).toHaveCount(1);
  await expect(page.getByRole("button", { name: "Next encounter" })).toBeDisabled();
  await expect(picker).toHaveValue("");
  await page.getByRole("button", { name: "Reset filters" }).click();
  await expect(picker.locator("option")).toHaveCount(2001);
});

test("all distribution charts and the full evaluation work offline", async ({ page }) => {
  await page.goto("/observatory");
  await page.getByRole("tab", { name: "Distributions" }).click();
  await expect(page.locator(".atlas-figure")).toHaveCount(10);
  await expect(page.locator(".atlas-bar").first()).toHaveAttribute("aria-label", /724,121/);
  await page.goto("/evidence");
  await expect(page.locator(".ev-results-table tbody tr")).toHaveCount(6);
  await expect(page.locator(".ev-leaderboard tbody tr")).toHaveCount(4);
  await page.getByRole("button", { name: "Recall ↑", exact: true }).click();
  await expect(page.getByRole("img", { name: /recall 76.7 percent/ })).toBeVisible();
});

test("recorded reasoning works without the API and no triage request is sent", async ({ page }) => {
  let calls = 0;
  page.on("request", (request) => { if (request.url().endsWith("/triage")) calls++; });
  await page.goto("/laboratory");
  await expect(page.getByRole("button", { name: "Compute probability", exact: true })).toBeDisabled();
  await page.getByRole("tab", { name: /Agent reasoning/ }).click();
  await page.getByRole("button", { name: "View recorded example", exact: true }).click();
  await expect(page.locator(".lab-verdicts")).toContainText("test:1001");
  await expect(page.locator(".lab-recorded-note")).toContainText("Recorded");
  await expect(page.getByRole("button", { name: "Run live analysis", exact: true })).toBeDisabled();
  expect(calls).toBe(0);
});

test("phone navigation and every route fit the viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await expect(page.locator(".mobile-nav-dialog")).toBeVisible();
  await page.locator(".mobile-nav-dialog").getByRole("link", { name: /Laboratory/ }).click();
  await expect(page).toHaveURL(/\/laboratory$/);
  await expect(page.locator(".mobile-nav-dialog")).not.toBeVisible();
  for (const path of ["/", "/observatory", "/laboratory", "/evidence", "/findings"]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});

test("disabling motion restores exact counts and keeps content visible", async ({ page }) => {
  await page.goto("/");
  const guide = page.getByRole("button", { name: "Field guide", exact: true });
  await guide.click();
  await page.getByRole("button", { name: "Close field guide" }).click();
  await expect(page.locator(".field-guide-dialog")).not.toBeVisible();
  await page.evaluate(() => { localStorage.setItem("conjunction-motion", "reduced"); window.dispatchEvent(new Event("conjunction-motion")); });
  await expect(page.locator("html")).toHaveAttribute("data-motion", "reduced");
  await expect(page.locator("[data-counter='1196860']")).toHaveText("1,196,860");
  await expect(page.locator("[data-counter='2000']")).toHaveText("2,000");
  await expect(page.locator("[data-counter='2167']")).toHaveText("2,167");
  await guide.click();
  await expect(page.locator(".field-guide-dialog")).toBeVisible();
  await expect(page.locator(".field-guide-dialog")).toHaveCSS("opacity", "1");
});

test("the findings page links the globe, windows and frozen contrasts without a backend", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/findings");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Fifteen");
  await expect(page.locator(".fd-readout")).toContainText("15 distinct observations behind 60");
  await page.getByRole("group", { name: "Reuse condition", exact: true }).getByRole("button", { name: "No reuse", exact: true }).click();
  await expect(page.locator(".fd-readout")).toContainText("60 distinct observations behind 60");
  await page.getByRole("group", { name: "Messages", exact: true }).getByRole("button", { name: /Message m2/ }).click();
  await expect(page.locator(".fd-readout")).toContainText("Message m2");
  await expect(page.locator(".fd-verdict")).toContainText("Material degradation confirmed");
  await page.locator(".fd-forest-row").nth(3).click();
  await expect(page.locator(".fd-contrast-detail")).toContainText("grouping");
  await page.getByRole("button", { name: "Historical test split", exact: true }).click();
  await expect(page.locator(".fd-real-grid")).toContainText("not evaluated on this split");
  expect(errors).toEqual([]);
});
