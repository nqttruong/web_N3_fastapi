import type { BrowserCapture, CapturedQuestion } from "../shared/contracts.js";

export type ExtractionResult =
  | { ok: true; capture: BrowserCapture }
  | { ok: false; error: string };

/** This function is injected into the active tab only after the user opens the extension popup. */
export function extractDethitiengnhat(): ExtractionResult {
  const here = new URL(window.location.href);
  const path = here.pathname.match(/^\/jlpt\/N3\/(\d+)\/(1|3)\/?$/);
  if (
    here.hostname !== "dethitiengnhat.com" &&
    here.hostname !== "www.dethitiengnhat.com"
  ) return { ok: false, error: "Chỉ hỗ trợ trang đề trên dethitiengnhat.com." };
  if (!path) return { ok: false, error: "Hãy mở một đề N3 cụ thể (phần Từ vựng hoặc Ngữ pháp/Đọc hiểu)." };

  type MutableQuestion = {
    number: number | null;
    section_heading: string;
    question_text: string;
    options: Map<number, string>;
    marks: Map<number, "correct" | "incorrect">;
    checked: number | null;
    key: number | null;
    passage: string | null;
    points: number | null;
  };

  const inline = (node: Node): string => {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent ?? "";
    if (!(node instanceof Element)) return "";
    const tag = node.tagName.toLowerCase();
    if (["script", "style", "button", "input", "textarea", "select", "svg"].includes(tag)) return "";
    if (tag === "br") return "\n";
    const children = Array.from(node.childNodes, inline).join("");
    if (tag === "u") return `<u>${children}</u>`;
    if (tag === "ruby") return `<ruby>${children}</ruby>`;
    if (tag === "rt") return `<rt>${children}</rt>`;
    if (["div", "p", "li"].includes(tag)) return `\n${children}\n`;
    return children;
  };
  const tidy = (value: string): string => value
    .split("\n")
    .map((line) => line.replace(/[\t\r\f\v ]+/g, " ").trim())
    .filter((line, index, all) => line !== "" || (index > 0 && all[index - 1] !== ""))
    .join("\n")
    .trim();
  const toNumber = (value: string): number | null => {
    const folded = value.replace(/[０-９]/g, (d) => String.fromCharCode(d.charCodeAt(0) - 0xfee0));
    const number = Number(folded);
    return Number.isInteger(number) ? number : null;
  };
  const textOf = (node: Element | null): string => node ? tidy(inline(node)) : "";
  const questions: MutableQuestion[] = [];
  const passages: string[] = [];
  let current: MutableQuestion | null = null;
  let heading = "";
  let passage: string | null = null;
  let hasResultMarks = false;

  const nodes = document.querySelectorAll(
    "div.big_item, div.question_content, div.question_list, div.answers[id^='QS'], div[id^='AS'], div[id^='diemso']",
  );
  for (const node of nodes) {
    if (node.classList.contains("big_item")) {
      heading = textOf(node);
      passage = null;
    } else if (node.classList.contains("question_content")) {
      const reader = node.querySelector(".japanese-reader-content") ?? node;
      passage = textOf(reader) || null;
      if (passage && !passages.includes(passage)) passages.push(passage);
    } else if (node.classList.contains("question_list")) {
      const reader = node.querySelector(".japanese-reader-content") ?? node;
      const fullText = textOf(reader);
      const numberMatch = /^\s*([0-9０-９]{1,3})\s*[.．]\s*/.exec(fullText);
      current = {
        number: numberMatch ? toNumber(numberMatch[1]!) : null,
        section_heading: heading,
        question_text: numberMatch ? fullText.slice(numberMatch[0].length) : fullText,
        options: new Map(),
        marks: new Map(),
        checked: null,
        key: null,
        passage,
        points: null,
      };
      questions.push(current);
    } else if (current && node.classList.contains("answers")) {
      const match = /^QS(\d+)([1-6])$/.exec(node.id);
      if (!match) continue;
      const questionNumber = Number(match[1]);
      const optionNumber = Number(match[2]);
      current.number ??= questionNumber;
      const raw = textOf(node);
      const wrong = /^\s*不正解\s*[:：]/.test(raw);
      const correct = !wrong && /^\s*正解\s*[:：]/.test(raw);
      if (wrong || correct) {
        hasResultMarks = true;
        current.marks.set(optionNumber, wrong ? "incorrect" : "correct");
      }
      current.options.set(optionNumber, raw.replace(/^\s*(?:(?:不正解|正解)\s*[:：]\s*)?(?:[1-6１-６]\s*[)）]\s*)?/, "").trim());
      const label = node.closest("label");
      const radio = label?.querySelector<HTMLInputElement>("input[type=radio]");
      if (radio?.checked) current.checked = optionNumber;
    } else if (current && /^AS\d+$/.test(node.id)) {
      current.number = Number(node.id.slice(2));
      current.key = toNumber(node.textContent?.trim() ?? "");
    } else if (current && /^diemso\d+$/.test(node.id)) {
      const points = Number(node.textContent?.trim());
      current.points = Number.isFinite(points) ? points : null;
    }
  }

  if (!questions.length || questions.every((question) => question.options.size === 0)) {
    return { ok: false, error: "Không tìm thấy câu hỏi và phương án theo cấu trúc đã hỗ trợ." };
  }
  const examTitle = tidy(document.querySelector("h3")?.textContent ?? document.title).slice(0, 300);
  const result: CapturedQuestion[] = questions.map((q) => {
    const optionNumbers = [...q.options.keys()].sort((a, b) => a - b);
    const options = optionNumbers.map((n) => q.options.get(n) ?? "");
    const correctMarker = [...q.marks.entries()].filter(([, resultMark]) => resultMark === "correct").map(([n]) => n);
    const wrongMarker = [...q.marks.entries()].filter(([, resultMark]) => resultMark === "incorrect").map(([n]) => n);
    const markerKey = correctMarker.length === 1 ? correctMarker[0]! : null;
    const sourceKey = markerKey ?? q.key;
    // A correct-result marker identifies the key, not necessarily what the learner selected.
    // A wrong-result marker identifies an actual selected distractor when radio state is gone.
    const selection = q.checked ?? (wrongMarker.length === 1 ? wrongMarker[0]! : null);
    const sourceKeyConflict = markerKey !== null && q.key !== null && markerKey !== q.key;
    const answerSource = markerKey !== null ? "page_result" : q.key !== null ? "page_key" : null;
    const numericIndex = (oneBased: number | null): number | null => {
      if (oneBased === null) return null;
      const index = optionNumbers.indexOf(oneBased);
      return index >= 0 ? index : null;
    };
    return {
      number: q.number,
      section_heading: q.section_heading,
      question_text: q.question_text,
      options,
      selected_answer_index: numericIndex(selection),
      source_correct_answer_index: numericIndex(sourceKey),
      answer_source: answerSource,
      source_key_conflict: sourceKeyConflict,
      passage: q.passage,
      points: q.points,
    };
  });

  return {
    ok: true,
    capture: {
      schema_version: "1.0",
      capture_id: crypto.randomUUID(),
      source: "dethitiengnhat",
      source_url: `${here.origin}${here.pathname}`,
      level: "N3",
      exam_title: examTitle,
      category: path[2] === "1" ? "vocabulary" : null,
      capture_state: hasResultMarks ? "graded" : "ungraded",
      captured_at: new Date().toISOString(),
      questions: result,
    },
  };
}
