"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ExternalLink, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { RichText } from "@/components/rich-text";
import { ErrorState, LoadingState, errorMessage } from "@/components/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, assetUrl } from "@/lib/api/client";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { EXAM_CATEGORIES, type DraftContent, type DraftQuestion, type ImportDraft, type Issue } from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { isoToLocalInput, localInputToIso } from "@/lib/import-schemas";
import { adapterMessageKey, severityMessageKey } from "@/lib/localized-labels";
import { useLocale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import { CommitDialog } from "./commit-dialog";
import { QuestionEditorCard } from "./question-editor-card";

function Stat({ id, label, value, tone }: { id: string; label: string; value: number; tone?: "warn" | "ok" | "bad" }) {
  return (
    <div className="rounded-xl border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        data-testid={`import-stat-${id}`}
        className={cn(
          "text-xl font-semibold tabular-nums",
          tone === "warn" && value > 0 && "text-amber-700 dark:text-amber-400",
          tone === "bad" && value > 0 && "text-destructive",
          tone === "ok" && "text-emerald-700 dark:text-emerald-400",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export function ImportEditor() {
  const { id } = useParams<{ id: string }>();
  const query = useQuery({ queryKey: queryKeys.importDraft(id), queryFn: () => api.getImport(id) });
  if (query.isPending) return <LoadingState rows={6} />;
  if (query.error) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  return <Editor key={query.data.version} draft={query.data} />;
}

function Editor({ draft }: { draft: ImportDraft }) {
  const { t, locale } = useLocale();
  const router = useRouter();
  const queryClient = useQueryClient();
  // Local working copy; re-created from the server whenever `version` changes (key above).
  const [content, setContent] = useState<DraftContent>(draft.content);
  const [sourceUrl, setSourceUrl] = useState(draft.source_url ?? "");
  const [dirty, setDirty] = useState(false);
  const [rawText, setRawText] = useState(draft.raw_input ?? "");
  const [commitOpen, setCommitOpen] = useState(false);
  const readOnly = draft.status === "committed";

  const setDraftData = (d: ImportDraft) => {
    queryClient.setQueryData(queryKeys.importDraft(d.id), d);
    queryClient.invalidateQueries({ queryKey: queryKeys.imports() });
  };
  const onError = (e: unknown) => {
    if (e instanceof ApiError && e.status === 409) {
      toast.error(e.message, { action: { label: t("reload"), onClick: () => queryClient.invalidateQueries({ queryKey: queryKeys.importDraft(draft.id) }) } });
    } else toast.error(errorMessage(e));
  };

  const edit = (fn: (c: DraftContent) => DraftContent) => {
    setContent((c) => fn(structuredClone(c)));
    setDirty(true);
  };
  const updateQuestion = (key: string, patch: Partial<DraftQuestion>) =>
    edit((c) => ({ ...c, questions: c.questions.map((q) => (q.key === key ? { ...q, ...patch } : q)) }));
  const moveQuestion = (index: number, delta: number) =>
    edit((c) => {
      const qs = [...c.questions];
      const [item] = qs.splice(index, 1);
      qs.splice(index + delta, 0, item!);
      return { ...c, questions: qs };
    });

  const urlError = sourceUrl && !/^https?:\/\/\S+$/i.test(sourceUrl.trim()) ? t("urlMustBeHttp") : null;

  const save = useMutation({
    mutationFn: () =>
      api.updateImport(draft.id, {
        version: draft.version,
        content,
        ...(sourceUrl.trim() !== (draft.source_url ?? "") ? { source_url: sourceUrl.trim() || null } : {}),
      }),
    onSuccess: (d) => {
      setDraftData(d);
      toast.success(t("draftSaved"));
    },
    onError,
  });
  const validate = useMutation({ mutationFn: () => api.validateImport(draft.id), onSuccess: setDraftData, onError });
  const reparse = useMutation({
    mutationFn: () => api.reparseImport(draft.id, draft.method === "images" ? undefined : rawText),
    onSuccess: (d) => {
      setDraftData(d);
      toast.success(`${t("reparsed")}: ${d.summary.total_questions} ${t("questionCount")}.`);
    },
    onError,
  });
  const reorderAssets = useMutation({
    mutationFn: (order: string[]) => api.updateImport(draft.id, { version: draft.version, asset_order: order }),
    onSuccess: (d) => {
      setDraftData(d);
      toast.info(t("imageOrderChanged"));
    },
    onError,
  });
  const remove = useMutation({
    mutationFn: () => api.deleteImport(draft.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.importsRoot });
      toast.success(t("draftDeleted"));
      router.push("/imports");
    },
    onError,
  });

  const draftIssues = draft.issues.filter((i) => !i.question_key);
  const issuesByQuestion = new Map<string, Issue[]>();
  for (const i of draft.issues) {
    if (i.question_key) issuesByQuestion.set(i.question_key, [...(issuesByQuestion.get(i.question_key) ?? []), i]);
  }
  const s = draft.summary;
  const busy = save.isPending || validate.isPending || reparse.isPending;

  return (
    <>
      <PageHeader
        title={<span lang="ja">{content.exam.title || t("untitledDraft")}</span>}
        description={
          <span className="flex flex-wrap items-center gap-2">
            <Badge variant={draft.status === "ready" ? "default" : draft.status === "failed" ? "destructive" : "outline"}>
              {draft.status === "uploaded" ? t("importUploaded") : draft.status === "parsing" ? t("importParsing") : draft.status === "needs_review" ? t("importNeedsReview") : draft.status === "ready" ? t("importReady") : draft.status === "committed" ? t("importCommitted") : t("importFailed")}
            </Badge>
            <span>{draft.method === "text" ? t("importText") : draft.method === "html" ? t("importHtml") : draft.method === "images" ? t("importImage") : t("extensionCapture")}</span>
            {draft.adapter ? <span>· {adapterMessageKey[draft.adapter] ? t(adapterMessageKey[draft.adapter]!) : draft.adapter}</span> : null}
            <span>· {t("created")} {formatDateTime(draft.created_at, locale)}</span>
          </span>
        }
        actions={
          readOnly ? (
            draft.exam_id ? (
              <Button asChild>
                <Link href={`/exams/${draft.exam_id}`}>{t("openSavedExam")}</Link>
              </Button>
            ) : null
          ) : (
            <>
              <Button variant="outline" disabled={!dirty || busy || !!urlError} onClick={() => save.mutate()}>
                <Save aria-hidden /> {save.isPending ? t("saving") : t("saveChanges")}
              </Button>
              <Button variant="outline" disabled={dirty || busy} onClick={() => validate.mutate()} title={dirty ? t("saveChangesFirst") : undefined}>
                <RefreshCw aria-hidden /> {t("validateAgain")}
              </Button>
              <Button
                disabled={dirty || busy || draft.status !== "ready"}
                title={dirty ? t("saveChangesFirst") : draft.status !== "ready" ? t("issuesRemain") : undefined}
                onClick={() => setCommitOpen(true)}
              >
                {t("saveAsExam")}
              </Button>
            </>
          )
        }
      />

      {dirty ? (
        <Alert className="mb-4">
          <AlertDescription>{t("unsavedDraftWarning")}</AlertDescription>
        </Alert>
      ) : null}
      {draft.status === "failed" ? (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>{t("parseFailed")} ({draft.error_code})</AlertTitle>
          <AlertDescription>
            <p>{t("requestFailedMessage")}</p>
            {draft.error_message ? <details className="mt-2 text-xs"><summary className="cursor-pointer">{t("errorDetails")}</summary><p className="mt-1 whitespace-pre-wrap">{draft.error_message}</p></details> : null}
          </AlertDescription>
        </Alert>
      ) : null}
      {readOnly ? (
        <Alert className="mb-4">
          <AlertTitle>{t("draftCommittedAt")} {formatDateTime(draft.committed_at, locale)}</AlertTitle>
          <AlertDescription>
            {t("draftRetainedForReference")}{" "}
            {draft.attempt_id ? (
              <Link className="underline" href={`/attempts/${draft.attempt_id}`}>
                {t("viewCreatedAttempt")}
              </Link>
            ) : null}
          </AlertDescription>
        </Alert>
      ) : null}

      <section aria-label={t("recognitionSummary")} className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat id="recognized" label={t("recognizedQuestions")} value={s.total_questions} />
        <Stat id="included" label={t("questionsToSave")} value={s.included_questions} />
        <Stat id="valid" label={t("validQuestions")} value={s.valid_questions} tone="ok" />
        <Stat id="missing-answer" label={t("missingAnswer")} value={s.missing_answer} tone="warn" />
        <Stat id="needs-review" label={t("needsReview")} value={s.needs_review} tone="warn" />
        <Stat id="verified" label={t("verifiedAnswers")} value={s.confirmed_answers} />
      </section>

      {draftIssues.length > 0 ? (
        <Card className="mb-6">
          <CardHeader>
            <CardTitle>{t("validateImportData")}</CardTitle>
            <CardDescription>
              {s.errors} {t("errorCount")}, {s.warnings} {t("warningCount")}. {t("validationSaveRule")}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm" aria-label={t("draftIssues")}>
              {draftIssues.map((i, n) => (
                <li key={`${i.code}-${n}`} className="flex flex-wrap items-start gap-2">
                  <Badge variant={i.severity === "error" ? "destructive" : "outline"}>{t(severityMessageKey[i.severity])}</Badge>
                  <span className="min-w-0 flex-1">{i.message}</span>
                  {typeof i.data?.exam_id === "string" ? (
                    <Link className="inline-flex items-center gap-1 text-xs underline" href={`/exams/${i.data.exam_id}`}>
                      {t("viewExam")} <ExternalLink className="size-3" aria-hidden />
                    </Link>
                  ) : null}
                  {typeof i.data?.draft_id === "string" ? (
                    <Link className="text-xs underline" href={`/imports/${i.data.draft_id}`}>
                      {t("viewDraft")}
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-6 min-w-0">
          <section aria-labelledby="questions-heading">
            <h2 id="questions-heading" className="mb-3 text-lg font-semibold">
              {t("questionsList")} ({content.questions.length})
            </h2>
            {content.questions.length === 0 ? (
              <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
                {t("noQuestionsDetected")}
              </p>
            ) : (
              <ol className="space-y-3">
                {content.questions.map((q, i) => (
                  <QuestionEditorCard
                    key={q.key}
                    question={q}
                    index={i}
                    total={content.questions.length}
                    passages={content.passages}
                    issues={dirty ? [] : (issuesByQuestion.get(q.key) ?? [])}
                    readOnly={readOnly}
                    onChange={(patch) => updateQuestion(q.key, patch)}
                    onMove={(delta) => moveQuestion(i, delta)}
                  />
                ))}
              </ol>
            )}
          </section>

          <section aria-labelledby="passages-heading">
            <div className="mb-3 flex items-center justify-between">
              <h2 id="passages-heading" className="text-lg font-semibold">
                {t("passages")} ({content.passages.length})
              </h2>
              {!readOnly ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    edit((c) => {
                      let n = c.passages.length + 1;
                      while (c.passages.some((p) => p.key === `p${n}`)) n += 1;
                      return { ...c, passages: [...c.passages, { key: `p${n}`, content: "" }] };
                    })
                  }
                >
                  <Plus aria-hidden /> {t("addPassage")}
                </Button>
              ) : null}
            </div>
            <ol className="space-y-3">
              {content.passages.map((p) => (
                <li key={p.key} className="rounded-xl border bg-muted/30 p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <span className="text-xs font-medium text-muted-foreground">{t("passageNumber")} {p.key}</span>
                    <span className="text-xs text-muted-foreground">
                      · {content.questions.filter((q) => q.passage_key === p.key).length} {t("linkedQuestions")}
                    </span>
                    {!readOnly ? (
                      <Button
                        size="icon-sm"
                        variant="ghost"
                        className="ml-auto"
                        aria-label={`${t("deletePassage")} ${p.key}`}
                        onClick={() =>
                          edit((c) => ({
                            ...c,
                            passages: c.passages.filter((x) => x.key !== p.key),
                            questions: c.questions.map((q) => (q.passage_key === p.key ? { ...q, passage_key: null } : q)),
                          }))
                        }
                      >
                        <Trash2 />
                      </Button>
                    ) : null}
                  </div>
                  {readOnly ? (
                    <p className="leading-relaxed whitespace-pre-wrap">
                      <RichText text={p.content} />
                    </p>
                  ) : (
                    <Textarea
                      lang="ja"
                      rows={5}
                      aria-label={`${t("passageContent")} ${p.key}`}
                      value={p.content}
                      onChange={(e) =>
                        edit((c) => ({ ...c, passages: c.passages.map((x) => (x.key === p.key ? { ...x, content: e.target.value } : x)) }))
                      }
                    />
                  )}
                </li>
              ))}
            </ol>
          </section>
        </div>

        <aside className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t("examInfo")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="meta-title">{t("examName")} *</Label>
                <Input
                  id="meta-title"
                  lang="ja"
                  disabled={readOnly}
                  value={content.exam.title}
                  onChange={(e) => edit((c) => ({ ...c, exam: { ...c.exam, title: e.target.value } }))}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="meta-url">{t("sourceUrl")}</Label>
                <Input id="meta-url" type="url" disabled={readOnly} value={sourceUrl} aria-invalid={!!urlError} onChange={(e) => { setSourceUrl(e.target.value); setDirty(true); }} />
                {urlError ? <p className="text-sm text-destructive">{urlError}</p> : <p className="text-xs text-muted-foreground">{t("serverDoesNotFetchUrl")}</p>}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label htmlFor="meta-level">{t("level")}</Label>
                  <Input id="meta-level" value="N3" readOnly className="bg-muted" />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="meta-category">{t("examType")} *</Label>
                  <Select
                    disabled={readOnly}
                    value={content.exam.category ?? ""}
                    onValueChange={(v) => edit((c) => ({ ...c, exam: { ...c.exam, category: v as DraftContent["exam"]["category"] } }))}
                  >
                    <SelectTrigger id="meta-category" className="w-full">
                      <SelectValue placeholder={t("selectExamType")} />
                    </SelectTrigger>
                    <SelectContent>
                      {EXAM_CATEGORIES.map((cat) => (
                        <SelectItem key={cat} value={cat}>
                          {cat === "vocabulary" ? t("vocabulary") : cat === "kanji" ? t("kanji") : cat === "grammar" ? t("grammar") : t("reading")}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("attemptFromImport")}</CardTitle>
              <CardDescription>
                {s.with_user_answer > 0
                  ? t("importContainsAnswers").replace("{count}", String(s.with_user_answer))
                  : t("importHasNoAnswers")}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  disabled={readOnly || s.with_user_answer === 0}
                  checked={content.attempt.create}
                  onCheckedChange={(v) => edit((c) => ({ ...c, attempt: { ...c.attempt, create: v === true } }))}
                />
                {t("createAttemptWhenSaving")}
              </label>
              {content.attempt.create ? (
                <div className="grid gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="attempt-start">{t("attemptStartedAt")} *</Label>
                    <Input
                      id="attempt-start"
                      type="datetime-local"
                      disabled={readOnly}
                      value={isoToLocalInput(content.attempt.started_at)}
                      onChange={(e) => edit((c) => ({ ...c, attempt: { ...c.attempt, started_at: localInputToIso(e.target.value) } }))}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="attempt-end">{t("attemptSubmittedAt")} *</Label>
                    <Input
                      id="attempt-end"
                      type="datetime-local"
                      disabled={readOnly}
                      value={isoToLocalInput(content.attempt.completed_at)}
                      onChange={(e) => edit((c) => ({ ...c, attempt: { ...c.attempt, completed_at: localInputToIso(e.target.value) } }))}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t("attemptImportGradingNote")}
                  </p>
                </div>
              ) : null}
            </CardContent>
          </Card>

          {draft.method === "images" ? (
            <Card>
              <CardHeader>
                <CardTitle>{t("uploadedImages")}</CardTitle>
                <CardDescription>{t("compareImagesOcrNote")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {draft.assets.map((a, i) => (
                  <details key={a.id} className="rounded-lg border p-2 text-xs">
                    <summary className="flex cursor-pointer items-center gap-2">
                      <span className="font-medium">#{i + 1}</span>
                      <span className="truncate">{a.original_filename}</span>
                      <Badge variant={a.ocr_status === "done" ? "outline" : "destructive"} className="ml-auto">
                        {a.ocr_status === "done" ? t("ocrDone") : a.ocr_status === "failed" ? t("ocrFailed") : t("ocrPending")}
                      </Badge>
                    </summary>
                    <a href={assetUrl(`/imports/${draft.id}/assets/${a.id}`)} target="_blank" rel="noopener noreferrer" className="mt-2 block">
                      {/* eslint-disable-next-line @next/next/no-img-element -- served by our API as normalised PNG */}
                        <img src={assetUrl(`/imports/${draft.id}/assets/${a.id}`)} alt={`${t("sourceImages")} ${i + 1}`} className="max-h-96 w-full rounded object-contain object-top" />
                    </a>
                    {a.ocr_text ? <pre className="mt-2 max-h-60 overflow-auto whitespace-pre-wrap" lang="ja">{a.ocr_text}</pre> : null}
                    {!readOnly ? (
                      <div className="mt-2 flex gap-1">
                        <Button size="icon-xs" variant="outline" aria-label={`${t("moveImageUp")} ${i + 1}`} disabled={i === 0 || reorderAssets.isPending || dirty} onClick={() => { const ids = draft.assets.map((x) => x.id); [ids[i - 1], ids[i]] = [ids[i]!, ids[i - 1]!]; reorderAssets.mutate(ids); }}>
                          <ArrowUp />
                        </Button>
                        <Button size="icon-xs" variant="outline" aria-label={`${t("moveImageDown")} ${i + 1}`} disabled={i === draft.assets.length - 1 || reorderAssets.isPending || dirty} onClick={() => { const ids = draft.assets.map((x) => x.id); [ids[i + 1], ids[i]] = [ids[i]!, ids[i + 1]!]; reorderAssets.mutate(ids); }}>
                          <ArrowDown />
                        </Button>
                      </div>
                    ) : null}
                  </details>
                ))}
                {!readOnly ? (
                  <Button size="sm" variant="outline" disabled={busy || dirty} onClick={() => window.confirm(t("reparseReplaceConfirm")) && reparse.mutate()}>
                    <RefreshCw aria-hidden /> {t("reparseFromOcr")}
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          ) : draft.method === "browser_capture" ? (
            <Card>
              <CardHeader>
                <CardTitle>{t("capturedSourceData")}</CardTitle>
                <CardDescription>
                  {t("captureReferenceHint")}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-muted p-3 font-mono text-xs" lang="ja">
                  {rawText}
                </pre>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>{draft.method === "html" ? t("htmlOriginal") : t("textOriginal")}</CardTitle>
                <CardDescription>{t("originalKeptForReference")}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Textarea
                  aria-label={t("originalData")}
                  lang="ja"
                  rows={10}
                  spellCheck={false}
                  disabled={readOnly}
                  className="h-72 max-h-96 resize-y overflow-auto font-mono text-xs field-sizing-fixed"
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                />
                {!readOnly ? (
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busy || dirty || !rawText.trim()}
                    onClick={() => window.confirm(t("reparseReplaceConfirm")) && reparse.mutate()}
                  >
                    <RefreshCw aria-hidden /> {reparse.isPending ? t("analyzing") : t("reparse")}
                  </Button>
                ) : null}
              </CardContent>
            </Card>
          )}

          {!readOnly ? (
            <Button
              variant="ghost"
              className="w-full text-destructive"
              disabled={remove.isPending}
              onClick={() => window.confirm(t("deleteDraftConfirm")) && remove.mutate()}
            >
              <Trash2 aria-hidden /> {t("deleteDraft")}
            </Button>
          ) : null}
        </aside>
      </div>

      {commitOpen ? <CommitDialog draft={draft} onClose={() => setCommitOpen(false)} /> : null}
    </>
  );
}
