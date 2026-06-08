# Resume Agent

An AI-powered resume tailoring agent that generates a customized one-page PDF resume from your profile for any job description. Built with Claude (Anthropic), Streamlit, and WeasyPrint.

## What it does

- **Resume Generator** — paste a job description, get a tailored one-page PDF resume. The agent selects the most relevant experiences, projects, and skills from your profile and rephrases them to align with the job's keywords. A built-in editor agent reviews the first draft and a second pass refines it.
- **My Profile** — build your profile directly in the app. Paste your existing resume and Claude extracts everything automatically — no JSON editing required.
- **Template Studio** — upload a resume you like the look of (or answer a few style questions) and Claude generates a custom PDF template matching that design.
- **Keyword Tracker** — every job description you process gets analyzed for skills and keywords. Over time it builds a frequency map of what the market wants, runs a gap analysis against your profile, and tells you what to learn next.

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/your-username/resume-agent.git
cd resume-agent
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** WeasyPrint requires system-level libraries. If PDF generation fails, follow the [WeasyPrint installation guide](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html) for your OS.

### 3. Add your Anthropic API key

Copy the example env file and add your key:

```bash
cp .env.example .env
```

Then edit `.env`:

```
ANTHROPIC_API_KEY=your-key-here
```

Get a key at [console.anthropic.com](https://console.anthropic.com).

### 4. Build your profile

Run the app and open the **My Profile** tab. Paste your existing resume text into the import box and click **Parse Resume** — Claude will extract all your experience, projects, education, and skills automatically. Review the result, make any edits, and click **Save Profile**.

If you prefer to start from a template manually:

```bash
cp profile.example.json profile.json
```

Then edit `profile.json` with your own information. The more detail you add to your bullet points, the better the agent can tailor them to specific jobs.

### 5. Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Usage

1. **My Profile** tab — paste your resume and let Claude build your profile, or fill in the form manually. Save when done.
2. **Template Studio** tab (optional) — upload a resume whose style you like, or answer the style questionnaire to generate a custom PDF template.
3. **Resume Generator** tab — paste a job description and click Generate. Download the tailored PDF.
4. **Keyword Tracker** tab — after several jobs, run a gap analysis to see what skills to learn next.

## Project structure

```
resume-agent/
  agent.py                      # Claude tailoring logic (generate → critique → revise)
  app.py                        # Streamlit UI
  profile_form.py               # Profile editor form (all sections)
  resume_parser.py              # Claude-powered resume text → profile extraction
  template_generator.py         # Claude Vision style extraction + template generation
  keyword_agent.py              # Skill extraction and gap analysis
  pdf_generator.py              # HTML → PDF rendering with WeasyPrint
  resume_template_default.html  # Default Jinja2 PDF template (shipped with repo)
  profile.example.json          # Example profile schema
  .env.example                  # Environment variable template
  requirements.txt              # Python dependencies
```

## Contributing

This is a personal project — feel free to fork it and make it your own.

**To fork:**
1. Click the **Fork** button at the top-right of this page on GitHub
2. Clone your fork: `git clone https://github.com/your-username/resume-agent.git`
3. Make your changes on a new branch: `git checkout -b my-feature`
4. Push to your fork: `git push origin my-feature`

If you fix a bug or build something useful, open a Pull Request and I'll take a look.

## Notes

- `profile.json` is gitignored — your personal data never leaves your machine
- Generated PDFs are saved to `generated_resumes/` (also gitignored)
- `resume_template.html` (your active template) is gitignored — the default ships as `resume_template_default.html`
- Keyword data is stored locally in `data/keywords.db` (also gitignored)
- The agent uses Claude Sonnet for resume generation and Claude Opus for template generation; Claude Haiku for editor review and keyword extraction
