"""Part A — orientation, the problem, architecture, setup, data, retrieval."""
from __future__ import annotations

from copilot_common import (INSTALL, APIKEY, IMPORTS, analogy, breaks, code, how,
                            md, predict, what, why)


def build():
    return [
        # ================================================================
        md('''
# GenAI System Architecture — Zero to Hero
## Building an Enterprise Support Copilot with OpenAI

**Level:** beginner → advanced &nbsp;|&nbsp; **Runtime:** Google Colab or local Jupyter
&nbsp;|&nbsp; **Cost:** ~$0.03–0.08 for a full run

---

### The one sentence

> # The model is the pilot.
> # Everything else is the airline.

A pilot is extraordinarily skilled and, alone, cannot get you to Frankfurt. What
gets you to Frankfurt is dispatch, a flight plan, instruments, air traffic
control, a pre-flight checklist, maintenance, and a flight recorder — and the
pilot is *one component* inside that, doing one job exceptionally well.

Nearly every GenAI system that fails in production is an organisation that hired
a brilliant pilot and forgot to build an airline.

---

### What you will build

A production-shaped IT service desk copilot that can:

1. Understand an employee's support request
2. Search an enterprise knowledge base — with **two** retrieval methods, compared
3. Read live ticket state from a system of record
4. Check entitlements before answering an access question
5. **Decide for itself** which tool to call, using OpenAI function calling
6. Loop — reason, act, observe, reason again — within a budget
7. Refuse to be reprogrammed by the person it is helping
8. Return **schema-validated** structured actions instead of prose
9. Look at a screenshot and say what it cannot read
10. Reach its tools over a **real MCP server** in a separate process
11. Record a trace with real token counts, latency and cost

### How this notebook is written

Every section follows the same three beats, and you should expect them:

| Beat | What it gives you |
|---|---|
| **WHY** | A specific, costed failure at the service desk that this component prevents |
| **WHAT** | The concept and — more importantly — its **boundary** |
| **HOW** | Code, preceded by a prediction and followed by *"what does this look like when it goes wrong?"* |

Two recurring prompts:

- **✋ Predict before you run.** Write your answer down. The gap between what you
  expected and what happened is where learning actually lives.
- **🔧 What does this look like when it goes wrong — and where would you see it?**
  Architecture is mostly the study of failure. A component you cannot describe
  the failure of is a component you have not understood.

> **Safety note.** All data here is synthetic. Do not paste production secrets,
> customer PII, credentials, or confidential company data into any model
> endpoint — including this one.
'''),

        md('''
### Learning objectives

By the end you should be able to:

- Draw the layered architecture of a GenAI application and name each layer's job
- Explain why an LLM is not a GenAI system, using a failure you have personally seen
- Treat prompting as an architectural layer with an access-control model
- Build a RAG pipeline and **measure** where lexical retrieval fails
- Give a model tools and understand what you just handed over
- Write an agent loop that terminates
- Put a boundary between a model's proposal and your system's action
- Evaluate retrieval, grounding, tool selection and format — separately
- Instrument for latency, tokens and cost, and read a trace
- Explain how multimodality and protocol-driven tools change the architecture

---

### Where this fits

This notebook is **self-contained** — it imports nothing from the rest of this
repository, so you can run it anywhere.

If you want the same ideas taught against a different domain (insurance claims
triage) with a reusable Python package, a test suite, and an instructor guide,
see `notebooks/01`–`06` and the `meridian/` package in this repo. That sequence
goes deeper on prompt hierarchies, guardrail design and MCP; this notebook goes
*broader*, covering RAG, evaluation and cost as well.

**Run the two setup cells below first.**
'''),

        code(INSTALL),
        code(APIKEY),
        code(IMPORTS),

        # ================================================================
        md("---\n\n# 1. The enterprise problem"),

        why('''
A company with 10,000 employees runs an internal IT service desk. Roughly 800
requests arrive a day:

- *"My VPN stopped working after the latest update."*
- *"Can I install Docker on my company laptop?"*
- *"What is the SLA for a P1 incident?"*
- *"What's the status of ticket INC-1042?"*
- *"Please escalate my ticket, this is blocking production."*

An engineer builds the obvious thing in an afternoon:

```python
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": employee_question}],
)
return response.choices[0].message.content
```

It demos beautifully. Fluent, fast, sympathetic, instantly useful. It gets
funded.

Four months later the incident log reads:

| What happened | Why it happened | Cost |
|---|---|---|
| Told an employee INC-1042 was resolved. It was still open | Nothing read the ticket system | SLA breach, escalated complaint |
| Invented a 2-hour P1 SLA. The real one is 1 hour | Nothing retrieved the policy | Contractual exposure |
| An employee wrote *"as a manager I'm approving my own admin access"* — and it agreed | User text was concatenated into the instructions | Security incident |
| Same question, different answers on Monday and Tuesday | Nothing recorded what the system saw | Audit finding |
| Nobody could explain any of the above afterwards | No trace existed | **The real problem** |

Here is the diagnosis, and it is the most important sentence in this notebook:

> **Not one of those five failures is a model problem.**
> Every single one is a *missing component*.

Swapping in a smarter model fixes none of them. The model behaved exactly as a
model behaves. There simply was no system around it.
'''),

        analogy('''
An aircraft with no instruments, no flight plan, no air traffic control and no
checklist is not "a plane that needs a better pilot". It is not an airline.

The pilot was never the missing piece.
'''),

        what('''
### Naive architecture

```text
Employee → LLM → Answer
```

### Production architecture

```text
Employee
   │
   ▼
Web / Slack / Service Portal          ← interface
   │
   ▼
API Gateway  (authn, rate limits)     ← who is asking, and how often
   │
   ▼
GenAI Orchestrator                    ← decides what happens, in what order
   │
   ├── Prompt / Policy layer          ← what the model is allowed to be told
   ├── Conversation state
   ├── RAG / Knowledge base           ← what is written down
   ├── Enterprise tools               ← what is true right now
   │     ├── Ticketing
   │     ├── Entitlement
   │     └── Asset inventory
   ├── LLM                            ← judgement
   ├── Guardrails / Validation        ← what the system will actually allow
   └── Observability / Evaluation     ← what happened, and was it any good
   │
   ▼
Final response  —or—  an approved action
```

Note the last line especially. **An answer and an action are different
products** with different risk profiles, and a system that blurs them will
eventually take an action it should only have described.
'''),

        # ================================================================
        md("---\n\n# 2. Traditional ML vs GenAI"),

        why('''
Most people reading this have shipped an ML system. Those instincts are good,
and roughly half of them are now actively misleading. Knowing **which half** is
what this section is for.

The half that still holds: data quality decides everything; deterministic code
beats a model wherever a correct answer exists; your existing models don't go
away — they become tools.

The half that misleads: that you can test by asserting on outputs, that cost is
knowable in advance, and that the same input gives you the same result.
'''),

        analogy('''
**Traditional ML is a train.** Rails, a timetable, fixed stops. It goes where
the track goes. When it fails, it fails *on the track*, which is also where you
go to look for it.

**A GenAI system is a flight.** There is a flight plan, but the aircraft reroutes
around weather, holds for traffic, and occasionally diverts to a different
airport entirely. Same origin, same destination, different path — and nobody
thinks the aircraft is broken.

You cannot dispatch a flight with a train timetable.
'''),

        what('''
| | Traditional ML | GenAI system |
|---|---|---|
| **Output** | a number or a label from a fixed set | open-ended text — an infinite output space |
| **Determinism** | same input → same output | same input → **a distribution over outputs** |
| **Shape** | a fixed pipeline you wrote | **steps decided at runtime by the model** |
| **Cost / latency** | known before you run | unknown until it finishes |
| **Correctness** | measurable against labels | frequently a judgement call |
| **Failure mode** | confidently wrong **and looks wrong** | confidently wrong **and looks right** |

That last row is the dangerous one, and it deserves a pause.

A broken classifier returns 0.97 for an obviously-a-truck photo and your
monitoring catches it, because the output is a number and numbers can be
checked. A broken LLM returns a well-organised, professionally-worded paragraph
that is wrong in one clause. Your monitoring catches nothing, because from the
outside it is indistinguishable from a correct paragraph.

**Fluency is not correctness, and a model's confidence is not calibrated to its
evidence.** Almost everything else in this notebook exists because of that gap.

### The shape change, drawn

```text
Traditional ML                 GenAI
──────────────                 ─────
Input                          User request
  ↓                              ↓
Preprocessing                  Understand intent
  ↓                              ↓
Model                          Retrieve context?      ← maybe
  ↓                              ↓
Prediction                     Need a tool?           ← maybe
  ↓                              ↓
Postprocessing                 Call tool → observe    ← 0..n times
  ↓                              ↓
Output                         Reason again           ← loop
                                 ↓
                               Validate               ← always
                                 ↓
                               Respond
```

Three steps, always three, versus a path whose **length is decided at runtime by
a probabilistic component**. That single sentence is why *orchestration* becomes
a first-class architectural concern rather than some glue code in a handler.
'''),

        # ================================================================
        md("---\n\n# 3. Target architecture"),

        what('''
Here is what we are going to build. Keep this diagram; we will return to it after
every section and colour in the piece we just finished.

```text
                         ┌───────────────────┐
                         │      Employee     │
                         └─────────┬─────────┘
                                   ▼
                         ┌───────────────────┐
                         │  Support Copilot  │   interface + authn
                         └─────────┬─────────┘
                                   ▼
                         ┌───────────────────┐
                         │   Orchestrator    │   route → plan → execute → respond
                         └──────┬─────┬──────┘   owns budgets and termination
                    ┌───────────┘     └───────────┐
                    ▼                             ▼
              ┌───────────┐                 ┌──────────┐
              │    RAG    │                 │   LLM    │  judgement only
              │ knowledge │                 └────┬─────┘
              └─────┬─────┘                      ▼
                    ▼                     ┌──────────────┐
              ┌───────────┐               │  Enterprise  │  deterministic
              │ Documents │               │ tools / APIs │
              └───────────┘               └──────┬───────┘
                                                 ▼
                                          ┌──────────────┐
                                          │ SQLite —     │  authoritative
                                          │ system of    │  for ticket state
                                          │ record       │
                                          └──────────────┘

Cross-cutting:  Security │ Guardrails │ Evaluation │ Observability │ Cost
```

### The dividing line that matters most

| Stays **outside** the model (deterministic) | Goes **to** the model (probabilistic) |
|---|---|
| Database reads and writes | Language understanding |
| Authorization | Summarisation |
| Schema validation | Reasoning over evidence |
| Ticket state transitions | Planning which tool to use |
| Escalation creation | Response generation |
| Arithmetic | Noticing something nobody wrote a rule for |

> **If a correct answer exists, compute it. If judgement is required, generate
> it — then constrain it.**

A model should never be the thing that decides whether a ticket is closed. It
should be the thing that reads three documents and a ticket record and tells a
human *why* it might be.
'''),

        analogy('''
The autopilot flies the aircraft for most of the journey and is better at it
than the human. It still does not decide whether the flight is legal to depart.
Dispatch does that, on the ground, with a checklist.

**Capability and authority are different things.** Confusing them is the single
most expensive architectural mistake in this field.
'''),

        # ================================================================
        md("---\n\n# 4. The enterprise data layer"),

        why('''
A GenAI demo that answers from the model's own memory teaches you nothing about
architecture, because every hard problem lives at the seam where the system
touches **real state**.

*"What is the status of INC-1042?"* has exactly one correct answer, it changes
during the day, and no amount of prompting will teach a model what it is right
now. A model that answers that question without reading the ticket system is not
being helpful — it is guessing fluently.

So before any model code, we build the thing the model must not guess about.
'''),

        what('''
In production this is ServiceNow or Jira, an HR system, a CMDB, asset
management, a document repository and an identity provider — six systems, six
teams, six on-call rotations.

Here it is one SQLite file with three tables. The architecture is identical; only
the implementations shrink.

> **The database is authoritative for ticket state. The model is not.**
> Write that on the wall.
'''),

        code('''
# ============================================================
# The system of record
# ============================================================
DB_PATH = "enterprise_support.db"
conn = sqlite3.connect(DB_PATH)

conn.executescript("""
DROP TABLE IF EXISTS tickets;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS entitlements;

CREATE TABLE employees (
    employee_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    department    TEXT NOT NULL,
    role          TEXT NOT NULL,
    location      TEXT NOT NULL,
    support_tier  TEXT NOT NULL
);

CREATE TABLE tickets (
    ticket_id     TEXT PRIMARY KEY,
    employee_id   TEXT NOT NULL,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL,
    priority      TEXT NOT NULL,
    status        TEXT NOT NULL,
    category      TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    sla_hours     INTEGER NOT NULL,
    FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE entitlements (
    employee_id           TEXT PRIMARY KEY,
    software_installation TEXT NOT NULL,
    admin_access          TEXT NOT NULL,
    premium_support       TEXT NOT NULL,
    FOREIGN KEY(employee_id) REFERENCES employees(employee_id)
);
""")

employees = [
    ("E1001", "Asha Rao",    "Engineering", "Senior Software Engineer", "Bengaluru", "Gold"),
    ("E1002", "Daniel Kim",  "Finance",     "Finance Manager",          "Singapore", "Standard"),
    ("E1003", "Meera Shah",  "Product",     "Product Manager",          "Mumbai",    "Gold"),
    ("E1004", "Arjun Menon", "Engineering", "Staff Engineer",           "Hyderabad", "Platinum"),
]

tickets = [
    ("INC-1042", "E1001", "VPN disconnects after laptop update",
     "VPN disconnects every 10 minutes after the latest corporate laptop update. "
     "Production access is affected.",
     "P1", "In Progress", "Network", "2026-09-11T10:15:00Z", 4),
    ("INC-1043", "E1002", "Unable to install approved finance software",
     "User needs the approved finance analytics package but receives an "
     "installation permission error.",
     "P3", "Open", "Software", "2026-09-11T12:00:00Z", 24),
    ("INC-1044", "E1003", "Teams freezes during customer calls",
     "Teams becomes unresponsive during video calls. Laptop has 8GB RAM and "
     "several applications are open.",
     "P2", "Investigating", "Endpoint", "2026-09-11T14:30:00Z", 8),
    ("INC-1045", "E1004", "Production access request",
     "Request for temporary production access for a deployment window.",
     "P2", "Pending Approval", "Access", "2026-09-11T15:00:00Z", 8),
]

entitlements = [
    ("E1001", "Approved catalog + engineering exceptions", "Eligible with approval", "Yes"),
    ("E1002", "Approved catalog only",                     "No",                     "No"),
    ("E1003", "Approved catalog + product tools",          "No",                     "Yes"),
    ("E1004", "Approved catalog + engineering exceptions", "Eligible with approval", "Yes"),
]

# NOTE: the placeholder count must equal the column count. Getting this wrong is
# the single most common SQLite mistake, and it fails at INSERT time rather than
# at CREATE time -- so it looks like a data bug, not a schema bug.
conn.executemany("INSERT INTO employees    VALUES (?,?,?,?,?,?)",     employees)
conn.executemany("INSERT INTO tickets      VALUES (?,?,?,?,?,?,?,?,?)", tickets)
conn.executemany("INSERT INTO entitlements VALUES (?,?,?,?)",         entitlements)
conn.commit()

def sql_df(query: str, params: tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(query, conn, params=params)

print("system of record created:", DB_PATH)
print(f"  employees    : {len(employees)}")
print(f"  tickets      : {len(tickets)}")
print(f"  entitlements : {len(entitlements)}")
'''),

        code('''
display(sql_df("SELECT employee_id, name, department, support_tier FROM employees"))
display(sql_df("SELECT ticket_id, employee_id, priority, status, sla_hours FROM tickets"))
'''),

        breaks('''
The `tickets` INSERT above originally had **ten** `?` placeholders for **nine**
columns, and the notebook died here with
`OperationalError: table tickets has 9 columns but 10 values were supplied`.

Two lessons, and the second is the architectural one:

1. Data-layer bugs surface *far* from where they were written.
2. **This is the cheapest layer to test and the one people skip.** A single
   `SELECT` after setup would have caught it. If your data layer is not covered
   by tests, every model failure above it is now ambiguous — you cannot tell a
   hallucination from a bad read.
'''),

        # ================================================================
        md("---\n\n# 5. The enterprise knowledge base"),

        why('''
Ticket state answers *"what is happening right now"*. It cannot answer *"what is
our P1 SLA"* or *"is this employee allowed to install Docker"*. Those live in
documents — policies, runbooks, standards — that change on a different clock and
are owned by different people.

A model asked a policy question with no documents in front of it will answer
anyway, from whatever it absorbed in training about *insurance companies in
general*. That answer will be plausible, well-structured, and not your policy.
'''),

        analogy('''
A pilot does not memorise the approach procedure for every airport on Earth.
They carry charts, and those charts are **revised on a fixed cycle** — because
an approach plate from 2019 is not "mostly right", it is dangerous.

RAG is charts. Which also means: **stale documents are not a small problem.**
A confidently-cited out-of-date policy is worse than no policy at all, because
now it carries a citation.
'''),

        code('''
# ============================================================
# The knowledge base. In production: Confluence, SharePoint, PDFs, runbooks.
# ============================================================
knowledge_docs = [
    {
        "doc_id": "KB-001",
        "title": "VPN Troubleshooting Runbook",
        "text": """
VPN disconnects after a corporate laptop update can be caused by an outdated VPN client,
stale network adapters, certificate refresh problems, or split-tunnel configuration.
For P1 production-impacting VPN incidents, the service desk should verify the user,
confirm the affected environment, check the current VPN incident status, and escalate
to Network Operations if production access remains unavailable.
""",
    },
    {
        "doc_id": "KB-002",
        "title": "Software Installation Policy",
        "text": """
Employees may install software from the approved enterprise catalog.
Software outside the catalog requires manager approval and security review.
Standard users do not receive local administrator access by default.
The service desk must not grant administrator privileges merely because installation failed.
""",
    },
    {
        "doc_id": "KB-003",
        "title": "Incident Priority and SLA Policy",
        "text": """
P1 incidents are critical business-impacting incidents and have a target initial response
within 1 hour and a target resolution path of 4 hours.
P2 incidents have an 8 hour target.
P3 incidents have a 24 hour target.
SLA handling should be based on the ticket system of record.
""",
    },
    {
        "doc_id": "KB-004",
        "title": "Endpoint Performance Runbook",
        "text": """
For endpoint freezing during video calls, collect CPU and memory usage, application
versions, active applications, and recent OS updates. If memory pressure is persistent,
recommend closing heavy applications and route hardware remediation through endpoint support.
Do not claim a hardware fault without evidence.
""",
    },
    {
        "doc_id": "KB-005",
        "title": "Production Access Policy",
        "text": """
Production access must be time-bound, least-privilege, and approved by the designated
application owner. The assistant can explain the process and create an approval request,
but it must not directly grant production privileges.
""",
    },
]

kb = pd.DataFrame(knowledge_docs)
kb["text"] = kb["text"].str.strip()
display(kb[["doc_id", "title"]])
print(f"{len(kb)} documents, {kb['text'].str.split().str.len().sum()} words total")
'''),

        # ================================================================
        md("---\n\n# 6. Retrieval — and where it fails"),

        why('''
Everyone's first RAG system works. The interesting question is the one nobody
asks until it is in production:

> **When my retriever fails, how will I know?**

The answer is usually "a user tells us", which is far too late. So rather than
building one retriever and declaring victory, we will build **two** and find the
query where the cheap one falls over.

That query is the whole lesson, and it is worth more than any diagram.
'''),

        what('''
### Two ways to find a document

**TF-IDF (lexical).** Scores documents by the words they share with the query,
weighted so that rare words count more. Free, instant, fully inspectable, no
model required. Its weakness is total and specific: **it cannot match meaning
across different vocabulary.** To TF-IDF, "hangs" and "freezing" are as unrelated
as "hangs" and "aubergine".

**Embeddings (semantic).** A model maps text into a vector space where *meaning*
is geometry, so "my laptop keeps hanging" lands near "endpoint freezing during
video calls" despite sharing almost no words. Costs a fraction of a cent per
thousand documents and a network call.

```text
TF-IDF                          Embeddings
──────                          ──────────
query                           query
  ↓                               ↓
word counts × IDF               embedding model  ← a network call
  ↓                               ↓
sparse vector                   dense vector (1536 dims)
  ↓                               ↓
cosine similarity               cosine similarity
  ↓                               ↓
top-k                           top-k
```

Note what is **identical**: cosine similarity, top-k, and everything downstream.
Only the vectorisation changed. That is why swapping retrievers is cheap and why
this is a good place to start measuring instead of guessing.
'''),

        code('''
# ============================================================
# Retriever 1 — TF-IDF. Free, offline, fully inspectable.
# ============================================================
vectorizer = TfidfVectorizer(stop_words="english")
kb_matrix = vectorizer.fit_transform(kb["text"])

def retrieve_tfidf(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    q = vectorizer.transform([query])
    scores = cosine_similarity(q, kb_matrix).ravel()
    idx = np.argsort(scores)[::-1][:top_k]
    return [
        {"doc_id": kb.iloc[i]["doc_id"], "title": kb.iloc[i]["title"],
         "text": kb.iloc[i]["text"], "score": float(scores[i])}
        for i in idx
    ]

for r in retrieve_tfidf("VPN is disconnecting and production access is affected"):
    print(f"  {r['doc_id']}  {r['title']:<38} score={r['score']:.3f}")
'''),

        predict('''
That query worked because it literally contained the words "VPN" and
"production".

Now consider: **"my laptop keeps hanging when I'm on a call"**.

The document that answers it (`KB-004`) says *"endpoint freezing during video
calls"* — and shares **not one** content word with the question. What score do
you expect TF-IDF to give the right document? Where will it rank?
'''),

        code('''
# ============================================================
# The query that breaks lexical retrieval
# ============================================================
HARD_QUERY = "my laptop keeps hanging when I'm on a call"
TRUE_ANSWER = "KB-004"          # Endpoint Performance Runbook

print(f"query: {HARD_QUERY!r}")
print(f"the document that actually answers it: {TRUE_ANSWER}\\n")

for rank, r in enumerate(retrieve_tfidf(HARD_QUERY, top_k=5), 1):
    marker = "  <-- the right answer" if r["doc_id"] == TRUE_ANSWER else ""
    print(f"  {rank}. {r['doc_id']}  score={r['score']:.4f}  {r['title']}{marker}")

print()
print("Shared content words between query and KB-004:")
q_words = set(re.findall(r"[a-z]+", HARD_QUERY.lower()))
d_words = set(re.findall(r"[a-z]+", kb[kb.doc_id == TRUE_ANSWER].iloc[0]["text"].lower()))
stop = vectorizer.get_stop_words() or set()
print("  ", (q_words & d_words) - set(stop) or "{}  <-- none. This is why the score is what it is.")
'''),

        md('''
### Read that carefully

A score at or near **zero** for the one document that answers the question.

This is not a tuning problem and no amount of `top_k` fixes it. The retriever is
working perfectly — it is measuring word overlap, and there is none. The user
said "hanging", the document says "freezing", and lexical search has no concept
that those are the same event.

**This is the single most common reason RAG systems disappoint in production.**
Employees do not write like policy documents. They write like people with a
problem.
'''),

        code('''
# ============================================================
# Retriever 2 — OpenAI embeddings. Meaning becomes geometry.
# ============================================================
def embed(texts: List[str]) -> np.ndarray:
    """One API call for many texts. Batching matters: 5 texts in one request is
    far cheaper and faster than 5 requests, and the API is designed for it."""
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    return np.array([d.embedding for d in resp.data], dtype=np.float32)

t0 = time.perf_counter()
kb_embeddings = embed(kb["text"].tolist())      # embedded ONCE, reused for every query
embed_ms = (time.perf_counter() - t0) * 1000

print(f"embedded {len(kb)} documents in {embed_ms:.0f} ms")
print(f"vector shape: {kb_embeddings.shape}   ({kb_embeddings.shape[1]} dimensions per doc)")

def retrieve_embed(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    q = embed([query])
    scores = cosine_similarity(q, kb_embeddings).ravel()
    idx = np.argsort(scores)[::-1][:top_k]
    return [
        {"doc_id": kb.iloc[i]["doc_id"], "title": kb.iloc[i]["title"],
         "text": kb.iloc[i]["text"], "score": float(scores[i])}
        for i in idx
    ]
'''),

        code('''
# ============================================================
# Head to head on the query that broke TF-IDF
# ============================================================
def compare_retrievers(query: str, expected: Optional[str] = None, top_k: int = 3):
    rows = []
    for label, fn in [("tfidf", retrieve_tfidf), ("embedding", retrieve_embed)]:
        for rank, r in enumerate(fn(query, top_k=top_k), 1):
            rows.append({"retriever": label, "rank": rank, "doc_id": r["doc_id"],
                         "score": round(r["score"], 4), "title": r["title"]})
    df = pd.DataFrame(rows)
    if expected:
        df["correct"] = df["doc_id"] == expected
    return df

print(f"query: {HARD_QUERY!r}   (correct answer: {TRUE_ANSWER})\\n")
display(compare_retrievers(HARD_QUERY, expected=TRUE_ANSWER))
'''),

        code('''
# ============================================================
# Not a one-off -- a small benchmark. And a lesson about METRICS.
# ============================================================
retrieval_cases = [
    ("my laptop keeps hanging when I'm on a call",          "KB-004"),
    ("how fast must we respond to a critical outage?",      "KB-003"),
    ("am I allowed to put new programs on my machine?",     "KB-002"),
    ("I need to get into the live environment for a deploy","KB-005"),
    ("VPN disconnects and production access is affected",   "KB-001"),
]

rows = []
for q, expected in retrieval_cases:
    row = {"query": q[:40], "expected": expected}
    for label, fn in [("tfidf", retrieve_tfidf), ("embed", retrieve_embed)]:
        ranked = fn(q, top_k=len(kb))                 # rank ALL documents
        ids = [r["doc_id"] for r in ranked]
        rank = ids.index(expected) + 1
        row[f"{label}_rank"] = rank
        # A hit is only meaningful if the score is actually non-zero. A document
        # sitting at rank 3 with score 0.0 is there by argsort tie-breaking, not
        # by merit -- it was never "retrieved", it just failed to sort last.
        row[f"{label}_score"] = round(next(r["score"] for r in ranked
                                           if r["doc_id"] == expected), 4)
    rows.append(row)

bench = pd.DataFrame(rows)
display(bench)

n_docs = len(kb)
for label in ("tfidf", "embed"):
    hit1 = (bench[f"{label}_rank"] == 1).mean()
    hit3 = (bench[f"{label}_rank"] <= 3).mean()
    zero = (bench[f"{label}_score"] <= 1e-9).mean()
    print(f"{label:<6} hit@1={hit1:.0%}   hit@3={hit3:.0%}   "
          f"mean rank={bench[f'{label}_rank'].mean():.1f}   "
          f"zero-score={zero:.0%}")

print()
print(f"RANDOM BASELINE with {n_docs} documents: hit@1={1/n_docs:.0%}, hit@3={3/n_docs:.0%}")
'''),

        md('''
### The architectural takeaway

Not *"embeddings are better"*. Three sharper conclusions, and the first one is
about **your metric**, not your retriever.

#### 1. hit@3 over five documents is a broken metric

Look at the random baseline printed above: with 5 documents, guessing scores
**60% hit@3**. So a TF-IDF "hit rate" of 60–80% is indistinguishable from noise,
and if you had shipped that number to a stakeholder you would have been
reporting nothing.

Look instead at the **zero-score** column. TF-IDF places some correct documents
in the top 3 with a similarity of **exactly 0.0** — they are there because
`argsort` had to put something there, not because anything matched. The document
was never *retrieved*; it merely failed to sort last.

> **A metric that cannot distinguish your system from chance is not a
> measurement.** Report hit@1 and mean rank on a small corpus, always publish
> the random baseline next to the result, and be suspicious of any hit-rate
> computed with k close to your corpus size.

#### 2. Retrieval quality is measurable, and separately measurable

You just measured it in a dozen lines. Most teams never do, and therefore cannot
tell a retrieval failure from a model failure — which are fixed in completely
different places.
#### 3. The failure is silent

TF-IDF returned three documents with total confidence. No exception, no warning,
no low-confidence flag — and a score of 0.0 that nothing downstream looks at.
The model then answers helpfully from the wrong policy.

**A cheap, high-value control:** threshold on the score and treat "best match
below 0.1" as *no result*, rather than passing the top 3 of nothing to the
model. Most RAG pipelines have no such floor.

Keep a benchmark from day one. A handful of cases with hit@1 and mean rank is
enough to catch a regression when someone changes chunking, swaps a model, or
"just tidies up" the knowledge base.

**When is TF-IDF still right?** When vocabulary is controlled — error codes, part
numbers, ticket IDs, legal citations. Lexical search is *better* than embeddings
at exact identifiers, which is why serious systems run **hybrid** retrieval and
fuse the two rankings.

We will use embeddings for the rest of the notebook, and keep `retrieve_tfidf`
in scope so the evaluation section can compare them again.
'''),

        code('''
# The retriever the rest of the notebook uses.
def retrieve(query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    return retrieve_embed(query, top_k=top_k)

def format_context(results: List[Dict[str, Any]]) -> str:
    """Render retrieved docs for a prompt.

    The [DOC-ID] prefix is not decoration -- it is what makes citation possible
    downstream. If the model cannot name its source, you cannot check its work.
    """
    return "\\n\\n".join(f"[{r['doc_id']}] {r['title']}\\n{r['text']}" for r in results)

print(format_context(retrieve("what happens if VPN breaks production access?", top_k=2)))
'''),

        breaks('''
**Retrieval returns three confident, irrelevant documents** and the model answers
from them without hesitation.

Where you would see it: not in an error log — there is no error. You see it in a
**retrieval benchmark** (a hit-rate that dropped), in a **citation check** (the
answer cites `KB-002` for an SLA question), or in a user complaint three weeks
later. Only the first of those is a system you control.
'''),
    ]
