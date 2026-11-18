import { apiRequest } from "./client";
import type {
  AttemptCreateInput,
  AttemptDetail,
  AttemptSummary,
  Mistake,
  JlptAnalytics,
  LearningItemPage,
  LearningSyncStatus,
  PairingCodeResult,
  SyncAdminDevice,
  DashboardSummary,
  Exam,
  ExamCategory,
  ExamCreateInput,
  ExamUpdateInput,
  AiCapabilities,
  AttemptExplanationOverview,
  CommitResult,
  ConfirmItemInput,
  ConfirmResult,
  ExtractResult,
  KnowledgeDetail,
  KnowledgeListItem,
  KnowledgeType,
  PracticeGeneration,
  PracticeQuestion,
  Rating,
  ReviewEventRead,
  ReviewItem,
  ReviewProgress,
  ReviewSession,
  WeaknessReport,
  Explanation,
  ExplanationJob,
  ExportPromptResult,
  ManualImportResult,
  QuestionExplanations,
  DraftContent,
  ExamCategory as Category,
  Health,
  ImportCapabilities,
  ImportDraft,
  ImportDraftListItem,
  Page,
  Passage,
  Question,
  QuestionCreateInput,
} from "./types";

type One<T> = { data: T };

export interface ExamListParams {
  page?: number;
  page_size?: number;
  q?: string;
  category?: ExamCategory;
}

