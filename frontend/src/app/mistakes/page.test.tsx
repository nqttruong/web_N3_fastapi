import { describe, expect, it, vi } from "vitest";

const { redirect } = vi.hoisted(() => ({ redirect: vi.fn() }));
vi.mock("next/navigation", () => ({ redirect }));

import MistakesPage from "./page";

describe("legacy mistakes deep link", () => {
  it("redirects the old route to the Mistake Notebook tab in Analytics", () => {
    MistakesPage();
    expect(redirect).toHaveBeenCalledWith("/analytics/jlpt?tab=mistakes");
  });
});
