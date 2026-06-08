"""
Profile editor UI — rendered inside the My Profile tab in app.py.

Call render_profile_form(profile_data) to get back the edited profile dict.
All state lives in st.session_state so edits survive Streamlit reruns.
"""

import json
import streamlit as st


def _v() -> str:
    """Return a version prefix tied to how many times load_form_state has been called.
    Appending this to widget keys forces Streamlit to treat them as new widgets
    after a profile import, preventing stale cached values from showing."""
    return str(st.session_state.get("_profile_version", 0))


# ── helpers ──────────────────────────────────────────────────────────────────

def _bullets_editor(bullets: list[str], key: str) -> list[str]:
    """Render a dynamic list of text areas for bullet points."""
    vkey = f"{_v()}_{key}_bullets"
    if vkey not in st.session_state:
        st.session_state[vkey] = bullets if bullets else [""]

    result = []
    for i, bullet in enumerate(st.session_state[vkey]):
        col_text, col_del = st.columns([11, 1])
        with col_text:
            val = st.text_area(
                f"Bullet {i + 1}",
                value=bullet,
                height=80,
                key=f"{_v()}_{key}_bullet_{i}",
                label_visibility="collapsed",
            )
            result.append(val)
        with col_del:
            st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
            if st.button("✕", key=f"{_v()}_{key}_del_{i}", help="Remove bullet"):
                st.session_state[vkey].pop(i)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    if st.button("+ Add bullet", key=f"{_v()}_{key}_add"):
        st.session_state[vkey].append("")
        st.rerun()

    st.session_state[vkey] = result
    return [b for b in result if b.strip()]


def _tags_editor(tags: list[str], key: str, label: str = "Skills / technologies") -> list[str]:
    """Comma-separated tag input that stores as a list."""
    current = ", ".join(tags) if tags else ""
    raw = st.text_input(label, value=current, key=key)
    return [t.strip() for t in raw.split(",") if t.strip()]


# ── section renderers ─────────────────────────────────────────────────────────

def _personal_info_section(info: dict) -> dict:
    st.subheader("Personal Information")
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Full name *", value=info.get("name", ""), key="pi_name")
        email = st.text_input("Email *", value=info.get("email", ""), key="pi_email")
        phone = st.text_input("Phone", value=info.get("phone", ""), key="pi_phone")
    with col2:
        location = st.text_input("Location (City, State)", value=info.get("location", ""), key="pi_location")
        linkedin = st.text_input("LinkedIn URL", value=info.get("linkedin", ""), key="pi_linkedin")
        github = st.text_input("GitHub URL", value=info.get("github", ""), key="pi_github")
    website = st.text_input("Personal website (optional)", value=info.get("website", ""), key="pi_website")
    return {
        "name": name, "email": email, "phone": phone,
        "location": location, "linkedin": linkedin,
        "github": github, "website": website,
    }


def _experience_section(experiences: list[dict], section_key: str, org_field: str = "company") -> list[dict]:
    """Render a list of experience entries. org_field is 'company' or 'organization'."""
    label = "Professional Experience" if org_field == "company" else "Non-Professional / Volunteer Experience"
    st.subheader(label)

    init_key = f"{section_key}_list"
    if init_key not in st.session_state:
        st.session_state[init_key] = experiences if experiences else []

    entries = st.session_state[init_key]
    result = []

    for i, exp in enumerate(entries):
        with st.expander(
            f"{exp.get(org_field, '') or exp.get('company', '') or 'New Entry'} — {exp.get('role', '')}",
            expanded=(i == 0 and not exp.get(org_field)),
        ):
            col1, col2 = st.columns(2)
            with col1:
                org = st.text_input(
                    "Company / Organization *",
                    value=exp.get(org_field, exp.get("company", "")),
                    key=f"{section_key}_{i}_org",
                )
                role = st.text_input("Role / Title *", value=exp.get("role", ""), key=f"{section_key}_{i}_role")
                location = st.text_input("Location", value=exp.get("location", ""), key=f"{section_key}_{i}_loc")
            with col2:
                start = st.text_input("Start date (e.g. June 2022)", value=exp.get("start_date", ""), key=f"{section_key}_{i}_start")
                end = st.text_input("End date (e.g. Present)", value=exp.get("end_date", ""), key=f"{section_key}_{i}_end")
                url = st.text_input("URL (optional)", value=exp.get("url", ""), key=f"{section_key}_{i}_url")

            st.markdown("**Bullet points** — describe your impact, tools used, and metrics")
            bullets = _bullets_editor(exp.get("bullet_points", [""]), key=f"{section_key}_{i}")

            col_save, col_del = st.columns([4, 1])
            with col_del:
                if st.button("Remove entry", key=f"{section_key}_{i}_remove", type="secondary"):
                    st.session_state[init_key].pop(i)
                    st.rerun()

            entry = {
                org_field: org,
                "role": role,
                "location": location,
                "start_date": start,
                "end_date": end,
                "bullet_points": bullets,
            }
            if url:
                entry["url"] = url
            result.append(entry)

    if st.button(f"+ Add entry", key=f"{section_key}_add_entry"):
        st.session_state[init_key].append({org_field: "", "role": "", "location": "", "start_date": "", "end_date": "", "bullet_points": [""]})
        st.rerun()

    st.session_state[init_key] = result
    return result


