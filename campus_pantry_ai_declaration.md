# Declaration of AI Use in Assessment

**Course:** COMP9120 Database Management Systems  
**Project:** Campus Pantry — FoodHub Booking, Attendance & Inventory Database System  
**Semester:** 25 Octomber, 2026  
**Institution:** The University of Sydney  

---

## 1. Compliance Statement
In accordance with the University of Sydney Academic Integrity Policy and course guidelines for COMP9120, this declaration details the specific, transparent use of Artificial Intelligence (AI) technologies in the preparation, refinement, testing, and documentation of this group project submission.

We affirm that:
1. All conceptual and logical designs are grounded in our group's verified understanding of relational database theory, normalisation (BCNF), and FoodHub business requirements.
2. All code, queries, and scripts submitted were executed, empirically tested, and validated against a live PostgreSQL 16 database cluster under our direct supervision.
3. No fabricated outputs, synthetic claims of correctness, or unverified results are included in the project deliverables.

---

## 2. Inventory of AI Assistance

| Category | AI Tool / Platform | Specific Application | Human Verification & Engineering Action |
|---|---|---|---|
| **Code Review & Auditing** | Antigravity AI Assistant | Static code inspection of SQL scripts (`01_schema.sql` through `05_validation.sql`) and Python files to identify syntax discrepancies and logic edge cases. | Identified genuine defects: nullable `session.shift_id`, Q6 strict inequality on back-to-back shift boundaries, and Txn A same-day booking conflict. |
| **SQL Hardening & Trigger Design** | Antigravity AI Assistant | Syntax generation for PL/pgSQL triggers (`validate_shift_status()`, `validate_stock_batch_product()`, and row-locking logic in `validate_booking()`). | Reviewed trigger lifecycle, confirmed serializability via row locks, verified error handling against PostgreSQL 16 engine. |
| **Test Automation** | Antigravity AI Assistant | Scaffolding the automated negative testing suite (`06_failure_tests.sql`) and 17-rule Python test runner (`test_all_rules.py`). | Authored boundary test fixtures (capacity limits, concurrent race condition threads, 16:00 closing timing); verified all 17 tests passed live. |
| **Documentation & Report Structuring** | Antigravity AI Assistant | Markdown formatting, BCNF mathematical notation alignment, and draft text polishing for readability. | Verified mathematical correctness of functional dependencies and superkey proofs; confirmed that all report screenshots, tables, and metrics reflect genuine database execution. |

---

## 3. Acknowledgement & Student Sign-Off

We declare that the intellectual ownership of the database architecture, relational schema, operational design choices, and final submission content belongs to the undersigned student team. The assistance provided by AI tools served exclusively as an assistive engineering and code quality tool, consistent with university guidelines.

**Student Name:** ________________________________________  
**Student ID (SID):** ____________________________________  
**Date:** 25 October 2026  
**Signature:** ___________________________________________  
