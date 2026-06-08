import json
import os
from dotenv import load_dotenv
import streamlit as st
from agent import tailor_resume
from pdf_generator import generate_pdf
from keyword_agent import (
    extract_keywords,
    get_frequency_by_category,
    get_frequency_report,
    get_jobs_count,
    run_gap_analysis,
    clear_database,
)

load_dotenv()

PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile.json")

st.set_page_config(page_title="Resume Agent", page_icon="📄", layout="wide")
st.title("Resume Agent")

tab_resume, tab_keywords = st.tabs(["Resume Generator", "Keyword Tracker"])

# Sidebar — API key and profile (shared across tabs)
with st.sidebar:
    st.header("Settings")
    api_key = st.text_input(
        "Anthropic API Key",
        value=os.environ.get("ANTHROPIC_API_KEY", ""),
        type="password",
        help="Your Claude API key. You can also set the ANTHROPIC_API_KEY environment variable.",
    )

    st.header("Profile")
    if os.path.exists(PROFILE_PATH):
        st.success("profile.json loaded")
        with open(PROFILE_PATH) as f:
            profile_data = json.load(f)
        with st.expander("View profile data"):
            st.json(profile_data)
    else:
        st.error("profile.json not found. Please create it in the project root.")
        profile_data = None

    st.markdown("---")
    st.markdown("Edit `profile.json` to update your experiences, then refresh this page.")


# ── Tab 1: Resume Generator ──────────────────────────────────────────────────
with tab_resume:
    st.markdown("Generate a tailored resume from your profile data and a job description.")

    job_description = st.text_area(
        "Paste the job description here",
        height=300,
        placeholder="Paste the full job posting text here...",
        key="resume_jd",
    )

    with st.expander("Notes (optional — soft guidance for this resume)"):
        notes = st.text_area(
            "Notes",
            height=120,
            placeholder="e.g. 'Order experiences with Morgan Stanley Software Engineer first' or 'Include a project that uses ChromaDB'.\n\nThese are soft instructions — the one-page constraint always takes priority.",
            label_visibility="collapsed",
        )

    if st.button("Generate Tailored Resume", type="primary", disabled=not (api_key and profile_data and job_description)):
        progress_placeholder = st.empty()

        def update_progress(msg):
            progress_placeholder.info(msg)

        try:
            # Extract keywords in the background while tailoring (same JD, no extra cost)
            tailored_data, editor_feedback = tailor_resume(
                profile_data, job_description, api_key, progress_callback=update_progress, notes=notes
            )
            progress_placeholder.info("Extracting keywords for Keyword Tracker...")
            try:
                extract_keywords(job_description, api_key)
            except Exception:
                pass  # keyword extraction is non-critical — don't fail the resume flow

            progress_placeholder.empty()
            st.session_state["tailored_data"] = tailored_data
            st.session_state["editor_feedback"] = editor_feedback
            st.success("Resume tailored successfully! (Generated → Reviewed → Finalized)")
        except json.JSONDecodeError as e:
            progress_placeholder.empty()
            st.error(f"Failed to parse Claude's response: {e}")
        except ValueError as e:
            progress_placeholder.empty()
            st.error(f"Validation error: {e}")
        except Exception as e:
            progress_placeholder.empty()
            st.error(f"Error: {e}")

    if "tailored_data" in st.session_state:
        tailored_data = st.session_state["tailored_data"]

        if "editor_feedback" in st.session_state:
            with st.expander("Editor Feedback (what was improved)"):
                st.markdown(st.session_state["editor_feedback"])

        st.subheader("Tailored Resume Preview")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Summary**")
            st.write(tailored_data.get("summary", ""))

        with col2:
            st.markdown("**Skills**")
            skills = tailored_data.get("skills", {})
            for category, items in skills.items():
                if items:
                    label = category.replace("_", " ").title()
                    st.write(f"**{label}:** {', '.join(items)}")

        st.markdown("**Professional Experience**")
        for exp in tailored_data.get("professional_experience", []):
            st.markdown(f"**{exp['role']}** at {exp['company']} ({exp['start_date']} – {exp['end_date']})")
            for bp in exp.get("bullet_points", []):
                st.markdown(f"- {bp}")

        st.markdown("**Projects**")
        for proj in tailored_data.get("projects", []):
            st.markdown(f"**{proj['name']}** — {', '.join(proj.get('technologies', []))}")
            for bp in proj.get("bullet_points", []):
                st.markdown(f"- {bp}")

        st.markdown("---")

        if st.button("Generate PDF"):
            with st.spinner("Generating PDF..."):
                try:
                    pdf_path = generate_pdf(tailored_data)
                    with open(pdf_path, "rb") as f:
                        pdf_bytes = f.read()
                    st.download_button(
                        label="Download PDF",
                        data=pdf_bytes,
                        file_name=os.path.basename(pdf_path),
                        mime="application/pdf",
                    )
                    st.success(f"PDF generated: {pdf_path}")
                except Exception as e:
                    st.error(f"PDF generation failed: {e}")


