import { apiRequest } from "@/lib/api/client";

type One<T> = { data: T };
export type Language = "ja" | "en" | "vi";
export interface MyWord {
  id: string;
  original_text: string;
  language: Language;
  meanings: Partial<Record<Language, string[]>>;
  japanese_reading: string | null;
  english_ipa: string | null;
  source_url: string | null;
  source_title: string | null;
  context: string | null;
  tags: string[];
  created_at: string;
  updated_at: string;
  progress: null | { state: string; due_at: string; review_count: number };
}
export type WordFields = Pick<MyWord, "original_text" | "language" | "meanings" | "japanese_reading" | "english_ipa" | "source_url" | "source_title" | "context" | "tags">;

export const myWordsApi = {
  list: (query: { q?: string; language?: Language; page?: number }) => apiRequest<One<{ items: MyWord[]; total: number; page: number }>>("/my-words/", { query }).then(r => r.data),
  create: (fields: WordFields) => apiRequest<One<{ word: MyWord; created: boolean }>>("/my-words/", { method: "POST", body: { ...fields, request_id: crypto.randomUUID() } }).then(r => r.data),
  edit: (id: string, fields: WordFields) => apiRequest<One<MyWord>>(`/my-words/${id}`, { method: "PUT", body: fields }).then(r => r.data),
  archive: (id: string) => apiRequest<One<{ archived: boolean }>>(`/my-words/${id}`, { method: "DELETE" }).then(r => r.data),
  review: (id: string, rating: "again" | "hard" | "good" | "easy") => apiRequest<One<{ word: MyWord; duplicate: boolean }>>(`/my-words/${id}/review`, { method: "POST", body: { request_id: crypto.randomUUID(), rating, time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC" } }).then(r => r.data),
};
