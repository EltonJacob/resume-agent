import copy
import json
import re
import anthropic


_ML_AI_KEYWORDS = [
    r'\bmachine learning\b', r'\bml\b', r'\bdeep learning\b', r'\bartificial intelligence\b',
    r'\bai\b', r'\bdata science\b', r'\bmlops\b', r'\bllm\b', r'\bneural network\b',
    r'\bcomputer vision\b', r'\bnlp\b', r'\bpytorch\b', r'\btensorflow\b',
]

_PYTORCH_CERT_NAMES = [
    "PyTorch: Fundamentals",
    "PyTorch: Techniques and Ecosystem Tools",
    "PyTorch: Advanced Architectures and Deployment",
]


_SWE_KEYWORDS = [
    r'\bsoftware engineer\b', r'\bsoftware developer\b', r'\bbackend engineer\b',
    r'\bfull.?stack engineer\b', r'\bfull.?stack developer\b', r'\bfrontend engineer\b',
    r'\bweb developer\b', r'\bapplication developer\b', r'\bplatform engineer\b',
]

_FAANG_COMPANIES = [
    r'\bapple\b', r'\bgoogle\b', r'\bmeta\b', r'\bamazon\b', r'\bnetflix\b',
    r'\bmicrosoft\b', r'\bfacebook\b', r'\bdeepmind\b', r'\bopenai\b', r'\banthropics\b',
]

_AGENTIC_KEYWORDS = [
    r'\bai agent\b', r'\bagent\b', r'\bagentic\b', r'\bmulti.?agent\b',
    r'\bautonomous agent\b', r'\borchestrat\b', r'\btool use\b', r'\bfunction calling\b',
    r'\bllm agent\b', r'\bagent workflow\b', r'\bagent framework\b',
]

_FOUNDING_KEYWORDS = [
    r'\bfounder\b', r'\bfounding\b', r'\bfounding engineer\b', r'\bstartup\b',
    r'\bearly.?stage\b', r'\bseed.?stage\b', r'\bseries a\b', r'\bseries b\b',
    r'\bpre.?seed\b', r'\bzero.?to.?one\b', r'\b0.?to.?1\b',
]

_MODERN_STACK_KEYWORDS = [
    r'\bnext\.?js\b', r'\breact 19\b', r'\bfastapi\b', r'\bclaude\b', r'\bllm\b',
    r'\banthropic\b', r'\bopenai\b', r'\bagentic\b', r'\bmulti.?agent\b',
    r'\bvercel\b', r'\bstripe\b', r'\bprisma\b', r'\bpostgres\b', r'\baws\b',
    r'\blangchain\b', r'\brag\b', r'\bretrieval.augmented\b', r'\bvector\b',
    r'\bfine.?tun\b', r'\bdiffusion\b', r'\blora\b', r'\btransformer\b',
]

_ENTERPRISE_LEGACY_KEYWORDS = [
    r'\b\.net\b', r'\basp\.?net\b', r'\bc#\b', r'\bangular\b', r'\bscala\b',
    r'\bjava ee\b', r'\bj2ee\b', r'\bspring\b', r'\bsap\b', r'\bsybase\b',
    r'\bdb2\b', r'\bjenkins\b', r'\bnuget\b', r'\bfinance\b', r'\bbanking\b',
    r'\bpayroll\b', r'\bsecurities\b', r'\btrading\b', r'\bmorgan stanley\b',
    r'\bfinancial services\b',
]


def _detect_faang_ml_role(job_description: str) -> bool:
    """Return True if applying to a FAANG/top-tier company AND the role is ML/AI related."""
    text = job_description.lower()
    is_faang = any(re.search(p, text) for p in _FAANG_COMPANIES)
    is_ml = any(re.search(p, text) for p in _ML_AI_KEYWORDS)
    return is_faang and is_ml


def _detect_agentic_role(job_description: str) -> bool:
    """Return True if the job description emphasizes AI agents or agentic workflows."""
    text = job_description.lower()
    return any(re.search(p, text) for p in _AGENTIC_KEYWORDS)


def _detect_founding_role(job_description: str) -> bool:
    """Return True if the JD is a founder/founding-engineer/early-stage startup role."""
    text = job_description.lower()
    return any(re.search(p, text) for p in _FOUNDING_KEYWORDS)


