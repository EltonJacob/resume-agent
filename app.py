import json
import os
import shutil
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
from profile_form import render_profile_form, load_form_state
from resume_parser import parse_resume
from template_generator import (
    extract_style_from_image,
    generate_template,
    build_style_from_questionnaire,
    pdf_to_image_bytes,
    DEFAULT_STYLE,
    TEMPLATE_DIR,
)

load_dotenv()

PROFILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profile.json")

st.set_page_config(page_title="Resume Agent", page_icon="📄", layout="wide")
st.title("Resume Agent")

tab_resume, tab_profile, tab_template, tab_keywords = st.tabs(["Resume Generator", "My Profile", "Template Studio", "Keyword Tracker"])

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
        st.success("Profile loaded")
        with open(PROFILE_PATH) as f:
            profile_data = json.load(f)
        with st.expander("View profile data"):
            st.json(profile_data)
        st.caption("Update your profile in the My Profile tab.")
    else:
        st.warning("No profile yet.")
        st.caption("Go to the **My Profile** tab to build your profile or import from an existing resume.")
        profile_data = None


# ── Tab 1: Resume Generator ──────────────────────────────────────────────────
with tab_resume:
    st.markdown("Generate a tailored resume from your profile data and a job description.")

    if not profile_data:
        st.info("No profile found. Head to the **My Profile** tab to build your profile — paste your existing resume and Claude will extract everything automatically. Then come back here to generate tailored resumes.")
    else:
        # Active template indicator
        active_tpl = os.path.join(TEMPLATE_DIR, "resume_template.html")
        default_tpl = os.path.join(TEMPLATE_DIR, "resume_template_default.html")
        if os.path.exists(active_tpl):
            # Check if it's the default by comparing size as a rough heuristic
            active_name = "default" if (
                os.path.exists(default_tpl) and
                os.path.getsize(active_tpl) == os.path.getsize(default_tpl)
            ) else "custom (from Template Studio)"
        else:
            active_name = "default"
        st.caption(f"Active template: **{active_name}** — change in the Template Studio tab.")

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

        if st.button("Generate Tailored Resume", type="primary", disabled=not (api_key and job_description)):
            progress_placeholder = st.empty()

            def update_progress(msg):
                progress_placeholder.info(msg)

            try:
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


# ── Tab 2: My Profile ────────────────────────────────────────────────────────
with tab_profile:
    st.markdown("Build and manage your profile. This is the data the agent uses to tailor your resume.")

    # ── Resume upload / parse ──
    with st.expander("Import from existing resume (paste or upload)", expanded=not os.path.exists(PROFILE_PATH)):
        st.markdown("Paste your existing resume text below and Claude will extract all the structured data into your profile automatically. Review and edit it before saving.")
        st.caption("Tip: copy-paste from a Word doc or PDF. The more detail you include, the better the agent performs.")

        uploaded_file = st.file_uploader("Upload a .txt file of your resume (optional)", type=["txt"])
        resume_text = ""
        if uploaded_file:
            resume_text = uploaded_file.read().decode("utf-8")
            st.success("File loaded. Click Parse Resume to extract your profile.")

        pasted = st.text_area(
            "Or paste resume text here",
            value=resume_text,
            height=300,
            placeholder="Paste your full resume text here...",
            key="resume_paste",
        )

        if st.button("Parse Resume → Populate Form", type="primary", disabled=not (api_key and pasted.strip())):
            with st.spinner("Claude is reading your resume and extracting your profile..."):
                try:
                    parsed = parse_resume(pasted.strip(), api_key)
                    load_form_state(parsed)
                    st.session_state["parsed_profile"] = parsed
                    st.success("Profile extracted! Review and edit the form below, then click Save Profile.")
                    st.rerun()
                except json.JSONDecodeError as e:
                    st.error(f"Failed to parse Claude's response: {e}")
                except Exception as e:
                    st.error(f"Parse failed: {e}")

    st.markdown("---")

    # Determine the base profile to seed the form from:
    # 1. A freshly parsed profile (from resume upload this session)
    # 2. The existing profile.json on disk
    # 3. An empty profile
    if "parsed_profile" in st.session_state:
        base_profile = st.session_state["parsed_profile"]
    elif profile_data:
        base_profile = profile_data
    else:
        base_profile = {}

    current_form = render_profile_form(base_profile)

    st.markdown("---")
    col_save, col_download = st.columns(2)

    with col_save:
        if st.button("Save Profile", type="primary"):
            name = current_form.get("personal_info", {}).get("name", "").strip()
            email = current_form.get("personal_info", {}).get("email", "").strip()
            if not name or not email:
                st.error("Name and email are required before saving.")
            else:
                with open(PROFILE_PATH, "w") as f:
                    json.dump(current_form, f, indent=2)
                st.success("Profile saved to profile.json. Your resume generator is ready to use.")
                # Clear parsed_profile so form now seeds from disk on next load
                st.session_state.pop("parsed_profile", None)
                st.rerun()

    with col_download:
        profile_json = json.dumps(current_form, indent=2)
        st.download_button(
            label="Download profile.json",
            data=profile_json,
            file_name="profile.json",
            mime="application/json",
            help="Download your profile as a JSON file for backup or use on another machine.",
        )


