import type { AnswerSource, ExamCategory, ExamStatus, QuestionType, Severity } from "@/lib/api/types";
import type { MessageKey } from "@/lib/i18n";

export const questionTypeMessageKey: Record<QuestionType, MessageKey> = {
  kanji_reading: "qtypeKanjiReading",
  orthography: "qtypeOrthography",
  word_formation: "qtypeWordFormation",
  contextual_definition: "qtypeContextualDefinition",
  paraphrase: "qtypeParaphrase",
  usage: "qtypeUsage",
  grammar_form: "qtypeGrammarForm",
  sentence_composition: "qtypeSentenceComposition",
  text_grammar: "qtypeTextGrammar",
  reading_short: "qtypeReadingShort",
  reading_medium: "qtypeReadingMedium",
  reading_long: "qtypeReadingLong",
  information_retrieval: "qtypeInformationRetrieval",
  other: "qtypeOther",
};

export const answerSourceMessageKey: Record<AnswerSource, MessageKey> = {
  manual: "answerSourceManual",
  site_key: "answerSourceSite",
  user_entered: "answerSourceUser",
  ocr: "answerSourceOcr",
};

export const examCategoryMessageKey: Record<ExamCategory, MessageKey> = {
  vocabulary: "vocabulary",
  kanji: "kanji",
  grammar: "grammar",
  reading: "reading",
};

export const examStatusMessageKey: Record<ExamStatus, MessageKey> = {
  draft: "statusDraft",
  ready: "statusReady",
  archived: "statusArchived",
};

export const severityMessageKey: Record<Severity, MessageKey> = {
  error: "severityError",
  warning: "severityWarning",
  info: "severityInfo",
};

export const adapterMessageKey: Record<string, MessageKey> = {
  generic_text: "adapterGenericText",
  generic_html: "adapterGenericHtml",
  dethitiengnhat_html: "adapterDethitiengnhatHtml",
  dethitiengnhat_capture: "adapterDethitiengnhatCapture",
  ocr_text: "adapterOcrText",
};
