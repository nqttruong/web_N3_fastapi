"use client";

import { ArrowDown, ArrowUp, CheckCircle2, Eye, Pencil, Plus, ShieldCheck, Trash2, Undo2 } from "lucide-react";
import { useState } from "react";

import { RichText } from "@/components/rich-text";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { QUESTION_TYPES, type DraftPassage, type DraftQuestion, type Issue } from "@/lib/api/types";
import { questionTypeMessageKey, answerSourceMessageKey } from "@/lib/localized-labels";
import { cn } from "@/lib/utils";
import { useLocale } from "@/lib/i18n";

const NONE = "__none__";

export function QuestionEditorCard({
  question,
  index,
  total,
  passages,
  issues,
  readOnly,
  onChange,
  onMove,
}: {
  question: DraftQuestion;
  index: number;
  total: number;
  passages: DraftPassage[];
  issues: Issue[];
  readOnly: boolean;
  onChange: (patch: Partial<DraftQuestion>) => void;
  onMove: (delta: number) => void;
}) {
  const { t } = useLocale();
  const [editing, setEditing] = useState(false);
  const q = question;
  const label = `${t("question")} ${q.question_number ?? `#${index + 1}`}`;
  const errors = issues.filter((i) => i.severity === "error");
  const warnings = issues.filter((i) => i.severity !== "error");
  const needsReview = q.parser_notes.length > 0 && !q.reviewed;

  // Picking a different key always drops the confirmation: the user must confirm again.
  const setCorrect = (value: number | null) => onChange({ correct_answer: value, answer_confirmed: false });

  return (
    <li
      data-testid="import-question"
      className={cn(
        "rounded-xl border p-4",
        !q.include && "opacity-60",
        q.include && errors.length > 0 && "border-destructive/50",
      )}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="font-semibold tabular-nums">{label}</span>
        <Badge variant="secondary">{t(questionTypeMessageKey[q.question_type])}</Badge>
        {q.passage_key ? <Badge variant="outline">{t("passageNumber")} {q.passage_key}</Badge> : null}
        {!q.include ? <Badge variant="outline">{t("notSaved")}</Badge> : null}
        {needsReview ? (
          <Badge variant="outline" className="border-amber-500/60 text-amber-700 dark:text-amber-400">
            {t("needsChecking")}
          </Badge>
        ) : null}
        {q.correct_answer === null ? (
          <Badge variant="outline" className="text-muted-foreground">{t("missingAnswer")}</Badge>
        ) : q.answer_confirmed ? (
          <Badge className="bg-emerald-600 text-white hover:bg-emerald-600">{t("answerConfirmedBadge")}</Badge>
        ) : (
          <Badge variant="outline" className="border-amber-500/60 text-amber-700 dark:text-amber-400">
            {t("answerNeedsVerification")}
          </Badge>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-1">
          {!readOnly ? (
            <>
              <label className="mr-2 flex items-center gap-1.5 text-xs">
                <Checkbox
                  checked={q.include}
                  onCheckedChange={(v) => onChange({ include: v === true })}
                  aria-label={t("saveQuestionLabel").replace("{label}", label)}
                />
                {t("saveThisQuestion")}
              </label>
              <Button size="icon-sm" variant="ghost" aria-label={`${t("moveQuestionUp")} ${label}`} disabled={index === 0} onClick={() => onMove(-1)}>
                <ArrowUp />
              </Button>
              <Button size="icon-sm" variant="ghost" aria-label={`${t("moveQuestionDown")} ${label}`} disabled={index === total - 1} onClick={() => onMove(1)}>
                <ArrowDown />
              </Button>
              <Button size="sm" variant={editing ? "secondary" : "outline"} onClick={() => setEditing((e) => !e)}>
                {editing ? <Eye aria-hidden /> : <Pencil aria-hidden />} {editing ? t("viewAction") : t("edit")}
              </Button>
            </>
          ) : null}
        </div>
      </div>

      {editing && !readOnly ? (
        <EditFields question={q} passages={passages} onChange={onChange} setCorrect={setCorrect} label={label} />
      ) : (
        <>
          <p className="mb-3 text-base leading-relaxed whitespace-pre-wrap">
            {q.question_text ? <RichText text={q.question_text} /> : <span className="text-destructive">{t("emptyValue")}</span>}
          </p>
          <ol className="grid gap-1.5 sm:grid-cols-2">
            {q.options.map((opt, i) => {
              const n = i + 1;
              const tags = [
                q.site_answer === n ? t("sourceAnswerLabel") : null,
                q.user_answer === n ? t("youSelected") : null,
                q.correct_answer === n ? (q.answer_confirmed ? t("answerKeyConfirmed") : t("answerKeyUnconfirmed")) : null,
              ].filter(Boolean);
              return (
                <li
                  key={i}
                  className={cn(
                    "flex items-start gap-2 rounded-lg border px-3 py-2 text-sm",
                    q.correct_answer === n && q.answer_confirmed && "border-emerald-600/50 bg-emerald-50 dark:bg-emerald-950/40",
                    q.correct_answer === n && !q.answer_confirmed && "border-dashed border-amber-500/60",
                  )}
                >
                  <span className="text-muted-foreground tabular-nums">{n}.</span>
                  <span className="min-w-0 flex-1">
                    <RichText className="break-words" text={opt} />
                    {tags.length ? <span className="mt-0.5 block text-xs text-muted-foreground">{tags.join(" · ")}</span> : null}
                  </span>
                </li>
              );
            })}
          </ol>
        </>
      )}

      {q.answer_source ? (
        <p className="mt-2 text-xs text-muted-foreground">{t("sourceOfAnswer")}: {t(answerSourceMessageKey[q.answer_source])}</p>
      ) : null}

      {q.parser_notes.length > 0 || errors.length > 0 || warnings.length > 0 ? (
        <ul className="mt-3 space-y-1 text-xs" aria-label={`${t("questionNotes")} ${label}`}>
          {q.parser_notes.map((n) => (
            <li key={n.code} className={cn(q.reviewed ? "text-muted-foreground line-through" : "text-amber-700 dark:text-amber-400")}>
              {t("parserLabel")}: {n.message}
            </li>
          ))}
          {errors
            .filter((i) => i.code !== "needs_review")
            .map((i) => (
              <li key={i.code} className="text-destructive">
                {i.message}
              </li>
            ))}
          {warnings.map((i) => (
            <li key={i.code} className="text-muted-foreground">
              {i.message}
            </li>
          ))}
        </ul>
      ) : null}

      {!readOnly ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {q.correct_answer !== null && !q.answer_confirmed ? (
            <Button size="sm" variant="outline" onClick={() => onChange({ answer_confirmed: true })}>
              <ShieldCheck aria-hidden /> {t("confirmAnswerNumber")} {q.correct_answer}
            </Button>
          ) : null}
          {q.answer_confirmed ? (
            <Button size="sm" variant="ghost" onClick={() => onChange({ answer_confirmed: false })}>
              <Undo2 aria-hidden /> {t("unconfirmAnswer")}
            </Button>
          ) : null}
          {q.site_answer !== null && q.correct_answer !== q.site_answer ? (
            <Button size="sm" variant="ghost" onClick={() => setCorrect(q.site_answer)}>
              {t("useSourceAnswer")} ({q.site_answer})
            </Button>
          ) : null}
          {needsReview ? (
            <Button size="sm" variant="outline" onClick={() => onChange({ reviewed: true })}>
              <CheckCircle2 aria-hidden /> {t("questionReviewed")}
            </Button>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

function EditFields({
  question: q,
  passages,
  onChange,
  setCorrect,
  label,
}: {
  question: DraftQuestion;
  passages: DraftPassage[];
  onChange: (patch: Partial<DraftQuestion>) => void;
  setCorrect: (v: number | null) => void;
  label: string;
}) {
  const { t } = useLocale();
  const id = `q-${q.key}`;
  const answerOptions = q.options.map((_, i) => String(i + 1));
  return (
    <div className="space-y-3" aria-label={t("editQuestionLabel").replace("{label}", label)}>
      <div className="grid gap-3 sm:grid-cols-[7rem_minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-1">
          <Label htmlFor={`${id}-num`}>{t("questionNumber")}</Label>
          <Input
            id={`${id}-num`}
            type="number"
            min={1}
            max={999}
            value={q.question_number ?? ""}
            onChange={(e) => onChange({ question_number: e.target.value ? Math.max(1, Math.min(999, Number(e.target.value))) : null })}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${id}-type`}>{t("questionType")}</Label>
          <Select value={q.question_type} onValueChange={(v) => onChange({ question_type: v as DraftQuestion["question_type"] })}>
            <SelectTrigger id={`${id}-type`} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {QUESTION_TYPES.map((questionType) => (
                <SelectItem key={questionType} value={questionType}>
                  {t(questionTypeMessageKey[questionType])}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${id}-passage`}>{t("passages")}</Label>
          <Select value={q.passage_key ?? NONE} onValueChange={(v) => onChange({ passage_key: v === NONE ? null : v })}>
            <SelectTrigger id={`${id}-passage`} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>{t("noLinkedPassage")}</SelectItem>
              {passages.map((p) => (
                <SelectItem key={p.key} value={p.key}>
                  {p.key}: {p.content.slice(0, 24)}…
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="space-y-1">
        <Label htmlFor={`${id}-text`}>{t("questionText")}</Label>
        <Textarea id={`${id}-text`} lang="ja" rows={3} value={q.question_text} onChange={(e) => onChange({ question_text: e.target.value })} />
        <p className="text-xs text-muted-foreground">{t("questionMarkupHint")}</p>
      </div>
      <fieldset className="space-y-2">
        <legend className="text-sm font-medium">{t("optionsTitle")}</legend>
        {q.options.map((opt, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-5 text-sm text-muted-foreground tabular-nums">{i + 1}.</span>
            <Input
              lang="ja"
              aria-label={`${label} · ${t("choice").replace("{number}", String(i + 1))}`}
              value={opt}
              onChange={(e) => onChange({ options: q.options.map((o, j) => (j === i ? e.target.value : o)) })}
            />
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label={`${t("removeOption")} ${i + 1}`}
              disabled={q.options.length <= 2}
              onClick={() => {
                const shift = (v: number | null) => (v === null || v === i + 1 ? null : v > i + 1 ? v - 1 : v);
                onChange({
                  options: q.options.filter((_, j) => j !== i),
                  correct_answer: shift(q.correct_answer),
                  site_answer: shift(q.site_answer),
                  user_answer: shift(q.user_answer),
                  answer_confirmed: false,
                });
              }}
            >
              <Trash2 />
            </Button>
          </div>
        ))}
        <Button size="sm" variant="ghost" disabled={q.options.length >= 6} onClick={() => onChange({ options: [...q.options, ""] })}>
          <Plus aria-hidden /> {t("addOption")}
        </Button>
      </fieldset>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor={`${id}-correct`}>{t("correctAnswerKey")}</Label>
          <Select value={q.correct_answer ? String(q.correct_answer) : NONE} onValueChange={(v) => setCorrect(v === NONE ? null : Number(v))}>
            <SelectTrigger id={`${id}-correct`} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>{t("noAnswer")}</SelectItem>
              {answerOptions.map((v) => (
                <SelectItem key={v} value={v}>
                  {v}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            {t("sourceShows")}: {q.site_answer ?? t("noAnswer").toLowerCase()}. {t("verifyAfterSelection")}
          </p>
        </div>
        <div className="space-y-1">
          <Label htmlFor={`${id}-user`}>{t("yourAnswerWhenTaking")}</Label>
          <Select value={q.user_answer ? String(q.user_answer) : NONE} onValueChange={(v) => onChange({ user_answer: v === NONE ? null : Number(v) })}>
            <SelectTrigger id={`${id}-user`} className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NONE}>{t("noSelectionKnow")}</SelectItem>
              {answerOptions.map((v) => (
                <SelectItem key={v} value={v}>
                  {v}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">{t("neverCorrectAnswer")}</p>
        </div>
      </div>
    </div>
  );
}
