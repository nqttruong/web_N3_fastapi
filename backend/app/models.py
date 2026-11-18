"""Import every model module so ``Base.metadata`` is complete (used by Alembic and tests)."""

from app.attempts.models import AttemptAnswer, ExamAttempt
from app.database.base import Base
from app.exams.models import Exam, ExamSource, Passage, Question
from app.explanations.models import AIExplanation, AIRequest, ExplanationJob, ExplanationJobItem
from app.imports.models import ImportAsset, ImportDraft
from app.knowledge.models import (
    KnowledgeEvidence,
    KnowledgeItem,
    KnowledgeRelationLink,
    QuestionKnowledge,
)
from app.learning_content.models import (
    LearningContentChange,
    LearningContentPack,
    LearningExample,
    LearningItem,
    LearningItemExample,
    LearningLesson,
    LearningSyncQueueLock,
    LearningSyncRun,
)
from app.learning_content.my_words_models import (
    MyWord,
    MyWordExtensionCredential,
    MyWordProgress,
    MyWordReviewEvent,
)
from app.learning_content.study_models import (
    LearningExerciseAnswer,
    LearningSavedItem,
    LearningSourceRight,
    LearningStudyEvent,
    LearningStudyProgress,
    LearningStudySession,
)
from app.practice.models import GeneratedPracticeQuestion, PracticeGeneration
from app.reviews.models import ReviewEvent, ReviewItem, ReviewSession
from app.sync.device import SyncDevice, SyncPairingAttempt, SyncPairingCode
from app.sync.models import AndroidReviewEvent, SyncChange
from app.sync.qr_models import SyncQRAudit, SyncQRSession

__all__ = [
    "AIExplanation",
    "AIRequest",
    "AndroidReviewEvent",
    "AttemptAnswer",
    "Base",
    "Exam",
    "ExamAttempt",
    "ExamSource",
    "ExplanationJob",
    "ExplanationJobItem",
    "GeneratedPracticeQuestion",
    "ImportAsset",
    "ImportDraft",
    "KnowledgeEvidence",
    "KnowledgeItem",
    "KnowledgeRelationLink",
    "LearningContentChange",
    "LearningContentPack",
    "LearningExample",
    "LearningExerciseAnswer",
    "LearningItem",
    "LearningItemExample",
    "LearningLesson",
    "LearningSavedItem",
    "LearningSourceRight",
    "LearningStudyEvent",
    "LearningStudyProgress",
    "LearningStudySession",
    "LearningSyncQueueLock",
    "LearningSyncRun",
    "MyWord",
    "MyWordExtensionCredential",
    "MyWordProgress",
    "MyWordReviewEvent",
    "Passage",
    "PracticeGeneration",
    "Question",
    "QuestionKnowledge",
    "ReviewEvent",
    "ReviewItem",
    "ReviewSession",
    "SyncChange",
    "SyncDevice",
    "SyncPairingAttempt",
    "SyncPairingCode",
    "SyncQRAudit",
    "SyncQRSession",
]
