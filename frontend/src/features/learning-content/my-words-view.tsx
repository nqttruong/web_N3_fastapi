"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingState, EmptyState } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useLocale } from "@/lib/i18n";
import { myWordsApi, type Language, type MyWord, type WordFields } from "./my-words-api";

const blank: WordFields = { original_text: "", language: "ja", meanings: { vi: [] }, japanese_reading: null, english_ipa: null, source_url: null, source_title: null, context: null, tags: [] };
const languageMessage: Record<Language, "languageJapanese" | "languageEnglish" | "languageVietnamese"> = { ja: "languageJapanese", en: "languageEnglish", vi: "languageVietnamese" };

function WordForm({ current, close }: { current: MyWord | null; close: () => void }) {
  const { t } = useLocale();
  const client = useQueryClient();
  const [fields, setFields] = useState<WordFields>(current ? { original_text: current.original_text, language: current.language, meanings: current.meanings, japanese_reading: current.japanese_reading, english_ipa: current.english_ipa, source_url: current.source_url, source_title: current.source_title, context: current.context, tags: current.tags } : blank);
  const save = useMutation({ mutationFn: async () => { if (current) await myWordsApi.edit(current.id, fields); else await myWordsApi.create(fields); }, onSuccess: () => { void client.invalidateQueries({ queryKey: ["my-words"] }); close(); } });
  const set = <K extends keyof WordFields>(key: K, value: WordFields[K]) => setFields(previous => ({ ...previous, [key]: value }));
  return <Card><CardHeader><CardTitle>{current ? t("editWord") : t("addMyWord")}</CardTitle></CardHeader><CardContent><form aria-label={current ? t("editWordForm") : t("addWordForm")} className="grid gap-3 sm:grid-cols-2" onSubmit={event => { event.preventDefault(); save.mutate(); }}>
    <label className="text-sm">{t("originalTerm")}<Input required maxLength={200} value={fields.original_text} onChange={event => set("original_text", event.target.value)} /></label>
    <label className="text-sm">{t("language")}<select className="mt-1 w-full rounded-md border bg-background p-2" value={fields.language} onChange={event => set("language", event.target.value as Language)}>{Object.entries(languageMessage).map(([code, key]) => <option key={code} value={code}>{t(key)}</option>)}</select></label>
    {(["ja", "en", "vi"] as Language[]).map(language => <label key={language} className="text-sm">{t("meaningFor").replace("{language}", t(languageMessage[language]))} ({t("oneMeaningPerLine")})<textarea className="mt-1 min-h-20 w-full rounded-md border bg-background p-2" value={(fields.meanings[language] ?? []).join("\n")} onChange={event => set("meanings", { ...fields.meanings, [language]: event.target.value.split("\n").map(line => line.trim()).filter(Boolean) })} /></label>)}
    <label className="text-sm">{t("japaneseReadingHiragana")}<Input value={fields.japanese_reading ?? ""} onChange={event => set("japanese_reading", event.target.value || null)} /></label>
    <label className="text-sm">{t("englishIpa")}<Input value={fields.english_ipa ?? ""} onChange={event => set("english_ipa", event.target.value || null)} /></label>
    <label className="text-sm">{t("sourcePage")}<Input type="url" value={fields.source_url ?? ""} onChange={event => set("source_url", event.target.value || null)} /></label>
    <label className="text-sm">{t("sourcePageTitle")}<Input value={fields.source_title ?? ""} onChange={event => set("source_title", event.target.value || null)} /></label>
    <label className="text-sm sm:col-span-2">{t("contextLabel")}<Input value={fields.context ?? ""} onChange={event => set("context", event.target.value || null)} /></label>
    <label className="text-sm sm:col-span-2">{t("tagsCommaSeparated")}<Input value={fields.tags.join(", ")} onChange={event => set("tags", event.target.value.split(",").map(tag => tag.trim()).filter(Boolean))} /></label>
    <div className="flex gap-2 sm:col-span-2"><Button type="submit" disabled={save.isPending}>{current ? t("saveChanges") : t("addWord")}</Button><Button type="button" variant="outline" onClick={close}>{t("cancel")}</Button></div>
    {save.error && <p role="alert" className="text-destructive sm:col-span-2">{t("myWordSaveError")}</p>}
  </form></CardContent></Card>;
}

