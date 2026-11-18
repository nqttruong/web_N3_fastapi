import type { ReactNode } from "react";

/** N3 Sensei assets annotate readings as {表記|よみ}; render the source text as ruby. */
export function JapaneseText({ value, className }: { value: string; className?: string }) {
  const parts: ReactNode[] = [];
  const pattern = /\{([^{}|]+)\|([^{}|]+)\}/g;
  let previous = 0;
  for (const match of value.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > previous) parts.push(value.slice(previous, start));
    parts.push(<ruby key={start}>{match[1]}<rt>{match[2]}</rt></ruby>);
    previous = start + match[0].length;
  }
  if (previous < value.length) parts.push(value.slice(previous));
  return <span lang="ja" className={className}>{parts}</span>;
}