def _score_modern_stack(job_description: str) -> int:
    """Count distinct modern-stack keyword matches in the JD."""
    text = job_description.lower()
    return sum(1 for p in _MODERN_STACK_KEYWORDS if re.search(p, text))


def _score_enterprise_legacy(job_description: str) -> int:
    """Count distinct enterprise/legacy keyword matches in the JD."""
    text = job_description.lower()
    return sum(1 for p in _ENTERPRISE_LEGACY_KEYWORDS if re.search(p, text))


def _pick_primary_swe_role(job_description: str) -> str:
    """Return 'eldonya', 'morgan_stanley', or 'tied' based on JD keyword overlap.

    Eldonya wins when the JD leans modern (Next.js, FastAPI, Claude, LLM, agentic, AWS, Stripe).
    Morgan Stanley wins when the JD leans enterprise/legacy (.NET, C#, Angular, Scala, finance).
    On a tie or low signal, Eldonya wins because it is the most recent role and uses current tech.
    """
    modern = _score_modern_stack(job_description)
    legacy = _score_enterprise_legacy(job_description)
    if legacy > modern + 1:
        return "morgan_stanley"
    return "eldonya"


def _detect_swe_fulltime_role(job_description: str, job_type: str) -> bool:
    """Return True if the job is a full-time software engineering role."""
    if job_type != "fulltime":
        return False
    text = job_description.lower()
    return any(re.search(p, text) for p in _SWE_KEYWORDS)


def _detect_ml_role(job_description: str) -> bool:
    """Return True if the job description is ML/AI related."""
    text = job_description.lower()
    return any(re.search(p, text) for p in _ML_AI_KEYWORDS)


def _group_pytorch_certs(resume: dict) -> dict:
    """Collapse the 3 PyTorch certs into a single grouped line entry."""
    certs = resume.get("certifications", [])
    pytorch_certs = [c for c in certs if c.get("name") in _PYTORCH_CERT_NAMES]
    other_certs = [c for c in certs if c.get("name") not in _PYTORCH_CERT_NAMES]

    if len(pytorch_certs) >= 2:
        grouped = {
            "name": "PyTorch: Fundamentals · Techniques & Ecosystem · Advanced Architectures",
            "issuer": pytorch_certs[0].get("issuer", "Deeplearning.ai"),
            "date": pytorch_certs[-1].get("date", ""),
        }
        resume["certifications"] = other_certs + [grouped]
    return resume


def _detect_job_type(job_description: str) -> str:
    """Return 'internship' or 'fulltime' based on job description keywords."""
    text = job_description.lower()
    internship_patterns = [r'\bintern\b', r'\binternship\b', r'\bco-op\b', r'\bcoop\b']
    for pattern in internship_patterns:
        if re.search(pattern, text):
            return "internship"
    return "fulltime"


def _apply_job_type_overrides(profile_data: dict, job_type: str) -> dict:
    """Return a copy of profile_data with email and Masters graduation_date adjusted."""
    profile = copy.deepcopy(profile_data)

    if job_type == "internship":
        profile["personal_info"]["email"] = "jacobe4@gator.uhd.edu"
    else:
        profile["personal_info"]["email"] = "eltonsj9@gmail.com"
        # Remove graduation_date from Masters (graduate) degree
        for edu in profile.get("education", []):
            degree = edu.get("degree", "").lower()
            if "master" in degree or "m.s" in degree or "ms " in degree:
                edu.pop("graduation_date", None)

    return profile


