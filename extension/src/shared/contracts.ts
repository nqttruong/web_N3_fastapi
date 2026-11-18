export type CaptureState = "graded" | "ungraded";
export type AnswerSource = "page_result" | "page_key" | null;
export type ExamCategory = "vocabulary" | "kanji" | "grammar" | "reading";

export interface CapturedQuestion {
  number: number | null;
  section_heading: string;
  question_text: string;
  options: string[];
  selected_answer_index: number | null;
  source_correct_answer_index: number | null;
  answer_source: AnswerSource;
  source_key_conflict: boolean;
  passage: string | null;
  points: number | null;
}

export interface BrowserCapture {
  schema_version: "1.0";
  capture_id: string;
  source: "dethitiengnhat";
  source_url: string;
  level: "N3";
  exam_title: string;
  category: ExamCategory | null;
  capture_state: CaptureState;
  captured_at: string;
  questions: CapturedQuestion[];
}

export interface ExtensionSettings {
  apiBaseUrl: string;
  frontendBaseUrl: string;
  token: string;
  dictionaryToken: string;
}

export interface ExtensionMessage {
  type: "PING" | "IMPORT_CAPTURE" | "DICT_LOOKUP" | "SAVE_WORD";
  capture?: BrowserCapture;
  text?: string;
  word?: Record<string, unknown>;
}

export interface ExtensionResponse {
  ok: boolean;
  message: string;
  draftId?: string;
  reused?: boolean;
  queued?: boolean;
  entries?: Array<{
    id: string;
    expression: string;
    reading: string | null;
    meaning_vi: string | null;
    meaning_en?: string | null;
    meaning_ja?: string | null;
    english_ipa?: string | null;
    source: string;
  }>;
  detectedLanguage?: string | null;
  webUrl?: string;
}
