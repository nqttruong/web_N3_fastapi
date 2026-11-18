import { z } from "zod";

import {
  EXAM_CATEGORIES,
  EXAM_STATUSES,
  QUESTION_TYPES,
  type ExamCreateInput,
  type QuestionCreateInput,
} from "@/lib/api/types";

const optionalHttpUrl = z
  .string()
  .trim()
  .max(2048, "URL quá dài")
  .refine((value) => {
    if (value === "") return true;
    try {
      const url = new URL(value);
      return url.protocol === "http:" || url.protocol === "https:";
    } catch {
      return false;
    }
  }, "URL phải bắt đầu bằng http:// hoặc https://");

export const examFormSchema = z.object({
  title: z.string().trim().min(1, "Vui lòng nhập tên đề").max(300, "Tên đề tối đa 300 ký tự"),
  level: z.literal("N3"),
  category: z.enum(EXAM_CATEGORIES, { error: "Vui lòng chọn loại đề" }),
  source_url: optionalHttpUrl,
  description: z.string().trim().max(5000, "Mô tả tối đa 5000 ký tự"),
  status: z.enum(EXAM_STATUSES),
});
export type ExamFormValues = z.infer<typeof examFormSchema>;

export function toExamInput(values: ExamFormValues): ExamCreateInput {
  return {
    title: values.title.trim(),
    level: values.level,
    category: values.category,
    status: values.status,
    source_url: values.source_url.trim() || null,
    description: values.description.trim() || null,
  };
}

export const MAX_OPTIONS = 4;

export const questionFormSchema = z
  .object({
    question_number: z.coerce
      .number<string | number>({ error: "Số câu phải là số" })
      .int("Số câu phải là số nguyên")
      .min(1, "Số câu tối thiểu là 1")
      .max(999, "Số câu tối đa là 999"),
    question_type: z.enum(QUESTION_TYPES),
    question_text: z
      .string()
      .trim()
      .min(1, "Vui lòng nhập nội dung câu hỏi")
      .max(5000, "Nội dung tối đa 5000 ký tự"),
    options: z.array(z.string().trim().max(1000, "Lựa chọn tối đa 1000 ký tự")).length(MAX_OPTIONS),
    correct_answer: z.enum(["", "1", "2", "3", "4"]),
    verified: z.boolean(),
    passage_id: z.string(),
  })
  .superRefine((values, ctx) => {
    const filled = values.options.map((o) => o.trim() !== "");
    const count = filled.filter(Boolean).length;
    if (count < 2) {
      ctx.addIssue({ code: "custom", path: ["options"], message: "Cần ít nhất 2 lựa chọn" });
    }
    const lastFilled = filled.lastIndexOf(true);
    if (filled.slice(0, lastFilled + 1).includes(false)) {
      ctx.addIssue({
        code: "custom",
        path: ["options"],
        message: "Các lựa chọn phải liền nhau (không bỏ trống ở giữa)",
      });
    }
    const trimmed = values.options.map((o) => o.trim()).filter(Boolean);
    if (new Set(trimmed).size !== trimmed.length) {
      ctx.addIssue({ code: "custom", path: ["options"], message: "Các lựa chọn không được trùng nhau" });
    }
    if (values.correct_answer !== "" && !filled[Number(values.correct_answer) - 1]) {
      ctx.addIssue({
        code: "custom",
        path: ["correct_answer"],
        message: "Đáp án đúng phải là một lựa chọn đã nhập",
      });
    }
    if (values.verified && values.correct_answer === "") {
      ctx.addIssue({
        code: "custom",
        path: ["verified"],
        message: "Chỉ xác nhận được khi đã chọn đáp án",
      });
    }
  });
export type QuestionFormInput = z.input<typeof questionFormSchema>;
export type QuestionFormValues = z.output<typeof questionFormSchema>;

export function toQuestionInput(values: QuestionFormValues): QuestionCreateInput {
  const correct = values.correct_answer === "" ? null : Number(values.correct_answer);
  return {
    question_number: values.question_number,
    question_type: values.question_type,
    question_text: values.question_text.trim(),
    options: values.options.map((o) => o.trim()).filter(Boolean),
    correct_answer: correct,
    answer_status: correct === null ? "missing" : values.verified ? "verified" : "unverified",
    passage_id: values.passage_id || null,
  };
}
