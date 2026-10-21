# Group Participation & Contribution Statement

**Course:** COMP9120 Database Management Systems  
**Project:** Campus Pantry — University Food Pantry Database System  
**Semester:** Semester 1, 2026  
**Institution:** The University of Sydney  

---

## 1. Team Contribution Summary

All group members actively participated in the design, development, debugging, testing, and documentation of the Campus Pantry database project. The percentage allocations below accurately reflect the division of labor across the conceptual, relational, code implementation, testing, and reporting phases:

| Member Name | Student ID (SID) | UniKey | Primary Responsibilities | Contribution % | Signature |
|---|---|---|---|---|---|
| **Member 1 (Lead Database Engineer / Submitting Student)** | *[Enter SID]* | *[Enter UniKey]* | Codebase audit, bug fixes, NOT NULL schema enforcement, PL/pgSQL staffing & concurrency triggers, `06_failure_tests.sql`, automated 17-rule test suite, live PostgreSQL testing, final report, video script, poster | **50%** | *_______________* |
| **Member 2 (Teammate / Co-Engineer)** | *[Enter SID]* | *[Enter UniKey]* | Initial conceptual ER design, preliminary relational schema draft (`01_schema.sql`), synthetic seed dataset (`02_seed_data.sql`), analytical queries (Q1–Q12), Python CLI foundation & service layer architecture | **50%** | *_______________* |
| **Total** | | | | **100%** | |

*(Note: If your group has 3 or 4 members, adjust the rows and split the percentage evenly, e.g., 33%/33%/34% or 25% each, ensuring the sum remains exactly 100%.)*

---

## 2. Detailed Task Breakdown by Project Phase

### Phase 1: Problem Definition & Conceptual Modeling
- **Collaborative:** Analysis of FoodHub operating rules, user persona definitions, identification of overlapping roles, and boundary rules (one booking per day, 50-person session limit, dual staff per shift).
- **Deliverables:** Approved Conceptual ERD, cardinality mapping, participation constraints.

### Phase 2: Relational Schema & Integrity Constraints
- **Initial Implementation:** Relational mapping, base tables, sequence definition, initial check constraints, initial views (`v_booking_attendance`, `v_latest_stock_count`, `v_shift_stock_report`).
- **Refinement & Hardening:** Implementation of `NOT NULL` session-shift relationship, UniKey regex check, `validate_shift_status()` trigger, `validate_stock_batch_product()` trigger, and dual row-level locking (`SELECT ... FOR UPDATE`) in `validate_booking()`.

### Phase 3: Analytical Queries & Transaction Workflows
- **Analytical Queries:** Design of queries Q1 through Q12. Correction of Q6 lateral join inequality handling consecutive back-to-back shifts.
- **Transaction Implementation:** Standard booking, admin override exception logging, QR check-in, booking cancellation, 16:00 operating day close no-show processing, atomic closing stock counts, and explicit rollback demonstration.

### Phase 4: Prototype & Concurrency Testing
- **Prototype:** Python 3 command-line interface (`cli.py`), modular transaction service layer (`services.py`), dynamic environment variable connection manager (`db.py`).
- **Verification:** Multi-threaded concurrency demo (`concurrency_demo.py`), automated negative test suite (`06_failure_tests.sql`), and 17-rule automated test runner (`test_all_rules.py`) with 100% empirical pass rate.

### Phase 5: Submission Deliverables
- **Documentation & Presentation:** Master README, comprehensive final technical report (Parts A–D), one-page presentation poster, 3-minute showcase presentation plan and recording script, AI-use declaration.

---

## 3. Team Confirmation
We hereby confirm that the division of contributions described above is an accurate, fair, and mutually agreed reflection of all group members' work throughout the project.

**Signed:**

Member 1: ____________________________ Date: _________________  
Member 2: ____________________________ Date: _________________  
