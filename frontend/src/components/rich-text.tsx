import { Fragment, type ReactNode } from "react";

/**
 * Renders question text that may contain the tiny inline markup produced by the importer:
 * `<u>…</u>` (underlined word in 漢字読み questions) and `<ruby>base<rt>reading</rt></ruby>`
 * (furigana). Everything else — including any other "<tag>" — is rendered as plain text by
 * React. This never uses innerHTML, so pasted content cannot inject markup or scripts.
 */
type Node = { tag: "root" | "u" | "ruby" | "rt"; children: (Node | string)[] };

const TOKEN = /(<\/?(?:u|ruby|rt)>)/;

export function parseInlineMarkup(text: string): Node {
  const root: Node = { tag: "root", children: [] };
  const stack: Node[] = [root];
  for (const part of text.split(TOKEN)) {
    if (!part) continue;
    const open = /^<(u|ruby|rt)>$/.exec(part);
    const close = /^<\/(u|ruby|rt)>$/.exec(part);
    const top = stack[stack.length - 1]!;
    if (open) {
      const tag = open[1] as Node["tag"];
      // <rt> only makes sense inside <ruby>; otherwise keep it as literal text.
      if (tag === "rt" && top.tag !== "ruby") {
        top.children.push(part);
        continue;
      }
      const node: Node = { tag, children: [] };
      top.children.push(node);
      stack.push(node);
    } else if (close && top.tag === close[1]) {
      stack.pop();
    } else {
      top.children.push(part);
    }
  }
  return root;
}

function render(node: Node | string, key: number): ReactNode {
  if (typeof node === "string") return <Fragment key={key}>{node}</Fragment>;
  const children = node.children.map(render);
  switch (node.tag) {
    case "u":
      return (
        <u key={key} className="decoration-2 underline-offset-4">
          {children}
        </u>
      );
    case "ruby":
      return <ruby key={key}>{children}</ruby>;
    case "rt":
      return (
        <rt key={key} className="text-[0.6em]">
          {children}
        </rt>
      );
    default:
      return <Fragment key={key}>{children}</Fragment>;
  }
}

export function RichText({ text, className }: { text: string; className?: string }) {
  return (
    <span lang="ja" className={className}>
      {render(parseInlineMarkup(text), 0)}
    </span>
  );
}
