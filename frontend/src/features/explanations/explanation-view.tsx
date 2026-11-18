import type { ReactNode } from "react";

import { RichText } from "@/components/rich-text";
import { Badge } from "@/components/ui/badge";
import type { ExplanationPayload, Finding, LearnerErrorView } from "@/lib/api/types";
import { cn } from "@/lib/utils";
import { useLocale } from "@/lib/i18n";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold tracking-wide text-muted-foreground uppercase">{title}</h3>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="text-sm">
      <span className="font-medium">{label}: </span>
      <span className="whitespace-pre-wrap">{children}</span>
    </div>
  );
}

/** Renders a validated explanation payload. Indices in the payload are 0-based; the UI shows 1-based. */
export function ExplanationView({
  payload,
  learner,
  selectedAnswer,
  findings = [],
}: {
  payload: ExplanationPayload;
  learner: LearnerErrorView | null;
  selectedAnswer?: number | null;
  findings?: Finding[];
}) {
  const { t } = useLocale();
  const correct = payload.options_analysis.find((o) => o.is_correct);
  const wrong = payload.options_analysis.filter((o) => !o.is_correct);
  const selectedIndex = learner?.selected_answer_index ?? (selectedAnswer ? selectedAnswer - 1 : null);
  const issuesByOption = new Map<number, Finding[]>();
  for (const f of findings) {
    if (f.option_index !== null) issuesByOption.set(f.option_index, [...(issuesByOption.get(f.option_index) ?? []), f]);
  }

  return (
    <div className="space-y-6" data-testid="explanation-view">
      <Section title={t("explainOverview")}>
        <div className="grid gap-2 sm:grid-cols-3">
          <div className="rounded-lg border p-3 text-sm">
            <p className="text-xs text-muted-foreground">{t("correctAnswerLabel")}</p>
            <p className="font-medium">
              {payload.correct_answer_index + 1}. {correct ? <RichText text={correct.option_text} /> : null}
            </p>
          </div>
          <div className="rounded-lg border p-3 text-sm">
            <p className="text-xs text-muted-foreground">{t("yourAnswer")}</p>
            <p className="font-medium">
              {selectedIndex === null ? (
                <span className="text-muted-foreground">{t("noData")}</span>
              ) : (
                <>
                  {selectedIndex + 1}. <RichText text={payload.options_analysis[selectedIndex]?.option_text ?? ""} />
                </>
              )}
            </p>
          </div>
          <div className="rounded-lg border p-3 text-sm">
            <p className="text-xs text-muted-foreground">{t("result")}</p>
            <p className="font-medium">
              {selectedIndex === null ? "—" : selectedIndex === payload.correct_answer_index ? t("resultCorrect") : t("resultIncorrect")}
            </p>
          </div>
        </div>
        <Field label={t("translation")}>{payload.translation_vi}</Field>
        <Field label={t("solutionMethod")}>{payload.solution_summary_vi}</Field>
      </Section>

      <Section title={t("whyCorrect")}>
        <p className="text-sm whitespace-pre-wrap">{payload.correct_explanation}</p>
        {correct ? (
          <div className="rounded-lg border border-emerald-600/40 bg-emerald-50/60 p-3 text-sm dark:bg-emerald-950/30">
            <p className="font-medium">
              {correct.option_index + 1}. <RichText text={correct.option_text} /> — {correct.meaning_vi}
            </p>
            <p className="mt-1 whitespace-pre-wrap">{correct.reason}</p>
            {correct.example_ja ? (
              <p className="mt-1 text-muted-foreground">
                {t("exampleItem")}: <RichText text={correct.example_ja} /> {correct.example_vi ? `— ${correct.example_vi}` : null}
              </p>
            ) : null}
          </div>
        ) : null}
        {payload.recognition_tips ? <Field label={t("recognitionClue")}>{payload.recognition_tips}</Field> : null}
      </Section>

      <Section title={t("wrongOptions")}>
        <ol className="space-y-3">
          {wrong.map((o) => (
            <li
              key={o.option_index}
              className={cn("rounded-lg border p-3 text-sm", selectedIndex === o.option_index && "border-destructive/50")}
            >
              <p className="font-medium">
                {o.option_index + 1}. <RichText text={o.option_text} /> — {o.meaning_vi}
                {selectedIndex === o.option_index ? <Badge variant="destructive" className="ml-2">{t("youSelected")}</Badge> : null}
              </p>
              <p className="mt-1 whitespace-pre-wrap">{o.reason}</p>
              <dl className="mt-2 space-y-1 text-muted-foreground">
                {o.difference_from_correct ? <Field label={t("differenceCorrect")}>{o.difference_from_correct}</Field> : null}
                {o.when_it_would_be_correct ? <Field label={t("whenCorrect")}>{o.when_it_would_be_correct}</Field> : null}
                {o.common_misconception ? <Field label={t("whyConfusing")}>{o.common_misconception}</Field> : null}
                {o.how_to_distinguish ? <Field label={t("distinguish")}>{o.how_to_distinguish}</Field> : null}
                {o.example_ja ? (
                  <Field label={t("exampleItem")}>
                    <RichText text={o.example_ja} /> {o.example_vi ? `— ${o.example_vi}` : null}
                  </Field>
                ) : null}
              </dl>
              {(issuesByOption.get(o.option_index) ?? []).map((f) => (
                <p key={f.code} className="mt-1 text-xs text-amber-700 dark:text-amber-400">
                  <details>
                    <summary className="cursor-pointer">{t("validation")} · {t(f.severity === "error" ? "severityError" : f.severity === "warning" ? "severityWarning" : "severityInfo")}</summary>
                    <p className="mt-1">{f.message}</p>
                  </details>
                </p>
              ))}
            </li>
          ))}
        </ol>
      </Section>

      <Section title={t("relatedKnowledge")}>
        {payload.evidence.length > 0 ? (
          <div className="space-y-2">
            <p className="text-sm font-medium">{t("passageEvidence")}</p>
            {payload.evidence.map((e, i) => (
              <blockquote key={i} className="border-l-2 pl-3 text-sm">
                <RichText text={e.quote_ja} />
                <p className="text-muted-foreground">{e.explanation_vi}</p>
              </blockquote>
            ))}
          </div>
        ) : null}
        {payload.vocabulary.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="py-1 pr-3">{t("word")}</th>
                  <th className="py-1 pr-3">{t("readingLabel")}</th>
                  <th className="py-1">{t("meaningLabel")}</th>
                </tr>
              </thead>
              <tbody>
                {payload.vocabulary.map((v, i) => (
                  <tr key={i} className="border-t">
                    <td className="py-1 pr-3" lang="ja">{v.surface}</td>
                    <td className="py-1 pr-3" lang="ja">{v.reading}</td>
                    <td className="py-1">
                      {v.meaning_vi}
                      {v.note ? <span className="text-muted-foreground"> — {v.note}</span> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
        {payload.kanji.length > 0 ? (
          <ul className="grid gap-2 sm:grid-cols-2">
            {payload.kanji.map((k, i) => (
              <li key={i} className="rounded-lg border p-2 text-sm">
                <span className="mr-2 text-2xl" lang="ja">{k.kanji}</span>
                <span lang="ja">{k.readings}</span> — {k.meaning_vi}
                {k.note ? <p className="text-xs text-muted-foreground">{k.note}</p> : null}
              </li>
            ))}
          </ul>
        ) : null}
        {payload.grammar_points.map((g, i) => (
          <div key={i} className="rounded-lg border p-3 text-sm">
            <p className="font-medium" lang="ja">{g.pattern} <span className="font-normal">— {g.meaning_vi}</span></p>
            <p className="mt-1 whitespace-pre-wrap">{g.usage}</p>
            {g.contrast ? <Field label={t("distinguish")}>{g.contrast}</Field> : null}
            {g.example_ja ? <Field label={t("exampleItem")}><RichText text={g.example_ja} /></Field> : null}
          </div>
        ))}
        {payload.sentence_structure ? <Field label={t("sentenceStructure")}>{payload.sentence_structure}</Field> : null}
      </Section>

      <Section title={t("possibleMistake")}>
        {learner && !learner.is_correct ? (
          <div className="space-y-1 rounded-lg border border-destructive/40 p-3 text-sm">
            {learner.possible_misconception ? <Field label={t("possibleConfusion")}>{learner.possible_misconception}</Field> : null}
            {learner.how_to_distinguish ? <Field label={t("distinguish")}>{learner.how_to_distinguish}</Field> : null}
            <Field label={t("reviewSuggestion")}>{learner.study_advice}</Field>
          </div>
        ) : learner?.is_correct ? (
          <p className="text-sm text-muted-foreground">{t("selectedCorrect")}</p>
        ) : (
          <p className="text-sm text-muted-foreground">
            {t("noPersonalAnswerAnalysis")}
          </p>
        )}
      </Section>

      <Section title={t("conclusion")}>
        <p className="text-sm font-medium whitespace-pre-wrap">{payload.key_takeaway}</p>
        {payload.review_topics.length ? (
          <div className="flex flex-wrap gap-1">
            {payload.review_topics.map((t) => (
              <Badge key={t} variant="secondary" lang="ja">{t}</Badge>
            ))}
          </div>
        ) : null}
        {!payload.quality.context_sufficient || payload.quality.uncertainty_notes.length ? (
          <div className="text-xs text-amber-700 dark:text-amber-400">
            {!payload.quality.context_sufficient ? <p>{t("aiContextWarning")}</p> : null}
            {payload.quality.uncertainty_notes.map((n, i) => (
              <p key={i}>{t("uncertainty")}: {n}</p>
            ))}
          </div>
        ) : null}
      </Section>
    </div>
  );
}
