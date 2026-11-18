"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ClipboardCopy, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingState, errorMessage } from "@/components/states";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import type { ManualImportResult } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n";

import { ExplanationView } from "./explanation-view";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Client-side syntax check only (the server does the real validation). Never edits content. */
export function checkJsonSyntax(raw: string): string | null {
  const fenced = /^\s*```(?:json)?\s*([\s\S]*?)\s*```\s*$/.exec(raw);
  try {
    JSON.parse(fenced ? fenced[1]! : raw);
    return null;
  } catch {
    return "invalid";
  }
}

export function ManualMode() {
  const { t } = useLocale();
  const params = useSearchParams();
  const allIds = (params.get("q") ?? "").split(",").filter((s) => UUID_RE.test(s));
  const attemptId = params.get("attempt");
  const requestedPart = Math.max(0, Number(params.get("part")) || 0);
  const part = Math.min(requestedPart, Math.max(0, Math.ceil(allIds.length / 20) - 1));
  const ids = allIds.slice(part * 20, part * 20 + 20);
  const queryClient = useQueryClient();
  const [raw, setRaw] = useState("");
  const [modelLabel, setModelLabel] = useState("");
  const [copied, setCopied] = useState(false);
  const [preview, setPreview] = useState<ManualImportResult | null>(null);
  const [saved, setSaved] = useState<ManualImportResult | null>(null);

  const exported = useQuery({
    queryKey: ["explanations", "export", ids.join(","), attemptId],
    queryFn: () => api.exportPrompt(ids, attemptId ?? undefined),
    enabled: ids.length > 0,
    staleTime: Infinity,
  });
  const allowedIds = exported.data?.question_ids ?? [];
  const syntaxError = raw.trim() ? checkJsonSyntax(raw) : null;

  const validate = useMutation({
    mutationFn: () => api.manualImport({ question_ids: allowedIds, raw_json: raw, save: false }),
    onSuccess: (r) => {
      setPreview(r);
      setSaved(null);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const save = useMutation({
    mutationFn: () =>
      api.manualImport({ question_ids: allowedIds, raw_json: raw, save: true, model_label: modelLabel.trim() || undefined }),
    onSuccess: (r) => {
      setSaved(r);
      queryClient.invalidateQueries({ queryKey: queryKeys.explanationsRoot });
      toast.success(`${r.items.filter((i) => i.saved_explanation_id).length} ${t("explanationsSavedAwaitingApproval")}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (ids.length === 0) {
    return <EmptyState title={t("noQuestionsSelected")} description={t("manualReviewHint")} />;
  }
  if (exported.isPending) return <LoadingState rows={4} />;
  if (exported.error) return <ErrorState error={exported.error} onRetry={() => exported.refetch()} />;
  const data = exported.data;
  const okCount = preview?.items.filter((i) => i.ok).length ?? 0;

  return (
    <>
      <PageHeader
        title={t("manualChatgptTitle")}
        description={`${data.question_ids.length} ${t("questionCount")}${allIds.length > 20 ? ` · ${t("nextQuestionGroup")} ${part + 1}/${Math.ceil(allIds.length / 20)}` : ""} · ${t("promptVersionLabel")} ${data.prompt_version} · ${t("schemaVersionLabel")} ${data.schema_version}`}
        actions={
          <div className="flex flex-wrap gap-2">
            {attemptId ? <Button asChild variant="outline"><Link href={`/attempts/${attemptId}`}>{t("backToAttempt")}</Link></Button> : null}
            {allIds.length > (part + 1) * 20 ? <Button asChild><Link href={`/explanations/manual?q=${allIds.join(",")}&attempt=${attemptId ?? ""}&part=${part + 1}`}>{t("nextQuestionGroup")} ({part + 2}/{Math.ceil(allIds.length / 20)})</Link></Button> : null}
          </div>
        }
      />
      {data.skipped.length ? (
        <Alert className="mb-4">
          <AlertTitle>{data.skipped.length} {t("notIncludedInPrompt")}</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-5">
              {data.skipped.map((s) => (
                <li key={s.question_id}>{s.message}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t("step1Chatgpt")}</CardTitle>
            <CardDescription>{t("promptDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              readOnly
              aria-label={t("chatgptPrompt")}
              className="h-72 font-mono text-xs field-sizing-fixed"
              value={data.prompt}
            />
            <Button
              onClick={async () => {
                // Open synchronously from the click so popup blockers allow it. No page content or
                // credentials are read from ChatGPT; the only data transfer is the user-approved clipboard copy.
                window.open("https://chatgpt.com/", "_blank", "noopener,noreferrer");
                try {
                  await navigator.clipboard.writeText(data.prompt);
                  setCopied(true);
                  toast.success(t("promptCopiedOpenChatgpt"));
                } catch {
                  toast.error(t("openedCopyFailed"));
                }
              }}
            >
              <ExternalLink aria-hidden /> {t("reviewWithChatgpt")}
            </Button>
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(data.prompt);
                  setCopied(true);
                  toast.success(t("promptCopied"));
                } catch {
                  toast.error(t("copyFailed"));
                }
              }}
            >
              {copied ? <Check aria-hidden /> : <ClipboardCopy aria-hidden />} {t("copyPrompt")}
            </Button>
            <p className="text-xs text-muted-foreground">{t("chatgptPasteInstruction")}</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t("step2PasteJson")}</CardTitle>
            <CardDescription>{t("jsonValidationDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Textarea
              aria-label={t("chatgptJson")}
              spellCheck={false}
              className="h-72 font-mono text-xs field-sizing-fixed"
              placeholder='{"explanations": [ ... ]}'
              value={raw}
              onChange={(e) => {
                setRaw(e.target.value);
                setPreview(null);
                setSaved(null);
              }}
            />
            {syntaxError ? (
              <p role="alert" className="text-sm text-destructive">
                {t("invalidJsonSyntax")}
              </p>
            ) : null}
            <div className="space-y-1.5">
              <Label htmlFor="model-label">{t("modelNameOptional")}</Label>
              <Input id="model-label" placeholder="ChatGPT" value={modelLabel} onChange={(e) => setModelLabel(e.target.value)} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button disabled={!raw.trim() || !!syntaxError || validate.isPending} onClick={() => validate.mutate()}>
                {validate.isPending ? t("validatePending") : t("checkPreview")}
              </Button>
              <Button
                variant="outline"
                disabled={!preview || okCount === 0 || save.isPending || !!saved}
                onClick={() => save.mutate()}
              >
                {save.isPending ? t("saving") : t("saveValidExplanations").replace("{count}", String(okCount))}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {preview ? (
        <section className="mt-6 space-y-4" aria-label={t("preview")}>
          <h2 className="text-lg font-semibold">{t("preview")} ({okCount}/{preview.items.length} {t("validCount")})</h2>
          {preview.missing_question_ids.length ? (
            <p className="text-sm text-muted-foreground">{preview.missing_question_ids.length} {t("selectedMissingExplanations")}</p>
          ) : null}
          {preview.items.map((item) => {
            const savedItem = saved?.items.find((s) => s.index === item.index);
            return (
              <Card key={item.index} data-testid="manual-preview-item">
                <CardHeader>
                  <CardTitle className="flex flex-wrap items-center gap-2 text-base">
                    {t("explanationNumber").replace("{number}", String(item.index + 1))}
                    {item.ok ? (
                      <Badge variant="outline" className="border-amber-500/60 text-amber-700 dark:text-amber-400">
                        {t("validWillSaveAs")} “{item.status === "approved" ? t("statusReady") : t("pendingApproval")}”
                      </Badge>
                    ) : (
                      <Badge variant="destructive">{t("invalidWillNotSave")}</Badge>
                    )}
                    {savedItem?.saved_explanation_id ? (
                      <Link className="text-sm underline" href={`/questions/${item.question_id}/explanation${attemptId ? `?attempt=${attemptId}` : ""}`}>
                        {t("savedOpenToApprove")}
                      </Link>
                    ) : null}
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {item.findings.length ? (
                    <ul className="space-y-1 text-sm">
                      {item.findings.map((f, i) => (
                        <li
                          key={`${f.code}-${i}`}
                          className={f.severity === "error" ? "text-destructive" : f.severity === "warning" ? "text-amber-700 dark:text-amber-400" : "text-muted-foreground"}
                        >
                          <details>
                            <summary className="cursor-pointer">{t("validation")} · {t(f.severity === "error" ? "severityError" : f.severity === "warning" ? "severityWarning" : "severityInfo")}</summary>
                            <p className="mt-1">{f.message}</p>
                          </details>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                  {item.ok && item.payload ? <ExplanationView payload={item.payload} learner={null} findings={item.findings} /> : null}
                </CardContent>
              </Card>
            );
          })}
        </section>
      ) : null}
    </>
  );
}
