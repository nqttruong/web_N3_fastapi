"""Load the self-authored seed dataset: ``uv run python -m app.seed``.

Idempotent: exams whose title already exists are skipped. Goes through the service layer so
all validation rules apply.
"""

from sqlalchemy import select

from app.database.session import get_sessionmaker
from app.exams import service
from app.exams.models import Exam, ExamSource
from app.exams.schemas import ExamCreate, ExamSourceCreate, PassageCreate, QuestionCreate
from app.seed.data import SEED_EXAMS, SEED_SOURCE


def main() -> None:
    with get_sessionmaker()() as db:
        source = db.scalar(select(ExamSource).where(ExamSource.name == SEED_SOURCE["name"]))
        if source is None:
            source = service.create_source(db, ExamSourceCreate(**SEED_SOURCE))
        created = 0
        for item in SEED_EXAMS:
            title = item["exam"]["title"]
            if db.scalar(select(Exam.id).where(Exam.title == title)):
                print(f"skip (exists): {title}")
                continue
            exam = service.create_exam(db, ExamCreate(**item["exam"], source_id=source.id))
            passage_id = None
            if "passage" in item:
                passage_id = service.create_passage(
                    db, exam.id, PassageCreate(content=item["passage"])
                ).id
            for q in item["questions"]:
                service.create_question(db, exam.id, QuestionCreate(**q, passage_id=passage_id))
            created += 1
            print(f"created: {title} ({len(item['questions'])} questions)")
        print(f"done — {created} exam(s) created")


if __name__ == "__main__":
    main()
