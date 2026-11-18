from app.exams.schemas import ExamCreate, QuestionCreate
from app.seed.data import SEED_EXAMS


def test_seed_dataset_passes_api_validation() -> None:
    assert SEED_EXAMS
    for item in SEED_EXAMS:
        ExamCreate(**item["exam"])
        numbers = [QuestionCreate(**q).question_number for q in item["questions"]]
        assert len(numbers) == len(set(numbers))
