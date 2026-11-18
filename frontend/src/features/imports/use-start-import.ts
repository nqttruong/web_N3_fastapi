"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { errorMessage } from "@/components/states";
import { queryKeys } from "@/lib/api/keys";
import type { ImportDraft } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n";

/** Shared success/error handling: open the preview of the new draft. */
export function useStartImport<V>(fn: (values: V) => Promise<ImportDraft>) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useLocale();
  return useMutation({
    mutationFn: fn,
    onSuccess: (draft) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.importsRoot });
      queryClient.setQueryData(queryKeys.importDraft(draft.id), draft);
      if (draft.status === "failed") toast.error(draft.error_message ?? t("importParseFailed"));
      else toast.success(t("importRecognizedToast").replace("{count}", String(draft.summary.total_questions)));
      router.push(`/imports/${draft.id}`);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
}
