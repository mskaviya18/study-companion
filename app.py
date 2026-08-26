"""
app.py

Streamlit UI for the AI Study Companion. Ties together all four backend
modules into one flow: upload reference material -> enter a topic ->
read grounded notes -> take an adaptive quiz -> see graded feedback ->
track mastery over time.

Includes a top-right menu with Google Sign-In and knowledge-base
management (view/remove indexed files, reset progress).

Run with:
    streamlit run app.py
"""

import os
import streamlit as st
from dotenv import load_dotenv

from rag_utils import (
    add_document_to_store, extract_text_from_pdf, extract_text_from_docx,
    extract_text_from_image, list_sources, delete_source,
)
from content_generator import generate_grounded_content, generate_general_content, NoReferenceMaterialError
from quiz_generator import generate_quiz
from evaluator import evaluate_quiz
from progress_tracker import (
    init_db,
    get_topic_mastery,
    get_recommended_difficulty,
    get_all_topics_summary,
    record_quiz_results,
    reset_progress,
    get_mastery_timeline,
)
import pandas as pd
import altair as alt

st.set_page_config(page_title="AI Study Companion", page_icon="📖", layout="centered")
load_dotenv()

if not os.environ.get("GROQ_API_KEY"):
    try:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
    except Exception:
        pass

if not os.environ.get("GROQ_API_KEY"):
    st.error(
        "GROQ_API_KEY is not set. Copy `.env.example` to `.env`, add your key, "
        "and restart the app."
    )
    st.stop()

# ---- Session state defaults ----
for key, default in [
    ("stage", "input"),
    ("topic", ""),
    ("notes", ""),
    ("sources", []),
    ("quiz", None),
    ("difficulty", "medium"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---- Theme (fixed: deep purple / electric blue) ----
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');

:root {
    --ink: #150A30; --panel: #201245; --paper: #E9E4FB;
    --accent: #4CC9F0; --accent-light: #7DE0FF; --violet: #7B2FF7;
    --mint: #4CE0B3; --magenta: #FF4D9D;
    --hair: rgba(233,228,251,0.14);
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #150A30 0%, #24124F 35%, #0D1B3E 70%, #1B0E3D 100%);
    background-size: 300% 300%;
}
@media (prefers-reduced-motion: no-preference) {
    .stApp { animation: auroraShift 22s ease infinite; }
    @keyframes auroraShift {
        0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; }
    }
}
.stApp::before {
    content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
    background:
        radial-gradient(circle at 15% 20%, rgba(76,201,240,0.16), transparent 40%),
        radial-gradient(circle at 85% 75%, rgba(123,47,247,0.20), transparent 45%),
        radial-gradient(circle at 50% 100%, rgba(255,77,157,0.08), transparent 50%);
}
@media (prefers-reduced-motion: no-preference) {
    .stApp::before { animation: driftGlow 26s ease-in-out infinite alternate; }
    @keyframes driftGlow { from { transform: translate(0,0) scale(1); } to { transform: translate(-2%,2%) scale(1.05); } }
}

h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; letter-spacing: 0.01em; }
h1 { color: var(--accent-light) !important; font-weight: 700 !important; }
h2, h3 { color: var(--paper) !important; font-weight: 600 !important; }

.app-banner { border-bottom: 1px solid var(--hair); padding-bottom: 0.85rem; margin-bottom: 1rem; }
.app-banner .eyebrow {
    font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; letter-spacing: 0.18em;
    text-transform: uppercase; color: var(--mint); margin-bottom: 0.15rem;
}
.app-banner h1 {
    margin: 0 !important; font-size: 2.1rem !important;
    background: linear-gradient(90deg, var(--accent-light), var(--violet));
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
}
.app-banner .tagline { font-family: 'Inter', sans-serif; font-style: italic; color: rgba(233,228,251,0.65); font-size: 0.95rem; margin-top: 0.2rem; }

.stButton > button {
    font-family: 'Inter', sans-serif; font-weight: 600; border-radius: 4px;
    border: 1px solid var(--accent); background: transparent; color: var(--accent-light);
    transition: all 0.15s ease;
}
.stButton > button:hover { background: var(--accent); color: var(--ink); border-color: var(--accent); box-shadow: 0 0 12px rgba(76,201,240,0.5); }
.stButton > button[kind="primary"] { background: linear-gradient(90deg, var(--accent), var(--violet)); color: #0B0620; border: none; }
.stButton > button[kind="primary"]:hover { box-shadow: 0 0 16px rgba(123,47,247,0.6); }

[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--hair); border-left: 4px solid var(--accent); border-radius: 4px; padding: 0.9rem 1.1rem; }
[data-testid="stMetricValue"] { font-family: 'IBM Plex Mono', monospace !important; color: var(--accent-light) !important; }
[data-testid="stMetricLabel"] { font-family: 'IBM Plex Mono', monospace !important; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.72rem !important; }

