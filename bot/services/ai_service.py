import logging
import warnings
import time
import google.generativeai as genai
from bot.config import GEMINI_API_KEYS
from bot.services.vector_service import search_chunks, get_all_chunks

logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")

MODEL_PRIORITY = [
    "gemini-1.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-pro",
    "gemini-2.5-flash",
]

_rate_limited: dict[tuple[int, str], float] = {}


def _generate(prompt: str) -> str:
    last_error = None
    now = time.time()
    keys = GEMINI_API_KEYS

    for model_name in MODEL_PRIORITY:
        for key_idx, api_key in enumerate(keys):
            combo = (key_idx, model_name)
            if now < _rate_limited.get(combo, 0):
                continue
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(model_name)
                result = model.generate_content(prompt)
                return result.text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "quota" in err_str.lower() or "rate" in err_str.lower():
                    _rate_limited[combo] = now + 86400
                    logger.warning(f"Key #{key_idx + 1} / {model_name} rate-limited, trying next...")
                    last_error = e
                    continue
                else:
                    raise e

    key_count = len(keys)
    raise RuntimeError(
        f"⚠️ Daily AI limit reached across all {key_count} key(s).\n\n"
        f"You can:\n"
        f"• Add more keys: save GEMINI_API_KEY_2, GEMINI_API_KEY_3 in Replit Secrets "
        f"(each gives +1,500 free requests/day)\n"
        f"• Get a free key at: https://aistudio.google.com/app/apikey\n"
        f"• Limits reset at midnight Pacific Time"
    )


def _focus_instruction(focus: str) -> str:
    if not focus:
        return ""
    return (
        f"\n\n⚠️ IMPORTANT FOCUS INSTRUCTION: The student has chosen to study ONLY the following section: "
        f'"{focus}". '
        f"You MUST focus EXCLUSIVELY on content related to {focus}. "
        f"Ignore all other chapters, sections, or topics outside this scope. "
        f"Every question, summary, note, or concept you generate must come ONLY from {focus}.\n"
    )


def _build_context(user_id: int, query: str = "", max_chars: int = 12000) -> str:
    if query:
        chunks = search_chunks(user_id, query, top_k=10)
    else:
        chunks = get_all_chunks(user_id)
    context = "\n\n---\n\n".join(chunks)
    if len(context) > max_chars:
        context = context[:max_chars] + "\n\n[...content truncated...]"
    return context


def generate_summary(user_id: int, focus: str = "") -> str:
    context = _build_context(user_id, max_chars=14000)
    if not context:
        return "No study materials found. Please upload PDFs first with /upload."
    focus_note = _focus_instruction(focus)
    prompt = f"""You are an expert study assistant. Based ONLY on the following study materials, create a comprehensive but concise summary.
{focus_note}
Structure your summary with:
1. Main Topics Covered
2. Key Concepts (bullet points)
3. Important Definitions
4. Core Formulas or Rules (if any)
5. Quick Revision Points

Study Materials:
{context}

Write clearly for a student preparing for exams. Be accurate and stick only to the provided content."""
    try:
        return _generate(prompt)
    except Exception as e:
        logger.error(f"AI summary error: {e}")
        return str(e)


def generate_questions(user_id: int, count: int = 100, focus: str = "") -> list[dict]:
    context = _build_context(user_id, max_chars=14000)
    if not context:
        return []
    focus_note = _focus_instruction(focus)
    prompt = f"""You are an expert exam paper setter. Based ONLY on the following study materials, generate exactly {count} practice questions.
{focus_note}
Rules:
- Mix question types: MCQ (with 4 options), Short Answer, Long Answer, True/False
- Cover ALL major topics in scope
- Focus on frequently tested concepts
- Mark difficulty: [Easy], [Medium], [Hard]
- For MCQs, provide the correct answer
- Number each question

Study Materials:
{context}

Format each question like:
Q1. [Easy] Question text here?
(For MCQ) A) option  B) option  C) option  D) option  Answer: X
(For others) Expected Answer: brief answer

Generate all {count} questions now."""
    try:
        return parse_questions(_generate(prompt))
    except Exception as e:
        logger.error(f"AI questions error: {e}")
        return []


def parse_questions(text: str) -> list[dict]:
    import re
    questions = []
    blocks = re.split(r'\n(?=Q\d+\.)', text.strip())
    for block in blocks:
        if block.strip():
            questions.append({"text": block.strip(), "raw": True})
    return questions


