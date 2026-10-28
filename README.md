# ASC Assistant

A private AI chat assistant for the **Ad Standards Council (ASC) Philippines** guidelines. It
pre-screens **advertising images** (billboards and other out-of-home ads) before they go to official
ASC screening.

It works like a chat. Attaching an image is **optional**:

- **Ask a question** (no image), e.g. *"What must a beer billboard include?"*. The assistant answers
  from the ASC rules, looking up the exact wording in the ASC Guidebook and citing the rule.
- **Attach an ad image** (with or without a message). It's checked against the ASC guidelines, and
  the answer says whether it looks **compliant** or **non-compliant**, with the ASC rule, the evidence
  from the ad and how to fix every problem.
- **Ask follow-ups** about a check, e.g. *"How do I fix issue 2?"*. The assistant remembers the result.

Everything runs **on your own computer**: no internet, account or API key is needed once it's set up,
and images never leave the machine.

> **This is a pre-screen, not an ASC decision.** A person must always review the result.

This is the Python version of the n8n workflow **"ASC v3"**. It does the same steps with the same
prompts, the same rule summaries and the same Qdrant guidelines (see [How it maps to n8n](#how-it-maps-to-the-n8n-workflow)).

---

## Contents

1. [What it does (in plain words)](#1-what-it-does-in-plain-words)
2. [Words you'll see in this guide](#2-words-youll-see-in-this-guide)
3. [What you need](#3-what-you-need)
4. [Installation, step by step](#4-installation-step-by-step)
5. [Everyday use](#5-everyday-use)
6. [How it works inside](#6-how-it-works-inside)
7. [The files in this project](#7-the-files-in-this-project)
8. [Settings](#8-settings)
9. [Changing prompts, rules and models](#9-changing-prompts-rules-and-models)
10. [Troubleshooting](#10-troubleshooting)
11. [Known limits](#11-known-limits)
12. [Web API reference](#12-web-api-reference)

---

## 1. What it does (in plain words)

```
  ┌───────────┐   1. DESCRIBE    ┌──────────────┐   2. CHECK RULES    ┌──────────────┐   3. VERIFY    ┌──────────┐
  │ Ad image  │ ───────────────▶ │ Written      │ ──────────────────▶ │ AI verdict   │ ─────────────▶ │  Result  │
  │ (JPG/PNG) │  minicpm-v:8b    │ description  │  gpt-oss:20b reads  │ (JSON)       │  Python code   │  page    │
  └───────────┘  looks at the    │ of the ad    │  the ASC rules and  └──────────────┘  removes made- └──────────┘
                 image           └──────────────┘  searches the ASC                    up problems,
                                                   Guidebook in Qdrant                 adds missed
                                                                                       decency issues
```

1. **Describe:** a vision model (**minicpm-v:8b**) looks at the image and writes down everything it sees:
   all text, the product, claims, warnings and fine print, people, and other visuals.
2. **Check the rules:** a reasoning model (**gpt-oss:20b**) compares that description with the ASC rule
   checklist. Along the way it searches the **ASC Guidebook** (stored in Qdrant as `asc_guidelines`)
   for the exact rule wording.
3. **Verify:** Python code double-checks the AI's answer:
   - It **removes** "violations" the AI made up, such as rules for the wrong product type, a
     "missing" warning that is actually there, or evidence that isn't in the ad.
   - It **adds** decency problems the AI missed, such as revealing clothing or intimate poses.
   - It attaches a **plain-language explanation** of every ASC rule.
4. **Result:** the verdict and findings appear in the chat. You record your own decision
   (Approve / Revise / Reject) and download a **PDF report**.

**Messages without an image** go straight to the reasoning model (gpt-oss:20b) with the full ASC rule
checklist. It searches the ASC Guidebook when it needs the exact wording, then answers. A safety check
flags any measurement in the answer (e.g. "12 pt", "1 inch") that isn't in the ASC rules, so made-up
requirements are clearly marked.

---

## 2. Words you'll see in this guide

| Word | What it means |
|---|---|
| **ASC** | Ad Standards Council, the body that screens ads in the Philippines. Its rules are in the ASC Guidebook (Code of Ethics and Manual of Procedures). |
| **OOH** | Out-of-home advertising: billboards, posters, transit ads. Seen by everyone, so the decency rules are strict. |
| **AI model** | The "brain" that reads and writes. This tool uses two: a **vision model** that can see images, and a **judge model** that reasons about rules. |
| **Ollama** | A free program that runs AI models on your computer. |
| **Qdrant** | A database that finds text **by meaning**. It holds the ASC Guidebook, cut into ~1,000-character passages. |
| **Embedding** | A list of numbers representing the meaning of a text. Searching compares these numbers. Made by **nomic-embed-text**. |
| **Collection** | One "table" in Qdrant. Ours is called `asc_guidelines`. |
| **Tool** | A function the AI is allowed to call. Here: `asc_guidelines`, which searches the guidebook. |
| **Prompt** | The written instructions given to an AI model. Ours are in the `prompts` folder. |
| **Docker** | A program that runs other programs in "containers". Qdrant (and n8n) run in Docker. |
| **Terminal** | A window where you type commands. On Windows use **PowerShell**: press Start, type `PowerShell`, press Enter. |
| **uv** | A tool that installs Python and this project's libraries, and runs the project. |
| **n8n** | A visual workflow tool. The first version of this checker was an n8n workflow. |

---

## 3. What you need

**Computer**

| | Minimum | Recommended |
|---|---|---|
| Operating system | Windows 10/11 | Windows 11 |
| Memory (RAM) | 16 GB | 32 GB |
| Graphics card | NVIDIA with 8 GB (slow) | NVIDIA with **16 GB** or more |
| Free disk space | 30 GB | 40 GB |

> The graphics card matters a lot. Without one, a check can take 10 minutes or more. The NVIDIA
> driver must be **version 531 or newer** (see [Troubleshooting](#the-check-is-very-slow)).

**Programs** (installed in the steps below)

- **Ollama**: runs the AI models
- **Docker Desktop**: runs the Qdrant database (skip if you already run n8n with Qdrant)
- **uv**: installs Python and this project's libraries

The internet is only needed **during installation**.

---

## 4. Installation, step by step

Do this **once** per computer. Every command goes into **PowerShell**: type or paste it
(right-click pastes), then press **Enter**.

### Step 1: Install Ollama

1. Download it from **https://ollama.com/download** and run the installer.
2. A llama icon appears near the clock (bottom right), which means Ollama is running.
3. Check it:

   ```powershell
   ollama --version
   ```

### Step 2: Download the three AI models

```powershell
ollama pull minicpm-v:8b
```

The vision model that describes the image (about **5.5 GB**).

```powershell
ollama pull gpt-oss:20b
```

The judge model that checks the ASC rules (about **13 GB**).

```powershell
ollama pull nomic-embed-text
```

The search model for the guidebook (about **270 MB**).

Check that all three are listed:

```powershell
ollama list
```

### Step 3: Start the Qdrant database

> **Already using the n8n workflow?** Then Qdrant is already running with the guidelines loaded.
> Skip to Step 4.

1. Install **Docker Desktop** from **https://www.docker.com/products/docker-desktop** and start it.
2. Start Qdrant (this keeps its data in a Docker volume called `qdrant_storage`):

   ```powershell
   docker run -d --name qdrant --restart unless-stopped -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
   ```

3. Check it: open **http://localhost:6333/dashboard** in a browser. You should see the Qdrant dashboard.

### Step 4: Install uv

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Close PowerShell and open it again**, then check:

```powershell
uv --version
```

> You don't need to install Python yourself. uv downloads the right version automatically.

### Step 5: Get the project and install its libraries

1. Copy the project folder (the one with this `README.md`) to the computer.
2. Open PowerShell **in that folder**. Tip: in File Explorer, open the folder, click the address
   bar, type `powershell` and press Enter.
3. Install the libraries:

   ```powershell
   uv sync
   ```

**Every command from here on must be run inside the project folder.**

### Step 6: Load the ASC Guidebook into Qdrant

> **Skip this if the guidelines are already loaded** (for example by n8n). If they aren't, the web
> page shows a yellow **"Setup needed"** bar saying the collection is empty.

You need the ASC Guidebook as a PDF with real text (not a scan). Then:

```powershell
uv run ingest_guidelines.py "C:\path\to\ASC Guidebook.pdf"
```

You'll see progress up to 100%. It takes a few minutes.

### Step 7: Start the app

```powershell
uv run server.py
```

When you see `Open http://127.0.0.1:8000 in your browser`, open that address.

**Leave this window open** while you use the app. Press **Ctrl + C** in it to stop.

### Step 8 (optional): Change settings

Everything works with the defaults. To change something (a model, a port…):

```powershell
copy .env.example .env
```

Then edit `.env` in Notepad and restart the app. All settings are explained in [Settings](#8-settings).

---

## 5. Everyday use

### Starting the app

1. Make sure **Ollama** (llama icon near the clock) and **Docker Desktop** are running.
2. Open PowerShell in the project folder and run `uv run server.py`.
3. Open **http://127.0.0.1:8000**.

The page is a simple chat. If something isn't ready (Ollama or Qdrant not running, a model not downloaded), a yellow
**"Setup needed"** bar at the top says exactly what to do. Otherwise there's nothing to look after.

### Asking a question (no image)

1. Type your question in the box at the bottom and press **Enter**, or click one of the suggestions
   on the welcome screen. English and Filipino/Taglish both work.
2. The answer appears as it's written (about 30 seconds to 2 minutes). Under it you can open:
   - **Sources**: the ASC Guidebook searches it made and the passages it read
   - **Thinking**: its reasoning
3. A yellow **⚠ note** under an answer means it mentions a measurement (size, percentage, distance)
   that is **not** in the ASC guidelines. Treat that part as a suggestion, not a requirement.

Use **Shift + Enter** for a new line, the **■** button to stop an answer, and **New chat** (in the sidebar)
to start over.

**Chats are saved automatically** in this browser (its local storage): reloading or reopening the page
brings the conversation back, and the assistant still remembers it for follow-up questions. Your chats are listed in the
**sidebar on the left**, grouped by date: click one to reopen it, hover and click **✕** to delete it, or
use **Clear all chats** at the bottom. The sidebar's top button collapses it to a slim strip (and
expands it again); on a phone, open it with the **☰** button. The 30 most
recent chats are kept. They are stored only in this browser on this computer, not on the server, so
another browser or computer won't see them, and clearing the browser's site data deletes them.

### Checking an ad

1. **Attach the image** (JPG or PNG) in any of these ways:
   - click the **📎 paperclip** next to the message box, or the **Check an ad image** card on the welcome screen
   - drag the image anywhere onto the page
   - paste a screenshot into the message box (**Ctrl + V**)

   A preview appears above the message box (click **×** to remove it).
2. Optionally type a note, e.g. *"This will run on a billboard along EDSA"*. It's given to the AI as
   context, never treated as part of the ad.
3. Press **Enter**. A progress line shows what's happening (*Reading the image… → Checking the ASC
   rules… → Double-checking the findings…*). It takes **about 3–6 minutes** on a 16 GB graphics card.
   Under the result you can open:
   - **What the AI saw in the image**: the description the findings are based on
   - **Sources**: what the AI looked up in the ASC Guidebook, and what it found
   - **Thinking**: the AI's reasoning
4. **Read the result:**

   | Result | What you see |
   |---|---|
   | **✕ Non-compliant** | One card per problem: the problem, **what the ASC rule says** (blue box), **evidence** from the ad, **how to fix** it, and the ASC reference. Problems tagged *"Added by decency check"* were missed by the AI but found by the code. |
   | **✓ Compliant** | Why it passed, plus every check that was made (mandatory statements, claims, visuals, decency) |
   | **! Could not check** | The reason, e.g. the AI's answer wasn't readable. Just run it again. |

   **Removed by verification** (if shown) lists problems the AI raised that weren't backed by the
   image, for transparency.
5. **Review it yourself.** Compare the image with the findings, choose **Approve / Revise / Reject**,
   and add notes.
6. Click **Download PDF report** to keep a record. The PDF (A4) contains:
   - the ad image, the verdict and every finding, with the rule explanation, evidence and fix
   - your decision (ticked box) and notes, plus *Reviewed by* and *Date* lines to sign
   - an appendix with what the AI saw in the image, so anyone can see what the findings were based on

   It's saved to your Downloads folder as e.g. `ASC-prescreen-golden-lager-2026-10-23.pdf`.
7. **Ask follow-ups** in the same chat, e.g. *"How do I fix issue 1?"* or *"Why is the energy claim
   not allowed?"*. The assistant knows the result of the check above.

> The decision and notes are saved with the chat in this browser, but that isn't a lasting record:
> download the PDF to keep them. Choose the decision and write the notes **before** clicking the button.
>
> Ctrl + P also prints the page (always in light colors), but the PDF report is the cleaner record.

### Checking from the terminal (no browser)

```powershell
uv run check.py "C:\path\to\ad.png"
```

This prints the description, the searches and the result, which is handy for testing. Stop the
web server first if both would run at the same time; they share the graphics card.

---

## 6. How it works inside

### Two paths

`server.py` receives each message at `/api/chat`:

- **No image:** `app/features/chat/service.py` sends the chat instructions (`prompts/chat.md`) plus the **ASC rule
  checklist** (taken from `prompts/judge.md`, so both always use the same rules), the recent
  conversation and the question to the judge model. It may search the guidebook up to 3 times, then
  answers. Older messages are dropped when the conversation gets long, so the rules always fit in the
  AI's memory. Finally, `app/features/chat/service.py` flags measurements in the answer that don't appear in the checklist
  or the passages it read.
- **Image attached:** the three-step check below (`app/features/ad_review/service.py`). The text of the message, if any,
  is passed to the judge as a clearly marked reviewer note.

After a check, the page adds a short summary of the result (verdict, problems, fixes and the image
description) to the conversation, so follow-up questions can use it.

### The image check, step by step

**Step 1: describe** (`app/infrastructure/ollama/vision.py`)
- Sends the image to **minicpm-v:8b** through Ollama, with two prompts:
  - `prompts/describe_system.md`: "describe only, in English, don't judge", taken from the n8n node.
  - `prompts/describe.md`: the 7 sections to fill in (ALL TEXT, PRODUCT, CLAIMS, WARNINGS AND FINE
    PRINT, PEOPLE, OTHER VISUALS, UNREADABLE). It insists on copying only text that is really in the image.
- The description is streamed to the page as it's written.

**Step 2: check the rules** (`app/features/ad_review/judgment.py`)
- Sends `prompts/judge.md` (the n8n AI Agent prompt, about 8,000 tokens) with the description
  filled in, to **gpt-oss:20b**.
- The prompt holds the full **ASC rule checklist** (G general, C claims, P price/promo, R category
  rules, plus the decency checklist D1–D6). It tells the AI to call the **`asc_guidelines`** tool 2 to
  5 times to confirm rule wording.
- Each search returns the **3 closest passages** from Qdrant (`app/features/guidelines/service.py`). Repeated searches are
  refused, and passages already shown aren't sent again, to keep the AI's memory from overflowing.
- The AI answers with **JSON**: the verdict, and either the violations (rule, evidence, problem, fix,
  rule explanation) or the checks that passed.

**Step 3: verify** (`app/features/ad_review/checks.py`, the Python version of the n8n "Code in JavaScript" node)
1. **Finds the product category** in the description from keywords (beer → `R-ALC`, supplement → `R-SUPP`, …).
2. **Removes made-up violations:**
   - a category rule for a product type the ad doesn't show (e.g. milk rules on a beer ad)
   - "MISSING: …" when the statement **is** in the description
   - evidence whose words aren't in the description (needs 60% word overlap)
3. **Adds decency problems the AI missed**, by scanning the description for intimate contact
   (kissing, embracing, hands on hips…) and revealing clothing (bikini, shirtless, lingerie…). Under
   ASC Article I Section 4 and Annex 3, borderline decency counts as non-compliant for OOH.
4. **Attaches rule explanations** from `prompts/rules.json`: the plain-language summary of all 54
   ASC rule IDs (G-01…G-14, C-01…C-17, P-01…P-07, R-…). These are used first because they're always
   accurate; the AI's own summary is the fallback.
5. **Handles language problems:** if the vision model answered in Chinese (it sometimes does), the
   judge's English translation (`description_en`) is used. If there is none, the result is
   "Could not check" rather than an unchecked verdict.

### How it maps to the n8n workflow

| n8n node | Python |
|---|---|
| Upload Image (form) | `static/index.html` + `server.py` (`/api/check`) |
| Extract from File | Not needed: the browser shows the image itself |
| Analyze image (minicpm-v:8b) | `app/infrastructure/ollama/vision.py` |
| AI Agent + Ollama Chat Model (gpt-oss:20b, think) | `app/features/ad_review/judgment.py` |
| asc_guidelines (Qdrant, retrieve-as-tool, top 3) + Embeddings Ollama1 | `app/features/guidelines/service.py` |
| Code in JavaScript | `app/features/ad_review/checks.py` + `prompts/rules.json` |
| Form (completion page) | The result panel in `static/index.html`, plus a downloadable PDF report (`app/features/reports/service.py`) |
| On form submission (PDF) → Default Data Loader → Text Splitter → Qdrant Vector Store | `ingest_guidelines.py` |

Both versions use **the same Qdrant collection**, so n8n and this app can run side by side.

---

## 7. The files in this project

```text
langchain/
├── app/
│   ├── main.py                   # App factory and feature-router composition
│   ├── bootstrap.py              # Model warm-up during application startup
│   ├── core/                     # Configuration, context compaction, process coordination
│   ├── api/                      # Shared NDJSON transport and original HTML pages
│   ├── features/
│   │   ├── chat/                 # Routes, conversation handling, scope, tool search loop
│   │   ├── ad_review/            # Routes, image-check orchestration, judgment, verification
│   │   ├── documents/            # Routes, extraction and ingestion workflow
│   │   ├── guidelines/           # ASC/MACEA retrieval policy and source formatting
│   │   ├── reports/              # Routes and PDF generation
│   │   └── status/               # Routes and service readiness
│   ├── infrastructure/
│   │   ├── ollama/               # Model clients, vision requests, CPU embedding service
│   │   └── qdrant/               # Vector-store and embedding adapters
│   └── cli/                      # Command-line workflows
├── tests/                        # Regression, architecture and HTTP-contract tests
├── server.py                     # Compatible server command
├── check.py                      # Compatible image-check command
├── ingest_guidelines.py          # Compatible document-ingestion command
├── prompts/                      # Prompt text and ASC rule summaries
├── static/                       # Original HTML interface
├── documents/                    # Existing source documents
├── archive/                      # Previous implementation, retained for reference
├── .env.example
├── pyproject.toml
└── uv.lock
```

Start with `app/main.py`, then follow a feature's `routes.py` into its service.
Routes own HTTP validation and response handling. Services own the workflows.
Ollama and Qdrant adapters own external-service access. Shared transport owns the
streaming protocol, and core owns configuration and process-wide coordination.

All existing API paths and multipart/NDJSON/PDF contracts remain unchanged, so
the separate Next.js frontend needs no URL changes. Importing the application
starts no model warm-up; FastAPI's lifespan starts that work when the server runs.
Configuration and resource paths resolve from the backend project root.

Existing commands still work:

```powershell
uv run server.py
uv run check.py "path/to/ad.png"
uv run ingest_guidelines.py "path/to/guide.pdf"
```

The package can also run as `uv run -m app`, or with Uvicorn at `app.main:app`.
Run the tests from the backend root:

```powershell
uv run -m unittest discover -s tests -p "test_*.py"
node --test tests/test_chat_stream.cjs
```

See [the architecture guide](docs/architecture.md) for dependency boundaries and
how to add a feature. Internal Python imports now use the `app.*` package; old
flat-module imports are not supported. The three root CLI entrypoints are retained.

---

## 8. Settings

All settings are optional. Copy `.env.example` to `.env`, edit it, and restart the app.

| Setting | Default | What it does |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where Ollama runs. Use another computer's address to run the models there. |
| `VISION_MODEL` | `minicpm-v:8b` | Step 1 model (must be able to see images). |
| `JUDGE_MODEL` | `gpt-oss:20b` | Step 2 model. Should support **tools**, so it can search the guidelines. |
| `JUDGE_NUM_CTX` | `16384` | How much text the judge can hold. Its instructions are ~8,000 tokens and a full check peaks around 11,000–13,000. Larger values don't fit a 16 GB card and make checks **much** slower. |
| `VISION_NUM_CTX` | `8192` | How much text the vision model can hold. |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Search model. **Must be the model the guidelines were stored with.** |
| `QDRANT_URL` | `http://localhost:6333` | The Qdrant server. |
| `QDRANT_API_KEY` | (empty) | Only if your Qdrant server needs a key. |
| `QDRANT_COLLECTION` | `asc_guidelines` | The collection with the guidebook. |
| `TOP_K` | `3` | Passages returned per guideline search (n8n used 3). |
| `MAX_SEARCHES` | `5` | Most guideline searches per image. |
| `PORT` | `8000` | Web page address: `http://127.0.0.1:<PORT>`. |
| `MAX_IMAGE_MB` | `20` | Largest image accepted. |
| `CHAT_HISTORY` | `12` | How many earlier chat messages the AI sees when answering (older ones are dropped first if they don't fit). |

---

## 9. Changing prompts, rules and models

### Change what the AI is told

The instructions are plain text files in `prompts/`. Edit them in any editor and restart the app.

| File | Change it to… |
|---|---|
| `describe.md` | ask the vision model to describe something more or differently |
| `chat.md` | change how the chat assistant answers (tone, length, accuracy rules). The ASC checklist is added to it automatically from `judge.md`. |
| `judge.md` | change the ASC checklist, strictness or output format (the chat uses the same checklist). It **must** keep the `{description}` placeholder, and the JSON output format that `app/features/ad_review/checks.py` reads (`verdict`, `reasons`, `checks_passed`, …). |
| `rules.json` | change the plain-language rule summaries shown in the results |

> If you edit the prompts in n8n too, copy the changes here (or the other way round). The two
> versions don't sync automatically.

### Use different models

1. Download the model, e.g. `ollama pull llama3.2-vision:11b`.
2. Check what it can do with `ollama show <model>`:
   - **Vision model:** must list `vision`.
   - **Judge model:** should list `tools`, so it can search the guidelines. Without tools the
     header shows **"Judge can't search"**, and it relies only on the checklist in the prompt.
     `thinking` is optional.
3. Set `VISION_MODEL=` or `JUDGE_MODEL=` in `.env` and restart.

Sizes to keep in mind on a 16 GB card: the vision and judge models run **one after the other**,
so each must fit on its own. They don't need to fit together.

### Change the search model

The guidelines were stored with `nomic-embed-text`. To use another embedding model, you must
**reload the guidebook** with it: delete the `asc_guidelines` collection in the Qdrant dashboard
(http://localhost:6333/dashboard), set `EMBEDDING_MODEL=` in `.env`, and run `ingest_guidelines.py`
again. **Note:** n8n's Embeddings nodes would then need the same model.

### Add more guideline documents

```powershell
uv run ingest_guidelines.py "C:\path\to\another-guideline.pdf"
```

To replace a file you added before (after an update, for example), add `--replace` at the end.

---

## 10. Troubleshooting

### The yellow bar says "Setup needed"

It names the problem. The common ones:

| Message | Fix |
|---|---|
| Start **Ollama** | Start Ollama from the Start menu |
| Download the missing model(s) | Run the `ollama pull …` command shown |
| Start the **Qdrant** server | Open Docker Desktop and start the `qdrant` container (▶ button) |
| The collection is empty | Load the guidebook ([Step 6](#step-6-load-the-asc-guidebook-into-qdrant)) |

### The check is very slow

A normal check takes about 3 minutes on a 16 GB NVIDIA card.

1. Look at the header: **Running on CPU** (orange) means the graphics card isn't used. Run
   `nvidia-smi`; if the **Driver Version** is below 531, update the driver from
   **nvidia.com/drivers**, then restart the computer.
2. Run `ollama ps` during a check. If **PROCESSOR** shows a big CPU share (e.g. `30%/70% CPU/GPU`),
   the model doesn't fit in the card's memory:
   - Close other programs that use the graphics card (browsers with many tabs, games, 3D software).
   - Don't raise `JUDGE_NUM_CTX` above 16384.
3. Part of every check is loading the models: the vision model and the judge take turns on the
   graphics card, because both don't fit at once.

### "Could not check: The AI did not return valid JSON"

The judge's answer was cut off or badly formatted. Run the check again. If it keeps happening,
open **Thinking** under the result. If the reasoning stops mid-sentence, the AI ran out of memory: lower
`MAX_SEARCHES` to 3.

### "The image description came back in another language"

minicpm-v sometimes answers in Chinese. Run the check again. If it keeps happening, try
`VISION_MODEL=llama3.2-vision:11b`.

### The result is clearly wrong

1. Open **What the AI sees in the image**. Most mistakes start here: the vision model misread
   small text or missed something. Higher-resolution images help.
2. Open **Guideline searches** to see which rules the AI looked up.
3. Adjust `prompts/describe.md` or `prompts/judge.md` if a mistake keeps repeating.

### Port 8000 is already in use

Set `PORT=8001` in `.env` and open `http://127.0.0.1:8001`.

---

## 11. Known limits

- **It's a pre-screen.** It can't replace ASC screening, and a person must review every result.
- **It only knows what the vision model sees.** Very small, blurry or stylized text may be
  misread or missed, which can cause false "missing statement" findings.
- **Documents can't be checked.** Claims that need proof (sales data for "No. 1", research for
  "best", permits, licenses) are noted as needing documents, not flagged as violations.
- **Images only:** JPG and PNG. No video, audio or multi-page PDFs.
- **One answer at a time.** Checks and chat answers share the graphics card, so a second one waits
  (the page says "Waiting for the current check to finish"). Stopping an answer with **■** stops the
  page, but the AI finishes its current step in the background first.
- **Chat answers can still be wrong.** The assistant is told to stick to the ASC rules, and made-up
  measurements are flagged, but always check important answers against the ASC Guidebook.
- **Chats are saved only in this browser.** They aren't shared between browsers or computers, and
  clearing the browser's site data deletes them. Images are kept as compressed copies; if the browser
  runs out of storage space (about 5 MB), images of the oldest chats are removed first, then the oldest
  chats. A chat whose image was removed still shows its result, but can't make a PDF report any more.
- **Decisions aren't saved.** Use **Download PDF report**.
- **The rules are from the ASC Guidebook of March 2019** (the version loaded in Qdrant and
  summarized in the prompts). Update both if ASC publishes changes.

---

## 12. Web API reference

The server only accepts connections from this computer (`127.0.0.1`).

| Method | Address | What it does |
|---|---|---|
| `GET` | `/` | The web page |
| `GET` | `/api/status` | Readiness: `{ollama, missing_models, qdrant, passages, judge_tools, device, busy, …}` |
| `POST` | `/api/chat` | Send a chat message. Form fields: `message` (text), `history` (JSON list of `{role, content}`), and optionally `image` (JPG/PNG). With an image it runs the check; without, it answers the question. Replies with a stream of JSON lines. |
| `POST` | `/api/check` | Check an image without chat. Send it as form field `image`. Replies with a stream of JSON lines. |
| `POST` | `/api/report` | Make the PDF report. Form fields: `image` (the same image) and `data` (JSON: `{result, decision, notes, file_name}`). Replies with the PDF file. |

`/api/chat` and `/api/check` send one JSON object per line:

| `type` | Fields | Meaning |
|---|---|---|
| `queued` | | Another check is running; this one waits |
| `stage` | `value`: `describe` / `judge` / `verify` | A new step started |
| `describe` | `text` | A piece of the image description |
| `token` | `text` | A piece of a chat answer |
| `warning` | `text` | A chat answer mentions measurements not found in the ASC rules |
| `thinking` | `text` | A piece of the judge's reasoning |
| `search` | `query`, `result` | A guideline search and the passages found |
| `tokens` | `value` | How full the judge's memory is |
| `result` | `result`, `reasons`, `checks_passed`, `approval_summary`, `removed_reasons`, `description`, `seconds`, … | The final result |
| `done` | | Finished |
| `error` | `message` | Something went wrong |

Example from PowerShell:

```powershell
curl.exe -F "image=@C:\path\to\ad.png" http://127.0.0.1:8000/api/check
```

---

## Privacy

- Images are processed in memory and **never stored** by the app.
- The AI models, the guidelines and the web page all run on this computer. The page loads nothing
  from the internet.
- The internet is only used during installation, and when Ollama or Docker check for updates.


## Upload searchable documents

`prompts/macea.md` contains the MACEA retrieval and review instructions, loaded by the shared chat/image search loop. Actual MACEA requirements come from the uploaded source passages, not a hardcoded checklist.

Open `/upload` from **Upload documents** in the chat header. Upload one PDF, UTF-8 TXT/MD, DOCX, or XLSX file. The page shows extraction, embedding, and storage progress and a final passage count. Web uploads are stored in the separate `macea_guidelines` collection using the existing Ollama embedding model. The assistant chooses `asc_guidelines` or `macea_guidelines` search tools from the question and conversation context. ASC content/claims searches use `QDRANT_COLLECTION` (default `asc_guidelines`); MACEA-specific searches use `macea_guidelines`. Requests covering both search both and distinguish the authorities. Chat questions explicitly naming an authority, and their follow-ups, trigger server-side retrieval before model generation, including definitions such as "What is MACEA?". Failed or empty mandatory retrieval stops the answer with a source-availability message; MACEA-only questions do not include the ASC checklist. Image-check validation remains ASC-specific. Existing documents are not moved.

Set `MAX_DOCUMENT_MB` in `.env` (default 20). Original files are processed in memory and are not retained. PDFs preserve page numbers; spreadsheets preserve worksheet names and row numbers. Word paragraphs and tables are included. Excel formulas are never executed: only cached values are read. Scanned PDFs require external OCR. Encrypted PDFs that open without a password are supported through `pypdf[crypto]`. PDFs requiring an opening password and legacy DOC/XLS formats are unsupported.

An existing basename triggers explicit replacement confirmation. Different filenames can contain duplicate content. Replacement embeds all new passages first, saves them, and then removes old passages. Failed storage batches trigger cleanup of new point IDs; incomplete cleanup or old-passage removal is reported as a failure and may require administrator repair. Qdrant does not provide an atomic document swap: searches may briefly see both versions. Closing the page does not cancel an ingestion already running. Uploads are serialized within this single-process server; do not run multiple server workers or CLI ingestion concurrently against the same collection.

The CLI remains available: `uv run ingest_guidelines.py "path/to/guide.pdf"` and `--replace`. It also supports the new formats and applies the same size limit. CLI ingestion continues to target `QDRANT_COLLECTION`; the web upload endpoint targets `macea_guidelines`. Text splitting remains 1,000 characters with 200-character overlap, in embedding/storage batches of 32. `POST /api/documents` accepts multipart `file` and `replace` and streams NDJSON stage/progress/duplicate/done/error events; request validation failures return HTTP 400.


## Image-check performance

Image checks now retrieve two focused ASC searches from the structured product/claims/people description (a third for other visuals when present), then make a single JSON judgment. An explicit MACEA reviewer note also retrieves MACEA context; the verdict and verification remain ASC-specific. The full ASC checklist and deterministic verification remain enabled. Chat retains its separate search loop.

Vision thinking is disabled when the selected vision model advertises support. Image judgment uses `IMAGE_JUDGE_REASONING=medium` independently of chat reasoning. `VISION_MAX_TOKENS=4096` and `IMAGE_JUDGE_MAX_TOKENS=6144` bound generation. `IMAGE_SEED=42` is applied to vision, judgment and evidence auditing to reduce sampling variation; it does not guarantee identical outputs across model/hardware changes. If either stage reaches its output limit, processing stops without a verdict; increase the relevant limit for unusually dense ads. Image results include `timings` for description, retrieval/judgment, and verification, plus total `seconds` (excluding queue time). The UI displays total processing time.

Model loading, GPU memory/offloading, image complexity, and service latency still affect duration. No fixed response-time guarantee is imposed by token limits. The two large models may still need to swap in GPU memory between vision and judgment.


## Aida conversation scope

Aida answers questions about ASC, MACEA, OOH advertising and related work, and Aida's own features and usage. A server-side scope decision runs before guideline retrieval or answer generation. Unrelated requests receive only a short scope reminder, including when earlier conversation was relevant. Greetings, thanks, and basic identity questions use immediate local replies. Other requests use a bounded JSON classification with recent conversation context for genuine follow-ups. If classification fails or returns an invalid decision, Aida gives the scope reminder without retrieval or generation. Image-check processing is unchanged.


## Evidence verification and review outcomes

Image results use `COMPLIANT` (Approve), `NON-COMPLIANT` (Reject), and `ERROR`. Approve means no verified violation was found in the available evidence. Unreadable text, missing documents, incomplete checks, discarded findings, and other uncertainties are listed under Notes; they do not establish full compliance. Verified violations retain their rule, evidence, and suggested correction. Evidence validation and negation-aware decency checks remain in place.

A proposed approval or rejection receives a separate model evidence audit against observations, rule summaries, and retrieved passages. Audit disagreement, truncation, or failure adds notes without replacing the verified decision. The UI, CLI, chat summaries, and PDF reports show notes consistently; saved `NEEDS_REVIEW` results display as Approve with their original uncertainty details.

Result `analysis` metadata includes the image, description, source and instruction hashes plus effective seed and reasoning level, so repeated checks can be compared without retaining original uploads. These safeguards reduce unsupported decisions; they do not independently establish OCR ground truth, legal compliance or guaranteed accuracy. Validate model quality against labeled real ads before relying on the pre-screen's decisions. Explicit `.env` overrides take precedence over the updated defaults.


## Current single-generation-model setup

The local configuration uses `qwen3.5:9b` for both image descriptions and chat/judgment.
Set `CHAT_REASONING=off`, `JUDGE_REASONING=off`, and `IMAGE_JUDGE_REASONING=off`
to explicitly disable Qwen thinking in chat, scope classification, image judgment,
and the independent evidence audit. Vision already requests `think=false` when supported.
Both model stages use a 16384-token context to avoid changing the model context between stages.
The evidence audit and deterministic verification remain enabled.

Guideline search still requires `nomic-embed-text`, since the existing Qdrant vectors
were created with it. The application uses a separate CPU Ollama on port 11435
when available; its health check uses the supported Python client's `list()` method.
Unloading a model releases its memory without deleting its downloaded files. Other
applications sharing Ollama can reload models independently.


## Context compaction

Prompt instructions omit decorative separator banners and blank lines while keeping
every instruction and the full rule checklist. MACEA-only chats include MACEA
instructions once. Evidence-audit JSON is serialized compactly, byte-identical
reference blocks are deduplicated, and an observation description repeated inside
the proposed result is stored once. Distinct authorities and source locations are
retained. Source passages, observations, quotations, findings, and negations are
not summarized or rewritten. No extra model call is used for compaction.

The Next.js client also omits operational review metadata from follow-up chat
context; full results remain available in saved messages and PDF reports. This is
lossless compaction of relevant context, not semantic summarization of old chats.
The existing chat memory limit and history window still apply. Savings vary by
input; model loading, vision generation and the evidence audit still take time.


## Swagger API documentation

Open **http://127.0.0.1:8000/docs** for interactive Swagger UI. The raw schema is
**http://127.0.0.1:8000/openapi.json**. These are backend URLs; port 3000 serves
the separate Next.js frontend. Swagger UI JavaScript, CSS and favicon are bundled
locally, so the docs require no CDN or external validator.

The five API operations are grouped by feature, with form-field descriptions,
request examples, typed readiness output, HTTP validation errors, NDJSON stream
examples, terminal-event conventions, and PDF response/download headers.
Use **Try it out** to send requests. This executes real operations: document
uploads store passages and confirmed replacements replace existing documents.
Swagger may display a stream only after it finishes; use a streaming client for
live progress. Processing errors can arrive as terminal `error` events after an
HTTP 200 response, so clients must inspect the stream as well as the HTTP status.

Swagger metadata lives in `app/api/documentation.py`, feature routes own their
operation descriptions, and status output is defined in
`app/features/status/schemas.py`. The upstream UI version and license are recorded
in `static/vendor/swagger-ui/README.md`.
