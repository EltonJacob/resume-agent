"""
Resume parser — converts an existing resume (plain text) into a profile.json-compatible dict.

Claude reads the resume text and extracts structured data matching the profile schema.
The result can be loaded directly into the profile form for the user to review and edit.
"""

import json
import anthropic

PARSER_SYSTEM_PROMPT = """You are a resume parser. Your job is to extract structured information from a resume and return it as a JSON object matching a specific schema.

Extract every piece of information you can find. For bullet points, preserve the original wording as closely as possible — do not summarize or paraphrase.

Return ONLY a valid JSON object with this exact structure (no markdown fences, no extra text):
{
  "personal_info": {
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "github": "",
    "website": ""
  },
  "summary": "",
  "professional_experience": [
    {
      "company": "",
      "role": "",
      "location": "",
      "start_date": "",
      "end_date": "",
      "url": "",
      "bullet_points": []
    }
  ],
  "non_professional_experience": [
    {
      "organization": "",
      "role": "",
      "start_date": "",
      "end_date": "",
      "bullet_points": []
    }
  ],
  "projects": [
    {
      "name": "",
      "combined_name": "",
      "description": "",
      "technologies": [],
      "bullet_points": [],
      "url": ""
    }
  ],
  "education": [
    {
      "institution": "",
      "degree": "",
      "minor": "",
      "location": "",
      "graduation_date": "",
      "gpa": "",
      "honors": [],
      "relevant_coursework": []
    }
  ],
  "certifications": [
    {
      "name": "",
      "issuer": "",
      "date": "",
      "credential_id": ""
    }
  ],
  "skills": {
    "Category Name": ["skill1", "skill2"]
  }
}

Rules:
- professional_experience: paid jobs, internships, full-time roles
- non_professional_experience: volunteer work, clubs, unpaid teaching, mentorship
- If a field is not present on the resume, use an empty string "" or empty list []
- For skills, group them into logical categories (Languages, Frameworks, Tools, Cloud, etc.)
- For technologies in projects, extract them from the bullet points and description if not explicitly listed
- Preserve all bullet points verbatim — do not shorten or paraphrase"""


def parse_resume(resume_text: str, api_key: str) -> dict:
    """Parse resume text into a profile dict using Claude.

    Args:
        resume_text: Plain text content of the resume.
        api_key: Anthropic API key.

    Returns:
        A profile dict matching the profile.json schema.
    """
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8096,
        system=PARSER_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Parse this resume into the structured JSON format:\n\n{resume_text}"
        }],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(raw)
