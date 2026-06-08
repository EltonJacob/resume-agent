"""
Keyword/Skills frequency agent.

Responsibilities:
- Extract structured skills and keywords from job descriptions using Claude
- Store them in a local SQLite database (data/keywords.db)
- Provide aggregated frequency analysis with gap detection against the candidate profile
- Normalize synonyms (k8s → Kubernetes) so counts are meaningful
"""

import json
import sqlite3
import os
from datetime import datetime
from collections import defaultdict

import anthropic

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "keywords.db")

EXTRACTION_SYSTEM_PROMPT = """You are a technical recruiter and skills analyst. Extract all skills, technologies, and keywords from a job description.

Your job is to return a structured JSON object with the following categories:
- "languages": Programming languages (Python, Java, SQL, etc.)
- "frameworks_libraries": Frameworks and libraries (PyTorch, React, FastAPI, etc.)
- "tools_platforms": Tools, platforms, cloud services (AWS, Docker, Kubernetes, etc.)
- "ml_ai_concepts": ML/AI concepts and techniques (anomaly detection, transformers, RLHF, etc.)
- "soft_skills": Soft skills and practices (cross-functional collaboration, agile, etc.)
- "domain_concepts": Domain-specific concepts (hardware validation, distributed systems, etc.)

Rules:
- Normalize synonyms: "k8s" → "Kubernetes", "LLMs" → "Large Language Models", "ML" → "Machine Learning"
- Use canonical casing: "Python" not "python", "PostgreSQL" not "postgres"
- Only include skills explicitly mentioned or strongly implied in the job description
- Do NOT include generic filler like "strong communication" unless truly emphasized
- Each category is a list of strings

Return ONLY a valid JSON object, no markdown fences."""


GAP_ANALYSIS_SYSTEM_PROMPT = """You are a career coach helping a candidate identify skill gaps.

Given:
1. A ranked list of skills appearing most frequently across job descriptions the candidate has applied to
2. The candidate's profile (their actual experience, skills, and projects)

Your job is to:
- Identify which high-frequency skills the candidate already has (covered)
- Identify which high-frequency skills the candidate is MISSING or has weak coverage of (gaps)
- For each gap, suggest a concrete learning action (course, project type, certification)
- Prioritize gaps by: frequency × importance (skills at top-tier companies matter more)

Return a JSON object with:
{
  "covered": [{"skill": "...", "frequency": N, "where_in_profile": "..."}],
  "gaps": [{"skill": "...", "frequency": N, "priority": "high/medium/low", "suggestion": "..."}],
  "summary": "2-3 sentence executive summary of the candidate's positioning"
}

Return ONLY valid JSON, no markdown fences."""


def _ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            job_title TEXT,
            company TEXT,
            extracted_at TEXT NOT NULL,
            category TEXT NOT NULL,
            skill TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            job_title TEXT,
            company TEXT,
            job_description TEXT,
            extracted_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_skill ON job_keywords(skill)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_category ON job_keywords(category)")
    conn.commit()
    conn.close()


def _job_already_extracted(job_id: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT 1 FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    return row is not None


def extract_keywords(job_description: str, api_key: str, job_title: str = "", company: str = "") -> dict:
    """Extract skills from a job description using Claude and store in SQLite.

    Returns the extracted skills dict (categories → skill lists).
    """
    _ensure_db()

    # Use a content-hash as job_id so duplicate pastes are idempotent
    import hashlib
    job_id = hashlib.sha256(job_description.strip().encode()).hexdigest()[:16]

    if _job_already_extracted(job_id):
        return _load_extracted(job_id)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=EXTRACTION_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Extract skills from this job description:\n\n{job_description}"}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    skills: dict = json.loads(raw)
    extracted_at = datetime.utcnow().isoformat()

    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR IGNORE INTO jobs VALUES (?, ?, ?, ?, ?)",
        (job_id, job_title, company, job_description, extracted_at),
    )
    rows = []
    for category, skill_list in skills.items():
        if isinstance(skill_list, list):
            for skill in skill_list:
                if skill and isinstance(skill, str):
                    rows.append((job_id, job_title, company, extracted_at, category, skill.strip()))
    conn.executemany(
        "INSERT INTO job_keywords (job_id, job_title, company, extracted_at, category, skill) VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()

    return skills


def _load_extracted(job_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT category, skill FROM job_keywords WHERE job_id = ?", (job_id,)
    ).fetchall()
    conn.close()
    result = defaultdict(list)
    for category, skill in rows:
        result[category].append(skill)
    return dict(result)


def get_frequency_report(top_n: int = 30) -> list[dict]:
    """Return skills ranked by frequency across all stored job descriptions."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT skill, category, COUNT(DISTINCT job_id) as freq
        FROM job_keywords
        GROUP BY skill, category
        ORDER BY freq DESC
        LIMIT ?
    """, (top_n,)).fetchall()
    conn.close()
    return [{"skill": r[0], "category": r[1], "frequency": r[2]} for r in rows]


def get_frequency_by_category() -> dict:
    """Return frequency counts grouped by category, each sorted by frequency."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("""
        SELECT category, skill, COUNT(DISTINCT job_id) as freq
        FROM job_keywords
        GROUP BY category, skill
        ORDER BY category, freq DESC
    """).fetchall()
    conn.close()

    result = defaultdict(list)
    for category, skill, freq in rows:
        result[category].append({"skill": skill, "frequency": freq})
    return dict(result)


def get_jobs_count() -> int:
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.close()
    return count


def run_gap_analysis(profile_data: dict, api_key: str) -> dict:
    """Run Claude gap analysis: top market skills vs. candidate profile."""
    top_skills = get_frequency_report(top_n=30)
    if not top_skills:
        return {"covered": [], "gaps": [], "summary": "No job data yet. Paste job descriptions first to build your skill frequency database."}

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""Here are the top skills ranked by how often they appear across job descriptions this candidate has applied to:

{json.dumps(top_skills, indent=2)}

Here is the candidate's full profile:

{json.dumps(profile_data, indent=2)}

Perform a gap analysis."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=GAP_ANALYSIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(raw)


def clear_database():
    """Wipe all stored keyword data (useful for resetting)."""
    _ensure_db()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM job_keywords")
    conn.execute("DELETE FROM jobs")
    conn.commit()
    conn.close()