# ── Tab 3: Template Studio ───────────────────────────────────────────────────
with tab_template:
    st.markdown("Create a custom resume template that matches your preferred visual style.")
    st.caption("The template controls how your PDF looks — fonts, colors, layout, section order. Your profile data stays the same.")

    SECTION_OPTIONS = ["skills", "experience", "projects", "education", "certifications", "summary"]

    # ── Path A: Upload a resume ──
    st.subheader("Option 1 — Upload your resume")
    st.markdown("Upload a PDF or image of a resume with the style you want. Claude will analyze the design and recreate it as your template.")

    uploaded_resume = st.file_uploader(
        "Upload resume (PDF, PNG, JPG)",
        type=["pdf", "png", "jpg", "jpeg"],
        key="template_upload",
    )

    if uploaded_resume:
        file_bytes = uploaded_resume.read()
        file_type = uploaded_resume.type

        # Convert PDF first page to image for Claude Vision
        if file_type == "application/pdf":
            with st.spinner("Converting PDF to image..."):
                try:
                    image_bytes = pdf_to_image_bytes(file_bytes)
                    display_media = "image/png"
                except Exception as e:
                    st.error(f"Could not read PDF: {e}")
                    image_bytes = None
                    display_media = None
        else:
            image_bytes = file_bytes
            display_media = file_type

        if image_bytes:
            st.image(image_bytes, caption="Resume preview — Claude will analyze this", use_container_width=True)

            template_name_vision = st.text_input(
                "Template name",
                value="my_style",
                key="tpl_name_vision",
                help="Used to name the saved template file.",
            )

            if st.button("Analyze & Generate Template", type="primary", disabled=not api_key, key="btn_vision"):
                with st.spinner("Step 1/2: Claude Vision is reading your resume design..."):
                    try:
                        style = extract_style_from_image(image_bytes, display_media, api_key)
                        st.session_state["detected_style"] = style
                    except Exception as e:
                        st.error(f"Style extraction failed: {e}")
                        style = None

                if style:
                    with st.expander("Detected style choices (review before generating)"):
                        st.json(style)

                    with st.spinner("Step 2/2: Generating your custom template..."):
                        try:
                            filepath = generate_template(style, api_key, template_name=template_name_vision)
                            st.session_state["generated_template_path"] = filepath
                            st.session_state["generated_template_name"] = template_name_vision
                            st.success(f"Template created: `{os.path.basename(filepath)}`")
                        except Exception as e:
                            st.error(f"Template generation failed: {e}")

    st.markdown("---")

    # ── Path B: Questionnaire ──
    st.subheader("Option 2 — Design it yourself")
    st.markdown("Answer a few questions about the style you want and Claude will generate a matching template.")

    with st.form("style_form"):
        col1, col2 = st.columns(2)

        with col1:
            accent_color = st.color_picker("Accent color", value="#1F3864", help="Used for your name, section titles, and dividers.")
            name_alignment = st.selectbox("Name alignment", ["center", "left"])
            name_style = st.selectbox("Name text style", ["uppercase", "normal"])
            section_divider = st.selectbox(
                "Section title divider",
                ["underline", "thick-bar", "none"],
                help="underline = thin line below title, thick-bar = filled color band, none = plain text",
            )
            bullet_style = st.selectbox("Bullet style", ["disc", "dash", "square"])

        with col2:
            font_family = st.selectbox(
                "Font",
                [
                    "Calibri, Arial, sans-serif",
                    "Arial, Helvetica, sans-serif",
                    "Georgia, Times New Roman, serif",
                    "Times New Roman, serif",
                    "Garamond, Georgia, serif",
                    "Verdana, Geneva, sans-serif",
                ],
            )
            entry_layout = st.selectbox(
                "Experience entry layout",
                ["two-line", "stacked", "inline"],
                help="two-line: Company | Date on line 1, Role | Location on line 2",
            )
            skills_layout = st.selectbox(
                "Skills layout",
                ["inline", "table"],
                help="inline: Languages: Python, SQL, Java  |  table: grid of columns",
            )
            show_summary = st.checkbox("Include a summary/objective section", value=False)

        st.markdown("**Section order** — drag to reorder (top = first on resume)")
        section_order = st.multiselect(
            "Sections to include (select in the order you want them)",
            options=SECTION_OPTIONS,
            default=["skills", "experience", "projects", "education", "certifications"],
            help="Select sections in the order you want them to appear on your resume.",
        )

        template_name_q = st.text_input("Template name", value="my_style", key="tpl_name_q")

        submitted = st.form_submit_button("Generate Template", type="primary", disabled=not api_key)

    if submitted:
        if not section_order:
            st.error("Please select at least one section.")
        else:
            style = build_style_from_questionnaire(
                accent_color=accent_color,
                font_family=font_family,
                name_alignment=name_alignment,
                name_style=name_style,
                section_divider=section_divider,
                section_order=section_order,
                entry_layout=entry_layout,
                bullet_style=bullet_style,
                skills_layout=skills_layout,
                show_summary=show_summary,
            )
            with st.spinner("Generating your custom template..."):
                try:
                    filepath = generate_template(style, api_key, template_name=template_name_q)
                    st.session_state["generated_template_path"] = filepath
                    st.session_state["generated_template_name"] = template_name_q
                    st.success(f"Template created: `{os.path.basename(filepath)}`")
                except Exception as e:
                    st.error(f"Template generation failed: {e}")

    # ── Result — preview + activate ──
    if "generated_template_path" in st.session_state:
        tpl_path = st.session_state["generated_template_path"]
        tpl_name = st.session_state.get("generated_template_name", "custom")

        if os.path.exists(tpl_path):
            st.markdown("---")
            st.subheader("Your Template")

            with st.expander("Preview HTML source"):
                with open(tpl_path) as f:
                    st.code(f.read(), language="html")

            col_dl, col_activate = st.columns(2)

            with col_dl:
                with open(tpl_path) as f:
                    st.download_button(
                        label="Download template HTML",
                        data=f.read(),
                        file_name=os.path.basename(tpl_path),
                        mime="text/html",
                    )

            with col_activate:
                if st.button("Use this template for PDF generation", type="primary"):
                    shutil.copy(tpl_path, os.path.join(TEMPLATE_DIR, "resume_template.html"))
                    st.success("Template activated. Your next PDF will use this design.")

            st.caption(f"Saved at: `{tpl_path}`")

    # ── Saved templates ──
    saved = [
        f for f in os.listdir(TEMPLATE_DIR)
        if f.startswith("resume_template_") and f.endswith(".html")
    ]
    if saved:
        st.markdown("---")
        st.subheader("Saved Templates")
        for tpl in sorted(saved):
            col_name, col_use = st.columns([4, 1])
            with col_name:
                st.markdown(f"`{tpl}`")
            with col_use:
                if st.button("Activate", key=f"activate_{tpl}"):
                    shutil.copy(
                        os.path.join(TEMPLATE_DIR, tpl),
                        os.path.join(TEMPLATE_DIR, "resume_template.html"),
                    )
                    st.success(f"`{tpl}` is now active.")
                    st.rerun()


# ── Tab 4: Keyword Tracker ───────────────────────────────────────────────────
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