function WordCard({ word, edit }: { word: MyWord; edit: (word: MyWord) => void }) {
  const { t, locale } = useLocale();
  const client = useQueryClient();
  const [revealed, setRevealed] = useState(false);
  const [speechStatus, setSpeechStatus] = useState<"speechUnsupported" | "voiceUnavailable" | "speechError" | "speechPlaying" | "speechFinished" | "speechStopped" | null>(null);
  const review = useMutation({ mutationFn: (rating: "again" | "hard" | "good" | "easy") => myWordsApi.review(word.id, rating), onSuccess: () => void client.invalidateQueries({ queryKey: ["my-words"] }) });
  const archive = useMutation({ mutationFn: () => myWordsApi.archive(word.id), onSuccess: () => void client.invalidateQueries({ queryKey: ["my-words"] }) });
  function speak() {
    if (!("speechSynthesis" in window)) { setSpeechStatus("speechUnsupported"); return; }
    const voice = window.speechSynthesis.getVoices().find(item => item.lang.toLowerCase().startsWith(word.language));
    if (!voice) { setSpeechStatus("voiceUnavailable"); return; }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(word.original_text);
    utterance.voice = voice;
    utterance.lang = voice.lang;
    utterance.onerror = () => setSpeechStatus("speechError");
    utterance.onstart = () => setSpeechStatus("speechPlaying");
    utterance.onend = () => setSpeechStatus("speechFinished");
    window.speechSynthesis.speak(utterance);
  }
  const languageName = (language: Language) => t(languageMessage[language]);
  const dateLocale = locale === "ja" ? "ja-JP" : locale === "en" ? "en-US" : "vi-VN";
  return <Card><CardHeader><CardTitle lang={word.language} className="text-2xl leading-relaxed">{word.original_text}</CardTitle></CardHeader><CardContent className="space-y-3"><p className="text-sm text-muted-foreground">{languageName(word.language)} · {word.japanese_reading || word.english_ipa || t("noReading")}</p>
    {revealed && <div className="space-y-1 border-t pt-3">{Object.entries(word.meanings).map(([language, entries]) => entries?.length ? <p key={language}><strong>{languageName(language as Language)}:</strong> {entries.join("; ")}</p> : null)}{word.context && <p className="text-sm text-muted-foreground">{t("contextPrefix")}: {word.context}</p>}{word.source_url && <a href={word.source_url} rel="noopener noreferrer" target="_blank" className="text-sm underline">{t("sourcePrefix")}: {word.source_title || word.source_url}</a>}</div>}
    <div className="flex flex-wrap gap-2"><Button variant="outline" size="sm" onClick={() => setRevealed(!revealed)}>{revealed ? t("hideMeaning") : t("revealCard")}</Button><Button variant="outline" size="sm" onClick={speak}>{t("listenPronunciation")}</Button><Button variant="outline" size="sm" onClick={() => { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); setSpeechStatus("speechStopped"); }}>{t("stopAudio")}</Button><Button variant="outline" size="sm" onClick={() => edit(word)}>{t("editWord")}</Button><Button variant="outline" size="sm" disabled={archive.isPending} onClick={() => archive.mutate()}>{t("removeSaved")}</Button></div>
    {speechStatus && <p role="status" className="text-xs text-muted-foreground">{t(speechStatus)}</p>}
    {revealed && <div className="flex flex-wrap gap-2" aria-label={t("reviewRating")}>{(["again", "hard", "good", "easy"] as const).map(rating => <Button key={rating} size="sm" disabled={review.isPending} onClick={() => review.mutate(rating)}>{t(rating === "again" ? "forgotten" : rating)}</Button>)}</div>}
    {word.progress && <p className="text-xs text-muted-foreground">{word.progress.review_count} {t("reviewCount")} · {t("nextReview")} {new Date(word.progress.due_at).toLocaleString(dateLocale)}</p>}
    {(review.error || archive.error) && <p role="alert" className="text-destructive">{t("myWordActionError")}</p>}
  </CardContent></Card>;
}

export function MyWordsView() {
  const { t } = useLocale();
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState<Language | undefined>();
  const [page, setPage] = useState(1);
  const [editor, setEditor] = useState<MyWord | null | "new">(null);
  const result = useQuery({ queryKey: ["my-words", query, language, page], queryFn: () => myWordsApi.list({ q: query, language, page }) });
  return <div className="space-y-5"><PageHeader title={t("myWordsTitle")} description={t("myWordsDescription")} actions={<Button onClick={() => setEditor("new")}>{t("addMyWord")}</Button>} />
    {editor && <WordForm key={editor === "new" ? "new" : editor.id} current={editor === "new" ? null : editor} close={() => setEditor(null)} />}
    <form className="flex flex-wrap gap-2" onSubmit={event => { event.preventDefault(); setPage(1); setQuery(search.trim()); }}><Input className="w-full sm:w-64" aria-label={t("findMyWords")} placeholder={t("searchWordsMeanings")} value={search} onChange={event => setSearch(event.target.value)} /><select className="rounded-md border bg-background p-2" aria-label={t("filterLanguage")} value={language ?? "all"} onChange={event => { setLanguage(event.target.value === "all" ? undefined : event.target.value as Language); setPage(1); }}><option value="all">{t("allLanguages")}</option>{Object.entries(languageMessage).map(([code,key]) => <option key={code} value={code}>{t(key)}</option>)}</select><Button type="submit" variant="outline">{t("search")}</Button></form>
    {result.isPending ? <LoadingState rows={3} label={t("loadingMyWords")} /> : result.error ? <ErrorState error={result.error} title={t("learningLoadError")} notFoundTitle={t("learningDataNotFound")} message={t("learningLoadError")} retryLabel={t("retry")} onRetry={() => void result.refetch()} /> : result.data.items.length ? <><p className="text-sm text-muted-foreground">{result.data.total} {t("wordCount")}</p><div className="grid gap-4 md:grid-cols-2">{result.data.items.map(word => <WordCard key={word.id} word={word} edit={setEditor} />)}</div>{result.data.total > page*30 && <Button variant="outline" onClick={() => setPage(page+1)}>{t("nextPage")}</Button>}{page > 1 && <Button variant="outline" onClick={() => setPage(page-1)}>{t("previousPage")}</Button>}</> : <EmptyState title={t("noMyWords")} description={t("addWordToStart")} action={<Button onClick={() => setEditor("new")}>{t("addMyWord")}</Button>} />}
  </div>;
}
