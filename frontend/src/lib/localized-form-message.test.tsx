import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LocaleProvider, useLocale } from "@/lib/i18n";
import { localizedFormMessage } from "./localized-form-message";

function ValidationSample() {
  const { t, locale } = useLocale();
  return <p role="alert">{localizedFormMessage("Vui lòng nhập tên đề", t, locale)}</p>;
}

describe("localized form messages", () => {
  it.each([
    ["vi", "Vui lòng nhập tên đề"],
    ["en", "Enter an exam name"],
    ["ja", "試験名を入力してください"],
  ])("translates existing validation feedback in %s", (locale, message) => {
    localStorage.setItem("jlpt-locale", locale);
    render(<LocaleProvider><ValidationSample /></LocaleProvider>);
    expect(screen.getByRole("alert")).toHaveTextContent(message);
  });
});
