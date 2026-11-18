"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { FormField } from "@/components/form-field";
import { errorMessage } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";
import { useLocale } from "@/lib/i18n";

const MAX_LENGTH = 20000;

export function PassageForm({ examId }: { examId: string }) {
  const { t } = useLocale();
  const queryClient = useQueryClient();
  const [content, setContent] = useState("");
  const [error, setError] = useState<string>();

  const mutation = useMutation({
    mutationFn: (text: string) => api.createPassage(examId, text),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.passages(examId) });
      toast.success(t("addPassageSuccess"));
      setContent("");
    },
    onError: (err) => toast.error(errorMessage(err)),
  });

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const text = content.trim();
    if (!text) return setError(t("passageRequired"));
    if (text.length > MAX_LENGTH) return setError(t("passageMaxLength").replace("{count}", String(MAX_LENGTH)));
    setError(undefined);
    mutation.mutate(text);
  }

  return (
    <form noValidate aria-label={t("addPassageForm")} onSubmit={submit} className="space-y-3">
      <FormField id="passage_content" label={t("passageContent")} error={error}>
        <Textarea
          id="passage_content"
          lang="ja"
          rows={5}
          aria-invalid={!!error}
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
      </FormField>
      <div className="flex justify-end">
        <Button type="submit" variant="outline" disabled={mutation.isPending}>
          {mutation.isPending ? t("saving") : t("addPassageForm")}
        </Button>
      </div>
    </form>
  );
}
