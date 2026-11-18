"use client";

import { useState } from "react";

export interface Bar {
  label: string;
  value: number | null;
  detail?: string;
}

/**
 * Single-series bar chart (one hue = magnitude only, so no categorical palette).
 * Thin bars with 4px rounded data-ends on a shared baseline, 2px gaps, hover tooltip,
 * labels in ink colours and a table view for screen readers / exact values.
 */
export function BarChart({
  title,
  bars,
  format = (v) => String(v),
  max,
  height = 120,
}: {
  title: string;
  bars: Bar[];
  format?: (v: number) => string;
  max?: number;
  height?: number;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const top = max ?? Math.max(1, ...bars.map((b) => b.value ?? 0));
  return (
    <figure className="space-y-2">
      <figcaption className="text-sm font-medium">{title}</figcaption>
      <div className="relative" style={{ height }} role="img" aria-label={title}>
        <div className="absolute inset-x-0 bottom-0 border-t border-border" aria-hidden />
        <div className="absolute inset-0 flex items-end gap-0.5">
          {bars.map((b, i) => (
            <div
              key={b.label}
              className="relative flex h-full flex-1 items-end"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            >
              {b.value === null ? (
                <div className="mx-auto h-1 w-1 rounded-full bg-muted-foreground/40" title="Không có dữ liệu" />
              ) : (
                <div
                  className="w-full rounded-t-[4px] bg-primary/80 transition-opacity"
                  style={{ height: `${Math.max(2, (b.value / top) * 100)}%`, opacity: hover === null || hover === i ? 1 : 0.45 }}
                />
              )}
              {hover === i ? (
                <div className="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1 -translate-x-1/2 rounded-md border bg-popover px-2 py-1 text-xs whitespace-nowrap text-popover-foreground shadow">
                  <div className="font-medium">{b.label}</div>
                  <div>{b.value === null ? "Không có dữ liệu" : format(b.value)}</div>
                  {b.detail ? <div className="text-muted-foreground">{b.detail}</div> : null}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
      <div className="flex justify-between text-[11px] text-muted-foreground">
        <span>{bars[0]?.label}</span>
        <span>{bars[bars.length - 1]?.label}</span>
      </div>
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">Xem bảng số liệu</summary>
        <table className="mt-1 w-full">
          <tbody>
            {bars.map((b) => (
              <tr key={b.label} className="border-t">
                <td className="py-0.5 pr-2">{b.label}</td>
                <td className="py-0.5 tabular-nums">{b.value === null ? "—" : format(b.value)}</td>
                <td className="py-0.5">{b.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
