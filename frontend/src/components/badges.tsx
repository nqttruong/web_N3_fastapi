import { Badge } from "@/components/ui/badge";
import type { AnswerStatus, ExamCategory, ExamStatus } from "@/lib/api/types";
import { useLocale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export function CategoryBadge({ category }: { category: ExamCategory }) {
  const { t } = useLocale();
  const label = category === "vocabulary" ? t("vocabulary") : category === "kanji" ? t("kanji") : category === "grammar" ? t("grammar") : t("reading");
  return <Badge variant="secondary">{label}</Badge>;
}

export function StatusBadge({ status }: { status: ExamStatus }) {
  const { t } = useLocale();
  const label = status === "draft" ? t("statusDraft") : status === "ready" ? t("statusReady") : t("statusArchived");
  return (
    <Badge variant={status === "ready" ? "default" : "outline"} className={cn(status === "archived" && "opacity-60")}>
      {label}
    </Badge>
  );
}

export function AnswerStatusBadge({ status }: { status: AnswerStatus }) {
  const { t } = useLocale();
  const label = status === "missing" ? t("answerMissing") : status === "unverified" ? t("answerUnverified") : t("answerVerified");
  return (
    <Badge
      variant="outline"
      className={cn(
        status === "verified" && "border-emerald-600/40 text-emerald-700 dark:text-emerald-400",
        status === "unverified" && "border-amber-500/50 text-amber-700 dark:text-amber-400",
        status === "missing" && "text-muted-foreground",
      )}
    >
      {label}
    </Badge>
  );
}

export function ResultBadge({ isCorrect, answered }: { isCorrect: boolean | null; answered: boolean }) {
  const { t } = useLocale();
  if (!answered) return <Badge variant="outline" className="text-muted-foreground">{t("resultUnanswered")}</Badge>;
  if (isCorrect === null) return <Badge variant="outline" className="border-amber-500/50 text-amber-700 dark:text-amber-400">{t("resultUngraded")}</Badge>;
  return isCorrect ? (
    <Badge className="bg-emerald-600 text-white hover:bg-emerald-600">{t("resultCorrect")}</Badge>
  ) : (
    <Badge variant="destructive">{t("resultIncorrect")}</Badge>
  );
}