def generate_mock_exam(user_id: int, exam_type: str = "mid", focus: str = "") -> str:
    context = _build_context(user_id, max_chars=14000)
    if not context:
        return "No study materials found. Upload PDFs first."
    focus_note = _focus_instruction(focus)
    if exam_type == "mid":
        structure = "Section B (3 short questions, 5 marks each), Section C (1 long question, 10 marks)"
        total = "25 marks written section, 1.5 hours"
    else:
        structure = "Section B (4 short questions, 5 marks each), Section C (2 medium questions, 10 marks each), Section D (1 essay, 20 marks)"
        total = "60 marks written section, 3 hours"
    prompt = f"""You are setting a {exam_type.upper()} EXAM written section. Based ONLY on the study materials below, create the written exam questions.
{focus_note}
Structure: {structure}
Total: {total}

Rules:
- Questions must come ONLY from the provided materials
- Include clear marking scheme for each question
- Write like a real university exam paper
- Add exam header with: Subject, Time Allowed, Total Marks, Instructions
- Do NOT include MCQ questions — those are handled separately

Study Materials:
{context}

Generate the written exam questions now:"""
    try:
        return _generate(prompt)
    except Exception as e:
        logger.error(f"Mock exam error: {e}")
        return str(e)


def generate_short_notes(user_id: int, focus: str = "") -> str:
    context = _build_context(user_id, max_chars=14000)
    if not context:
        return "No study materials found. Upload PDFs first."
    focus_note = _focus_instruction(focus)
    prompt = f"""You are a student who creates the perfect short notes. Based ONLY on these study materials, create concise short notes perfect for last-minute revision.
{focus_note}
Format:
- Use bullet points
- Bold key terms (use **term**)
- Group by topic
- Include formulas/rules
- Max 2-3 lines per concept
- Use simple language

Study Materials:
{context}

Create the short notes now — clear, scannable, exam-ready:"""
    try:
        return _generate(prompt)
    except Exception as e:
        logger.error(f"Short notes error: {e}")
        return str(e)


def generate_quiz_questions(user_id: int, count: int = 10, focus: str = "") -> list[dict]:
    context = _build_context(user_id, max_chars=10000)
    if not context:
        return []
    focus_note = _focus_instruction(focus)
    prompt = f"""Generate exactly {count} quiz questions (MCQ format only) from this study material.
{focus_note}
Rules:
- 4 options each (A, B, C, D)
- Only ONE correct answer
- Mix easy, medium, hard
- Based ONLY on provided material
- Do NOT include the answer in the question text

Study Materials:
{context}

Output in this EXACT format for each question:
QUESTION: [question text]
A: [option]
B: [option]
C: [option]
D: [option]
ANSWER: [A/B/C/D]
EXPLANATION: [one sentence explanation]
---"""
    try:
        return parse_quiz_questions(_generate(prompt))
    except Exception as e:
        logger.error(f"Quiz error: {e}")
        return []


def parse_quiz_questions(text: str) -> list[dict]:
    import re
    questions = []
    blocks = re.split(r'\n---\n', text.strip())
    for block in blocks:
        if "QUESTION:" not in block:
            continue
        try:
            q = {}
            q["question"] = re.search(r'QUESTION:\s*(.+)', block).group(1).strip()
            q["a"] = re.search(r'A:\s*(.+)', block).group(1).strip()
            q["b"] = re.search(r'B:\s*(.+)', block).group(1).strip()
            q["c"] = re.search(r'C:\s*(.+)', block).group(1).strip()
            q["d"] = re.search(r'D:\s*(.+)', block).group(1).strip()
            q["answer"] = re.search(r'ANSWER:\s*([ABCD])', block).group(1).strip()
            exp = re.search(r'EXPLANATION:\s*(.+)', block)
            q["explanation"] = exp.group(1).strip() if exp else ""
            questions.append(q)
        except Exception:
            continue
    return questions


def generate_flashcards(user_id: int, count: int = 20, focus: str = "") -> list[dict]:
    context = _build_context(user_id, max_chars=12000)
    if not context:
        return []
    focus_note = _focus_instruction(focus)
    prompt = f"""Create {count} flashcards from this study material. Each flashcard has a FRONT (question/term) and BACK (answer/definition).
{focus_note}
Focus on: key terms, definitions, important concepts, formulas, dates, and facts.
Based ONLY on the provided material.

Output in this EXACT format:
FRONT: [term or question]
BACK: [definition or answer]
---

Study Materials:
{context}

Generate {count} flashcards now:"""
    try:
        return parse_flashcards(_generate(prompt))
    except Exception as e:
        logger.error(f"Flashcard error: {e}")
        return []


def parse_flashcards(text: str) -> list[dict]:
    import re
    cards = []
    blocks = re.split(r'\n---\n', text.strip())
    for block in blocks:
        if "FRONT:" not in block or "BACK:" not in block:
            continue
        try:
            front = re.search(r'FRONT:\s*(.+)', block).group(1).strip()
            back = re.search(r'BACK:\s*(.+)', block).group(1).strip()
            cards.append({"front": front, "back": back})
        except Exception:
            continue
    return cards


