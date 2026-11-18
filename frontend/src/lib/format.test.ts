import { describe, expect, it } from "vitest";

import { formatDateTime, formatDuration, formatPercent } from "./format";

describe("format helpers", () => {
  it("formats accuracy ratios", () => {
    expect(formatPercent(null)).toBe("—");
    expect(formatPercent(0.5)).toBe("50%");
    expect(formatPercent(2 / 3)).toBe("66,7%");
  });

  it("formats durations", () => {
    expect(formatDuration("2026-01-01T00:00:00Z", null)).toBe("—");
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:00:45Z")).toBe("45 giây");
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:12:05Z")).toBe("12 phút 5 giây");
  });

  it("formats exam metrics and timestamps using the selected interface locale", () => {
    expect(formatPercent(2 / 3, "en")).toBe("66.7%");
    expect(formatPercent(2 / 3, "ja")).toBe("66.7%");
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:12:05Z", "en")).toBe("12 min 5 sec");
    expect(formatDuration("2026-01-01T00:00:00Z", "2026-01-01T00:12:05Z", "ja")).toBe("12 分 5 秒");
    expect(formatDateTime("2026-01-01T00:00:00Z", "en")).toContain("Jan");
    expect(formatDateTime("2026-01-01T00:00:00Z", "ja")).toContain("2026");
  });
});