SYSTEM_PROMPT = """You are a resume tailoring agent. Your job is to create a tailored ONE-PAGE resume from a candidate's profile data optimized for a specific job description.

CRITICAL RULES:
1. ONLY use information from the provided profile data. NEVER invent or fabricate anything.
2. You may rephrase bullet points to align with the job description keywords, but facts must stay truthful.
3. Select only the most relevant subset of experiences, projects, and skills.
4. If the candidate lacks experience in an area, do NOT add it.
5. NEVER add technologies, tools, frameworks, or languages to a bullet point unless that exact tool already appears in that role's original bullet points. You may reword sentences, but do NOT insert new technology names. For example, if a role's bullets only mention C# and SQL, do NOT add Python, PyTorch, or any other tool.
6. NEVER make bullet points vague. Every rephrased bullet must preserve: (a) the specific tools/technologies mentioned in the original, (b) any quantitative metrics (percentages, time saved, counts), and (c) the concrete action taken. Do NOT replace specific tool names with generic terms like "systems integration", "automation tools", or "workflow platform".
7. NEVER write filler bullets. Bullets like "Built and maintained scalable web applications with clean, maintainable code" or "Collaborated with cross-functional teams to deliver high-quality software" are forbidden — they describe what every engineer does and add no value. Every bullet must mention a specific system, tool, metric, or outcome that is unique to that role.

ONE-PAGE CONSTRAINTS — FILL THE PAGE BUT DO NOT EXCEED IT:
The resume must fit on exactly one page with NO empty space at the bottom. Every line of available space must be used. Use all available space effectively.
- Do NOT include a summary field (set to empty string "").
- Professional experience: include ALL positions. Each bullet should be 1-2 lines long (80-180 characters). Rephrase to include job-relevant keywords.
  - Apple (Machine Learning Engineer Intern): default is 4 bullet points. Give 5-6 bullets ONLY if the role is ML/AI-heavy or the company is Apple. Never fewer than 4.
  - For software engineering full-time roles: give Morgan Stanley Software Engineer the most bullet points (5-6). Give UHD Student Assistant 2-3 bullets. Give Morgan Stanley Intern 2 bullets.
  - For all other roles: use 5 bullet points for the most recent/relevant role, 4 (default) for Apple, and 2 for internships/student roles.
- Projects: include EXACTLY 3 project entries. For EVERY project entry, the "technologies" field MUST be fully populated from the project's source data — never leave it empty or sparse. The technologies are displayed directly on the resume after the project name as: "Project Name | Python, React, OpenAI GPT-4, ..." so they must be complete and accurate. Actively look for opportunities to combine two projects into one entry when they share a theme and together demonstrate a stronger skillset than either alone. To combine: set "name" to the primary project's name, set "combined_name" to e.g. "Multi-Agent Research System & AI Business Assistant", merge and deduplicate technologies from BOTH projects, and write 3 bullets drawing from both projects. When NOT to combine: if a project stands strongly on its own (e.g. Eldonya Autopilot — deployed, production, real business impact). Otherwise leave "combined_name" as empty string "". Never fewer than 3 bullets per project entry. Good candidates to combine: Multi-Agent Research System + AI Business Assistant (both multi-agent LLM systems), AI vs. Real Image Classifier + AI Powered Request Dispatcher (both PyTorch/ML classification), PageRank + Line Editor (both C++ data structures).
- Skills: include 3-4 of the most relevant skill categories. Include enough skills per category to fill the line width.
- Education: include as-is. Include graduation_date if present in the input — do NOT add or invent one if it is missing. Include relevant_coursework for the graduate degree (pick 4-6 most relevant courses) but set to empty list for undergraduate.
- Certifications: ALWAYS include ALL certifications from the profile. Never omit any. Certifications always appear at the BOTTOM of the resume, after education.
- Non-professional experience: include if there is remaining space and it adds value. Include it when the page would otherwise have empty space at the bottom — use 1-2 bullet points only.
- The goal is a FULL one-page resume — not sparse, not overflowing. If the page still has empty space after following the rules above, add more bullet points to the most relevant roles or expand project bullets until the page is full.

OUTPUT: Return ONLY a valid JSON object (no markdown fences, no extra text) with this structure:
{
  "personal_info": { ...same as input... },
  "summary": "",
  "professional_experience": [
    {
      "company": "...",
      "role": "...",
      "location": "...",
      "start_date": "...",
      "end_date": "...",
      "bullet_points": ["short bullet 1", "short bullet 2"]
    }
  ],
  "non_professional_experience": [],
  "projects": [
    {
      "name": "...",
      "combined_name": "",
      "description": "",
      "technologies": ["..."],
      "bullet_points": ["short bullet"],
      "url": ""
    }
  ],
  "education": [{ ...same as input but with "relevant_coursework": []... }],
  "certifications": [],
  "skills": {
    "category_name_from_input": ["skill1", "skill2"]
  }
}

IMPORTANT: Use the EXACT same skill category keys as the input profile (e.g. "Languages", "ML/AI Techniques & Models"). Do NOT rename or create new category keys."""


