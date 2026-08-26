import uuid
import pandas as pd
import streamlit as st

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

st.set_page_config(page_title="AI Study Companion", layout="centered")
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

with st.sidebar:
    st.header("Your progress")
    summary = get_all_topics_summary()

    if not summary:
        st.write("No attempts yet. Take a quiz to see your progress here.")
    else:
        for topic_summary in summary:
            mastery = topic_summary["mastery"]
            # Fix display label
            attempts_count = topic_summary.get("attempts", 0)
            label = f"{topic_summary['topic']} — {mastery}/100 ({attempts_count} attempts)"
            
            if mastery < 60:
                st.warning(label)
            else:
                st.success(label)

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
            type=["txt", "pdf"],
        )
        topic_label = st.text_input(
            "Label this material (used to track your progress)",
            placeholder="e.g. Binary Search Trees",
        )

        if st.button("Generate study notes", type="primary", key="upload_generate"):
            topic_label = topic_label.strip()

            if uploaded_file is None:
                st.warning("Please upload a .txt or .pdf file.")
            elif not topic_label:
                st.warning("Please enter a label for this material.")
            else:
                st.session_state.topic = topic_label
                st.session_state.difficulty = get_recommended_difficulty(topic_label)

                with st.spinner("Reading document and generating notes..."):
                    try:
                        if uploaded_file.name.lower().endswith(".pdf"):
                            raw_text = extract_text_from_pdf(uploaded_file)
                        else:
                            raw_text = uploaded_file.read().decode(
                                "utf-8", errors="ignore"
                            )

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
                # Generate a unique ID for this specific quiz run
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

        # 1. Show model answer or missed points directly
        model_ans = result.get("ideal_answer") or result.get("correct_answer")
        if model_ans:
            st.success(f"**Correct Answer:** {model_ans}")
        elif result.get("missing_points"):
            st.warning(f"**Missed Points:** {', '.join(result['missing_points'])}")

        # 2. Show score directly underneath
        st.caption(f"**Score:** {result['score']}/100")
        st.markdown("---")
    new_mastery = get_topic_mastery(st.session_state.topic)
    st.info(f"Updated mastery for this topic: {new_mastery}/100")

    # Fetch attempt history and format labels sequentially (Attempt 1, Attempt 2, etc.)
    history = get_topic_attempt_history(st.session_state.topic)

    if len(history) >= 2:
        st.markdown(f"**Progress on {st.session_state.topic}**")
        
        # Format X-axis sequentially 1..N regardless of raw backend counts
        chart_df = pd.DataFrame(
            {
                "Score": [entry["score"] for entry in history],
            },
            index=[f"Attempt {i + 1}" for i in range(len(history))],
        )
        st.bar_chart(chart_df)

    # Action Buttons for Retaking or Changing Topics
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Retake quiz (Same Topic)", type="primary", use_container_width=True):
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

    with col2:
        if st.button("Study another topic", use_container_width=True):
            st.session_state.stage = "input"
            st.session_state.topic = ""
            st.session_state.notes = ""
            st.session_state.sources = []
            st.session_state.quiz = None
            st.session_state.quiz_id = ""
            st.session_state.results = None
            st.rerun()