import type {
  AnswerSource,
  AnswerStatus,
  ExamCategory,
  ExamStatus,
  ImportMethod,
  ImportStatus,
  QuestionType,
  Severity,
} from "@/lib/api/types";

export const categoryLabels: Record<ExamCategory, string> = {
  vocabulary: "Từ vựng",
  kanji: "Kanji",
  grammar: "Ngữ pháp",
  reading: "Đọc hiểu",
};

export const statusLabels: Record<ExamStatus, string> = {
  draft: "Bản nháp",
  ready: "Sẵn sàng",
  archived: "Đã lưu trữ",
};

export const answerStatusLabels: Record<AnswerStatus, string> = {
  missing: "Chưa có đáp án",
  unverified: "Chưa xác nhận",
  verified: "Đã xác nhận",
};

export const questionTypeLabels: Record<QuestionType, string> = {
  kanji_reading: "Đọc kanji (漢字読み)",
  orthography: "Cách viết (表記)",
  word_formation: "Cấu tạo từ (語形成)",
  contextual_definition: "Điền từ theo ngữ cảnh (文脈規定)",
  paraphrase: "Từ đồng nghĩa (言い換え類義)",
  usage: "Cách dùng từ (用法)",
  grammar_form: "Chọn ngữ pháp (文法形式の判断)",
  sentence_composition: "Sắp xếp câu (文の組み立て)",
  text_grammar: "Ngữ pháp đoạn văn (文章の文法)",
  reading_short: "Đọc hiểu ngắn (短文)",
  reading_medium: "Đọc hiểu trung (中文)",
  reading_long: "Đọc hiểu dài (長文)",
  information_retrieval: "Tìm thông tin (情報検索)",
  other: "Khác",
};

export const OPTION_MARKS = ["1", "2", "3", "4", "5", "6"] as const;

export const importStatusLabels: Record<ImportStatus, string> = {
  uploaded: "Đã tải lên",
  parsing: "Đang phân tích",
  needs_review: "Cần kiểm tra",
  ready: "Sẵn sàng lưu",
  committed: "Đã lưu thành đề",
  failed: "Lỗi",
};

export const importMethodLabels: Record<ImportMethod, string> = {
  text: "Dán văn bản",
  html: "Dán HTML",
  images: "Ảnh chụp (OCR)",
  browser_capture: "Chrome Extension",
};

export const answerSourceLabels: Record<AnswerSource, string> = {
  manual: "Nhập thủ công",
  site_key: "Đáp án trang nguồn",
  user_entered: "Bạn tự chọn",
  ocr: "Đọc từ ảnh (OCR)",
};

export const severityLabels: Record<Severity, string> = {
  error: "Lỗi",
  warning: "Cảnh báo",
  info: "Thông tin",
};

export const adapterLabels: Record<string, string> = {
  generic_text: "Bộ tách văn bản chung",
  generic_html: "Bộ tách HTML chung (chưa kiểm chứng cấu trúc)",
  dethitiengnhat_html: "Dethitiengnhat (cấu trúc đã kiểm chứng)",
  dethitiengnhat_capture: "Dethitiengnhat (capture từ extension)",
  ocr_text: "OCR + bộ tách văn bản",
};

export const explanationStatusLabels: Record<"generated" | "needs_review" | "approved" | "rejected", string> = {
  generated: "Chờ xác nhận",
  needs_review: "Cần kiểm tra",
  approved: "Đã xác nhận",
  rejected: "Chưa chính xác",
};

export const jobStatusLabels: Record<string, string> = {
  pending: "Đang chờ",
  running: "Đang chữa",
  completed: "Hoàn tất",
  partial_failed: "Hoàn tất một phần (có câu lỗi)",
  failed: "Thất bại",
  cancelled: "Đã huỷ",
};

export const jobItemStatusLabels: Record<string, string> = {
  pending: "Đang chờ",
  running: "Đang chữa…",
  cached: "Đã có lời giải",
  succeeded: "Đã chữa",
  failed: "Lỗi",
  skipped: "Bỏ qua",
  cancelled: "Đã huỷ",
};

export const knowledgeTypeLabels: Record<"grammar" | "vocabulary" | "kanji" | "reading_skill", string> = {
  grammar: "Ngữ pháp",
  vocabulary: "Từ vựng",
  kanji: "Kanji",
  reading_skill: "Kỹ năng đọc",
};

export const roleLabels: Record<"tests" | "distractor" | "context", string> = {
  tests: "Được hỏi",
  distractor: "Phương án nhiễu",
  context: "Ngữ cảnh",
};

export const priorityLabels: Record<"review_now" | "due_soon" | "stable" | "insufficient_data", string> = {
  review_now: "Cần ôn ngay",
  due_soon: "Sắp đến hạn",
  stable: "Đang ổn định",
  insufficient_data: "Chưa đủ dữ liệu",
};

export const reviewTypeLabels: Record<"original_question" | "knowledge_recall" | "contrast", string> = {
  original_question: "Làm lại câu sai",
  knowledge_recall: "Nhớ kiến thức",
  contrast: "Phân biệt dễ nhầm",
};

export const srsStateLabels: Record<"new" | "learning" | "review" | "mastered", string> = {
  new: "Mới",
  learning: "Đang học",
  review: "Ôn dài hạn",
  mastered: "Thành thạo",
};

export const ratingLabels: Record<"again" | "hard" | "good" | "easy", string> = {
  again: "Quên",
  hard: "Khó",
  good: "Tốt",
  easy: "Dễ",
};

export const confidenceLabels: Record<"none" | "low" | "medium" | "high", string> = {
  none: "chưa có dữ liệu",
  low: "độ tin cậy thấp",
  medium: "độ tin cậy trung bình",
  high: "độ tin cậy cao",
};

export const blockedReasonLabels: Record<string, string> = {
  answer_not_verified: "Đáp án câu gốc chưa được xác nhận",
  missing_passage: "Câu đọc hiểu thiếu đoạn văn",
  question_deleted: "Câu hỏi đã bị xoá",
  knowledge_inactive: "Mục kiến thức đã lưu trữ hoặc gộp",
};
