import { describe, expect, it } from "vitest";

import type { ImportDraft, Issue } from "@/lib/api/types";

import { candidatesFrom } from "./commit-dialog";

const issue = (code: string, data: Record<string, unknown> | null): Issue => ({
  severity: "warning",
  code,
  message: code,
  question_key: null,
  data,
});

describe("candidatesFrom", () => {
  it("offers each existing exam once, from duplicate issues only", () => {
    const draft = {
      issues: [
        issue("duplicate_source_url", { exam_id: "e1", title: "A" }),
        issue("duplicate_exam", { exam_id: "e1", title: "A" }),
        issue("questions_in_other_exam", { exam_id: "e2", title: "B" }),
        issue("existing_attempts", { exam_id: "e3", title: "C" }),
        issue("duplicate_draft", { draft_id: "d1" }),
      ],
    } as unknown as ImportDraft;
    expect(candidatesFrom(draft).map((c) => [c.exam_id, c.reason])).toEqual([
      ["e1", "duplicate_source_url"],
      ["e2", "questions_in_other_exam"],
    ]);
  });
});
