# Campus Pantry: FoodHub Scheduling, Attendance & Traceable Inventory

**COMP9120 Database Management Systems — The University of Sydney**  
*Lead Database Engineers: Group Project Team*

---

## 🎯 1. Project Overview & Operational Challenges
FoodHub provides vital food relief to University of Sydney students. Operating without a robust database caused severe challenges:
- **Attendance Uncertainty:** Booking totals did not reflect actual turnouts, hindering perishable food planning.
- **Congestion & Inequity:** Unregulated walk-ins caused long queues and potential double-booking.
- **Untracked Stock Movement:** Overwritten stock balances concealed food waste, damage, and shrinkage.
- **Roster Understaffing:** Shifts ran with insufficient supervisory staff.

---

## 💡 2. Architectural Solution
A robust relational database built on **PostgreSQL 16**, paired with an ACID-compliant Python 3 prototype:

```
[Student Interface]           [Front-Desk Barcode Scanner]          [Staff & Inventory Operations]
        │                                  │                                      │
        ▼                                  ▼                                      ▼
Session Reservations             Idempotent QR Attendance            Batch Traceability & Audits
(One/day default, max 50)      (Confirms attendance at desk)       (Unique StockNumbers, Count History)
        │                                  │                                      │
        └──────────────────────────────────┴──────────────────────────────────────┘
                                           │
                                           ▼
                      PostgreSQL 16 Engine (search_path = campus_pantry)
              Triggers: Concurrency Locking, Staffing Constraints, Validation
```

---

## 🔑 3. Key Relational Innovations & Business Rules

### A. Dual Concurrency Row-Level Locking
- Prevents double-booking races across simultaneous student requests.
- Serializes concurrent reservations for the final available seat:
  ```sql
  SELECT session_date, capacity FROM session WHERE session_id = NEW.session_id FOR UPDATE;
  PERFORM 1 FROM student WHERE unikey = NEW.student_unikey FOR UPDATE;
  ```

### B. Shift Supervision Integrity
- Shifts require **strictly two staff members**: 1 Main Supervisor and 1 Assistant.
- `UNIQUE (shift_id, assignment_role)` prevents duplicate roles; `validate_shift_status()` trigger prevents unstaffed shifts from opening.

### C. Dignified Front-Desk Workflow & 16:00 No-Show Policy
- Emailed random alphanumeric tokens (`qr_token`) protect client privacy.
- Students can arrive at any point during operating hours without penalty.
- Un-scanned bookings are marked `ABSENT` strictly after the daily 16:00 closing time.

### D. Provenance & Batch Stock Tracking
- Every food batch receives a persistent identifier (`STK-######`) linked to invoice lines.
- Append-only `stock_count` table records opening, closing, and spot counts without destroying historical data.

---

## 📊 4. Empirical Verification & Analytical Insights

| Category | Verified Invariant | Result |
|---|---|---|
| **Boundary Tests** | 50th booking succeeds; 51st booking rejected with error | **100% Passed** |
| **Concurrency** | Simultaneous threads competing for last seat: 1 succeeds, 1 rejected | **100% Passed** |
| **Integrity Checks** | 12 invariant SQL checks (over-capacity, orphan batches, invalid times) | **0 Anomalies** |
| **Analytical Reports** | Q1–Q12 queries (shift reconciliation, demand velocity, reorder alerts) | **Verified Live** |

```
                       Dispensing by Product (Q2 Summary)
Rice 1 kg       ████████████████████████████████████ 55 packs
UHT Oat Milk 1L ███████████████████████ 35 cartons
Sliced Bread    ██████████████████ 28 loaves
Canned Beans    ████████████████ 25 cans
Tuna 185g       ████████████████ 25 cans
Oats 500g       ████████████████ 25 packs
Pasta 500g      ███████████████ 24 packs
Fresh Apples    ███████████ 18 bags
```

---

## 🚀 5. Impact & Summary
Campus Pantry delivers complete operational transparency, eliminates double-bookings, preserves supply-chain accountability, and safeguards student dignity through reliable, high-performance database engineering.