def _projects_section(projects: list[dict]) -> list[dict]:
    st.subheader("Projects")
    st.caption("Add your most significant projects. The agent will select the 3 most relevant for each job.")

    if "proj_list" not in st.session_state:
        st.session_state["proj_list"] = projects if projects else []

    entries = st.session_state["proj_list"]
    result = []

    for i, proj in enumerate(entries):
        with st.expander(proj.get("name", "") or "New Project", expanded=(i == 0 and not proj.get("name"))):
            name = st.text_input("Project name *", value=proj.get("name", ""), key=f"proj_{i}_name")
            description = st.text_area(
                "Short description (1-2 sentences)",
                value=proj.get("description", ""),
                height=80,
                key=f"proj_{i}_desc",
            )
            technologies = _tags_editor(proj.get("technologies", []), key=f"proj_{i}_tech", label="Technologies (comma-separated) *")
            url = st.text_input("Project URL (optional)", value=proj.get("url", ""), key=f"proj_{i}_url")

            st.markdown("**Bullet points** — what you built, how, and the impact")
            bullets = _bullets_editor(proj.get("bullet_points", [""]), key=f"proj_{i}")

            if st.button("Remove project", key=f"proj_{i}_remove", type="secondary"):
                st.session_state["proj_list"].pop(i)
                st.rerun()

            result.append({
                "name": name,
                "combined_name": proj.get("combined_name", ""),
                "description": description,
                "technologies": technologies,
                "bullet_points": bullets,
                "url": url,
            })

    if st.button("+ Add project", key="proj_add"):
        st.session_state["proj_list"].append({"name": "", "description": "", "technologies": [], "bullet_points": [""], "url": ""})
        st.rerun()

    st.session_state["proj_list"] = result
    return result


def _education_section(education: list[dict]) -> list[dict]:
    st.subheader("Education")

    if "edu_list" not in st.session_state:
        st.session_state["edu_list"] = education if education else []

    entries = st.session_state["edu_list"]
    result = []

    for i, edu in enumerate(entries):
        with st.expander(edu.get("institution", "") or "New Institution", expanded=(i == 0 and not edu.get("institution"))):
            col1, col2 = st.columns(2)
            with col1:
                institution = st.text_input("Institution *", value=edu.get("institution", ""), key=f"edu_{i}_inst")
                degree = st.text_input("Degree *", value=edu.get("degree", ""), key=f"edu_{i}_deg")
                minor = st.text_input("Minor (optional)", value=edu.get("minor", ""), key=f"edu_{i}_minor")
            with col2:
                location = st.text_input("Location", value=edu.get("location", ""), key=f"edu_{i}_loc")
                grad_date = st.text_input("Graduation date", value=edu.get("graduation_date", ""), key=f"edu_{i}_grad")
                gpa = st.text_input("GPA (optional)", value=edu.get("gpa", ""), key=f"edu_{i}_gpa")

            honors_raw = ", ".join(edu.get("honors", []))
            honors = st.text_input("Honors (comma-separated)", value=honors_raw, key=f"edu_{i}_honors")
            coursework = _tags_editor(edu.get("relevant_coursework", []), key=f"edu_{i}_courses", label="Relevant coursework (comma-separated)")

            if st.button("Remove", key=f"edu_{i}_remove", type="secondary"):
                st.session_state["edu_list"].pop(i)
                st.rerun()

            result.append({
                "institution": institution,
                "degree": degree,
                "minor": minor,
                "location": location,
                "graduation_date": grad_date,
                "gpa": gpa,
                "honors": [h.strip() for h in honors.split(",") if h.strip()],
                "relevant_coursework": coursework,
            })

    if st.button("+ Add education", key="edu_add"):
        st.session_state["edu_list"].append({"institution": "", "degree": "", "location": "", "graduation_date": "", "gpa": "", "honors": [], "relevant_coursework": []})
        st.rerun()

    st.session_state["edu_list"] = result
    return result