EDITOR_PROMPT = """You are a resume editor/critic. You review tailored resumes against job descriptions and provide actionable feedback to improve them.

Given a job description and a tailored resume (JSON), critique the resume on:

1. **Keyword alignment**: Are the most important keywords and phrases from the job description reflected in the resume? Which ones are missing?
2. **Bullet point impact**: Are bullet points results-oriented with quantifiable metrics? Are they concise (1-2 lines)? Do they use strong action verbs?
3. **Skill relevance**: Are the selected skill categories the best match for this job? Should any be swapped?
4. **Project selection**: Are the chosen projects the most relevant? Should different ones be highlighted?
5. **Content prioritization**: Is the most relevant experience given proper emphasis (more bullet points)?
6. **Missing opportunities**: Are there experiences or skills from the profile that should be included but weren't?

IMPORTANT CONSTRAINTS:
- Do NOT suggest adding skills or experiences that are not in the candidate's profile.
- Focus on better selection and rephrasing of EXISTING content.
- Keep suggestions concrete and specific.

Return your feedback as plain text with numbered suggestions. Be direct and specific."""


def _parse_json_response(response_text: str) -> dict:
    """Parse JSON from Claude's response, stripping markdown fences if present."""
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Claude's response: {e}\n\nRaw response (last 300 chars): ...{text[-300:]}")


def _format_notes(notes: str) -> str:
    """Format candidate notes as a soft-guidance block for injection into prompts."""
    if not notes or not notes.strip():
        return ""
    return (
        "\n\nCANDIDATE NOTES (soft guidance — follow where possible, but one-page constraint always takes priority):\n"
        + notes.strip()
        + "\n"
    )


def _generate_initial_resume(profile_data: dict, job_description: str, client, context_hint: str = "", notes: str = "") -> dict:
    """Step 1: Generate the initial tailored resume."""
    user_message = f"""Here is the candidate's full profile data:

{json.dumps(profile_data, indent=2)}

Here is the job description to tailor the resume for:

{job_description}
{context_hint}{_format_notes(notes)}
Please create a tailored resume by selecting and rephrasing the most relevant content from the profile. Remember: do NOT add anything that is not in the profile data."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return _parse_json_response(response.content[0].text)


def critique_resume(tailored_resume: dict, job_description: str, client, notes: str = "") -> str:
    """Step 2: Editor agent critiques the resume against the job description."""
    user_message = f"""Here is the job description:

{job_description}
{_format_notes(notes)}
Here is the tailored resume to review:

{json.dumps(tailored_resume, indent=2)}

Please provide specific, actionable feedback to improve this resume's alignment with the job description. If candidate notes were provided above, also check whether the resume follows them and flag any that were not honored."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=EDITOR_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return response.content[0].text.strip()


