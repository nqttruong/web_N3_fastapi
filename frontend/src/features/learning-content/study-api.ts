import { apiRequest } from "@/lib/api/client";

type One<T> = { data: T };
export type StudyType = "vocabulary" | "kanji" | "grammar";
export type Rating = "again" | "hard" | "good" | "easy";
export interface StudyItem {
  id: string;
  item_type: StudyType;
  pack_id: string;
  lesson_id: string;
  lesson_title: string;
  payload: Record<string, unknown>;
  examples: { japanese: string; furigana?: string; translationVi?: string }[];
  saved: boolean;
  progress: null | { state: string; due_at: string; review_count: number; step_index: number };
  exercise_results: Record<string, { selected_index: number; is_correct: boolean; answered_at: string }>;
}
export interface LessonSummary { pack_id: string; pack_title: string; lesson_id: string; number: number; title: string; description: string | null; total: number; learned: number; jlpt_level: string }
export interface CourseSummary { number: number; title: string; counts: Record<StudyType, number>; total: number; learned: number; due: number; status: "new" | "in_progress" | "completed" | "needs_review"; last_studied_at: string | null }
export interface CourseLesson { number: number; title: string; sections: Record<StudyType, StudyItem[]> }
export interface LessonDetail { pack_id: string; lesson_id: string; number: number; title: string; description: string | null; items: StudyItem[] }
export interface StudyOverview { content_counts: Record<string, number>; learned: number; learned_by_type: Record<string, number>; due: number; available_new: number; saved: number; last_activity_at: string | null; active_session_id: string | null; recent_activity: { item_id: string; item_type: StudyType; title: string; rating: Rating; reviewed_at: string; origin: string }[] }
export interface StudySession { id: string; mode: string; position: number; total: number; current: StudyItem | null; finished_at: string | null; ratings: Record<string, number> }
export interface SourceRight { pack_id: string; source_id: string; source_name: string; source_license: string; license_verified: boolean; source_content_hash?: string; row_count?: number; declaration: null | { rights_holder: string; rights_basis: string; allowed_usage: string; attribution: string | null; approved: boolean; approved_at: string | null; source_content_hash?: string | null } }
export interface PdfPreview { source_content_hash: string; row_count: number; samples: { number: number; expression: string; reading: string | null; meaning_vi: string; source_page: number; source_lesson_number: number }[] }

export const studyApi = {
  overview: () => apiRequest<One<StudyOverview>>("/learning-content/study/overview", { query: { time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC" } }).then(r => r.data),
  lessons: (type?: StudyType) => apiRequest<One<LessonSummary[]>>("/learning-content/lessons", { query: { type } }).then(r => r.data),
  course: () => apiRequest<One<CourseSummary[]>>("/learning-content/course").then(r => r.data),
  courseLesson: (number: number) => apiRequest<One<CourseLesson>>(`/learning-content/course/${number}`).then(r => r.data),
  lesson: (packId: string, lessonId: string) => apiRequest<One<LessonDetail>>(`/learning-content/lessons/${encodeURIComponent(packId)}/${encodeURIComponent(lessonId)}`).then(r => r.data),
  saved: () => apiRequest<One<StudyItem[]>>("/learning-content/saved").then(r => r.data),
  save: (id: string, saved: boolean) => apiRequest<One<{ saved: boolean }>>(`/learning-content/items/${id}/saved`, { method: saved ? "PUT" : "DELETE" }).then(r => r.data),
  start: (body: { mode: "lesson" | "course" | "review" | "saved"; pack_id?: string; lesson_id?: string; course_number?: number; item_type?: StudyType }) => apiRequest<One<StudySession>>("/learning-content/study/sessions", { method: "POST", body: { ...body, time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC" } }).then(r => r.data),
  session: (id: string) => apiRequest<One<StudySession>>(`/learning-content/study/sessions/${id}`).then(r => r.data),
  rate: (id: string, requestId: string, rating: Rating) => apiRequest<One<StudySession>>(`/learning-content/study/sessions/${id}/rate`, { method: "POST", body: { request_id: requestId, rating, time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC" } }).then(r => r.data),
  answerExercise: (itemId: string, exerciseId: string, requestId: string, selectedIndex: number) => apiRequest<One<{ selected_index: number; is_correct: boolean; answer_index: number; explanation_vi: string | null; duplicate: boolean }>>(`/learning-content/items/${itemId}/exercises/${encodeURIComponent(exerciseId)}/answers`, { method: "POST", body: { request_id: requestId, selected_index: selectedIndex } }).then(r => r.data),
  sources: () => apiRequest<One<SourceRight[]>>("/learning-content/rights/sources").then(r => r.data),
  pdfPreview: () => apiRequest<One<PdfPreview>>("/learning-content/rights/pdf-preview").then(r => r.data),
  declareRights: (body: { pack_id: string; source_id: string; rights_holder: string; rights_basis: string; allowed_usage: string; attribution: string | null; scope: "private"; approved: boolean; source_content_hash?: string }) => apiRequest<One<{ sync_run_id: string }>>("/learning-content/rights/sources", { method: "PUT", body }).then(r => r.data),
};

export function studyTitle(item: StudyItem) {
  return String(item.payload[item.item_type === "vocabulary" ? "expression" : item.item_type === "kanji" ? "character" : "pattern"] ?? "");
}
