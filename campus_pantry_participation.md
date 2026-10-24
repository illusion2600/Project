# COMP9120 Assignment Coversheet — Group Assessment

**School of Computer Science, Faculty of Engineering, The University of Sydney**

| | |
|---|---|
| **Assignment name** | Campus Pantry: FoodHub Booking, Attendance and Inventory Database |
| **Group** | 94 (Good Good Study, Day Day Up Group) |

## Declaration

We the undersigned declare that we have read and understood the [*University of Sydney Academic Dishonesty and Plagiarism in Coursework Policy*](https://www.sydney.edu.au/policies/default.aspx?mode=glossary&word=Academic+honesty), and except where specifically acknowledged, the work contained in this assignment/project is our own work, and has not been copied from other sources or been previously submitted for award or assessment. We understand that failure to comply with the *Academic Dishonesty and Plagiarism in Coursework Policy* can lead to severe penalties as outlined under Chapter 8 of the *University of Sydney By-Law 1999* (as amended). These penalties may be imposed in cases where any significant portion of my submitted work has been copied without proper acknowledgement from other sources, including published works, the internet, existing programs, the work of other students, or work previously submitted for other awards or assessments. We realise that we may be asked to identify those portions of the work contributed by each of us and required to demonstrate our individual knowledge of the relevant material by answering oral questions or by undertaking supplementary work, either written or in the laboratory, in order to arrive at the final assessment mark.

## Assignment team members

| Student name | Student ID | Participated | Agree to share | Signature |
|---|---|---|---|---|
| Ziyue Wu | 560769023 | Yes | Yes | |
| Nikhil Khatri | 560743481 | Yes | Yes | |
| Samouwel Aboud | 570293396 | Yes | Yes | |

## Participation summary — Group 94

| Member | Student ID | Participation |
|---|---|---|
| Ziyue Wu | 560769023 | 40% |
| Nikhil Khatri | 560743481 | 40% |
| Samouwel Aboud | 570293396 | 20% |
| **Total** | | **100%** |

---

### Member 1 — Ziyue Wu (560769023) · 40%

**Role: conceptual design, Python prototype, testing and final report.**

I drafted the Week 9 milestone proposal framework, including the problem statement, intended users, data requirements and business rules, and designed the conceptual ER model. I produced the final ERD, including the overlapping IsA hierarchy, the ApprovedBy override relationship, the ShiftRequest weak entity with its Submits/ForShift identifying relationships and Reviews, and the ShiftStock relationship with a multivalued adjustment attribute, and aligned it with the implemented schema. I also produced the relational schema (RM) diagram, generated from the live PostgreSQL catalogue so that it matches `01_schema.sql`.

I wrote the SQL queries and built the PostgreSQL database that the prototype runs on: the schema (16 tables with keys, constraints, triggers and three reporting views), the seed data, the twelve analytical queries (Q1–Q12, covering shift stock movements, dispensing estimates, latest counts, low stock, session demand, handover variances, rosters, purchase costs, attendance rates, expiry alerts and near-capacity sessions), the transaction and validation scripts, and a one-shot rebuild script with fixes for the booking trigger, UniKey format and identity sequences.

I developed the Python command-line prototype (`cli.py`, `services.py`, `db.py`) and its README, covering student session bookings, session capacity management, cancellations, QR-token check-ins, end-of-day no-show marking, admin-override bookings, staff shifts and volunteer rostering, and inventory operations (stock counts, receipts and waste). Each operation runs as a single PostgreSQL transaction that rolls back on any error, and bookings use row-level locking to prevent concurrent double-booking and overselling.

I worked on testing duplicate-booking prevention, the 50-student session limit, concurrent bookings, rollback behaviour and database integrity. I rebuilt the whole system on a clean PostgreSQL 16 database and confirmed that all 10 failure tests and all 17 automated Python tests passed (run twice to check repeatability), that the integrity checks in `05_validation.sql` returned no violations, and that the concurrency demo and CLI workflows behaved correctly. This review also identified stale figures in the earlier report draft and the limitations now documented in the report.

I wrote the final project report in the official template: requirements, ER design rationale, ER-to-relational mapping, functional dependencies and normalisation analysis (3NF/BCNF trade-offs), integrity constraints, transaction and concurrency reasoning, testing evidence and APA references, and merged the group's edits. I also prepared demo notes on the system's limitations for the showcase video.

### Member 2 — Nikhil Khatri (560743481) · 40%

**Role: project initiation, requirements analysis, conceptual design, SQL planning, Python CLI development and system integration.**

I initiated the idea for the Campus Pantry: FoodHub Booking, Attendance and Inventory Database System and helped establish the project's overall direction and objectives. I developed an initial Entity-Relationship Diagram (ERD) to outline the proposed database structure and identify the key entities and relationships required by the system. I also summarised the project requirements and prepared sample SQL queries to support the initial development process.

During implementation, I took responsibility for building essential system features and expanding the application's functionality. I significantly enhanced the initial Python command-line interface, adding and refining workflows for student session bookings and cancellations, session capacity management, QR-token-based attendance, staff operations, volunteer shift requests and approvals, and inventory management. I also worked on integrating these features with the PostgreSQL database to ensure that application operations aligned with the intended database structure and business rules.

I contributed to system testing and debugging by checking the functionality of different workflows, investigating errors and validating important operational rules. This included examining booking restrictions, capacity limits, attendance processing, volunteer shift workflows and inventory operations. I also worked on identifying areas requiring further improvement to make the system more reliable and suitable for demonstration.

Finally, I took responsibility for preparing the demonstration video, showcasing the system's key features and explaining how the implemented workflows address the project's objectives. My contribution covered the initial idea, preliminary database design, feature development, system enhancements, testing and final demonstration.

### Member 3 — Samouwel Aboud (570293396) · 20%

**Role: project review and planning, documentation and poster development.**

Sam contributed to the planning and presentation aspects of the Campus Pantry: FoodHub Booking, Attendance and Inventory Database System. During the initial stages, he prepared the project review documents, helping establish the foundation for understanding the problem, defining the project's direction and organising the team's early work.

His contribution to project planning supported the transition from the initial concept to the more detailed requirements, database design and implementation stages. The review materials provided a starting point for the team to refine the project's objectives, scope and intended functionality as development progressed.

Sam was also responsible for documentation, helping communicate the project's purpose, design and functionality in a structured manner. This work supported the team's efforts to present the system clearly and explain how its booking, attendance, volunteer management and inventory features fit within the overall solution.

In addition, Sam took responsibility for creating the project poster. This involved presenting the project in a concise and accessible format, highlighting its main objectives and features for viewers. The poster complements the technical implementation by providing a visual overview of the system and its intended purpose.

Overall, Sam's contribution focused on project review, planning, documentation and visual presentation. These responsibilities supported the organisation and communication of the project from its initial planning stages through to its final presentation.
