import uuid
import pandas as pd
import streamlit as st

# MUST BE THE FIRST STREAMLIT COMMAND
st.set_page_config(page_title="AI Study Companion", layout="centered")

# Custom CSS styling
st.markdown(
    """
    <style>
    /* Force light text in dark sidebar */
    [data-testid="stSidebar"] * {
        color: #f5efe6 !important;
    }

    /* Fix Textarea (Short Answer Boxes) & Text Inputs */
    [data-testid="stTextArea"] textarea,
    [data-testid="stTextInput"] input,
    div[data-baseweb="textarea"],
    div[data-baseweb="input"] {
        background-color: #fdfbf7 !important;
        color: #2c1d1a !important;
        -webkit-text-fill-color: #2c1d1a !important;
        border: 1px solid #d1c7bd !important;
        border-radius: 8px !important;
    }

    /* Placeholder text style */
    [data-testid="stTextArea"] textarea::placeholder,
    [data-testid="stTextInput"] input::placeholder {
        color: #8c827a !important;
        -webkit-text-fill-color: #8c827a !important;
    }

    /* Radio button options text visibility */
    [data-testid="stRadio"] label p {
        color: #2c1d1a !important;
    }

    /* File Uploader Dropzone styling */
    [data-testid="stFileUploaderDropzone"],
    [data-testid="stFileUploader"] section {
        background-color: #fdfbf7 !important;
        border: 1.5px dashed #c8b9a6 !important;
        border-radius: 8px !important;
    }

    [data-testid="stFileUploaderDropzone"] * {
        color: #2c1d1a !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

from content_generator import generate_content, generate_content_from_text
from quiz_generator import generate_quiz
from evaluator import evaluate_quiz
from rag_utils import extract_text_from_pdf
from progress_tracker import (
    init_db,
    get_topic_mastery,
    get_recommended_difficulty,
    get_all_topics_summary,
    get_topic_attempt_history,
    record_quiz_results,
)

init_db()

for key, default in [
    ("stage", "input"),
    ("topic", ""),
    ("notes", ""),
    ("sources", []),
    ("quiz", None),
    ("quiz_id", ""),
    ("difficulty", "medium"),
    ("results", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

st.title("AI Study Companion")

# --- SIDEBAR (Shows progress only for the currently active topic) ---
with st.sidebar:
    st.header("Your progress")
    
    active_topic = st.session_state.get("topic", "").strip()
    
    if not active_topic:
        st.write("No active topic selected. Generate study notes or take a quiz to track progress.")
    else:
        history = get_topic_attempt_history(active_topic)
        
        if not history:
            st.write(f"No quiz attempts yet for **{active_topic}**.")
        else:
            current_mastery = get_topic_mastery(active_topic)
            attempts_count = len(history)
            label = f"{active_topic} — {current_mastery}/100 ({attempts_count} attempts)"
            
            if current_mastery < 60:
                st.warning(label)
            else:
                st.success(label)

            st.divider()
            st.subheader(f"Progress on {active_topic}")
            
            # Prepare data for horizontal bar chart
            chart_df = pd.DataFrame(
                {
                    "Score": [entry["score"] for entry in history],
                },
                index=[f"Attempt {i + 1}" for i in range(len(history))],
            )
            
            # Render horizontal bars in sidebar
            st.bar_chart(chart_df, horizontal=True)

            # Progress metric at the bottom left
            st.metric(
                label="Current Mastery Score",
                value=f"{current_mastery} / 100",
            )

# --- MAIN VIEWPORT STAGES ---
if st.session_state.stage == "input":
    mode = st.radio(
        "How do you want to generate notes?",
        ["AI-generated (enter a topic)", "Upload a document"],
        key="input_mode",
        horizontal=True,
    )

    if mode == "AI-generated (enter a topic)":
        topic = st.text_input(
            "Enter a syllabus topic",
            placeholder="e.g. Binary Search Trees",
        )

        if st.button("Generate study notes", type="primary"):
            topic = topic.strip()

            if not topic:
                st.warning("Please enter a syllabus topic.")
            else:
                st.session_state.topic = topic
                st.session_state.difficulty = get_recommended_difficulty(topic)

                with st.spinner("Retrieving reference material and generating notes..."):
                    try:
                        notes, sources = generate_content(topic)
                    except Exception as exc:
                        st.error(f"Could not generate notes: {exc}")
                    else:
                        st.session_state.notes = notes
                        st.session_state.sources = sources
                        st.session_state.stage = "notes"
                        st.rerun()

    else:
        uploaded_file = st.file_uploader(
            "Upload reference material",
            type=["txt", "pdf", "docx", "png", "jpg", "jpeg"],
        )
        topic_label = st.text_input(
            "Label this material (used to track your progress)",
            placeholder="e.g. Binary Search Trees",
        )

        if st.button("Generate study notes", type="primary", key="upload_generate"):
            topic_label = topic_label.strip()

            if uploaded_file is None:
                st.warning("Please upload a supported file (.txt, .pdf, .docx, or image).")
            elif not topic_label:
                st.warning("Please enter a label for this material.")
            else:
                st.session_state.topic = topic_label
                st.session_state.difficulty = get_recommended_difficulty(topic_label)

                with st.spinner("Reading document and generating notes..."):
                    try:
                        file_ext = uploaded_file.name.lower()
                        if file_ext.endswith(".pdf"):
                            raw_text = extract_text_from_pdf(uploaded_file)
                        elif file_ext.endswith((".png", ".jpg", ".jpeg")):
                            from rag_utils import extract_text_from_image
                            raw_text = extract_text_from_image(uploaded_file)
                        elif file_ext.endswith(".docx"):
                            from rag_utils import extract_text_from_docx
                            raw_text = extract_text_from_docx(uploaded_file)
                        else:
                            raw_text = uploaded_file.read().decode("utf-8", errors="ignore")

                        notes, sources = generate_content_from_text(
                            topic_label,
                            raw_text,
                            source_name=uploaded_file.name,
                        )
                    except Exception as exc:
                        st.error(f"Could not generate notes: {exc}")
                    else:
                        st.session_state.notes = notes
                        st.session_state.sources = sources
                        st.session_state.stage = "notes"
                        st.rerun()

elif st.session_state.stage == "notes":
    st.subheader(f"Notes: {st.session_state.topic}")
    st.markdown(st.session_state.notes)

    if st.session_state.sources:
        st.caption(f"Grounded in: {', '.join(st.session_state.sources)}")

    mastery = get_topic_mastery(st.session_state.topic)
    mastery_text = f"{mastery}/100" if mastery is not None else "no attempts yet"
    st.info(
        f"Current mastery: {mastery_text} — "
        f"next quiz difficulty: **{st.session_state.difficulty}**"
    )

    if st.button("Take the quiz", type="primary"):
        with st.spinner("Generating quiz from these notes..."):
            try:
                st.session_state.quiz = generate_quiz(
                    st.session_state.topic,
                    st.session_state.notes,
                    difficulty=st.session_state.difficulty,
                )
            except Exception as exc:
                st.error(f"Could not generate quiz: {exc}")
            else:
                st.session_state.quiz_id = str(uuid.uuid4())
                st.session_state.stage = "quiz"
                st.rerun()

    if st.button("Choose a different topic"):
        st.session_state.stage = "input"
        st.session_state.topic = ""
        st.session_state.notes = ""
        st.session_state.sources = []
        st.session_state.quiz = None
        st.session_state.quiz_id = ""
        st.session_state.results = None
        st.rerun()

elif st.session_state.stage == "quiz":
    quiz = st.session_state.quiz

    if not quiz:
        st.error("No quiz is available. Please generate a new quiz.")
        if st.button("Back to topic"):
            st.session_state.stage = "input"
            st.rerun()
        st.stop()

    st.subheader(f"Quiz: {st.session_state.topic}")

    mcq_answers = []

    with st.form("quiz_form"):
        st.markdown("**Multiple choice**")

        for i, question in enumerate(quiz.get("mcq", [])):
            choice = st.radio(
                question["question"],
                question["options"],
                key=f"mcq_{st.session_state.quiz_id}_{i}",
                index=None,
            )
            mcq_answers.append(choice)

        st.markdown("**Short answer**")
        short_answers = []

        for i, question in enumerate(quiz.get("short_answer", [])):
            answer = st.text_area(
                question["question"],
                key=f"short_{st.session_state.quiz_id}_{i}",
            )
            short_answers.append(answer)

        submitted = st.form_submit_button("Submit quiz", type="primary")

    if submitted:
        if any(answer is None for answer in mcq_answers):
            st.error("Please answer every multiple-choice question.")
        elif any(not answer.strip() for answer in short_answers):
            st.error("Please answer every short-answer question.")
        else:
            mcq_indices = [
                question["options"].index(answer)
                for question, answer in zip(quiz.get("mcq", []), mcq_answers)
            ]

            with st.spinner("Grading your answers..."):
                try:
                    results = evaluate_quiz(
                        quiz,
                        mcq_indices,
                        short_answers,
                    )
                    record_quiz_results(
                        st.session_state.topic,
                        results,
                        st.session_state.difficulty,
                    )
                except Exception as exc:
                    st.error(f"Could not grade the quiz: {exc}")
                else:
                    st.session_state.results = results
                    st.session_state.stage = "results"
                    st.rerun()

elif st.session_state.stage == "results":
    results = st.session_state.results

    if not results:
        st.error("No results are available.")
        st.session_state.stage = "input"
        st.rerun()

    st.subheader(f"Results: {st.session_state.topic}")
    st.metric("Overall score", f"{results['overall_score']}/100")

    st.markdown("### Multiple choice")
    for result in results["mcq"]:
        if result["correct"]:
            st.success(f"**Question:** {result['question']}")
        else:
            st.error(
                f"**Question:** {result['question']}\n\n"
                f"**Correct answer:** {result['correct_option']}\n\n"
                f"**Explanation:** {result['explanation']}"
            )

    st.markdown("---")
    st.markdown("### Short answer")
    for i, result in enumerate(results["short_answer"], 1):
        st.markdown(f"**Q{i}: {result['question']}**")

        model_ans = result.get("ideal_answer") or result.get("correct_answer")
        if model_ans:
            st.success(f"**Correct Answer:** {model_ans}")
        elif result.get("missing_points"):
            st.warning(f"**Missed Points:** {', '.join(result['missing_points'])}")

        st.caption(f"**Score:** {result['score']}/100")
        st.markdown("---")

    new_mastery = get_topic_mastery(st.session_state.topic)
    st.info(f"Updated mastery for this topic: {new_mastery}/100")

    # Action Buttons: Read Notes, Retake Quiz, or Change Topic
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📖 Read notes again", use_container_width=True):
            st.session_state.stage = "notes"
            st.rerun()

    with col2:
        if st.button("🔄 Retake quiz", type="primary", use_container_width=True):
            st.session_state.difficulty = get_recommended_difficulty(st.session_state.topic)
            
            with st.spinner("Generating a new quiz..."):
                try:
                    st.session_state.quiz = generate_quiz(
                        st.session_state.topic,
                        st.session_state.notes,
                        difficulty=st.session_state.difficulty,
                    )
                except Exception as exc:
                    st.error(f"Could not generate quiz: {exc}")
                else:
                    st.session_state.quiz_id = str(uuid.uuid4())
                    st.session_state.results = None
                    st.session_state.stage = "quiz"
                    st.rerun()

    with col3:
        if st.button("➕ Study another topic", use_container_width=True):
            st.session_state.stage = "input"
            st.session_state.topic = ""
            st.session_state.notes = ""
            st.session_state.sources = []
            st.session_state.quiz = None
            st.session_state.quiz_id = ""
            st.session_state.results = None
            st.rerun()