def _certifications_section(certs: list[dict]) -> list[dict]:
    st.subheader("Certifications")

    if "cert_list" not in st.session_state:
        st.session_state["cert_list"] = certs if certs else []

    entries = st.session_state["cert_list"]
    result = []

    for i, cert in enumerate(entries):
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            name = st.text_input("Certification name", value=cert.get("name", ""), key=f"cert_{i}_name", label_visibility="collapsed" if i > 0 else "visible")
        with col2:
            issuer = st.text_input("Issuer", value=cert.get("issuer", ""), key=f"cert_{i}_issuer", label_visibility="collapsed" if i > 0 else "visible")
        with col3:
            date = st.text_input("Date", value=cert.get("date", ""), key=f"cert_{i}_date", label_visibility="collapsed" if i > 0 else "visible")
        with col4:
            st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
            if st.button("✕", key=f"cert_{i}_remove", help="Remove"):
                st.session_state["cert_list"].pop(i)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        result.append({"name": name, "issuer": issuer, "date": date, "credential_id": cert.get("credential_id", "")})

    if st.button("+ Add certification", key="cert_add"):
        st.session_state["cert_list"].append({"name": "", "issuer": "", "date": "", "credential_id": ""})
        st.rerun()

    st.session_state["cert_list"] = result
    return result


def _skills_section(skills: dict) -> dict:
    st.subheader("Skills")
    st.caption("Each row is a skill category. Skills are comma-separated. Add or remove categories as needed.")

    if "skills_data" not in st.session_state:
        st.session_state["skills_data"] = list(skills.items()) if skills else [("Languages", "")]

    result = {}
    new_list = []

    for i, (cat, items) in enumerate(st.session_state["skills_data"]):
        items_str = ", ".join(items) if isinstance(items, list) else items
        col_cat, col_items, col_del = st.columns([2, 6, 1])
        with col_cat:
            cat_val = st.text_input("Category", value=cat, key=f"skill_{i}_cat", label_visibility="collapsed" if i > 0 else "visible")
        with col_items:
            items_val = st.text_input("Skills (comma-separated)", value=items_str, key=f"skill_{i}_items", label_visibility="collapsed" if i > 0 else "visible")
        with col_del:
            st.markdown("<div style='margin-top:28px'>", unsafe_allow_html=True)
            if st.button("✕", key=f"skill_{i}_del"):
                st.session_state["skills_data"].pop(i)
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        new_list.append((cat_val, items_val))
        if cat_val.strip():
            result[cat_val] = [s.strip() for s in items_val.split(",") if s.strip()]

    if st.button("+ Add skill category", key="skill_add"):
        st.session_state["skills_data"].append(("", ""))
        st.rerun()

    st.session_state["skills_data"] = new_list
    return result


# ── public API ────────────────────────────────────────────────────────────────

def load_form_state(profile: dict):
    """Seed session_state from a profile dict (called when a profile is imported or loaded)."""
    # Bump version so all versioned widget keys (bullets, lists) are treated as fresh
    st.session_state["_profile_version"] = st.session_state.get("_profile_version", 0) + 1

    st.session_state["pi_name"] = profile.get("personal_info", {}).get("name", "")
    st.session_state["pi_email"] = profile.get("personal_info", {}).get("email", "")
    st.session_state["pi_phone"] = profile.get("personal_info", {}).get("phone", "")
    st.session_state["pi_location"] = profile.get("personal_info", {}).get("location", "")
    st.session_state["pi_linkedin"] = profile.get("personal_info", {}).get("linkedin", "")
    st.session_state["pi_github"] = profile.get("personal_info", {}).get("github", "")
    st.session_state["pi_website"] = profile.get("personal_info", {}).get("website", "")

    st.session_state["prof_exp_list"] = profile.get("professional_experience", [])
    st.session_state["non_prof_exp_list"] = profile.get("non_professional_experience", [])
    st.session_state["proj_list"] = profile.get("projects", [])
    st.session_state["edu_list"] = profile.get("education", [])
    st.session_state["cert_list"] = profile.get("certifications", [])
    st.session_state["skills_data"] = list(profile.get("skills", {}).items())


def render_profile_form(existing_profile: dict) -> dict:
    """Render the full profile editor. Returns the current form values as a profile dict."""
    personal_info = _personal_info_section(existing_profile.get("personal_info", {}))
    st.markdown("---")
    professional_experience = _experience_section(
        existing_profile.get("professional_experience", []),
        section_key="prof_exp",
        org_field="company",
    )
    st.markdown("---")
    non_professional_experience = _experience_section(
        existing_profile.get("non_professional_experience", []),
        section_key="non_prof_exp",
        org_field="organization",
    )
    st.markdown("---")
    projects = _projects_section(existing_profile.get("projects", []))
    st.markdown("---")
    education = _education_section(existing_profile.get("education", []))
    st.markdown("---")
    certifications = _certifications_section(existing_profile.get("certifications", []))
    st.markdown("---")
    skills = _skills_section(existing_profile.get("skills", {}))

    return {
        "personal_info": personal_info,
        "summary": "",
        "professional_experience": professional_experience,
        "non_professional_experience": non_professional_experience,
        "projects": projects,
        "education": education,
        "certifications": certifications,
        "skills": skills,
    }
