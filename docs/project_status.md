# NPPI — Project Status
**Last updated:** 2026-06-21
**Update this file as each layer progresses.**

---

## Layer Status

| Layer | Name | Status | Document |
|---|---|---|---|
| 1 | Storage Foundation | **Complete and locked** | docs/layer1_storage_design.md · docs/layer1_signoff.md |
| 2 | Data Harvest | Not started | — |
| 3 | Data Extraction | Not started | — |
| 4 | Data Validation | Not started | — |
| 5 | Intelligence Layer | Not started | — |
| 6 | Dashboard & Reporting | Not started | — |
| 7 | Audit Trail | Not started | — |

---

## Open Questions — Unresolved

1. Concurrent users — undefined. Client to define during requirement study.
2. Document retention policy — not yet defined by client.
3. Auth and access control — deferred to Layer 4 design.

---

## Layer 1 — Storage Foundation

**Status:** Complete and locked. All tests passed on live AWS S3 Mumbai with real NPPA data.

---

### What is Layer 1 about?

Before we can analyse medicine prices, we need a safe place to store the documents that contain those prices. Layer 1 builds that place. Nothing more, nothing less.

---

### What problem does it solve?

Government officials today retrieve pricing documents manually — PDFs, circulars, notifications — from different portals. Nobody knows if a document was tampered with. Nobody knows if the same document was stored twice. Nobody knows if data quietly changed without anyone noticing. Layer 1 solves all three.

---

### What does it do?

1. **Receives documents** — any government pricing document that arrives gets accepted into the system
2. **Tags every document on arrival** — records where it came from, who issued it, when it arrived, what type it is, how big it is
3. **Checks for duplicates** — if the same document arrives twice (even from a different website), the second one is rejected automatically
4. **Checks for tampering** — every document gets a unique digital fingerprint (like a seal). If anyone changes even one character, the fingerprint breaks and an alert fires
5. **Keeps everything safe** — documents are never overwritten or deleted. Every action is logged. You can go back in time and see exactly what was stored and when

---

### How does it work?

Think of it like a government document receiving room with three rules:

- Every document that arrives gets a unique seal stamped on it
- If a document with the same seal already exists, the new one is turned away at the door
- Every night, the seal on every stored document is rechecked — if anything has changed, an alarm goes off

---

### Where does everything live?

- All documents stored on AWS servers in Mumbai — data never leaves India
- Four organised sections: **Bronze** (raw documents), **Silver** (extracted content — built later), **Gold** (verified clean data — built later), **Corruption Log** (alert records when tampering is detected)

---

### What did we prove?

We tested it with a real NPPA government document:

| Test | What happened |
|---|---|
| New document arrives | Stored safely with all metadata |
| Same document arrives again | Rejected — no duplicate stored |
| Document gets tampered | Detected immediately — alert written |

All three passed.

---

### What Layer 1 does NOT do

- It does not collect documents from the internet — that is Layer 2
- It does not read or understand what is inside documents — that is Layer 3
- It does not validate whether prices are correct — that is Layer 4

Layer 1 is purely: documents land safely, get tagged, stay safe.
