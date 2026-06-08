import copy
import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(TEMPLATE_DIR, "generated_resumes")


def _render_html(resume_data: dict, template_name: str) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template(template_name)
    return template.render(**resume_data)


def _page_count(html_content: str) -> int:
    doc = HTML(string=html_content).render()
    return len(doc.pages)


def _trim_to_one_page(resume_data: dict, template_name: str) -> dict:
    """Progressively trim resume content until it fits on one page.

    Trimming order (certifications are NEVER removed — they always stay):
    1. Remove non-professional experience
    2. Remove relevant_coursework from education
    3. Remove projects one at a time (from the end)
    4. Remove bullet points from professional experience (last bullet of longest list)
    5. Remove skill categories (from the end)
    """
    data = copy.deepcopy(resume_data)

    # Check if already fits
    if _page_count(_render_html(data, template_name)) <= 1:
        return data

    # Step 1: Remove non-professional experience
    if data.get("non_professional_experience"):
        data["non_professional_experience"] = []
        if _page_count(_render_html(data, template_name)) <= 1:
            return data

    # Step 2: Remove relevant_coursework from all education entries
    for edu in data.get("education", []):
        edu["relevant_coursework"] = []
    if _page_count(_render_html(data, template_name)) <= 1:
        return data

    # Step 3: Remove projects one at a time from the end
    while len(data.get("projects", [])) > 1:
        data["projects"].pop()
        if _page_count(_render_html(data, template_name)) <= 1:
            return data

    # Step 4: Trim bullet points from professional experience
    # Remove last bullet from the entry with the most bullets, repeat
    for _ in range(20):  # safety limit
        experiences = data.get("professional_experience", [])
        if not experiences:
            break
        # Find entry with most bullets
        max_idx = max(range(len(experiences)),
                      key=lambda i: len(experiences[i].get("bullet_points", [])))
        bullets = experiences[max_idx].get("bullet_points", [])
        if len(bullets) <= 1:
            break
        bullets.pop()
        if _page_count(_render_html(data, template_name)) <= 1:
            return data

    # Step 5: Remove skill categories from the end
    skills = data.get("skills", {})
    keys = list(skills.keys())
    while len(keys) > 1:
        del skills[keys.pop()]
        if _page_count(_render_html(data, template_name)) <= 1:
            return data

    # Step 6: Last resort — remove last project
    if data.get("projects"):
        data["projects"] = []
        if _page_count(_render_html(data, template_name)) <= 1:
            return data

    return data


def _ensure_active_template(template_name: str = "resume_template.html") -> None:
    """If the active template doesn't exist, copy the default so PDF generation never fails."""
    active = os.path.join(TEMPLATE_DIR, template_name)
    if not os.path.exists(active):
        default = os.path.join(TEMPLATE_DIR, "resume_template_default.html")
        if os.path.exists(default):
            import shutil
            shutil.copy(default, active)


def generate_pdf(resume_data: dict, template_name: str = "resume_template.html") -> str:
    """Render tailored resume data into a one-page PDF.

    Automatically trims content if it exceeds one page.

    Args:
        resume_data: Tailored resume content dict from the agent.
        template_name: HTML template filename.

    Returns:
        Path to the generated PDF file.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    _ensure_active_template(template_name)

    # Trim content to fit one page
    trimmed_data = _trim_to_one_page(resume_data, template_name)

    html_content = _render_html(trimmed_data, template_name)

    name = trimmed_data.get("personal_info", {}).get("name", "resume").replace(" ", "_")
    output_path = os.path.join(OUTPUT_DIR, f"{name}_resume.pdf")

    HTML(string=html_content).write_pdf(output_path)
    return output_path
