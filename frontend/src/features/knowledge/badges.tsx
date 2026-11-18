import { Badge } from "@/components/ui/badge";
import type { KnowledgeStats, Priority } from "@/lib/api/types";
import { formatPercent } from "@/lib/format";
import { confidenceLabels, priorityLabels } from "@/lib/labels";
import { cn } from "@/lib/utils";

export function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <Badge
      variant="outline"
      className={cn(
        priority === "review_now" && "border-destructive/50 text-destructive",
        priority === "due_soon" && "border-amber-500/60 text-amber-700 dark:text-amber-400",
        priority === "stable" && "border-emerald-600/50 text-emerald-700 dark:text-emerald-400",
        priority === "insufficient_data" && "text-muted-foreground",
      )}
    >
      {priorityLabels[priority]}
    </Badge>
  );
}

/** Error rate with its sample size and interval — never a bare percentage. */
export function ErrorRate({ stats }: { stats: Pick<KnowledgeStats, "correct" | "incorrect" | "error_rate" | "error_rate_low" | "error_rate_high" | "confidence"> }) {
  const n = stats.correct + stats.incorrect;
  if (n === 0) return <span className="text-muted-foreground">Chưa có câu được chấm</span>;
  return (
    <span title={`Khoảng tin cậy 95%: ${formatPercent(stats.error_rate_low)}–${formatPercent(stats.error_rate_high)}`}>
      <span className="tabular-nums">{formatPercent(stats.error_rate)}</span>{" "}
      <span className="text-xs text-muted-foreground">
        sai ({stats.incorrect}/{n} câu, {confidenceLabels[stats.confidence]})
      </span>
    </span>
  );
}
