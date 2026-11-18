"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { JapaneseText } from "@/components/japanese-text";
import { errorMessage } from "@/components/states";
import { Button } from "@/components/ui/button";
import { studyApi, type StudyItem } from "./study-api";

interface Exercise { id: string; prompt: string; options: string[]; answerIndex: number; explanationVi?: string | null }

function parsedExercises(item: StudyItem): Exercise[] {
  const rows = item.payload.exercises;
  if (!Array.isArray(rows)) return [];
  return rows.filter((row): row is Exercise => typeof row === "object" && row !== null && typeof row.id === "string" && typeof row.prompt === "string" && Array.isArray(row.options) && typeof row.answerIndex === "number");
}

function ExerciseCard({ item, exercise }: { item: StudyItem; exercise: Exercise }) {
  const client = useQueryClient();
  const [latest, setLatest] = useState<{ selected_index: number; is_correct: boolean } | null>(item.exercise_results?.[exercise.id] ?? null);
  const [pendingIndex, setPendingIndex] = useState<number | null>(null);
  const requestId = useRef<string | null>(null);
  const answer = useMutation({
    mutationFn: (selected: number) => studyApi.answerExercise(item.id, exercise.id, requestId.current ??= crypto.randomUUID(), selected),
    onSuccess: result => { setLatest(result); setPendingIndex(null); requestId.current = null; void client.invalidateQueries({ queryKey: ["study-lesson"] }); },
  });
  return <div className="space-y-3 rounded-xl border p-4" aria-label="Bài luyện ngữ pháp">
    <p className="font-medium"><JapaneseText value={exercise.prompt} /></p>
    <div className="grid gap-2">{exercise.options.map((option, index) => <Button key={index} variant="outline" className="h-auto min-h-11 justify-start whitespace-normal text-left" disabled={latest !== null || answer.isPending || (pendingIndex !== null && pendingIndex !== index)} onClick={() => { setPendingIndex(index); answer.mutate(index); }}><JapaneseText value={option} /></Button>)}</div>
    {latest && <div role="status" className="space-y-2 text-sm"><p className={latest.is_correct ? "text-teal-700" : "text-destructive"}>{latest.is_correct ? "Đúng" : `Chưa đúng · đáp án: ${exercise.options[exercise.answerIndex]}`}</p>{exercise.explanationVi && <p>{exercise.explanationVi}</p>}<Button variant="outline" size="sm" onClick={() => { setLatest(null); requestId.current = null; }}>Làm lại</Button></div>}
    {answer.error && <p role="alert" className="text-sm text-destructive">{errorMessage(answer.error)} · Chọn lại cùng đáp án để gửi lại.</p>}
  </div>;
}

export function GrammarExercises({ item }: { item: StudyItem }) {
  const exercises = parsedExercises(item);
  if (!exercises.length) return null;
  return <section className="space-y-3" aria-label="Luyện ngữ pháp"><h3 className="font-semibold">Bài luyện</h3>{exercises.map(exercise => <ExerciseCard key={exercise.id} item={item} exercise={exercise} />)}</section>;
}
