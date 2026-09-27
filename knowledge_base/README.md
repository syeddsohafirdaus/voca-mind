# Voca Mind Knowledge Base Repository (`knowledge_base/`)

This directory serves as the curated document repository for **Voca Mind's** Retrieval-Augmented Generation (RAG) system.

---

## ⚠️ Important Product Boundary & Non-Clinical Disclaimer

**The knowledge base contains curated, general psychoeducational information ONLY.**

- Content in this knowledge base is **NOT** medical advice, psychiatric diagnosis, or individual treatment planning.
- Content must **NEVER** include individual user statements, user conversation logs, or inferred patient health records.
- All documents must undergo formal review by qualified reviewers before being marked as `reviewed: true` and ingested into vector storage.

---

## 📋 Purpose & Architectural Role

The purpose of the Voca Mind knowledge base is to provide grounded, authoritative, non-diagnostic psychoeducational material (such as stress management techniques, sleep hygiene education, and grounding exercises) to enhance conversational AI responses.

### Key Knowledge Base Principles:
1. **Authoritative Provenance:** Every document must originate from vetted, reliable public health or educational sources.
2. **Strict Metadata Requirement:** Every document must specify source name, source URL, publisher, topic, review status, and version.
3. **Impersonal Educational Scope:** Documents contain general educational concepts only. No user PII or individual user statements are stored here.
4. **Future Ingestion Pipeline:** Documents in this repository will be chunked deterministically, embedded using vector models, and indexed into **Qdrant** for semantic retrieval.

---

## 📂 Directory Structure

- `sources/` – Raw source document records and reference links.
- `documents/` – Formatted knowledge base documents ready for ingestion.
- `metadata/` – JSON metadata schemas and document template configurations (`document-template.json`).
