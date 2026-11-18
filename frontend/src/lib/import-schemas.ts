import { z } from "zod";

import { EXAM_CATEGORIES, type ExamCategory } from "@/lib/api/types";

export const IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"] as const;

const optionalUrl = z
  .string()
  .trim()
  .max(2048, "URL quá dài")
  .refine((v) => {
    if (!v) return true;
    try {
      const u = new URL(v);
      return u.protocol === "http:" || u.protocol === "https:";
    } catch {
      return false;
    }
  }, "URL phải bắt đầu bằng http:// hoặc https://");

export const importMetaSchema = z.object({
  source_url: optionalUrl,
  title: z.string().trim().max(300, "Tên đề tối đa 300 ký tự"),
  category: z.union([z.enum(EXAM_CATEGORIES), z.literal("")]),
});
export type ImportMetaValues = z.infer<typeof importMetaSchema>;

export function textImportSchema(maxChars: number) {
  return importMetaSchema.extend({
    text: z
      .string()
      .refine((v) => v.trim().length > 0, "Vui lòng dán nội dung đề")
      .refine((v) => v.length <= maxChars, `Tối đa ${maxChars.toLocaleString("vi-VN")} ký tự`),
  });
}

export function htmlImportSchema(maxBytes: number) {
  return importMetaSchema.extend({
    html: z
      .string()
      .refine((v) => v.trim().length > 0, "Vui lòng dán mã HTML")
      .refine((v) => /<[a-z!/][^>]*>/i.test(v), "Nội dung không giống HTML (thiếu thẻ)")
      .refine(
        (v) => new TextEncoder().encode(v).length <= maxBytes,
        `HTML tối đa ${(maxBytes / 1_000_000).toLocaleString("vi-VN")} MB`,
      ),
  });
}

export function toImportMeta(values: ImportMetaValues): {
  source_url?: string;
  title?: string;
  category?: ExamCategory;
} {
  return {
    source_url: values.source_url.trim() || undefined,
    title: values.title.trim() || undefined,
    category: values.category || undefined,
  };
}

export interface ImageCheck {
  ok: File[];
  errors: string[];
}

/** Client-side pre-check; the server re-validates by file content. */
export function checkImages(files: File[], limits: { maxImages: number; maxBytes: number }): ImageCheck {
  const errors: string[] = [];
  if (files.length > limits.maxImages) errors.push(`Tối đa ${limits.maxImages} ảnh mỗi lần.`);
  const ok: File[] = [];
  for (const f of files) {
    if (!(IMAGE_TYPES as readonly string[]).includes(f.type)) {
      errors.push(`“${f.name}”: chỉ hỗ trợ PNG, JPG, WEBP.`);
    } else if (f.size > limits.maxBytes) {
      errors.push(`“${f.name}”: vượt quá ${Math.round(limits.maxBytes / 1024 / 1024)} MB.`);
    } else if (f.size === 0) {
      errors.push(`“${f.name}”: tệp rỗng.`);
    } else {
      ok.push(f);
    }
  }
  return { ok, errors };
}

/** `<input type="datetime-local">` value (local time) ↔ ISO string with offset. */
export function localInputToIso(value: string): string | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

export function isoToLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
