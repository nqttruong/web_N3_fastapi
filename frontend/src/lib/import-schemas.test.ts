import { describe, expect, it } from "vitest";

import {
  checkImages,
  htmlImportSchema,
  isoToLocalInput,
  localInputToIso,
  textImportSchema,
  toImportMeta,
} from "./import-schemas";

const meta = { source_url: "", title: "", category: "" as const };

describe("import form schemas", () => {
  it("validates text input and limits", () => {
    const schema = textImportSchema(10);
    expect(schema.safeParse({ ...meta, text: "1. 文" }).success).toBe(true);
    expect(schema.safeParse({ ...meta, text: "   " }).success).toBe(false);
    expect(schema.safeParse({ ...meta, text: "あ".repeat(11) }).success).toBe(false);
    expect(schema.safeParse({ ...meta, text: "x", source_url: "ftp://a" }).success).toBe(false);
  });

  it("requires something that looks like HTML and checks byte size", () => {
    const schema = htmlImportSchema(20);
    expect(schema.safeParse({ ...meta, html: "<p>1</p>" }).success).toBe(true);
    expect(schema.safeParse({ ...meta, html: "plain text" }).success).toBe(false);
    // 7 Japanese chars = 21 bytes in UTF-8
    expect(schema.safeParse({ ...meta, html: "<p>あいうえおかき</p>" }).success).toBe(false);
  });

  it("drops empty meta fields", () => {
    expect(toImportMeta({ source_url: " ", title: "", category: "" })).toEqual({
      source_url: undefined,
      title: undefined,
      category: undefined,
    });
  });
});

describe("checkImages", () => {
  const file = (name: string, type: string, size: number) => new File([new Uint8Array(size)], name, { type });

  it("accepts png/jpeg/webp within limits", () => {
    const r = checkImages([file("a.png", "image/png", 10), file("b.webp", "image/webp", 10)], { maxImages: 5, maxBytes: 100 });
    expect(r.ok).toHaveLength(2);
    expect(r.errors).toEqual([]);
  });

  it("reports wrong type, oversize, empty and too many", () => {
    const r = checkImages(
      [file("a.gif", "image/gif", 10), file("b.png", "image/png", 1000), file("c.png", "image/png", 0)],
      { maxImages: 2, maxBytes: 100 },
    );
    expect(r.ok).toHaveLength(0);
    expect(r.errors).toHaveLength(4);
  });
});

describe("datetime helpers", () => {
  it("round-trips local input values", () => {
    const iso = localInputToIso("2026-11-10T09:30");
    expect(iso).not.toBeNull();
    expect(isoToLocalInput(iso)).toBe("2026-11-10T09:30");
    expect(localInputToIso("")).toBeNull();
  });
});
