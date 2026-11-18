"""Small self-authored JLPT N3-style dataset for development and tests.

Every sentence below was written for this project. Nothing is copied from dethitiengnhat.com
or from official JLPT materials.
"""

from typing import Any

SEED_SOURCE = {"name": "Tự biên soạn (seed)", "base_url": "https://example.invalid/seed"}

SEED_EXAMS: list[dict[str, Any]] = [
    {
        "exam": {
            "title": "[Seed] N3 Từ vựng — Đọc kanji",
            "category": "vocabulary",
            "status": "ready",
            "description": "Bộ câu tự biên soạn để phát triển và kiểm thử (漢字読み).",
        },
        "questions": [
            {
                "question_number": 1,
                "question_type": "kanji_reading",
                "question_text": "駅の近くに新しい図書館が建設される予定だ。（建設）",
                "options": ["けんせつ", "けんせち", "けんぜつ", "げんせつ"],
                "correct_answer": 1,
                "answer_status": "verified",
            },
            {
                "question_number": 2,
                "question_type": "kanji_reading",
                "question_text": "この料理は材料を細かく切ることが大切です。（細かく）",
                "options": ["こまかく", "ほそかく", "さいかく", "しずかく"],
                "correct_answer": 1,
                "answer_status": "verified",
            },
            {
                "question_number": 3,
                "question_type": "kanji_reading",
                "question_text": "週末は家族と一緒に郊外へ出かけた。（郊外）",
                "options": ["こうがい", "こうかい", "ごうがい", "きょうがい"],
                "correct_answer": 1,
                "answer_status": "verified",
            },
        ],
    },
    {
        "exam": {
            "title": "[Seed] N3 Ngữ pháp — Chọn mẫu câu",
            "category": "grammar",
            "status": "ready",
            "description": "Bộ câu tự biên soạn để phát triển và kiểm thử (文法形式の判断).",
        },
        "questions": [
            {
                "question_number": 1,
                "question_type": "grammar_form",
                "question_text": "毎日練習した（　　）、試合に勝つことができた。",
                "options": ["おかげで", "せいで", "くせに", "わりに"],
                "correct_answer": 1,
                "answer_status": "verified",
            },
            {
                "question_number": 2,
                "question_type": "grammar_form",
                "question_text": "彼は知っている（　　）、何も教えてくれなかった。",
                "options": ["からには", "くせに", "ついでに", "とたんに"],
                "correct_answer": 2,
                "answer_status": "verified",
            },
            {
                "question_number": 3,
                "question_type": "grammar_form",
                "question_text": "ドアを開けた（　　）、猫が外へ飛び出した。",
                "options": ["うちに", "ばかりに", "とたん", "最中に"],
                "correct_answer": 3,
                "answer_status": "verified",
            },
            {
                "question_number": 4,
                "question_type": "grammar_form",
                "question_text": "この店のパンは値段の（　　）おいしい。",
                "options": ["わりに", "かわりに", "ように", "たびに"],
                "correct_answer": 1,
                "answer_status": "unverified",
            },
        ],
    },
    {
        "exam": {
            "title": "[Seed] N3 Đọc hiểu — Đoạn văn ngắn",
            "category": "reading",
            "status": "draft",
            "description": "Đoạn văn tự viết, dùng cho kiểm thử luồng passage.",
        },
        "passage": (
            "私の町には小さな公園がある。以前は誰も使っていなかったが、去年、近所の人たちが"
            "花を植えたり、ベンチを直したりした。今では、朝は散歩をするお年寄り、"
            "夕方は子どもたちでにぎやかだ。"
        ),
        "questions": [
            {
                "question_number": 1,
                "question_type": "reading_short",
                "question_text": "公園が変わったのはなぜか。",
                "options": [
                    "市が新しい公園を作ったから",
                    "近所の人たちが手入れをしたから",
                    "子どもたちが花を植えたから",
                    "お年寄りがベンチを買ったから",
                ],
                "correct_answer": 2,
                "answer_status": "verified",
            },
        ],
    },
]
