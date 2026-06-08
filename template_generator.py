"""
Template generator — creates a custom Jinja2/WeasyPrint HTML resume template.

Two paths:
1. Vision path: user uploads a resume PDF/image → Claude Vision extracts style choices
2. Questionnaire path: user answers style questions → Claude generates from those answers

Both paths call _generate_template() with a StyleSpec dict and produce a
resume_template_<name>.html file in the project root.
"""

import base64
import io
import os
import re

import anthropic

TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))


# ── Style spec dataclass-style dict ──────────────────────────────────────────
# All keys are optional — defaults are filled in before generation.

DEFAULT_STYLE = {
    "accent_color": "#1F3864",       # hex color for name, section titles, borders
    "font_family": "Calibri, Arial, sans-serif",
    "font_size_body": "9.5pt",
    "name_size": "22pt",
    "name_alignment": "center",      # center | left
    "name_style": "uppercase",       # uppercase | normal
    "section_divider": "underline",  # underline | thick-bar | none
    "section_order": ["skills", "experience", "projects", "education", "certifications"],
    "entry_layout": "two-line",      # two-line (company+date / role+location) | stacked | inline
    "bullet_style": "disc",          # disc | dash | square
    "skills_layout": "inline",       # inline (Category: a, b, c) | table
    "show_summary": False,
}


# ── Vision extraction ─────────────────────────────────────────────────────────

VISION_SYSTEM_PROMPT = """You are a resume design analyst. You will be shown an image of a resume.
Your job is to extract the visual design choices — NOT the content — and return them as a JSON object.

Analyze:
- accent_color: the dominant non-black color used (hex code, e.g. "#1F3864"). If none, use "#000000"
- font_family: best guess at the font (e.g. "Calibri, Arial, sans-serif" or "Times New Roman, serif")
- font_size_body: approximate body text size (e.g. "9.5pt" or "10pt")
- name_size: approximate size of the candidate's name at top (e.g. "20pt" or "24pt")
- name_alignment: "center" or "left"
- name_style: "uppercase" if the name is all-caps, otherwise "normal"
- section_divider: "underline" if section titles have a line below, "thick-bar" if there's a filled bar/band, "none" if plain text
- section_order: list of section names in the order they appear top-to-bottom. Use these names only: ["skills", "experience", "projects", "education", "certifications", "summary"]
- entry_layout: "two-line" if company+date on one line and role+location on next, "stacked" if all on separate lines, "inline" if all on one line
- bullet_style: "disc" (filled circle), "dash" (—), or "square"
- skills_layout: "inline" if skills are shown as "Category: skill1, skill2", "table" if in a grid/columns
- show_summary: true if there's a professional summary/objective section, false otherwise

Return ONLY a valid JSON object, no markdown, no explanation."""


def pdf_to_image_bytes(pdf_bytes: bytes, page: int = 0) -> bytes:
    """Convert first page of a PDF to PNG bytes using PyMuPDF."""
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_obj = doc[page]
    mat = fitz.Matrix(2.0, 2.0)  # 2x zoom = ~144 DPI, good for Claude vision
    pix = page_obj.get_pixmap(matrix=mat)
    return pix.tobytes("png")


def image_bytes_to_base64(image_bytes: bytes) -> str:
    return base64.standard_b64encode(image_bytes).decode("utf-8")


def extract_style_from_image(image_bytes: bytes, media_type: str, api_key: str) -> dict:
    """Send a resume image to Claude Vision and extract style choices."""
    client = anthropic.Anthropic(api_key=api_key)

    b64 = image_bytes_to_base64(image_bytes)

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        system=VISION_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64,
                    },
                },
                {
                    "type": "text",
                    "text": "Extract the visual design choices from this resume image.",
                },
            ],
        }],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    import json
    extracted = json.loads(raw)

    # Merge with defaults so any missing keys are filled in
    style = {**DEFAULT_STYLE, **extracted}
    return style


# ── Template generation ───────────────────────────────────────────────────────

GENERATOR_SYSTEM_PROMPT = """You are an expert HTML/CSS developer specializing in resume templates for WeasyPrint PDF generation.

You will be given a style specification and must generate a complete, self-contained Jinja2 HTML template
that matches those design choices exactly.

CRITICAL REQUIREMENTS:
1. The template must use Jinja2 syntax — variable references like {{ personal_info.name }}, loops like {% for exp in professional_experience %}
2. WeasyPrint CSS only — no flexbox gap, no grid, no CSS variables, no transforms. Use display:flex with justify-content/align-items. Use margin/padding for spacing.
3. The template must render all these data fields (only show sections if the data is non-empty):
   - personal_info: name, email, phone, location, linkedin, github, website
   - skills: dict of {category: [list of skills]}
   - professional_experience: list of {company, role, location, start_date, end_date, bullet_points}
   - non_professional_experience: list of {organization, role, start_date, end_date, bullet_points}
   - projects: list of {name, combined_name, technologies, bullet_points}
   - education: list of {institution, degree, minor, gpa, graduation_date, honors, relevant_coursework}
   - certifications: list of {name, date}
4. Page size: letter, margins: 0.35in 0.5in
5. Must fit one page — use the font sizes and spacing given in the spec
6. Section order must match the spec exactly
7. Use {% if x %} guards so empty sections are hidden
8. For projects: {% if proj.combined_name %}show combined_name{% else %}show name{% endif %}

Return ONLY the complete HTML file content, no explanation, no markdown fences."""


def _build_generation_prompt(style: dict) -> str:
    import json
    return f"""Generate a Jinja2/WeasyPrint HTML resume template with these exact style specifications:

{json.dumps(style, indent=2)}

The template must produce a professional, visually polished one-page resume that faithfully implements every style choice above."""


def generate_template(style: dict, api_key: str, template_name: str = "custom") -> str:
    """Generate a Jinja2 HTML template from a style spec and save it to disk.

    Returns the file path of the saved template.
    """
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=8096,
        system=GENERATOR_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_generation_prompt(style)}],
    )

    html = response.content[0].text.strip()
    # Strip markdown fences if Claude added them despite instructions
    if html.startswith("```"):
        html = html.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", template_name.lower())
    filename = f"resume_template_{safe_name}.html"
    filepath = os.path.join(TEMPLATE_DIR, filename)

    with open(filepath, "w") as f:
        f.write(html)

    return filepath


def build_style_from_questionnaire(
    accent_color: str,
    font_family: str,
    name_alignment: str,
    name_style: str,
    section_divider: str,
    section_order: list[str],
    entry_layout: str,
    bullet_style: str,
    skills_layout: str,
    show_summary: bool,
) -> dict:
    """Assemble a StyleSpec from questionnaire answers."""
    return {
        **DEFAULT_STYLE,
        "accent_color": accent_color,
        "font_family": font_family,
        "name_alignment": name_alignment,
        "name_style": name_style,
        "section_divider": section_divider,
        "section_order": section_order,
        "entry_layout": entry_layout,
        "bullet_style": bullet_style,
        "skills_layout": skills_layout,
        "show_summary": show_summary,
    }
