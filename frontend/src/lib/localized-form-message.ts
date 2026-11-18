import type { Locale, MessageKey } from "@/lib/i18n";

type Translate = (key: MessageKey) => string;

const messages: Record<string, MessageKey> = {
  "URL quá dài": "errUrlTooLong",
  "URL phải bắt đầu bằng http:// hoặc https://": "errUrlInvalid",
  "Vui lòng nhập tên đề": "errExamTitleRequired",
  "Tên đề tối đa 300 ký tự": "errTitleMax",
  "Vui lòng chọn loại đề": "errCategoryRequired",
  "Mô tả tối đa 5000 ký tự": "errDescriptionMax",
  "Số câu phải là số": "errQuestionNumber",
  "Số câu phải là số nguyên": "errQuestionInteger",
  "Số câu tối thiểu là 1": "errQuestionMin",
  "Số câu tối đa là 999": "errQuestionMax",
  "Vui lòng nhập nội dung câu hỏi": "errQuestionTextRequired",
  "Nội dung tối đa 5000 ký tự": "errQuestionTextMax",
  "Lựa chọn tối đa 1000 ký tự": "errOptionMax",
  "Cần ít nhất 2 lựa chọn": "errTwoOptions",
  "Các lựa chọn phải liền nhau (không bỏ trống ở giữa)": "errOptionsContiguous",
  "Các lựa chọn không được trùng nhau": "errOptionsDuplicate",
  "Đáp án đúng phải là một lựa chọn đã nhập": "errCorrectAnswerMissing",
  "Chỉ xác nhận được khi đã chọn đáp án": "errConfirmRequiresAnswer",
  "Vui lòng dán nội dung đề": "errPasteText",
  "Vui lòng dán mã HTML": "errPasteHtml",
  "Nội dung không giống HTML (thiếu thẻ)": "errNotHtml",
};

const numberText = (value: number, locale: Locale) => value.toLocaleString(locale);

/** Localizes existing client validation text without changing validation rules or server payloads. */
export function localizedFormMessage(message: string | undefined, t: Translate, locale: Locale): string | undefined {
  if (!message) return message;
  const key = messages[message];
  if (key) return t(key);

  let match = /^Tối đa ([\d.,]+) ký tự$/.exec(message);
  if (match) return t("errTextLimit").replace("{count}", numberText(Number(match[1]!.replace(/\./g, "").replace(",", ".")), locale));
  match = /^HTML tối đa ([\d.,]+) MB$/.exec(message);
  if (match) return t("errHtmlLimit").replace("{size}", numberText(Number(match[1]!.replace(/\./g, "").replace(",", ".")), locale));
  match = /^Tối đa (\d+) ảnh mỗi lần\.$/.exec(message);
  if (match) return t("errImageLimit").replace("{count}", numberText(Number(match[1]), locale));
  match = /^“(.+)”: chỉ hỗ trợ PNG, JPG, WEBP\.$/.exec(message);
  if (match) return t("errImageType").replace("{name}", match[1]!);
  match = /^“(.+)”: vượt quá (\d+) MB\.$/.exec(message);
  if (match) return t("errImageSize").replace("{name}", match[1]!).replace("{size}", match[2]!);
  match = /^“(.+)”: tệp rỗng\.$/.exec(message);
  if (match) return t("errImageEmpty").replace("{name}", match[1]!);
  return message;
}
