import { beforeEach, describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { extractDethitiengnhat } from "../src/content/extract.js";
import { normalizeApiBaseUrl, normalizeFrontendBaseUrl } from "../src/shared/settings.js";

function page(body: string, path = "/jlpt/N3/32/3") {
  window.history.replaceState({}, "", path);
  document.body.innerHTML = body;
}

describe("Dethitiengnhat active-tab extraction", () => {
  beforeEach(() => {
    page("");
  });

  it("captures graded radio answers, answer markers, furigana, underline and linked passage", () => {
    page(`
      <h3>Đề Thi Thử JLPT N3 /32</h3>
      <div class="big_item">文法 問題１ 次の文に入れなさい</div>
      <div class="question_list"><div class="japanese-reader-content">1. 雨なので<u>中止</u>です。</div></div>
      <label><div class="answers" id="QS11">不正解: 1) のに</div><input type="radio" name="q1"></label>
      <label><div class="answers" id="QS12">正解: 2) ので</div><input type="radio" name="q1" checked></label>
      <label><div class="answers" id="QS13">3) ながら</div><input type="radio" name="q1"></label>
      <label><div class="answers" id="QS14">4) ばかりか</div><input type="radio" name="q1"></label>
      <div id="AS1">2</div><div id="diemso1">1</div>
      <div class="big_item">文章を読んで、質問に答えなさい</div>
      <div class="question_content"><div class="japanese-reader-content">図書館は夜九時まで開きます。<br><br>仕事のあとに本を借りられます。<ruby>便利<rt>べんり</rt></ruby>です。</div></div>
      <div class="question_list"><div class="japanese-reader-content">2. 図書館は何時までですか。</div></div>
      <label><div class="answers" id="QS21">正解: 1) 九時まで</div><input type="radio" name="q2" checked></label>
      <label><div class="answers" id="QS22">2) 八時まで</div><input type="radio" name="q2"></label>
      <label><div class="answers" id="QS23">3) 七時まで</div><input type="radio" name="q2"></label>
      <label><div class="answers" id="QS24">4) 六時まで</div><input type="radio" name="q2"></label>
      <div id="AS2">1</div><div id="diemso2">2</div>`);

    const result = extractDethitiengnhat();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const [grammar, reading] = result.capture.questions;
    expect(result.capture.capture_state).toBe("graded");
    expect(result.capture.category).toBeNull();
    expect(grammar).toMatchObject({
      number: 1,
      question_text: "雨なので<u>中止</u>です。",
      options: ["のに", "ので", "ながら", "ばかりか"],
      selected_answer_index: 1,
      source_correct_answer_index: 1,
      answer_source: "page_result",
    });
    expect(reading?.question_text).toBe("図書館は何時までですか。");
    expect(reading?.passage).toBe("図書館は夜九時まで開きます。\n\n仕事のあとに本を借りられます。<ruby>便利<rt>べんり</rt></ruby>です。");
    expect(result.capture.source_url).toBe("https://dethitiengnhat.com/jlpt/N3/32/3");
  });

  it("parses the shared PR2 scored Dethitiengnhat fixture", () => {
    const source = readFileSync(
      resolve(process.cwd(), "../backend/tests/fixtures/imports/dethitiengnhat_like_scored.html"),
      "utf8",
    );
    page(source);
    const selected = document.querySelector<HTMLInputElement>('input[name="QS2"]');
    if (selected) selected.checked = true;

    const result = extractDethitiengnhat();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.capture.capture_state).toBe("graded");
    expect(result.capture.questions).toHaveLength(6);
    expect(result.capture.questions.every((question) => question.options.length === 4)).toBe(true);
    expect(result.capture.questions[1]).toMatchObject({
      number: 2,
      question_text: "雨が降っている（　　）、試合は<u>中止</u>になった。",
      options: ["のに", "ので", "ながら", "ばかりか"],
      selected_answer_index: 0,
      source_correct_answer_index: 1,
      answer_source: "page_result",
    });
    expect(result.capture.questions[4]?.passage).toContain("仕事が終わってから本を借りに行ける");
    expect(result.capture.questions[2]?.question_text).toContain("<ruby>約束<rt>やくそく</rt></ruby>");
    expect(result.capture.questions[0]?.points).toBe(0);
  });

  it("does not infer unanswered choices or missing source keys before grading", () => {
    page(`
      <h3>N3 vocab</h3><div class="big_item">読み方を選びなさい</div>
      <div class="question_list"><div class="japanese-reader-content">1. 悲しい。</div></div>
      <div class="answers" id="QS11">1) かなしい</div><label><input type="radio" name="q1"></label>
      <div class="answers" id="QS12">2) あやしい</div><label><input type="radio" name="q1"></label>
      <div class="answers" id="QS13">3) くやしい</div><label><input type="radio" name="q1"></label>
      <div class="answers" id="QS14">4) やさしい</div><label><input type="radio" name="q1"></label>`);
    const result = extractDethitiengnhat();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.capture.capture_state).toBe("ungraded");
    expect(result.capture.questions[0]).toMatchObject({
      selected_answer_index: null,
      source_correct_answer_index: null,
      answer_source: null,
    });
  });

  it("flags a page key that conflicts with the graded correct marker", () => {
    page(`
      <h3>N3</h3><div class="big_item">文法 問題１</div>
      <div class="question_list"><div class="japanese-reader-content">1. 文</div></div>
      <label><div class="answers" id="QS11">正解: 1) あ</div><input type="radio" name="q1" checked></label>
      <label><div class="answers" id="QS12">2) い</div><input type="radio" name="q1"></label>
      <label><div class="answers" id="QS13">3) う</div><input type="radio" name="q1"></label>
      <label><div class="answers" id="QS14">4) え</div><input type="radio" name="q1"></label>
      <div id="AS1">2</div>`);
    const result = extractDethitiengnhat();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.capture.questions[0]).toMatchObject({
      source_correct_answer_index: 0,
      answer_source: "page_result",
      source_key_conflict: true,
    });
  });

  it("does not infer the learner's answer from a correct-result marker", () => {
    page(`
      <h3>N3</h3><div class="big_item">文法 問題１</div>
      <div class="question_list"><div class="japanese-reader-content">1. 文</div></div>
      <label><div class="answers" id="QS11">正解: 1) あ</div><input type="radio" name="q1"></label>
      <label><div class="answers" id="QS12">2) い</div><input type="radio" name="q1"></label>
      <label><div class="answers" id="QS13">3) う</div><input type="radio" name="q1"></label>
      <label><div class="answers" id="QS14">4) え</div><input type="radio" name="q1"></label>`);
    const result = extractDethitiengnhat();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.capture.questions[0]).toMatchObject({
      selected_answer_index: null,
      source_correct_answer_index: 0,
    });
  });

  it("rejects listing pages, unsupported hostnames, and unknown DOM layouts", () => {
    page("<h3>N3</h3>", "/jlpt/N3");
    expect(extractDethitiengnhat()).toMatchObject({ ok: false });
    window.history.replaceState({}, "", "/jlpt/N3/32/1");
    window.history.replaceState({}, "", "/jlpt/N3/32/1");
    expect(extractDethitiengnhat()).toMatchObject({ ok: false });
    page("<h3>N3</h3><div class='question_list'>no answers</div>");
    expect(extractDethitiengnhat()).toMatchObject({ ok: false });
  });
});

describe("loopback settings validation", () => {
  it("allows only loopback URLs and normalizes the defaults", () => {
    expect(normalizeApiBaseUrl("http://127.0.0.1:8000/api/v1/")).toBe("http://127.0.0.1:8000/api/v1");
    expect(normalizeFrontendBaseUrl("http://localhost:3000")).toBe("http://localhost:3000");
    expect(normalizeApiBaseUrl("https://example.com/api/v1")).toBeNull();
    expect(normalizeFrontendBaseUrl("http://127.0.0.1:3000/path")).toBeNull();
    expect(normalizeApiBaseUrl("http://user:pass@127.0.0.1:8000/api/v1")).toBeNull();
  });
});
