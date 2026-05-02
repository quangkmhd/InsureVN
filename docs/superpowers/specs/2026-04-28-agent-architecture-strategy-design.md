# InsureVN Multi-Agent System Architecture Strategy

This document outlines the specialized agents required to fully automate the insurance lifecycle and address all 100 customer scenarios defined in `docs/customer_intent_scenarios_100_questions.md`.

## Architecture Paradigm: Hierarchical Swarm
The system uses a central **Orchestrator Agent** (Router) built on LangGraph. This orchestrator does not answer questions directly; it delegates sub-tasks to highly specialized expert agents, collects their outputs, and synthesizes the final response.

---

## 1. The Core Brains (Knowledge & Search)
These agents retrieve facts and documentation.

*   **GraphRAG Agent (Knowledge Graph Searcher):**
    *   *Purpose:* Retrieves complex clauses, definitions, and unstructured rules from Markdown/PDF documents stored in Qdrant and Knowledge Graphs. Understands relationships between exclusions and conditions.
    *   *Use Case:* Explaining "pre-existing conditions," "exclusions," and general policy understanding (Qs 1-15).
*   **SQL Agent (Database Querier):**
    *   *Purpose:* Translates natural language into SQL to fetch structured data (premium costs, limits, hospital networks, user profiles).
    *   *Use Case:* Comparing prices, finding hospitals in-network, checking user status (Qs 16-30, 56-65).
*   **Web Search Agent (Live Data Gatherer):**
*   **Web Search Agent (Live Data Gatherer):**
    *   *Purpose:* Finds real-time information not stored in the internal database.
*   **User State & Memory Agent (CRM / Profile Agent):**
    *   *Purpose:* Manages the personal context of the user (age, family, current plan, medical history, current claim progress) by connecting to the User Database. Injects this context into other agents.
    *   *Use Case:* "What step is my claim #123 at?" (Q 81), "If I change jobs to construction, is my current plan still valid?" (Q 37).

---
---

## 2. The Doers (Execution & Logic)
These agents perform deterministic actions, calculations, and data extraction.

*   **Calculator / Actuary Agent:**
    *   *Purpose:* Executes Python code to calculate exact payouts, premiums, deductibles, and co-pays. Prevents LLM math hallucinations.
    *   *Use Case:* "How much will I be paid for this 15M VND bill?" (Qs 85, 91-95).
*   **Rule & Eligibility Agent:**
    *   *Purpose:* Strictly compares dates, ages, and conditions against policy rules (e.g., waiting periods, age limits).
    *   *Use Case:* "Can I claim for this symptom today?" (Qs 66, 70, 74).
*   **Vision & OCR Agent:**
    *   *Purpose:* Extracts structured JSON data from uploaded images (ID cards, medical bills, invoices).
    *   *Use Case:* Data entry, claim submission (Qs 47, 86-88).
*   **Document Generator Agent:**
    *   *Purpose:* Fills templates and generates PDF/Word documents for policies or forms.
    *   *Use Case:* Contract signing, form auto-fill (Qs 46, 52, 61).

---

## 3. The Specialists (Advanced Edge Cases)
These are highly specialized agents designed for complex insurance industry scenarios.

*   **Medical Translation & Mapping Agent:**
    *   *Purpose:* Translates colloquial symptoms ("stomach ache") into official ICD-10 medical codes so the Rule Agent can process them.
    *   *Use Case:* Symptom checking, medical record analysis (Qs 66, 86-88).
*   **Underwriting Assistant Agent:**
    *   *Purpose:* Assesses risk *before* purchase based on user health declarations (accept, load premium, exclude, reject).
    *   *Use Case:* Pre-existing condition assessment, health check requirements (Qs 22, 53, 48).
*   **Comparison Engine Agent:**
    *   *Purpose:* Scores and ranks multiple insurance packages based on the user's specific profile and needs.
    *   *Use Case:* Personalized recommendations (Qs 31-45).
*   **Contract Summarization & "Gotcha" Hunter Agent:**
    *   *Purpose:* Scans 50+ page PDFs specifically looking for hidden unfavorable clauses, red flags, or tricky exclusions.
    *   *Use Case:* Reviewing external contracts, explaining dangers (Qs 14, 15, 27).