def generate_important_concepts(user_id: int, focus: str = "") -> str:
    context = _build_context(user_id, max_chars=14000)
    if not context:
        return "No study materials found. Upload PDFs first."
    focus_note = _focus_instruction(focus)
    prompt = f"""You are an expert exam coach. Analyze these study materials and identify the most important, exam-worthy concepts.
{focus_note}
Provide:
1. TOP 10 MOST IMPORTANT CONCEPTS (with brief explanation each)
2. REPEATED THEMES (concepts that appear multiple times — likely exam topics)
3. HIGH-VALUE FORMULAS/RULES
4. CONCEPTS STUDENTS OFTEN MISS
5. MUST-KNOW vs NICE-TO-KNOW

Base your analysis ONLY on the provided materials.

Study Materials:
{context}"""
    try:
        return _generate(prompt)
    except Exception as e:
        logger.error(f"Important concepts error: {e}")
        return str(e)


def predict_exam_questions(user_id: int, focus: str = "") -> str:
    context = _build_context(user_id, max_chars=14000)
    if not context:
        return "No study materials found. Upload PDFs first."
    focus_note = _focus_instruction(focus)
    prompt = f"""You are an experienced professor who knows what comes in exams. Based on these study materials, predict the most likely exam questions.
{focus_note}
Provide:
1. TOP 5 VERY LIKELY QUESTIONS (almost certain to appear)
2. NEXT 10 PROBABLE QUESTIONS (good chance of appearing)
3. KEY TOPICS TO FOCUS ON (based on frequency in materials)
4. TOPICS TO AVOID WASTING TIME ON (unlikely to appear)
5. LAST-NIGHT STUDY PRIORITY ORDER

Be specific — name actual concepts, not vague topics.

Study Materials:
{context}"""
    try:
        return _generate(prompt)
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        return str(e)


def generate_one_night_summary(user_id: int, focus: str = "") -> str:
    context = _build_context(user_id, max_chars=14000)
    if not context:
        return "No study materials found. Upload PDFs first."
    focus_note = _focus_instruction(focus)
    prompt = f"""It's the night before the exam. A student needs to cram everything essential in 2-3 hours. Create the PERFECT one-night-before summary.
{focus_note}
Rules:
- Only the most important stuff
- Super concise — every word counts
- Organized by priority (most important first)
- Include memory tricks where helpful
- End with a "Last 15 Minutes Checklist"

Study Materials:
{context}

Create the emergency study guide:"""
    try:
        return _generate(prompt)
    except Exception as e:
        logger.error(f"One-night summary error: {e}")
        return str(e)


def explain_concept(user_id: int, concept: str) -> str:
    context = _build_context(user_id, query=concept, max_chars=8000)
    prompt = f"""Explain this concept in simple, beginner-friendly language: "{concept}"

{"Use the following study materials as your primary source:" if context else ""}
{context if context else ""}

Explanation format:
1. Simple Definition (1-2 sentences)
2. What it means in plain language
3. Real-world example or analogy
4. Why it matters / where it's used
5. Common mistakes students make about this

Keep it clear and simple."""
    try:
        return _generate(prompt)
    except Exception as e:
        logger.error(f"Explain error: {e}")
        return str(e)


def analyze_exam_style(user_id: int, focus: str = "") -> str:
    context = _build_context(user_id, max_chars=14000)
    if not context:
        return "No study materials found. Upload PDFs first."
    focus_note = _focus_instruction(focus)
    prompt = f"""You are analyzing a student's uploaded materials which include previous university exam papers and study notes.
{focus_note}
TASK: Study the EXACT style, format, and pattern of questions from the previous exams in these materials, then generate NEW questions in the EXACT same style.

Step 1 — Analyze the exam style:
- What question formats are used? (MCQ / essay / fill-in-the-blank / problem-solving)
- What is the typical difficulty level?
- What topics come up most?
- How are questions worded?
- How many marks per question?

Step 2 — Generate 30 NEW questions:
- Match the EXACT style of the previous exams
- Cover the same topics
- Use the same question formats
- Same difficulty level
- Include mark allocations if the original exams had them

Study Materials (includes previous exams + notes):
{context}

Output format:
## Exam Style Analysis
[Your analysis of the exam patterns]

## 30 New Exam-Style Questions
[Questions that exactly match the university's style]"""
    try:
        return _generate(prompt)
    except Exception as e:
        logger.error(f"Exam style error: {e}")
        return str(e)
