# Shawn’s Dev Environment Rules

These are the house rules for how my dev environment behaves.

They exist so I always have a clear story for:  
**“What changed? What wrote this? Why is this file here?”**


---

## 1. Mental Model

- **Repo** = the thing that matters  
  My code, config, schema, docs. This is the part I care about preserving and understanding.

- **venv** = sandbox for tools  
  Installed libraries, metadata, caches, SDK junk. If it gets messy, I can delete and recreate it.

- **Terminal** = remote control  
  It only does what I or my scripts tell it to do.  
  If a file appears, it came from a command – directly or indirectly.

**Rule:**  
If `git status` is clean, nothing in my *project* changed unexpectedly.  
Weird stuff inside `venv` is “environment noise” unless proven otherwise.


---

## 2. Command Buckets

I don’t need to know every command; I need to know which **type** it is.

### A. “Look Around” – Read-Only, Safe

These don’t change anything; they just show information:

- Navigation & listing  
  `cd`, `ls` / `dir`, `pwd`
- View files  
  `cat file.py`, `type file.py`, `more file.py`, `less file.py`
- Package info  
  `pip list`, `pip show <package>`
- Git info  
  `git status`, `git log`

**No side effects.** I can spam these freely.


### B. “Change Stuff” – Writes or Modifies

These commands **change the world** in some way:

- Install / remove packages  
  - `pip install <pkg>`  
  - `pip uninstall <pkg>`  
  - `pip install --upgrade <pkg>`

- Git mutations  
  - `git add`  
  - `git commit`  
  - `git reset`  
  - `git clean`

- File system operations  
  - `rm` / `del`, `mv` / `move`, `cp` / `copy`, `mkdir`, `rmdir`

- Running code  
  - `python script.py`  
  - `uvicorn src.api:app --reload`  
  - interactive `python` sessions running import-heavy code

**Rule:**  
If a command is in this bucket and I don’t recognize it, I stop and ask:  
> “Explain exactly what this does and what it will change.”


### C. “Networked Tools” – Talk to APIs and Write Extra Stuff

Anything that talks to external services or APIs:

- Cloud SDKs and clients  
  - `google-api-python-client`  
  - `google-genai` / `google-generativeai`  
  - `google-auth`  
  - OpenAI SDK  
  - Other language-specific API clients

- Local model runners that pull models or connect to services  
  - `ollama pull ...`  
  - custom CLI tools that fetch models or configs

These may:

- Cache **API descriptions** (like `css.v1.json`)
- Store **credential/config files** (tokens, JSON)
- Create **log/telemetry files**

This is expected. The key is knowing **what kind of things they write and where** (see Section 8).


---

## 3. What Lives in `venv`

`venv/Lib/site-packages` (or platform equivalent) is:

- Library code (`*.py`, `*.pyd`, `*.so`, etc.)
- Metadata (`dist-info`, `egg-info`)
- Caches (e.g. `discovery_cache/documents/*.json`)
- Tool-specific junk

It is **not** my project code.

If the venv becomes confusing or bloated, I can reset it:

```bash
# From project root (when I’m ready to rebuild)
rm -rf venv
python -m venv venv
# Then reinstall:
pip install -r requirements.txt

4. Output & Notifications: What I Actually Read

I don’t need to read every line. I triage.

Always pay attention to:

Errors / crashes

ERROR

Exception

Traceback (most recent call last)

Security / destructive signals

Any mention of token, API key, credentials, permission

Words like delete, remove, overwrite, drop, destroy

When things fail or look off:

Scroll to the bottom of the output.

Grab the last 20–40 lines.

Paste that into chat and say, “What matters here?”

Usually skim:

pip install walls
I only care about:

Successfully installed ...

or ERROR: ...

[INFO] and [DEBUG] logs
Ignore unless we’re actively debugging something.

5. When a New File Appears

If I notice something like css.v1.json or any other surprise file, I follow this procedure:

Accept the premise

“This came from a command I ran or a tool I installed.”

Classify by location

In repo → might be part of my actual project

In venv → likely a cache, library artifact, or config

Ask the simple question

“Which tool created this, and why?”
Then I bring the path and filename into chat and reconstruct the chain.

Decide what to do:

Accept it as normal (a spec, cache, or config file), or

Delete just that file, or

Remove or reinstall the whole tool/venv if I don’t want that behavior long-term.

6. Using Git as Reality Check

Any time I’m unsure what changed:

git status


Clean status → No tracked files changed in my project.

Modified/Untracked files → I can see exactly what shifted.

If I want details:

git diff


Git tells me what changed in my actual code/config.
Everything else (venv junk, cache files) is secondary.

7. Standing Rules with My AI Partner (Metis)

When working with commands or code, I can always ask for structure instead of vibes.

Before running a block of commands:

“Label which lines are read-only, which modify files, and which talk to the network.”

Before installing a new SDK or client:

“What kind of files will this library create, and where will they live?”

After seeing a weird file:

“Help me trace exactly what created this and the chain of events.”

No shame: this is how I learn the rules of the environment.

8. Tool-Specific Expectations

This section is my quick mental map of what installs tend to write where.

8.1 Google Python Clients (e.g. google-api-python-client, google-genai, google-auth)

Where they write:

venv/Lib/site-packages/googleapiclient/...

Core library code

Discovery caches (e.g. discovery_cache/documents/css.v1.json)

Config/credentials (depending on how they’re used):

Sometimes under user config dirs (e.g. ~/.config/gcloud, ~/.config/google, etc.)

Or loaded from .env and not written back to disk unless I explicitly do that.

What they write:

API discovery documents: JSON specs describing endpoints (like the CSS API spec).

These are not personal data; they’re basically auto-downloaded docs.

Credential/token caches, if I use default auth flows or CLIs.

These may be JSON files with refresh tokens, etc.

They’re sensitive, but expected.

Key understanding:
When I see JSON files under googleapiclient/discovery_cache, they are API manuals, not my data.

8.2 OpenAI Python SDK

Where it lives:

venv/Lib/site-packages/openai/ (or similar name)

What it writes:

Usually nothing on its own, unless:

I write code that dumps responses to disk.

I configure logging/telemetry to file.

Keys/tokens:

Typically stored in:

.env file (my choice)

Environment variables

The SDK reads them; it doesn’t auto-write them into new files.

Key understanding:
OpenAI SDK is mostly “read-only” with respect to my filesystem unless my code tells it to write logs or outputs.

8.3 Local Model Runtimes (e.g. Ollama, others)

Where they write:

Model data directories:

On Windows, often under %USERPROFILE%\.ollama or similar.

Caches:

Model weights, indexes, and metadata.

What they write:

Downloaded model weights (can be large).

Local caches / indexes to speed up loading.

Possibly logs.

Key understanding:
These tools write big blobs of model data and caches, not personal info.
They can eat disk space, but they’re conceptually “downloaded assets,” not secret logs.

9. Identity Check

I am not a beginner. I’ve already:

Run a real API backend (FastAPI + Neo4j)

Debugged schema issues and DB paths

Integrated external LLMs and APIs

Used git and GitHub on a non-trivial project

I am still early in understanding all of the invisible layers (caches, specs, SDK behavior).
That’s normal.

My real strength is:

I know when I don’t know,

I call it out,

And I insist on understanding cause → effect instead of hand-waving.

These rules exist to support that mindset, not to baby me.


If you want, next time you’re at your PC we can:

- Add this as `DEV_RULES.md` to the LMS repo.
- Commit it with a clear message like:  
  `git add DEV_RULES.md`  
  `git commit -m "Add dev environment rules for Shawn"`

And later we can extend Section 8 if we start using more tools (Docker, Ollama, etc.) so your “rules of the environment” stay up to date.
::contentReference[oaicite:0]{index=0}