[data-testid="stAlert"] { border-radius: 4px; font-family: 'Inter', sans-serif; }

section[data-testid="stSidebar"] { border-right: 1px solid var(--hair); background: rgba(21,10,48,0.55); }
section[data-testid="stSidebar"] h2 { font-size: 1.05rem !important; }

.stRadio label, .stTextInput label, .stTextArea label { font-family: 'Inter', sans-serif; font-weight: 500; }

hr { border-color: var(--hair) !important; }
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

.section-header { display: flex; align-items: center; gap: 0.5rem; margin: 1.1rem 0 0.6rem 0; position: relative; z-index: 1; }
.section-header svg { flex-shrink: 0; }
.section-header span { font-family: 'Space Grotesk', sans-serif; font-weight: 600; font-size: 1.25rem; color: var(--paper); }

[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--hair) !important; background: rgba(32,18,69,0.45); border-radius: 8px !important; backdrop-filter: blur(6px); }

.stTextInput input:focus, .stTextArea textarea:focus { border-color: var(--accent) !important; box-shadow: 0 0 0 1px var(--accent), 0 0 10px rgba(76,201,240,0.35) !important; }

div[role="radiogroup"] { gap: 0.4rem; }
div[role="radiogroup"] label { border: 1px solid var(--hair); border-radius: 20px; padding: 0.3rem 0.9rem 0.3rem 0.5rem; transition: border-color 0.15s ease, background 0.15s ease; }
div[role="radiogroup"] label:hover { border-color: var(--accent); }

section[data-testid="stSidebar"] div[style*="border-left"] { transition: transform 0.15s ease, border-color 0.15s ease; }
section[data-testid="stSidebar"] div[style*="border-left"]:hover { transform: translateX(2px); }

.stSpinner > div { font-family: 'Inter', sans-serif; }