export const api = {
  health: () => apiRequest<One<Health>>("/health").then((r) => r.data),

  dashboard: () => apiRequest<One<DashboardSummary>>("/analytics/summary").then((r) => r.data),

  learningContentStatus: () =>
    apiRequest<One<LearningSyncStatus>>("/learning-content/sync/status").then((r) => r.data),
  requestLearningContentSync: (token?: string) =>
    apiRequest<One<{ run_id: string; status: string; message: string }>>("/learning-content/sync", {
      method: "POST",
      headers: token ? { "X-Learning-Sync-Token": token } : undefined,
    }).then((r) => r.data),
  listLearningContent: (params: { type?: string; jlpt_level?: string; q?: string; page?: number; page_size?: number } = {}) =>
    apiRequest<One<LearningItemPage>>("/learning-content/items", { query: params }).then((r) => r.data),
  listSyncDevices: (adminKey?: string) =>
    apiRequest<One<SyncAdminDevice[]>>("/sync/admin/devices", {
      headers: adminKey ? { "X-Sync-Admin-Key": adminKey } : undefined,
    }).then((r) => r.data),
  createSyncPairingCode: (adminKey: string, expiresInMinutes = 10) =>
    apiRequest<One<PairingCodeResult>>("/sync/admin/pairing-codes", {
      method: "POST",
      headers: { "X-Sync-Admin-Key": adminKey },
      body: { expires_in_minutes: expiresInMinutes },
    }).then((r) => r.data),
  revokeSyncDevice: (deviceId: string, adminKey?: string) =>
    apiRequest<One<{ status: string; device_id: string }>>(`/sync/admin/devices/${deviceId}`, {
      method: "DELETE",
      headers: adminKey ? { "X-Sync-Admin-Key": adminKey } : undefined,
    }).then((r) => r.data),

  listExams: (params: ExamListParams = {}) =>
    apiRequest<Page<Exam>>("/exams", { query: { ...params } }),
  getExam: (id: string) => apiRequest<One<Exam>>(`/exams/${id}`).then((r) => r.data),
  createExam: (input: ExamCreateInput) =>
    apiRequest<One<Exam>>("/exams", { method: "POST", body: input }).then((r) => r.data),
  updateExam: (id: string, input: ExamUpdateInput) =>
    apiRequest<One<Exam>>(`/exams/${id}`, { method: "PATCH", body: input }).then((r) => r.data),

  listPassages: (examId: string) =>
    apiRequest<One<Passage[]>>(`/exams/${examId}/passages`).then((r) => r.data),
  createPassage: (examId: string, content: string) =>
    apiRequest<One<Passage>>(`/exams/${examId}/passages`, {
      method: "POST",
      body: { content },
    }).then((r) => r.data),

  // N3 sections stay well under 100 questions; the API caps page_size at 100.
  listQuestions: (examId: string, opts: { includeAnswers?: boolean } = {}) =>
    apiRequest<Page<Question>>(`/exams/${examId}/questions`, {
      query: { page_size: 100, include_answers: opts.includeAnswers ?? true },
    }),
  createQuestion: (examId: string, input: QuestionCreateInput) =>
    apiRequest<One<Question>>(`/exams/${examId}/questions`, {
      method: "POST",
      body: input,
    }).then((r) => r.data),
  updateQuestion: (questionId: string, input: Partial<QuestionCreateInput>) =>
    apiRequest<One<Question>>(`/questions/${questionId}`, { method: "PATCH", body: input }).then(
      (r) => r.data,
    ),
  deleteQuestion: (questionId: string) =>
    apiRequest<void>(`/questions/${questionId}`, { method: "DELETE" }),

  listAttempts: (params: { page?: number; page_size?: number; exam_id?: string } = {}) =>
    apiRequest<Page<AttemptSummary>>("/attempts", { query: { ...params } }),
  listMistakes: (params: { page?: number; page_size?: number; exam_id?: string; skill?: string; q?: string } = {}) =>
    apiRequest<Page<Mistake>>("/attempts/mistakes", { query: { ...params } }),
  getAttempt: (id: string) =>
    apiRequest<One<AttemptDetail>>(`/attempts/${id}`).then((r) => r.data),
  createAttempt: (input: AttemptCreateInput) =>
    apiRequest<One<AttemptDetail>>("/attempts", { method: "POST", body: input }).then(
      (r) => r.data,
    ),

  // ---------------------------------------------------------------- imports (PR2)
  importCapabilities: () =>
    apiRequest<One<ImportCapabilities>>("/imports/capabilities").then((r) => r.data),
  listImports: (params: { page?: number; page_size?: number } = {}) =>
    apiRequest<Page<ImportDraftListItem>>("/imports", { query: { ...params } }),
  getImport: (id: string) => apiRequest<One<ImportDraft>>(`/imports/${id}`).then((r) => r.data),
  importText: (input: ImportMeta & { text: string }) =>
    apiRequest<One<ImportDraft>>("/imports/text", { method: "POST", body: compact(input) }).then((r) => r.data),
  importHtml: (input: ImportMeta & { html: string }) =>
    apiRequest<One<ImportDraft>>("/imports/html", { method: "POST", body: compact(input) }).then((r) => r.data),
  importImages: (files: File[], meta: ImportMeta) => {
    const form = new FormData();
    for (const file of files) form.append("files", file, file.name);
    for (const [k, v] of Object.entries(compact(meta))) form.append(k, String(v));
    return apiRequest<One<ImportDraft>>("/imports/images", { method: "POST", body: form }).then((r) => r.data);
  },
  updateImport: (
    id: string,
    input: { version: number; content?: DraftContent; source_url?: string | null; asset_order?: string[] },
  ) => apiRequest<One<ImportDraft>>(`/imports/${id}`, { method: "PATCH", body: input }).then((r) => r.data),
  reparseImport: (id: string, rawInput?: string) =>
    apiRequest<One<ImportDraft>>(`/imports/${id}/parse`, {
      method: "POST",
      body: rawInput === undefined ? {} : { raw_input: rawInput },
    }).then((r) => r.data),
  validateImport: (id: string) =>
    apiRequest<One<ImportDraft>>(`/imports/${id}/validate`, { method: "POST" }).then((r) => r.data),
  commitImport: (id: string, input: { target: "new" | "existing"; existing_exam_id?: string }) =>
    apiRequest<One<CommitResult>>(`/imports/${id}/commit`, { method: "POST", body: input }).then((r) => r.data),
  deleteImport: (id: string) => apiRequest<void>(`/imports/${id}`, { method: "DELETE" }),

  // ---------------------------------------------------------------- explanations (PR3)
  getQuestion: (id: string) => apiRequest<One<Question>>(`/questions/${id}`).then((r) => r.data),
  aiCapabilities: () => apiRequest<One<AiCapabilities>>("/explanations/capabilities").then((r) => r.data),
  questionExplanations: (questionId: string, attemptAnswerId?: string) =>
    apiRequest<One<QuestionExplanations>>(`/questions/${questionId}/explanations`, {
      query: { attempt_answer_id: attemptAnswerId },
    }).then((r) => r.data),
  generateExplanation: (input: { question_id: string; attempt_answer_id?: string; force?: boolean }) =>
    apiRequest<One<{ outcome: "cached" | "generated"; explanation: Explanation }>>("/explanations/generate", {
      method: "POST",
      body: input,
    }).then((r) => r.data),
  approveExplanation: (id: string, note?: string) =>
    apiRequest<One<Explanation>>(`/explanations/${id}/approve`, { method: "POST", body: { note: note || null } }).then((r) => r.data),
  rejectExplanation: (id: string, note?: string) =>
    apiRequest<One<Explanation>>(`/explanations/${id}/reject`, { method: "POST", body: { note: note || null } }).then((r) => r.data),
  attemptExplanations: (attemptId: string) =>
    apiRequest<One<AttemptExplanationOverview>>(`/attempts/${attemptId}/explanations`).then((r) => r.data),
  startBatch: (input: { attempt_id: string; question_ids?: string[]; force?: boolean }) =>
    apiRequest<One<ExplanationJob>>("/explanations/batch", { method: "POST", body: input }).then((r) => r.data),
  getJob: (id: string) => apiRequest<One<ExplanationJob>>(`/explanations/jobs/${id}`).then((r) => r.data),
  retryJob: (id: string) => apiRequest<One<ExplanationJob>>(`/explanations/jobs/${id}/retry`, { method: "POST" }).then((r) => r.data),
  cancelJob: (id: string) => apiRequest<One<ExplanationJob>>(`/explanations/jobs/${id}/cancel`, { method: "POST" }).then((r) => r.data),
  exportPrompt: (questionIds: string[], attemptId?: string) =>
    apiRequest<One<ExportPromptResult>>("/explanations/export-prompt", {
      method: "POST",
      body: { question_ids: questionIds, ...(attemptId ? { attempt_id: attemptId } : {}) },
    }).then((r) => r.data),
  // ---------------------------------------------------------------- knowledge (PR4)
  listKnowledge: (params: { type?: KnowledgeType; status?: string; q?: string; priority?: string } = {}) =>
    apiRequest<One<KnowledgeListItem[]>>("/knowledge", { query: { ...params } }).then((r) => r.data),
  getKnowledge: (id: string) => apiRequest<One<KnowledgeDetail>>(`/knowledge/${id}`).then((r) => r.data),
  extractKnowledge: (input: { question_ids?: string[]; attempt_id?: string }) =>
    apiRequest<One<ExtractResult>>("/knowledge/extract", { method: "POST", body: input }).then((r) => r.data),
  confirmKnowledge: (input: { items: ConfirmItemInput[]; relations: { source_ref: string; target_ref: string; relation_type: string }[]; create_reviews: boolean }) =>
    apiRequest<One<ConfirmResult>>("/knowledge/confirm", { method: "POST", body: input }).then((r) => r.data),
  updateKnowledge: (id: string, input: { version: number; title?: string; content?: string; status?: "active" | "archived" }) =>
    apiRequest<One<KnowledgeDetail>>(`/knowledge/${id}`, { method: "PATCH", body: input }).then((r) => r.data),
  mergeKnowledge: (targetId: string, sourceIds: string[]) =>
    apiRequest<One<KnowledgeDetail>>("/knowledge/merge", { method: "POST", body: { target_id: targetId, source_ids: sourceIds } }).then((r) => r.data),
  splitKnowledge: (id: string, input: { title: string; content?: string; question_ids: string[] }) =>
    apiRequest<One<KnowledgeDetail>>(`/knowledge/${id}/split`, { method: "POST", body: input }).then((r) => r.data),

  // ---------------------------------------------------------------- reviews (PR4)
  listReviews: (bucket: string) =>
    apiRequest<One<{ bucket: string; counts: Record<string, number>; items: ReviewItem[] }>>("/reviews", { query: { bucket } }).then((r) => r.data),
  createReviewSession: (limit = 20) =>
    apiRequest<One<ReviewSession>>("/reviews/sessions", { method: "POST", body: { limit } }).then((r) => r.data),
  getReviewSession: (id: string) => apiRequest<One<ReviewSession>>(`/reviews/sessions/${id}`).then((r) => r.data),
  answerCard: (sessionId: string, cardId: string, selectedIndex: number | null) =>
    apiRequest<One<{ card: ReviewSession["cards"][number]; reveal: Record<string, unknown> }>>(`/reviews/sessions/${sessionId}/answer`, {
      method: "POST",
      body: { card_id: cardId, selected_index: selectedIndex },
    }).then((r) => r.data),
  rateReview: (input: { request_id: string; review_item_id: string; rating: Rating; timezone: string; session_id?: string; card_id?: string }) =>
    apiRequest<One<{ event: ReviewEventRead; duplicate: boolean; item: ReviewItem }>>("/reviews/events", { method: "POST", body: input }).then((r) => r.data),
  reviewHistory: (params: { review_item_id?: string; knowledge_id?: string; limit?: number }) =>
    apiRequest<One<ReviewEventRead[]>>("/reviews/history", { query: { ...params } }).then((r) => r.data),
  setReviewStatus: (id: string, version: number, status: "active" | "suspended" | "done") =>
    apiRequest<One<ReviewItem>>(`/reviews/${id}`, { method: "PATCH", body: { version, status } }).then((r) => r.data),

  // ---------------------------------------------------------------- analytics (PR4)
  weaknesses: (window: string) => apiRequest<One<WeaknessReport>>("/analytics/weaknesses", { query: { window } }).then((r) => r.data),
  jlptAnalytics: () => apiRequest<One<JlptAnalytics>>("/analytics/jlpt").then((r) => r.data),
  reviewProgress: (days = 30) => apiRequest<One<ReviewProgress>>("/analytics/review-progress", { query: { days } }).then((r) => r.data),

  // ---------------------------------------------------------------- practice (PR4)
  generatePractice: (knowledgeId: string, count: number) =>
    apiRequest<One<PracticeGeneration>>("/practice/generate", { method: "POST", body: { knowledge_id: knowledgeId, count } }).then((r) => r.data),
  listPractice: (knowledgeId: string) =>
    apiRequest<One<PracticeQuestion[]>>("/practice", { query: { knowledge_id: knowledgeId } }).then((r) => r.data),
  approvePractice: (id: string) => apiRequest<One<PracticeQuestion>>(`/practice/${id}/approve`, { method: "POST", body: {} }).then((r) => r.data),
  rejectPractice: (id: string) => apiRequest<One<PracticeQuestion>>(`/practice/${id}/reject`, { method: "POST", body: {} }).then((r) => r.data),
  exportPracticePrompt: (knowledgeId: string, count: number) =>
    apiRequest<One<{ prompt: string; prompt_version: string }>>("/practice/export-prompt", { method: "POST", body: { knowledge_id: knowledgeId, count } }).then((r) => r.data),
  importPractice: (input: { knowledge_id: string; count: number; raw_json: string; save: boolean; model_label?: string }) =>
    apiRequest<One<{ saved: boolean; set_errors: { code: string; message: string }[]; questions: { index: number; ok: boolean; errors: { code: string; message: string }[]; warnings: { code: string; message: string }[]; question: Record<string, unknown> | null }[]; generation: PracticeGeneration | null }>>(
      "/practice/manual-import",
      { method: "POST", body: input },
    ).then((r) => r.data),

  manualImport: (input: { question_ids: string[]; raw_json: string; save: boolean; model_label?: string }) =>
    apiRequest<One<ManualImportResult>>("/explanations/manual-import", { method: "POST", body: input }).then((r) => r.data),
};

export interface ImportMeta {
  source_url?: string;
  title?: string;
  category?: Category;
}

function compact<T extends object>(obj: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(obj).filter(([, v]) => v !== undefined && v !== null && v !== ""),
  ) as Partial<T>;
}
