import { redirect } from "next/navigation";

export default function ImportsPage() {
  redirect("/exams?tab=drafts");
}