/* Push the menu button hard to the top-right of the content column */
div[data-testid="column"]:has(button[aria-haspopup="dialog"]) { display: flex; justify-content: flex-end; }
</style>
""", unsafe_allow_html=True)

ICONS = {
    "book": '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4CC9F0" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5V5a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v14"/><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H19"/><path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H19v-5"/></svg>',
    "quiz": '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4CC9F0" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
    "chart": '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4CC9F0" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/></svg>',
}


def section_header(icon_key, title):
    st.markdown(f'<div class="section-header">{ICONS[icon_key]}<span>{title}</span></div>', unsafe_allow_html=True)


init_db()

if not list_sources():
    import glob
    for path in glob.glob("data/*.txt") + glob.glob("data/*.pdf"):
        try:
            if path.endswith(".pdf"):
                with open(path, "rb") as f:
                    text = extract_text_from_pdf(f)
            else:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            if text.strip():
                add_document_to_store(os.path.basename(path), text)
        except Exception:
            pass

# ---- Banner + top-right menu ----
banner_col, menu_col = st.columns([7, 1])
with banner_col:
    st.markdown("""
    <div class="app-banner">
        <div class="eyebrow">Syllabus → Notes → Quiz</div>
        <h1>The Study Companion</h1>
        <div class="tagline">Grounded notes, adaptive quizzes, and a record of what you actually know.</div>
    </div>
    """, unsafe_allow_html=True)

with menu_col:
    with st.popover("☰"):
        st.markdown("**Knowledge base**")
        indexed_now = list_sources()
        if not indexed_now:
            st.caption("No files indexed yet")
        else:
            for src in indexed_now:
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.caption(src)
                with c2:
                    if st.button("✕", key=f"remove_{src}", help=f"Remove {src}"):
                        delete_source(src)
                        st.rerun()

        st.divider()
        if st.button("Reset all progress data", use_container_width=True):
            reset_progress()
            st.rerun()

# ---- Sidebar: upload + progress dashboard ----
with st.sidebar:
    section_header("book", "Reference material")
    uploaded_files = st.file_uploader(
        "Add syllabus material (.txt, .pdf, .docx, or a scanned image)",
        type=["txt", "pdf", "docx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )
    if uploaded_files and st.button("Add to knowledge base"):
        for f in uploaded_files:
            try:
                name_lower = f.name.lower()
                if name_lower.endswith(".pdf"):
                    text = extract_text_from_pdf(f)
                elif name_lower.endswith(".docx"):
                    text = extract_text_from_docx(f)
                elif name_lower.endswith((".png", ".jpg", ".jpeg")):
                    with st.spinner(f"Running OCR on {f.name}..."):
                        text = extract_text_from_image(f)
                else:
                    text = f.read().decode("utf-8", errors="ignore")

                if not text.strip():
                    st.warning(f"{f.name}: no extractable text found, skipped.")
                    continue

                with st.spinner(f"Indexing {f.name}..."):
                    n_chunks = add_document_to_store(f.name, text)
                st.success(f"{f.name}: {n_chunks} chunks added.")
            except RuntimeError as e:
                st.error(f"{f.name}: {e}")
            except Exception as e:
                st.error(f"{f.name}: failed to index ({e})")

    indexed = list_sources()

    st.divider()
    section_header("chart", "Your progress")
    summary = get_all_topics_summary()
    timeline = get_mastery_timeline()
    if not summary:
        st.caption("No attempts yet. Take a quiz to see your progress here.")
    else:
        for t in summary:
            topic_history = sorted(
                [row for row in timeline if row["topic"] == t["topic"]],
                key=lambda r: r["timestamp"],
            )
            latest_score = topic_history[-1]["score"] if topic_history else t["mastery"]
            prev_score = topic_history[-2]["score"] if len(topic_history) > 1 else None
            delta = round(latest_score - prev_score, 1) if prev_score is not None else None

            up = delta is not None and delta > 0
            down = delta is not None and delta < 0
            delta_color = T["mint"] if up else (T["magenta"] if down else "rgba(233,228,251,0.5)")
            arrow = "▲" if up else ("▼" if down else "—")
            delta_text = f"{arrow} {abs(delta):.1f}" if delta is not None else "first attempt"
            line_color = T["mint"] if latest_score >= 60 else T["magenta"]

            st.markdown(f"""
            <div style="background:rgba(32,18,69,0.6); border:1px solid {T['hair']};
                        border-radius:6px; padding:0.6rem 0.8rem; margin-bottom:0.6rem;">
                <div style="display:flex; justify-content:space-between; align-items:baseline;">
                    <span style="font-family:'Space Grotesk',sans-serif; font-weight:600; color:#E9E4FB; font-size:0.9rem;">
                        {t['topic']}
                    </span>
                    <span style="font-family:'IBM Plex Mono',monospace; font-size:0.95rem; color:{line_color}; font-weight:600;">
                        {latest_score:.0f}
                    </span>
                </div>
                <div style="font-family:'IBM Plex Mono',monospace; font-size:0.68rem; color:{delta_color}; margin-top:0.1rem;">
                    {delta_text} · {t['attempts']} attempt{'s' if t['attempts'] != 1 else ''}
                </div>
            </div>
            """, unsafe_allow_html=True)

            if len(topic_history) >= 2:
                df = pd.DataFrame(topic_history)
                df["idx"] = range(len(df))
                spark = (
                    alt.Chart(df)
                    .mark_area(line={"color": line_color, "size": 1.5}, opacity=0.15, color=line_color)
                    .encode(
                        x=alt.X("idx:O", axis=None),
                        y=alt.Y("score:Q", axis=None, scale=alt.Scale(domain=[0, 100])),
                        tooltip=[
                            alt.Tooltip("timestamp:T", title="Date", format="%b %d, %H:%M"),
                            alt.Tooltip("score:Q", title="Score"),
                        ],
                    )
                    .properties(height=44)
                    .configure_view(strokeWidth=0)
                )
                st.altair_chart(spark, use_container_width=True)



# ---- Stage 1: topic input ----
if st.session_state.stage == "input":
    mode = st.radio(
        "How should notes be generated?",
        ["From my uploaded material (grounded)", "From AI's general knowledge (no upload needed)"],
        index=0 if indexed else 1,
    )
    grounded_mode = mode.startswith("From my uploaded")

    if grounded_mode and not indexed:
        st.warning("No material uploaded yet. Upload a file in the sidebar, or switch to general-knowledge mode above.")

    topic = st.text_input("Enter a syllabus topic", placeholder="e.g. Binary Search Trees")
    generate_disabled = grounded_mode and not indexed
    if st.button("Generate study notes", type="primary", disabled=generate_disabled) and topic:
        st.session_state.topic = topic
        st.session_state.difficulty = get_recommended_difficulty(topic)
        try:
            with st.spinner("Generating notes..."):
                if grounded_mode:
                    notes, sources = generate_grounded_content(topic)
                else:
                    notes, sources = generate_general_content(topic)
            st.session_state.notes = notes
            st.session_state.sources = sources
            st.session_state.stage = "notes"
            st.rerun()
        except NoReferenceMaterialError:
            st.error(
                "No indexed material matched this topic closely enough. "
                "Try a topic that's covered in your uploaded files, upload more material, "
                "or switch to general-knowledge mode above."
            )
        except (ValueError, RuntimeError) as e:
            st.error(f"Could not generate notes: {e}")

# ---- Stage 2: show notes, offer quiz ----
elif st.session_state.stage == "notes":
    section_header("book", f"Notes: {st.session_state.topic}")
    with st.container(border=True):
        st.markdown(st.session_state.notes)
        if st.session_state.sources:
            st.caption(f"Grounded in: {', '.join(st.session_state.sources)}")

    mastery = get_topic_mastery(st.session_state.topic)
    mastery_text = f"{mastery}/100" if mastery is not None else "no attempts yet"
    st.info(f"Current mastery: {mastery_text} — next quiz difficulty: **{st.session_state.difficulty}**")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Take the quiz", type="primary"):
            try:
                with st.spinner("Generating quiz from these notes..."):
                    st.session_state.quiz = generate_quiz(
                        st.session_state.topic, st.session_state.notes,
                        difficulty=st.session_state.difficulty,
                    )
                st.session_state.stage = "quiz"
                st.rerun()
            except RuntimeError as e:
                st.error(f"Could not generate the quiz: {e}. Try clicking again.")
    with col2:
        if st.button("Choose a different topic"):
            st.session_state.stage = "input"
            st.rerun()

# ---- Stage 3: take the quiz ----
elif st.session_state.stage == "quiz":
    quiz = st.session_state.quiz
    section_header("quiz", f"Quiz: {st.session_state.topic}")

    mcq_answers = []
    with st.container(border=True):
        with st.form("quiz_form"):
            st.markdown("**Multiple choice**")
            for i, q in enumerate(quiz["mcq"]):
                choice = st.radio(q["question"], q["options"], key=f"mcq_{i}", index=None)
                mcq_answers.append(choice)

            st.markdown("**Short answer**")
            short_answers = []
            for i, q in enumerate(quiz["short_answer"]):
                answer = st.text_area(q["question"], key=f"short_{i}")
                short_answers.append(answer)

            submitted = st.form_submit_button("Submit quiz", type="primary")

    if submitted:
        if any(a is None for a in mcq_answers) or any(not a.strip() for a in short_answers):
            st.error("Please answer every question before submitting.")
        else:
            try:
                mcq_indices = [q["options"].index(a) for q, a in zip(quiz["mcq"], mcq_answers)]
                with st.spinner("Grading your answers..."):
                    results = evaluate_quiz(quiz, mcq_indices, short_answers)
                record_quiz_results(st.session_state.topic, results, st.session_state.difficulty)
                st.session_state.results = results
                st.session_state.stage = "results"
                st.rerun()
            except Exception as e:
                st.error(f"Grading failed: {e}. Please try submitting again.")

# ---- Stage 4: results ----
elif st.session_state.stage == "results":
    results = st.session_state.results
    section_header("chart", f"Results: {st.session_state.topic}")
    with st.container(border=True):
        st.metric("Overall score", f"{results['overall_score']}/100")

        st.markdown("**Multiple choice**")
        for r in results["mcq"]:
            if r["correct"]:
                st.success(r["question"])
            else:
                st.error(f"{r['question']}\n\nCorrect answer: {r['correct_option']}\n\n{r['explanation']}")

        st.markdown("**Short answer**")
        for r in results["short_answer"]:
            st.write(f"**{r['question']}**")
            st.write(f"Score: {r['score']}/100 — {r['feedback']}")
            if r["missing_points"]:
                st.caption(f"You missed: {', '.join(r['missing_points'])}")

        new_mastery = get_topic_mastery(st.session_state.topic)
        st.info(f"Updated mastery for this topic: {new_mastery}/100")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Take another quiz on this topic", type="primary"):
            st.session_state.difficulty = get_recommended_difficulty(st.session_state.topic)
            try:
                with st.spinner("Generating a new quiz..."):
                    st.session_state.quiz = generate_quiz(
                        st.session_state.topic, st.session_state.notes,
                        difficulty=st.session_state.difficulty,
                    )
                st.session_state.stage = "quiz"
                st.rerun()
            except RuntimeError as e:
                st.error(f"Could not generate the quiz: {e}. Try clicking again.")
    with col2:
        if st.button("Study another topic"):
            st.session_state.stage = "input"
            st.session_state.quiz = None
            st.rerun()