*   **Market Sentiment & Review Agent:**
    *   *Purpose:* Scrapes forums (Voz, Otofun, Facebook) to analyze real-world claim experiences and company reputation, bypassing PR.
    *   *Use Case:* "Which company is the most reputable/easiest to claim?" (Qs 7, 19).
*   **Fraud Detection Agent:**
    *   *Purpose:* Analyzes claim history and behavior patterns to flag suspicious activity before payout approval.
    *   *Use Case:* Background check during claims (Q 90).
*   **Predictive Optimization Agent:**
*   **Predictive Optimization Agent:**
    *   *Purpose:* Analyzes past premium vs. claim history to recommend long-term financial optimizations (e.g., increasing deductible to lower premium).
    *   *Use Case:* Renewals, avoiding overpaying, lifetime value (Qs 6, 42, 96-100).
*   **Network & Direct-Billing Navigator Agent:**
    *   *Purpose:* Guides the customer through the healthcare system. Checks if a specific hospital is in the direct-billing network, explains the process (whether upfront payment is needed, required cards/apps).
    *   *Use Case:* "I want an eye exam at Vinmec, do I need to pay upfront?" (Qs 67-72).

---
---

## 4. The Interfaces (User Experience)
These agents handle the interaction layer, ensuring smooth and empathetic communication.

*   **Claim Workflow & Guide Agent:**
    *   *Purpose:* Provides precise checklists of required documents for *specific types of illnesses/accidents*. Guides the user on how to submit claims and tracks progress.
    *   *Use Case:* "I had a motorcycle accident, what do I need to do to get compensated?" (Qs 76-80).

*   **Form & Validation Agent:**
    *   *Purpose:* Interactively asks the user for missing information one step at a time instead of presenting long forms.
    *   *Use Case:* Missing documents, application process (Qs 49, 50, 80).
*   **Empathy & Translator Agent:**
    *   *Purpose:* The final step in the pipeline. Translates harsh or complex output from the Doers/Specialists into friendly, empathetic, and easy-to-understand language.
    *   *Use Case:* Explaining rejections, delivering payout news, general support.

## 5. The Infrastructure & Governance (Under-the-hood & Safety)
These agents operate primarily in the background or as middleware to ensure the entire system remains secure, compliant, empathetic, and up-to-date.

*   **Compliance Guardrail Agent:**
    *   *Purpose:* Acts as the final firewall before any message reaches the user. Scans the synthesized response to ensure no fraudulent advice is given, no over-promising of 100% payouts without underwriter approval, and enforces necessary legal disclaimers.
    *   *Use Case:* Preventing regulatory fines, ensuring disclaimers on medical/financial advice.
*   **Data Extraction & ETL Agent:**
    *   *Purpose:* A background worker that automatically parses new insurance product PDFs or Markdown files, normalizes the data (e.g., converting "Giường nằm" to `room_board_limit`), and inserts it into the SQL Database and Knowledge Graph.
    *   *Use Case:* Keeping the system's product knowledge current without manual data entry.
*   **Escalation & Tone Classifier Agent:**
    *   *Purpose:* Analyzes the emotional sentiment of the user's input. If anger, panic, or an urgent medical crisis is detected, it bypasses standard logic agents, shifts to a highly empathetic tone, and facilitates an immediate handoff to a human agent.
    *   *Use Case:* Emergency hospital admissions, furious customers experiencing claim rejections.
*   **Data Anonymization (PII/PHI) Agent:**
    *   *Purpose:* Operates immediately after the Vision/OCR Agent and before data enters the main system. It redacts Personally Identifiable Information (PII) and Protected Health Information (PHI) such as names, IDs, and contact info from medical records and bills.
    *   *Use Case:* Ensuring HIPAA/local data privacy compliance when handling sensitive medical documents.
*   **QA / Shadow Evaluator Agent:**
    *   *Purpose:* An asynchronous background agent that randomly samples 10% of user chat logs daily. It generates a "gold standard" response and compares it against the system's actual response, alerting developers if the deviation exceeds a safety threshold.
    *   *Use Case:* Continuous quality control, prompt tuning, detecting hallucination drift over time.
