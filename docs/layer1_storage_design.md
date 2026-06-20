# NPPI — Layer 1: Storage Foundation
## Design Document for Engineering Lead
**Status:** Engineering review complete — Ready for build
**Last updated:** 2026-06-20

---

## Problem Statement

Government officials dealing with pharmaceutical pricing in India have no reliable digital system to find, verify, or analyse medicine prices. Decisions are made on manually retrieved, inconsistent, and unverifiable data. This platform solves that by building a national-scale intelligence system — starting with a trustworthy, traceable storage foundation that every other layer depends on.

---

## Goals

1. Documents land in one place safely
2. Every document is tagged with metadata on arrival
3. No duplicate documents enter the system
4. Nothing is ever modified or lost without automatic detection
5. Structure is ready for the OCR pipeline to plug into in Layer 3

## Non-Goals

- Collecting or harvesting documents — that is Layer 2
- Reading, parsing, or extracting content from documents — that is Layer 3
- Validating extracted data — that is Layer 4
- Full auth, RBAC/ABAC, encryption at rest — deferred to full project
- Production-grade uptime, DR, RPO/RTO — deferred to full project

---

## PoC Context

The client has asked for a layer-by-layer demo. Each layer is approved before the next is built. Layer 1 is the first demo. It must prove one thing clearly: every document that enters this system is safe, organised, and traceable from the moment it arrives.

We are using real NPPA data — publicly available pharmaceutical pricing documents. Not synthetic data.

---

## Constraints — All 9 from Government Work Order

| Tech Stack Chosen | Constraints Addressed | PoC? | Decision & Reasoning |
|---|---|---|---|
| AWS S3 — Mumbai (ap-south-1) | **1.** Data never leaves India — bucket restricted strictly to ap-south-1 Mumbai, no cross-border transit. **5.** 1B+ records, petabyte scale — S3 handles national-scale storage by default. **8.** DPDP Act 2023, CERT-In — all data physically stored within Indian borders, satisfies Indian data law from day one. | Yes — proves documents land and stay inside India from day one | Only full AWS region in India. Petabyte scale by default. Satisfies data residency and DPDP Act on day one. |
| Delta Lake (Open Source) | **2.** Open standards, no vendor lock-in — Delta Lake is fully open source, no proprietary format. **3.** Government owns all IP — open format means government can move to any engine at any time, nothing is held hostage. **4.** Tamper-evident audit trail — every action logged in transaction ledger, fingerprint stored on every document arrival, any modification detected automatically. **9.** No auto-finalisation — raw documents in Bronze are never overwritten or auto-processed without a deliberate pipeline action. | Yes — proves corruption detection, full transaction logging, and open format | Open source. Adds transaction log, fingerprinting, and time travel on top of S3. Government owns everything and can move away from any vendor at any time. |
| Databricks Free (Single Node) | **2.** Open standards — Spark-based open standard engine underneath. **5.** 1B+ records, petabyte scale — single node PoC proves the approach; identical runtime scales to multi-node for full project with no architectural change. | Yes — executes all pipeline rules, writes to S3, enforces Delta Lake structure | Spark is an open standard. Delta Lake data fully portable if Databricks ever replaced. Zero cost for PoC. |
| Bronze / Silver / Gold Zones | **4.** Tamper-evident trail — each zone is a controlled, auditable checkpoint. Documents only move forward through deliberate actions, never backwards, never silently. **9.** No auto-finalisation — Bronze to Silver only after OCR runs. Silver to Gold only after validation and officer approval. Gates built into the flow from day one. | Yes — establishes the three-stage structure all future layers write into | Bronze stores raw untouched documents. Silver stores extracted fields. Gold stores validated clean records. Defined now so every future layer has a clear, isolated, auditable home. |
| — | **6.** 99.5% uptime — requires multi-zone high-availability deployment. **7.** RPO 15 min, RTO 4 hours — requires disaster recovery across Mumbai and Hyderabad regions. | No — deferred to full project | Not needed for PoC — no live government data at risk. Addressed in full project infrastructure design. |

---

## Proposed Design

### Architecture

```
AWS Mumbai (Cloud)
    └── AWS S3 (physical file storage)
            └── Delta Lake (logbook, fingerprinting, rules engine)
                    └── Databricks Free (engine — executes rules, runs jobs)
                            └── Database: nppi
                                    ├── Table: bronze  — raw documents, untouched as received
                                    ├── Table: silver  — structured extracted fields (Layer 3 writes here)
                                    └── Table: gold    — validated clean records (Layer 4 writes here)
```

