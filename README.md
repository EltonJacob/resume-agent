# Resume Agent

An AI-powered resume tailoring agent that generates a customized one-page PDF resume from your profile for any job description. Built with Claude (Anthropic), Streamlit, and WeasyPrint.

## What it does

- **Resume Generator** — paste a job description, get a tailored one-page PDF resume. The agent selects the most relevant experiences, projects, and skills from your profile and rephrases them to align with the job's keywords. A built-in editor agent reviews the first draft and a second pass refines it.
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

### 4. Create your profile

Copy the example profile and fill it in with your own information:

```bash
cp profile.example.json profile.json
```

Open `profile.json` and replace the fictional data with your own:
- Personal info (name, email, phone, LinkedIn, GitHub)
- Professional experience with bullet points describing your work
- Projects with technologies and bullet points
- Education, certifications, and skills

The more detail you add to your bullet points, the better the agent can tailor them to specific jobs.

### 5. Run the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Usage

1. Open the **Resume Generator** tab
2. Paste a full job description into the text area
3. Click **Generate Tailored Resume**
4. Review the preview and download the PDF
5. Switch to the **Keyword Tracker** tab after several jobs to see your gap analysis

## Project structure

```
resume-agent/
  agent.py              # Claude tailoring logic (generate → critique → revise)
  app.py                # Streamlit UI
  keyword_agent.py      # Skill extraction and gap analysis
  pdf_generator.py      # HTML → PDF rendering with WeasyPrint
  resume_template.html  # Jinja2 HTML template for the PDF
  profile.example.json  # Example profile — copy to profile.json and fill in your data
  .env.example          # Environment variable template
  requirements.txt      # Python dependencies
```

## Notes

- `profile.json` is gitignored — your personal data never leaves your machine
- Generated PDFs are saved to `generated_resumes/` (also gitignored)
- Keyword data is stored locally in `data/keywords.db` (also gitignored)
- The agent uses Claude Sonnet for resume generation and Claude Haiku for the editor review and keyword extraction