# ── Tab 2: Keyword Tracker ───────────────────────────────────────────────────
with tab_keywords:
    jobs_count = get_jobs_count()
    st.markdown(f"Tracking keywords across **{jobs_count} job description{'s' if jobs_count != 1 else ''}** you've applied to.")

    # Manual extraction (for jobs pasted here directly without generating a resume)
    with st.expander("Add a job description to the tracker (without generating a resume)"):
        kw_jd = st.text_area(
            "Job description",
            height=200,
            placeholder="Paste a job description to extract and track its keywords...",
            key="kw_jd",
        )
        kw_col1, kw_col2 = st.columns(2)
        with kw_col1:
            kw_title = st.text_input("Job title (optional)", key="kw_title")
        with kw_col2:
            kw_company = st.text_input("Company (optional)", key="kw_company")

        if st.button("Extract & Track Keywords", disabled=not (api_key and kw_jd)):
            with st.spinner("Extracting keywords..."):
                try:
                    extracted = extract_keywords(kw_jd, api_key, job_title=kw_title, company=kw_company)
                    st.success("Keywords extracted and saved.")
                    with st.expander("View extracted keywords"):
                        st.json(extracted)
                except Exception as e:
                    st.error(f"Extraction failed: {e}")

    st.markdown("---")

    if jobs_count == 0:
        st.info("No keyword data yet. Generate a resume or add a job description above to start tracking.")
    else:
        # ── Frequency breakdown by category ──
        st.subheader("Skills Frequency by Category")
        st.caption("How many unique job descriptions mention each skill. Skills appearing in more jobs rank higher.")

        freq_by_cat = get_frequency_by_category()
        category_labels = {
            "languages": "Programming Languages",
            "frameworks_libraries": "Frameworks & Libraries",
            "tools_platforms": "Tools & Platforms",
            "ml_ai_concepts": "ML / AI Concepts",
            "soft_skills": "Soft Skills",
            "domain_concepts": "Domain Concepts",
        }

        if freq_by_cat:
            cols = st.columns(2)
            for i, (category, skills_list) in enumerate(freq_by_cat.items()):
                label = category_labels.get(category, category.replace("_", " ").title())
                with cols[i % 2]:
                    st.markdown(f"**{label}**")
                    top = skills_list[:15]  # show top 15 per category
                    for entry in top:
                        bar_width = int((entry["frequency"] / jobs_count) * 100)
                        st.markdown(
                            f"`{entry['skill']}` — {entry['frequency']} job{'s' if entry['frequency'] != 1 else ''} "
                            f"{'█' * min(bar_width // 10 + 1, 10)}"
                        )
                    st.markdown("")

        # ── Overall top skills ──
        st.subheader("Top 20 Skills Across All Jobs")
        top_skills = get_frequency_report(top_n=20)
        if top_skills:
            max_freq = top_skills[0]["frequency"]
            for entry in top_skills:
                bar = int((entry["frequency"] / max_freq) * 20)
                st.markdown(
                    f"**{entry['skill']}** ({entry['category'].replace('_', ' ')}) — "
                    f"{entry['frequency']} job{'s' if entry['frequency'] != 1 else ''} "
                    f"`{'█' * bar}`"
                )

        st.markdown("---")

        # ── Gap analysis ──
        st.subheader("Gap Analysis")
        st.caption("Compare market demand against your profile to find what to learn next.")

        if st.button("Run Gap Analysis", type="primary", disabled=not (api_key and profile_data)):
            with st.spinner("Analyzing gaps..."):
                try:
                    gap_result = run_gap_analysis(profile_data, api_key)
                    st.session_state["gap_result"] = gap_result
                except Exception as e:
                    st.error(f"Gap analysis failed: {e}")

        if "gap_result" in st.session_state:
            gap = st.session_state["gap_result"]

            st.info(gap.get("summary", ""))

            gap_col1, gap_col2 = st.columns(2)

            with gap_col1:
                st.markdown("**Already covered in your profile**")
                for item in gap.get("covered", []):
                    st.markdown(f"- **{item['skill']}** ({item['frequency']} jobs) — *{item.get('where_in_profile', '')}*")

            with gap_col2:
                st.markdown("**Gaps — what to learn next**")
                priority_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                for item in gap.get("gaps", []):
                    icon = priority_colors.get(item.get("priority", "low"), "⚪")
                    st.markdown(f"{icon} **{item['skill']}** ({item['frequency']} jobs)")
                    st.caption(f"  {item.get('suggestion', '')}")

        st.markdown("---")

        # ── Danger zone ──
        with st.expander("Reset keyword database"):
            st.warning("This will delete all stored keyword data. This cannot be undone.")
            if st.button("Clear all keyword data", type="secondary"):
                clear_database()
                st.success("Database cleared.")
                st.rerun()
