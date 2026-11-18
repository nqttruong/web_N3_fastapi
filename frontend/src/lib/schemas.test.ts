import { describe, expect, it } from "vitest";

import { examFormSchema, questionFormSchema, toExamInput, toQuestionInput } from "./schemas";

const validExam = {
  title: "  N3 文法 1  ",
  level: "N3" as const,
  category: "grammar" as const,
  source_url: "",
  description: "",
  status: "draft" as const,
};

describe("examFormSchema", () => {
  it("accepts a minimal exam and maps blanks to null", () => {
    const parsed = examFormSchema.parse(validExam);
    expect(toExamInput(parsed)).toEqual({
      title: "N3 文法 1",
      level: "N3",
      category: "grammar",
      status: "draft",
      source_url: null,
      description: null,
    });
  });

  it.each([
    [{ title: "   " }, "title"],
    [{ category: "listening" }, "category"],
    [{ source_url: "ftp://example.com" }, "source_url"],
    [{ source_url: "not a url" }, "source_url"],
    [{ level: "N2" }, "level"],
  ])("rejects %j", (patch, field) => {
    const result = examFormSchema.safeParse({ ...validExam, ...patch });
    expect(result.success).toBe(false);
    expect(result.error?.issues.map((i) => i.path[0])).toContain(field);
  });
});

const validQuestion = {
  question_number: "3",
  question_type: "grammar_form" as const,
  question_text: "雨が降っている（　　）、試合は中止になった。",
  options: ["ので", "のに", "", ""],
  correct_answer: "1" as const,
  verified: true,
  passage_id: "",
};

describe("questionFormSchema", () => {
  it("coerces the number, drops empty trailing options and marks verified", () => {
    const parsed = questionFormSchema.parse(validQuestion);
    expect(toQuestionInput(parsed)).toEqual({
      question_number: 3,
      question_type: "grammar_form",
      question_text: "雨が降っている（　　）、試合は中止になった。",
      options: ["ので", "のに"],
      correct_answer: 1,
      answer_status: "verified",
      passage_id: null,
    });
  });

  it("defaults to unverified when the checkbox is off and missing when no answer", () => {
    const unverified = questionFormSchema.parse({ ...validQuestion, verified: false });
    expect(toQuestionInput(unverified).answer_status).toBe("unverified");
    const missing = questionFormSchema.parse({ ...validQuestion, correct_answer: "", verified: false });
    expect(toQuestionInput(missing)).toMatchObject({ correct_answer: null, answer_status: "missing" });
  });

  it.each([
    [{ options: ["ので", "", "", ""] }, "options"],
    [{ options: ["ので", "", "のに", ""] }, "options"],
    [{ options: ["ので", "ので", "", ""] }, "options"],
    [{ correct_answer: "3" }, "correct_answer"],
    [{ correct_answer: "", verified: true }, "verified"],
    [{ question_number: "0" }, "question_number"],
    [{ question_number: "abc" }, "question_number"],
    [{ question_text: "  " }, "question_text"],
  ])("rejects %j", (patch, field) => {
    const result = questionFormSchema.safeParse({ ...validQuestion, ...patch });
    expect(result.success).toBe(false);
    expect(result.error?.issues.map((i) => i.path[0])).toContain(field);
  });
});
