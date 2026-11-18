// Types mirroring the backend OpenAPI contract (docs/api-contract.md).

export const EXAM_CATEGORIES = ["vocabulary", "kanji", "grammar", "reading"] as const;
export type ExamCategory = (typeof EXAM_CATEGORIES)[number];

export const EXAM_STATUSES = ["draft", "ready", "archived"] as const;
export type ExamStatus = (typeof EXAM_STATUSES)[number];

export const JLPT_LEVELS = ["N1", "N2", "N3", "N4", "N5"] as const;
export type JlptLevel = (typeof JLPT_LEVELS)[number];

export const ANSWER_STATUSES = ["missing", "unverified", "verified"] as const;
export type AnswerStatus = (typeof ANSWER_STATUSES)[number];

export const QUESTION_TYPES = [
  "kanji_reading",
  "orthography",
  "word_formation",
  "contextual_definition",
  "paraphrase",
  "usage",
  "grammar_form",
  "sentence_composition",
  "text_grammar",
  "reading_short",
  "reading_medium",
  "reading_long",
  "information_retrieval",
  "other",
] as const;
export type QuestionType = (typeof QUESTION_TYPES)[number];

export interface PageMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface Page<T> {
  data: T[];
  meta: PageMeta;
}

export interface Exam {
  id: string;
  source_id: string | null;
  source_name: string | null;
  source_url: string | null;
  level: JlptLevel;
  category: ExamCategory;
  title: string;
  description: string | null;
  status: ExamStatus;
  question_count: number;
  verified_answer_count: number;
  attempt_count: number | null;
  latest_attempt_started_at: string | null;
  latest_attempt_accuracy: number | null;
  approved_explanation_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface ExamCreateInput {
  title: string;
  level: JlptLevel;
  category: ExamCategory;
  description?: string | null;
  source_url?: string | null;
  status?: ExamStatus;
}

export type ExamUpdateInput = Partial<ExamCreateInput>;

export interface Passage {
  id: string;
  exam_id: string;
  content: string;
  created_at: string;
}

export interface Question {
  id: string;
  exam_id: string;
  passage_id: string | null;
  question_number: number;
  question_type: QuestionType;
  question_text: string;
  options: string[];
  correct_answer: number | null;
  answer_status: AnswerStatus;
  answer_source?: AnswerSource | null;
  created_at: string;
  updated_at: string;
}

export interface QuestionCreateInput {
  question_number: number;
  question_type: QuestionType;
  question_text: string;
  options: string[];
  correct_answer: number | null;
  answer_status?: AnswerStatus;
  passage_id?: string | null;
}

export interface AttemptSummary {
  id: string;
  exam_id: string;
  exam_title: string;
  exam_category: ExamCategory;
  started_at: string;
  completed_at: string | null;
  total_questions: number;
  correct_count: number;
  incorrect_count: number;
  unanswered_count: number;
  ungraded_count: number;
  source?: "practice" | "import";
  accuracy: number | null;
  approved_explanation_count: number | null;
  pending_explanation_count: number | null;
  created_at: string;
}

export interface AttemptAnswer {
  question_id: string;
  question_number: number;
  question_type: QuestionType;
  question_text: string;
  options: string[];
  passage_id: string | null;
  selected_answer: number | null;
  correct_answer: number | null;
  is_correct: boolean | null;
  current_answer_status: AnswerStatus;
}

export interface AttemptDetail extends AttemptSummary {
  exam_source_url: string | null;
  answers: AttemptAnswer[];
}

export interface Mistake {
  question_id: string;
  exam_id: string;
  exam_title: string;
  exam_category: ExamCategory;
  question_number: number;
  question_type: QuestionType;
  question_text: string;
  options: string[];
  passage_id: string | null;
  occurrences: number;
  first_wrong_at: string;
  last_wrong_at: string;
  latest_attempt_id: string;
  latest_attempt_answer_id: string;
  latest_attempt_started_at: string;
  latest_selected_answer: number;
  correct_answer_at_submission: number | null;
  current_answer_status: AnswerStatus;
  status: "derived";
}

export interface JlptAnalytics {
  attempt_count: number;
  correct: number;
  incorrect: number;
  unanswered: number;
  ungraded: number;
  accuracy: number | null;
  correct_over_all: number | null;
  average_duration_seconds: number | null;
  skill_results: Record<string, { correct: number; incorrect: number; unanswered: number; ungraded: number; total: number }>;
  mistakes_by_question_type: Record<string, number>;
  trend: { week: string; attempts: number; correct: number; incorrect: number; unanswered: number; ungraded: number }[];
  repeated_exams: { exam_id: string; exam_title: string; attempts: number; latest_at: string }[];
  sources: Record<string, number>;
  android_attempt_count: number | null;
  listening_data_available: boolean;
  score_note: string;
}

export interface LearningPack {
  id: string;
  title: string;
  jlpt_level: string;
  source_version: number;
  source_commit_sha: string | null;
  license_blocked_count: number;
  active_item_count: number;
  synced_at: string;
  is_archived: boolean;
}

export interface LearningSyncRun {
  id: string;
  status: "queued" | "running" | "succeeded" | "no_changes" | "failed";
  trigger: "startup" | "interval" | "manual";
  source_commit_sha: string | null;
  source_manifest_hash: string | null;
  counts: Record<string, number>;
  error: string | null;
  attempts: number;
  requested_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface LearningSyncStatus {
  source_configured: boolean;
  source_available: boolean;
  source_description: string;
  interval_minutes: number;
  last_checked_at: string | null;
  last_success_at: string | null;
  current_versions: LearningPack[];
  active_counts: Record<string, number>;
  last_run: LearningSyncRun | null;
}

export interface SyncAdminDevice {
  device_id: string;
  device_name: string;
  paired_at: string;
  last_seen_at: string | null;
  last_pull_at: string | null;
  last_push_at: string | null;
  revoked_at: string | null;
}

export interface PairingCodeResult {
  pairing_code: string;
  expires_at: string;
  expires_in_minutes: number;
}

export interface LearningItem {
  id: string;
  stable_source_id: string;
  item_type: "vocabulary" | "kanji" | "grammar";
  jlpt_level: string;
  pack_id: string;
  pack_title: string;
  source_version: number;
  lesson_id: string;
  lesson_number: number;
  lesson_title: string;
  order_index: number;
  source_name: string;
  source_license: string;
  payload: Record<string, unknown>;
  examples: { japanese: string; furigana: string | null; translationVi: string | null }[];
}

export interface LearningItemPage {
  items: LearningItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface AttemptCreateInput {
  exam_id: string;
  started_at: string;
  completed_at?: string;
  answers: { question_id: string; selected_answer: number | null }[];
}

export interface DashboardSummary {
  total_exams: number;
  total_questions: number;
  total_attempts: number;
  total_correct: number;
  total_incorrect: number;
  total_unanswered: number;
  total_ungraded: number;
  accuracy: number | null;
  recent_exams: Exam[];
  recent_attempts: AttemptSummary[];
}

export interface Health {
  status: "ok" | "degraded";
  database: "ok" | "unavailable";
  environment: string;
  version: string;
}

// ------------------------------------------------------------------ PR2: imports
export const ANSWER_SOURCES = ["manual", "site_key", "user_entered", "ocr"] as const;
export type AnswerSource = (typeof ANSWER_SOURCES)[number];

export const IMPORT_STATUSES = ["uploaded", "parsing", "needs_review", "ready", "committed", "failed"] as const;
export type ImportStatus = (typeof IMPORT_STATUSES)[number];
export type ImportMethod = "text" | "html" | "images" | "browser_capture";
export type Severity = "error" | "warning" | "info";

export interface ParserNote {
  code: string;
  message: string;
}

export interface Issue {
  severity: Severity;
  code: string;
  message: string;
  question_key: string | null;
  data: Record<string, unknown> | null;
}

export interface DraftExam {
  title: string;
  category: ExamCategory | null;
  level: JlptLevel;
  description: string | null;
}

export interface DraftPassage {
  key: string;
  content: string;
}

export interface DraftQuestion {
  key: string;
  include: boolean;
  question_number: number | null;
  question_type: QuestionType;
  question_text: string;
  options: string[];
  passage_key: string | null;
  site_answer: number | null;
  user_answer: number | null;
  correct_answer: number | null;
  answer_source: AnswerSource | null;
  answer_confirmed: boolean;
  parser_notes: ParserNote[];
  reviewed: boolean;
  points: number | null;
  is_example: boolean;
}

export interface DraftAttempt {
  create: boolean;
  started_at: string | null;
  completed_at: string | null;
}

export interface DraftContent {
  exam: DraftExam;
  passages: DraftPassage[];
  questions: DraftQuestion[];
  attempt: DraftAttempt;
  parse_notes: Issue[];
}

export interface DraftSummary {
  total_questions: number;
  included_questions: number;
  valid_questions: number;
  missing_answer: number;
  needs_review: number;
  confirmed_answers: number;
  with_user_answer: number;
  errors: number;
  warnings: number;
}

export interface ImportAsset {
  id: string;
  position: number;
  original_filename: string | null;
  detected_type: string;
  byte_size: number;
  width: number;
  height: number;
  ocr_status: "pending" | "done" | "failed";
  ocr_engine: string | null;
  ocr_text: string | null;
}

export interface ImportDraft {
  id: string;
  status: ImportStatus;
  method: ImportMethod;
  adapter: string | null;
  source_url: string | null;
  raw_input: string | null;
  content: DraftContent;
  issues: Issue[];
  summary: DraftSummary;
  assets: ImportAsset[];
  error_code: string | null;
  error_message: string | null;
  version: number;
  exam_id: string | null;
  attempt_id: string | null;
  committed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImportDraftListItem {
  id: string;
  status: ImportStatus;
  method: ImportMethod;
  adapter: string | null;
  source_url: string | null;
  title: string;
  question_count: number;
  issues: Issue[];
  error_code: string | null;
  error_message: string | null;
  exam_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImportCapabilities {
  ocr: { available: boolean; engine: string | null; languages: string[]; reason: string | null };
  limits: {
    max_text_chars: number;
    max_html_bytes: number;
    max_images: number;
    max_image_bytes: number;
    max_image_pixels: number;
    accepted_image_types: string[];
  };
  adapters: string[];
}

export interface CommitResult {
  draft_id: string;
  exam_id: string;
  attempt_id: string | null;
  already_committed: boolean;
  created_questions: number;
  reused_questions: number;
  upgraded_answers: number;
  warnings: Issue[];
}

// ------------------------------------------------------------------ PR3: AI explanations
export type ExplanationStatus = "generated" | "needs_review" | "approved" | "rejected";
export type JobStatus = "pending" | "running" | "completed" | "partial_failed" | "failed" | "cancelled";
export type JobItemStatus = "pending" | "running" | "cached" | "succeeded" | "failed" | "skipped" | "cancelled";

export interface OptionAnalysis {
  option_index: number;
  option_text: string;
  meaning_vi: string;
  is_correct: boolean;
  reason: string;
  when_it_would_be_correct: string | null;
  difference_from_correct: string | null;
  common_misconception: string | null;
  how_to_distinguish: string | null;
  example_ja: string | null;
  example_vi: string | null;
}

export interface ExplanationPayload {
  schema_version: string;
  question_id: string;
  correct_answer_index: number; // 0-based
  translation_vi: string;
  solution_summary_vi: string;
  correct_explanation: string;
  recognition_tips: string | null;
  options_analysis: OptionAnalysis[];
  grammar_points: { pattern: string; meaning_vi: string; usage: string; contrast: string | null; example_ja: string | null }[];
  vocabulary: { surface: string; reading: string; meaning_vi: string; note: string | null }[];
  kanji: { kanji: string; readings: string; meaning_vi: string; note: string | null }[];
  sentence_structure: string | null;
  evidence: { quote_ja: string; explanation_vi: string }[];
  key_takeaway: string;
  review_topics: string[];
  quality: { context_sufficient: boolean; source_answer_concern: string | null; uncertainty_notes: string[] };
}

export interface Finding {
  severity: Severity;
  code: string;
  message: string;
  option_index: number | null;
}

export interface LearnerErrorView {
  selected_answer_index: number;
  is_correct: boolean;
  selected_option_text: string;
  possible_misconception: string | null;
  how_to_distinguish: string | null;
  study_advice: string;
}

export interface Explanation {
  id: string;
  question_id: string;
  provider: string;
  model: string;
  origin: "api" | "manual";
  status: ExplanationStatus;
  stale: boolean;
  is_current: boolean;
  prompt_version: string;
  schema_version: string;
  verified_answer_snapshot: number | null;
  flagged_answer_concern: boolean;
  validation_issues: Finding[];
  payload: ExplanationPayload | null;
  learner_error_analysis: LearnerErrorView | null;
  usage: { input_tokens: number | null; output_tokens: number | null; cost_usd: number | null } | null;
  review_note: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface QuestionExplanations {
  question_id: string;
  current_id: string | null;
  eligible: boolean;
  ineligible_code: string | null;
  ineligible_message: string | null;
  versions: Explanation[];
}

export interface JobItem {
  id: string;
  question_id: string;
  question_number: number | null;
  attempt_answer_id: string | null;
  status: JobItemStatus;
  tries: number;
  error_code: string | null;
  error_message: string | null;
  explanation_id: string | null;
}

export interface ExplanationJob {
  id: string;
  attempt_id: string | null;
  status: JobStatus;
  force: boolean;
  counts: Record<string, number>;
  items: JobItem[];
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface AttemptExplanationOverview {
  attempt_id: string;
  wrong_count: number;
  eligible_wrong_count: number;
  explained_wrong_count: number;
  needs_review_count: number;
  items: {
    attempt_answer_id: string;
    question_id: string;
    question_number: number;
    selected_answer: number | null;
    is_correct: boolean | null;
    eligible: boolean;
    ineligible_code: string | null;
    explanation_id: string | null;
    explanation_status: ExplanationStatus | null;
  }[];
  latest_job: ExplanationJob | null;
}

export interface AiCapabilities {
  api_available: boolean;
  provider: string | null;
  model: string | null;
  reason: string | null;
  prompt_version: string;
  schema_version: string;
  max_concurrent_requests: number;
  batch_max_questions: number;
  budget: Record<string, unknown>;
}

export interface ExportPromptResult {
  prompt: string;
  prompt_version: string;
  schema_version: string;
  question_ids: string[];
  skipped: { question_id: string; code: string; message: string }[];
  json_schema: Record<string, unknown>;
}

export interface ManualImportItem {
  index: number;
  question_id: string | null;
  ok: boolean;
  status: ExplanationStatus | null;
  findings: Finding[];
  payload: ExplanationPayload | null;
  saved_explanation_id: string | null;
}

export interface ManualImportResult {
  saved: boolean;
  items: ManualImportItem[];
  missing_question_ids: string[];
}

// ------------------------------------------------------------------ PR4: knowledge, reviews, practice
export type KnowledgeType = "grammar" | "vocabulary" | "kanji" | "reading_skill";
export type KnowledgeRole = "tests" | "distractor" | "context";
export type Priority = "review_now" | "due_soon" | "stable" | "insufficient_data";
export type ReviewTypeName = "original_question" | "knowledge_recall" | "contrast";
export type SrsStateName = "new" | "learning" | "review" | "mastered";
export type Rating = "again" | "hard" | "good" | "easy";

export interface KnowledgeCandidate {
  ref: string;
  question_id: string;
  explanation_id: string;
  knowledge_type: KnowledgeType;
  canonical_key: string;
  title: string;
  summary: string;
  details: Record<string, unknown>;
  role: KnowledgeRole;
  selected: boolean;
  action: "create" | "link" | "needs_decision";
  match: { knowledge_id: string; title: string; content: string; reason: "same_key" | "similar_title"; meaning_similarity: number } | null;
  warnings: string[];
}

export interface QuestionExtraction {
  question_id: string;
  question_number: number;
  explanation_id: string | null;
  skipped_code: string | null;
  skipped_message: string | null;
  candidates: KnowledgeCandidate[];
  relations: { source_ref: string; target_ref: string; relation_type: "confused_with" }[];
}

export interface ExtractResult {
  questions: QuestionExtraction[];
  reading_skills: Record<string, string>;
}

export interface ConfirmItemInput {
  ref: string;
  question_id: string;
  explanation_id: string;
  knowledge_type: KnowledgeType;
  title: string;
  summary: string;
  details: Record<string, unknown>;
  role: KnowledgeRole;
  action: "create" | "link" | "create_new_sense" | "skip";
  target_knowledge_id?: string;
}

export interface ConfirmResult {
  items: { ref: string; knowledge_id: string | null; outcome: "created" | "linked" | "skipped" }[];
  created: number;
  linked: number;
  skipped: number;
  relations_created: number;
  review_items_created: number;
  review_items_existing: number;
}

export interface KnowledgeStats {
  encounters: number;
  correct: number;
  incorrect: number;
  unanswered: number;
  ungraded: number;
  never_attempted_questions: number;
  error_rate: number | null;
  error_rate_low: number | null;
  error_rate_high: number | null;
  confidence: "none" | "low" | "medium" | "high";
  recent_incorrect_7d: number;
  last_incorrect_at: string | null;
  review_events: number;
  last_rating: string | null;
  next_due_at: string | null;
  priority: Priority;
}

export interface KnowledgeListItem {
  id: string;
  knowledge_type: KnowledgeType;
  title: string;
  content: string;
  canonical_key: string;
  status: "active" | "archived" | "merged";
  question_count: number;
  stats: KnowledgeStats;
  created_at: string;
  updated_at: string;
}

export interface KnowledgeDetail extends KnowledgeListItem {
  details: Record<string, unknown>;
  merged_into_id: string | null;
  source_explanation_id: string | null;
  version: number;
  questions: {
    question_id: string;
    exam_id: string;
    exam_title: string;
    question_number: number;
    question_text: string;
    role: KnowledgeRole;
    mistakes: { attempt_id: string; attempt_answer_id: string; selected_answer: number | null; started_at: string }[];
  }[];
  related: { knowledge_id: string; title: string; knowledge_type: KnowledgeType; relation_type: string; direction: string }[];
  evidence: {
    question_id: string | null;
    explanation_id: string | null;
    explanation_status: ExplanationStatus | null;
    explanation_stale: boolean | null;
    role: KnowledgeRole;
    extracted: Record<string, unknown>;
    confirmed_at: string;
  }[];
  review_items: { id: string; review_type: ReviewTypeName; status: string; srs_state: SrsStateName; due_at: string | null; review_count: number; last_reviewed_at: string | null }[];
}

export interface ReviewItem {
  id: string;
  review_type: ReviewTypeName;
  label: string;
  knowledge_id: string | null;
  related_knowledge_id: string | null;
  source_question_id: string | null;
  source_question_ids: string[];
  source_explanation_id: string | null;
  status: "active" | "suspended" | "done";
  srs_state: SrsStateName;
  step_index: number | null;
  interval_minutes: number;
  due_at: string | null;
  last_reviewed_at: string | null;
  review_count: number;
  lapse_count: number;
  algorithm_version: string;
  ladder: string;
  version: number;
  blocked_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReviewCard {
  card_id: string;
  review_item_id: string;
  review_type: ReviewTypeName;
  kind: "question" | "practice" | "meaning_choice" | "reading_choice" | "contrast" | "self_check";
  label: string;
  prompt: string;
  passage: string | null;
  options: string[];
  answered: boolean;
  selected_index: number | null;
  correct: boolean | null;
  rated: boolean;
  answer_index?: number | null;
}

export interface ReviewSession {
  id: string;
  cards: ReviewCard[];
  created_at: string;
  finished_at: string | null;
}

export interface ReviewEventRead {
  id: string;
  review_item_id: string;
  rating: Rating;
  reviewed_at: string;
  request_id: string | null;
  card_kind: string | null;
  selected_answer_index: number | null;
  answer_correct: boolean | null;
  previous_state: Record<string, unknown> | null;
  next_state: Record<string, unknown> | null;
  next_due_at: string | null;
  algorithm_version: string | null;
  timezone: string | null;
  label?: string;
  review_type?: ReviewTypeName;
}

export interface PracticeQuestion {
  id: string;
  generation_id: string;
  knowledge_id: string;
  source_explanation_id: string | null;
  status: "needs_review" | "approved" | "rejected";
  question_type: string;
  question_text: string;
  options: string[];
  answer_index: number;
  payload: { explanation_vi?: string; options_analysis?: { option_index: number; option_text: string; reason: string }[]; focus?: string };
  validation_issues: { code: string; message: string }[];
  reviewed_at: string | null;
  review_note: string | null;
  times_used: number;
  created_at: string;
}

export interface PracticeGeneration {
  id: string;
  knowledge_id: string;
  origin: "api" | "manual";
  provider: string;
  model: string;
  prompt_version: string;
  requested_count: number;
  accepted_count: number;
  status: "completed" | "partial" | "failed";
  issues: { code: string; message: string; index?: number }[];
  usage: Record<string, unknown> | null;
  created_at: string;
  questions: PracticeQuestion[];
}

export interface CountStats {
  encounters: number;
  correct: number;
  incorrect: number;
  unanswered: number;
  ungraded: number;
  error_rate: number | null;
  error_rate_low: number | null;
  error_rate_high: number | null;
  confidence: "none" | "low" | "medium" | "high";
  recent_incorrect_7d: number;
}

export interface WeaknessReport {
  window: string;
  categories: Record<string, CountStats>;
  priorities: Record<Priority, number>;
  knowledge_types: Record<string, { items: number; incorrect: number }>;
  top_knowledge: (KnowledgeStats & { knowledge_id: string; title: string; knowledge_type: KnowledgeType })[];
  timeline: (CountStats & { week_start: string })[];
  improvement: { knowledge_id: string; title: string; first_review_at: string; before: CountStats; after: CountStats }[];
  min_observations: number;
}

export interface ReviewProgress {
  days: number;
  total_reviews: number;
  ratings: Record<Rating, number>;
  answer_accuracy: number | null;
  answered: number;
  due_now: number;
  per_day: { date: string; reviews: number; answered: number; answered_correct: number }[];
}