Bronze is the only zone Layer 1 writes to. Silver and Gold are defined now so the structure exists when Layer 3 and Layer 4 need them — nothing writes to them until those layers are built.

**Zone structure decision:** Bronze, Silver, and Gold are three separate Delta tables inside one Databricks database named `nppi` — not S3 folder paths, and not three separate databases. Each table has its own transaction log, its own schema, and its own fingerprint history. Full isolation, managed as one unit. Three separate databases would require three separate connections, three separate permission systems, and three separate monitoring setups — more complexity with no benefit.

---

### Document Metadata Schema

Every document is tagged with the following fields on arrival into Bronze. Captured at ingestion — before any processing occurs.

| Field | Type | What it captures |
|---|---|---|
| source | String | URL or portal the document was downloaded from |
| origin | String | Issuing authority — NPPA, Ministry of Health, etc. |
| arrival_date | Timestamp | Date and time the document entered the system |
| document_type | Enum | Format — PDF, CSV, HTML |
| document_category | String | Content — Ceiling Price Schedule, Circular, Notification |
| file_size | Integer (bytes) | Detects incomplete or truncated files |

**Note:** Document ID, fingerprint, and processing status are system-generated by Delta Lake and Databricks — not part of the ingestion metadata schema.

**Note:** source and origin are two separate fields. Source is where we downloaded the document from. Origin is who issued it. These are not the same thing.

---

### Duplicate Detection

Duplicates are detected by content fingerprint — not filename or URL. The same document available on two different government portals will have identical content and therefore an identical fingerprint.

**Fingerprint algorithm: SHA-256.** MD5 was considered and rejected — two different documents can produce the same MD5 fingerprint, meaning a bad actor could swap one document for another and the system would not catch it. SHA-256 does not have this collision problem. For a government platform where tamper-evidence is a legal requirement, MD5 is not acceptable. SHA-256 is the standard choice.

```
Document arrives
    → Databricks generates SHA-256 fingerprint of file content
    → Check: does this fingerprint already exist in nppi.bronze?
    → Yes → reject as duplicate, log the attempt
    → No → store in nppi.bronze, record metadata
```

Content is never read at this stage. Detection happens on the file itself.

---

### Corruption Detection

Silent corruption is the highest-priority risk. Unlike duplicates or scale failures — which are visible — corrupted data looks normal. The system keeps running, officers get answers, and nobody knows those answers are wrong. For a platform where government policy is made on these numbers, that is a governance failure.

```
Document arrives
    → Pipeline generates SHA-256 fingerprint of file content
    → Fingerprint stored in nppi.bronze alongside document metadata

Every time document is accessed:
    → Pipeline recalculates SHA-256 fingerprint of file at S3 path
    → Compare against stored fingerprint in nppi.bronze
    → Mismatch → two things happen automatically:
          1. Record written to nppi.corruption_log
                 (doc_id, detected_at, stored_fingerprint, actual_fingerprint)
          2. Databricks SQL Alert queries corruption_log and fires notification
    → Access blocked, officer alerted
    → Match → document intact, proceed
```

Officers are alerted automatically. No manual checking required. The original is always preserved — Delta Lake is append-only, nothing is ever overwritten.

**Alert mechanism decision:** Two-part for the PoC. First, a permanent record is written to a dedicated `nppi.corruption_log` Delta table — auditable, queryable, never deleted. Second, a Databricks SQL Alert monitors the corruption_log table on a schedule and fires a notification visible in the Databricks dashboard when a new mismatch record appears. For the full project this connects to email or a proper monitoring system.

**Note on Databricks Free Edition:** Databricks Community Edition (the old free product) retired on January 1, 2026. The project uses Databricks Free Edition — its replacement. Databricks SQL Alerts are available in the Free Edition and confirmed to work for this use case.

---

## Alternatives Considered

### Cloud — AWS vs Azure vs MeitY CSP

| Option | Decision |
|---|---|
| Azure India | Rejected. Deeper native Databricks integration but only 30 days free credit vs AWS 12 months. Not worth the tradeoff for PoC. |
| MeitY-empanelled CSP | Rejected. Limited tooling, slower setup, not suitable for PoC velocity. Relevant for full project compliance discussion. |
| AWS India | Chosen. 12 months free tier, full India region, native Delta Lake and Databricks support. |