def revise_resume(profile_data: dict, job_description: str, initial_resume: dict, feedback: str, client, context_hint: str = "", notes: str = "") -> dict:
    """Step 3: Resume agent revises the resume based on editor feedback."""
    user_message = f"""Here is the candidate's full profile data:

{json.dumps(profile_data, indent=2)}

Here is the job description to tailor the resume for:

{job_description}
{context_hint}{_format_notes(notes)}
Here is the initial tailored resume:

{json.dumps(initial_resume, indent=2)}

Here is feedback from an editor reviewing the resume against the job description:

{feedback}

Please create an improved version of the resume incorporating the editor's feedback. Use ONLY information from the profile data — do NOT fabricate anything. Return the complete resume JSON."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return _parse_json_response(response.content[0].text)


def tailor_resume(profile_data: dict, job_description: str, api_key: str, progress_callback=None, notes: str = "") -> tuple[dict, str]:
    """Use Claude to tailor resume content to a job description with editor review.

    Workflow: Generate → Critique → Revise

    Args:
        profile_data: The candidate's full profile as a dict.
        job_description: The job posting text.
        api_key: Anthropic API key.
        progress_callback: Optional callable to report progress (receives a status string).

    Returns:
        A tuple of (tailored resume dict, editor feedback string).
    """
    client = anthropic.Anthropic(api_key=api_key)

    job_type = _detect_job_type(job_description)
    profile_data = _apply_job_type_overrides(profile_data, job_type)

    context_hint = ""
    if _detect_swe_fulltime_role(job_description, job_type):
        primary = _pick_primary_swe_role(job_description)
        if primary == "eldonya":
            context_hint += (
                "\nIMPORTANT PRIORITIZATION: This is a full-time software engineering role with a modern-stack lean. "
                "Eldonya is the PRIMARY experience — give it 5-6 bullet points selected for maximum keyword overlap "
                "with the JD (Next.js, React, TypeScript, FastAPI, PostgreSQL, AWS, Stripe, Python, Claude, multi-agent, etc.). "
                "Give Morgan Stanley Software Engineer 3-4 bullets focused on the legacy/data tools that still align (REST APIs, SQL, CI/CD, Agile). "
                "Give Apple ML Engineer Intern exactly 4 bullets. Give UHD Student Assistant 2-3 bullets. Give Morgan Stanley Intern 2 bullets. "
                "Do NOT write filler bullets for any role.\n"
            )
        else:
            context_hint += (
                "\nIMPORTANT PRIORITIZATION: This is an enterprise/legacy-leaning software engineering role. "
                "Morgan Stanley Software Engineer is the PRIMARY experience — give it 5-6 bullet points. "
                "Every Morgan Stanley bullet MUST include a specific tool (Angular, Scala, ASP.NET, C#, SQL, Jenkins, NuGet, SAP BI, Sybase, DB2), "
                "a concrete action (redesigned, migrated, automated, developed), and a metric or outcome where available. "
                "Give Eldonya 3-4 bullets emphasizing backend, database, infrastructure, and full-stack work that maps to the JD. "
                "Give Apple ML Engineer Intern exactly 4 bullets. Give UHD Student Assistant 2-3 bullets. Give Morgan Stanley Intern 2 bullets. "
                "Do NOT write filler bullets for any role.\n"
            )

    if _detect_faang_ml_role(job_description):
        context_hint += (
            "\nIMPORTANT PRIORITIZATION OVERRIDE: This is a ML/AI role at a top-tier tech company (Apple, Google, Meta, Amazon, etc.). "
            "Give the Apple ML Engineer Intern role 5-6 bullet points — this is an ML/AI role at a top company so Apple is the primary experience. "
            "Highlight: anomaly detection on 1M+ telemetry data points, SHAP explainability, Isolation Forest/VAE models, PostgreSQL schema, and hardware validation impact. "
            "Give Eldonya 4-5 bullets focused on multi-agent system, Claude API integration, LoRA fine-tuning, and Claude Vision work. "
            "Give Morgan Stanley 2-3 bullets focusing on data, automation, and engineering aspects. "
            "Give other roles 2 bullets each.\n"
        )

    if _detect_agentic_role(job_description):
        context_hint += (
            "\nIMPORTANT PROJECT PRIORITIZATION: This role involves AI agents or agentic workflows. "
            "You MUST include 'Eldonya Autopilot — AI-Powered E-Commerce Operations Platform' as the "
            "FIRST and most prominent project. It is a deployed, production multi-agent system — 11 specialized "
            "agents (asyncio.gather), 9-rule cross-reference engine, Claude Haiku with prompt caching, "
            "Slack Socket Mode human-in-the-loop approval, deployed to AWS Lightsail. "
            "Strongly consider 'Eldonya AI Image Platform — LoRA Product Image Generation' as the SECOND project — "
            "it is a three-agent system (prompt agent, Claude Vision competitor agent, retrain agent) with a self-learning loop. "
            "Give Eldonya the most bullets in professional experience (5-6), heavily weighting autopilot and media-platform bullets.\n"
        )

    if _detect_founding_role(job_description):
        context_hint += (
            "\nIMPORTANT PRIORITIZATION: This is a founder, founding-engineer, or early-stage startup role. "
            "Eldonya is the PRIMARY experience — give it 6 bullet points. The FIRST bullet MUST be the one starting with "
            "'Founded and operate Eldonya' to establish ownership and cross-surface scope. Then select 5 technical bullets "
            "that span all three surfaces (marketplace, AI ad-ops, AI media) to demonstrate end-to-end engineering breadth. "
            "Include BOTH 'Eldonya Autopilot' and 'Eldonya AI Image Platform' as two of the three project entries.\n"
        )

    # Always include guidance on the Eldonya founder-context bullet so it isn't picked for non-founding roles.
    if not _detect_founding_role(job_description):
        context_hint += (
            "\nELDONYA BULLET SELECTION: The Eldonya bullet that begins 'Founded and operate Eldonya' is a "
            "FOUNDER-CONTEXT bullet. Do NOT include it for this JD. Select only technical bullets that name "
            "specific tools, metrics, and concrete actions.\n"
        )

    # Step 1: Generate initial resume (retry once on parse failure)
    if progress_callback:
        progress_callback("Step 1/3: Generating initial resume...")
    for attempt in range(2):
        try:
            initial_resume = _generate_initial_resume(profile_data, job_description, client, context_hint, notes)
            break
        except ValueError:
            if attempt == 1:
                raise
            if progress_callback:
                progress_callback("Step 1/3: Retrying initial resume generation...")
    validate_against_profile(initial_resume, profile_data)

    # Step 2: Editor critiques the resume
    if progress_callback:
        progress_callback("Step 2/3: Editor reviewing resume...")
    feedback = critique_resume(initial_resume, job_description, client, notes)

    # Step 3: Revise based on feedback (retry once on parse failure)
    if progress_callback:
        progress_callback("Step 3/3: Finalizing resume with feedback...")
    for attempt in range(2):
        try:
            final_resume = revise_resume(profile_data, job_description, initial_resume, feedback, client, context_hint, notes)
            break
        except ValueError:
            if attempt == 1:
                raise
            if progress_callback:
                progress_callback("Step 3/3: Retrying revision...")
    validate_against_profile(final_resume, profile_data)

    if _detect_ml_role(job_description):
        final_resume = _group_pytorch_certs(final_resume)

    final_resume = _sanitize_bullets(final_resume)

    return final_resume, feedback


def _clean_bullet(text: str) -> str:
    """Fix common punctuation and formatting artifacts in a bullet point."""
    # Remove empty parentheses: (), (,), ( ), (  )
    text = re.sub(r'\(\s*,?\s*\)', '', text)
    # Remove parentheses with only punctuation/spaces inside: (, ) or (. ) etc.
    text = re.sub(r'\(\s*[,./\s]+\s*\)', '', text)
    # Fix dangling comma before closing paren: (Scala,) -> (Scala)
    text = re.sub(r',\s*\)', ')', text)
    # Fix leading comma after opening paren: (, Scala) -> (Scala)
    text = re.sub(r'\(\s*,\s*', '(', text)
    # Fix " /with" or "/with" artifacts -> "with"
    text = re.sub(r'\s*/with\b', ' with', text)
    text = re.sub(r'\bsecond to\b\s*/?\s*', '', text)
    # Fix double spaces left behind after removals
    text = re.sub(r'  +', ' ', text)
    # Fix trailing/leading punctuation artifacts like " ," or " ." or ", ."
    text = re.sub(r'\s+,', ',', text)
    text = re.sub(r',\s*,', ',', text)
    return text.strip().strip(',').strip()


def _sanitize_bullets(resume: dict) -> dict:
    """Run _clean_bullet over all bullet points in experience and projects."""
    for exp in resume.get("professional_experience", []):
        exp["bullet_points"] = [_clean_bullet(b) for b in exp.get("bullet_points", [])]
    for exp in resume.get("non_professional_experience", []):
        exp["bullet_points"] = [_clean_bullet(b) for b in exp.get("bullet_points", [])]
    for proj in resume.get("projects", []):
        proj["bullet_points"] = [_clean_bullet(b) for b in proj.get("bullet_points", [])]
    return resume



def validate_against_profile(tailored: dict, original: dict) -> None:
    """Validate and sanitize the tailored resume against the original profile."""
    # --- Companies ---
    original_companies = {
        exp["company"] for exp in original.get("professional_experience", [])
    }
    # non_professional_experience uses "organization" key — include them so the
    # validator doesn't flag them as fabricated if the LLM places them in experience
    original_companies |= {
        exp["organization"] for exp in original.get("non_professional_experience", [])
        if "organization" in exp
    }
    tailored_companies = {
        exp["company"] for exp in tailored.get("professional_experience", [])
    }
    fabricated_companies = tailored_companies - original_companies
    if fabricated_companies:
        raise ValueError(f"Fabricated companies detected: {fabricated_companies}")

    # --- Projects ---
    # Allow combined entries (combined_name set) as long as the base "name" field
    # still references a real project from the original profile.
    original_projects = {p["name"] for p in original.get("projects", [])}
    tailored["projects"] = [
        p for p in tailored.get("projects", []) if p["name"] in original_projects
    ]

    # --- Skills ---
    original_text = json.dumps(original).lower()
    for category, items in tailored.get("skills", {}).items():
        if isinstance(items, list):
            tailored["skills"][category] = [
                s for s in items if s.strip().lower() in original_text
            ]

    # Bullet text is governed by the system prompt (Rule 5) which forbids adding
    # technologies not present in the original role. We do not strip bullet text
    # here because regex-based removal mangles sentence structure.
