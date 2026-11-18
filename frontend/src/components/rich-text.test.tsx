import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RichText } from "./rich-text";

describe("RichText", () => {
  it("renders underline and ruby as elements", () => {
    const { container } = render(<RichText text="この<u>川</u>は<ruby>深<rt>ふか</rt></ruby>い" />);
    expect(container.querySelector("u")?.textContent).toBe("川");
    expect(container.querySelector("ruby rt")?.textContent).toBe("ふか");
    expect(container.textContent).toBe("この川は深ふかい");
  });

  it("never turns other markup into elements", () => {
    const evil = '<img src=x onerror="alert(1)"><script>alert(2)</script><b>太字</b>';
    const { container } = render(<RichText text={evil} />);
    expect(container.querySelector("img, script, b")).toBeNull();
    expect(container.textContent).toBe(evil);
  });

  it("keeps unbalanced tags as text", () => {
    const { container } = render(<RichText text="a</u>b<rt>c" />);
    expect(container.querySelector("u, rt")).toBeNull();
    expect(container.textContent).toBe("a</u>b<rt>c");
  });

  it("preserves furigana written in brackets and full-width spaces", () => {
    const text = "緑葉（りょくよう）という店（　　）";
    const { container } = render(<RichText text={text} />);
    expect(container.textContent).toBe(text);
  });
});