### Lakehouse Format — Delta Lake vs Apache Iceberg vs Plain S3

| Option | Decision |
|---|---|
| Plain S3 | Rejected. No transaction log, no fingerprinting, no time travel, no corruption detection. Does not meet any storage requirements. |
| Apache Iceberg | Rejected for PoC. Equally strong, also open source, also supports ACID and time travel. Databricks is built specifically for Delta Lake — tighter integration, faster PoC setup. Can be revisited for full project. |
| Delta Lake | Chosen. Tighter Databricks integration, battle-tested at scale, open source. |

### Engine — Databricks vs Self-hosted Apache Spark

| Option | Decision |
|---|---|
| Self-hosted Apache Spark | Rejected for PoC. Open source, no vendor dependency, runs anywhere — but requires significant infrastructure setup and configuration. Weeks of work before anything runs. |
| Databricks Free | Chosen. Spark under the hood but fully managed. Built specifically for Delta Lake. Fastest path to a working storage layer. |

---

## Tradeoffs

| Decision | What We Gain | What We Give Up |
|---|---|---|
| Databricks Free | Fastest setup, zero cost, no infrastructure management | Data training clause — see warning below |
| Delta Lake over Iceberg | Tighter Databricks integration, better tooling | Slightly less portable if we move away from Databricks in future |
| AWS over Azure | Longer free tier runway for PoC | Slightly less polished Databricks experience — Azure Databricks is a joint Microsoft-Databricks product |

---

## Warning — Databricks Free Data Training Clause

Databricks Free terms state: "Databricks reserves the right to train on your data."

This is accepted for the PoC because all NPPA data used is publicly available government data — no sensitive or private information is at risk.

**Before any non-public government data is processed, Databricks Free must be replaced with paid Databricks or self-hosted Delta Lake. This is not optional.**

---

## Open Questions

These are unresolved items the engineering lead should be aware of before the full project begins:

1. **Concurrent users** — undefined. Client stated "to be defined during requirement study." Will affect Gold layer query performance design in later layers.

2. **Document retention policy** — how long must raw Bronze documents be kept? Work order states "as required by applicable regulatory and audit policy" — not yet defined by client. Flag this before full project build begins.

3. **Auth and access control** — who can read Bronze? Who can read Gold? Deliberately deferred to Layer 4 design. Do not implement any access controls yet — they will be defined in Layer 4.

---

## Engineering Decisions Log

Questions raised during engineering review before build began. Recorded here so future engineers understand why things are built the way they are.

| # | Question | Answer | Raised By |
|---|---|---|---|
| 1 | What hashing algorithm for content fingerprinting? | SHA-256. MD5 rejected — has known collision vulnerability. For a tamper-evident government platform, SHA-256 is the only acceptable choice. | Engineering |
| 2 | Are Bronze/Silver/Gold S3 folder paths or separate Delta tables? | Separate Delta tables inside one Databricks database named `nppi`. Not S3 folders (no isolation, no per-zone transaction log). Not three separate databases (unnecessary complexity). | Engineering |
| 3 | What does "alert fires automatically" mean in practice — fires to what? | Two things: (1) a record written to `nppi.corruption_log` Delta table, (2) a Databricks SQL Alert that monitors the corruption_log and fires a notification in the Databricks dashboard. | Engineering |
| 4 | Does Databricks Free Edition support SQL Alerts and notifications? | Yes. Verified against Databricks documentation. Note: Databricks Community Edition (old free product) retired January 1, 2026. This project uses Databricks Free Edition — its replacement — which supports SQL Alerts. | Engineering |

---

## What Comes Next

Layer 1 build is complete when:
- AWS S3 bucket created in Mumbai region (ap-south-1)
- Databricks Free Edition account created and connected to S3
- `nppi` database created in Databricks
- `nppi.bronze` Delta table created with full metadata schema
- `nppi.silver` Delta table created (empty — Layer 3 writes here)
- `nppi.gold` Delta table created (empty — Layer 4 writes here)
- `nppi.corruption_log` Delta table created
- SHA-256 duplicate detection running on every document arrival
- SHA-256 corruption detection running on every document access
- Databricks SQL Alert configured on corruption_log table

After Layer 1 demo is approved by client — Layer 2 design begins: Data Harvest.
