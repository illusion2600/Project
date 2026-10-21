# Campus Pantry: 3-Minute Video Showcase Plan & Recording Script

**Project:** Campus Pantry (COMP9120 Database Management Systems)  
**Total Target Duration:** 2 minutes 50 seconds (Maximum allowed: 3 minutes)  
**Presenter:** Group Member / Lead Presenter  
**Required Windows/Tabs:**
1. Split Screen Left: Terminal running `python cli.py` (Command-Line Prototype).
2. Split Screen Right: Terminal or pgAdmin Query Tool connected to PostgreSQL `campus_pantry`.

---

## Video Timeline & Storyboard

| Timestamp | Phase | Core Feature Shown | Screen Action & Narration |
|---|---|---|---|
| **0:00 – 0:25** | **Introduction** | Project Overview & Architecture | • Show Architecture Slide / PostgreSQL connection.<br>• Explain FoodHub problem: scheduling, attendance, batch tracking.<br>• Point out live PostgreSQL 16 backend. |
| **0:25 – 0:55** | **Student Booking & Capacity** | 1. Available Sessions<br>2. Successful Booking<br>3. QR Token Issuance | • Log into CLI as student `alex1001`.<br>• Show session availability (spaces remaining).<br>• Book session slot.<br>• Show generated QR check-in token. |
| **0:55 – 1:25** | **Business Rule Enforcement** | 4. Duplicate Booking Rejection<br>5. Staff Admin Override | • Attempt second booking for `alex1001` on same date $\to$ **Immediate trigger rejection**.<br>• Log in as Staff `must2203` $\to$ Create approved administrative override with reason. |
| **1:25 – 1:55** | **Front Desk Operations** | 6. QR Check-In<br>7. Repeated Scan Idempotency | • Front desk scans student's QR token $\to$ Marked `ATTENDED`.<br>• Re-scan same token $\to$ Rejected cleanly as already attended.<br>• Show live attendance update in database view. |
| **1:55 – 2:25** | **Inventory & Analytical Reports** | 8. Physical Stock Count<br>9. Consumption Report (Q2) | • Staff records physical stock closing count (`STK-000001`).<br>• Run Query Q2 or low stock report $\to$ shows live estimated dispensing and balances. |
| **2:25 – 2:50** | **Integrity & Concurrency** | 10. Concurrency Locking<br>11. Automated Test Suite | • Run `python concurrency_demo.py` $\to$ shows row-level lock preventing race condition.<br>• Display final 17/17 test pass summary table. |

---

## Detailed Step-by-Step Recording Script

### Scene 1: Introduction (0:00 – 0:25)
**Visual:** Presenter webcam + screen showing terminal with PostgreSQL connection ready.  
**Narrator:**  
> "Welcome to our demonstration of **Campus Pantry**, a relational database system developed for the University of Sydney FoodHub charity.  
> Managing a high-demand student pantry requires strict scheduling, dignified front-desk check-in, dual-staff shift supervision, and immutable inventory batch tracking.  
> Our system is built on **PostgreSQL 16** with strict BCNF relations, PL/pgSQL triggers, and dual row-level locking. Let's see it in action."

---

### Scene 2: Student Booking & Capacity (0:25 – 0:55)
**Visual:** Terminal running `python cli.py`.  
**Terminal Action:** Enter `alex1001` at UniKey prompt.  
**Narrator:**  
> "First, we log in as a student, Alex (`alex1001`).  
> Alex selects Option 1 to view today's half-hour sessions. We see real-time capacity figures powered by our `v_booking_attendance` view.  
> Alex chooses Option 2 to book Session 3. The system executes a multi-step transaction, locks the session and student rows, validates that capacity is under 50, and confirms Booking ID 16 with a secure, non-identifying QR token."

---

### Scene 3: Business Rule Rejection & Admin Override (0:55 – 1:25)
**Visual:** Student tries to book again; then switch to staff login.  
**Terminal Action:** Select Option 2 again $\to$ try to book Session 4.  
**Narrator:**  
> "What happens if Alex attempts to book a second session on the same day?  
> Our `validate_booking()` trigger immediately intervenes: *'Student already has an active booking on this date.'*  
> Now let's switch to our Main Supervisor, Mustafa (`must2203`). Under exceptional welfare circumstances, an administrator can grant a special walk-in override. Mustafa logs the student, the session, and the welfare reason. The database permits the exception while logging full staff accountability."

---

### Scene 4: Front-Desk Check-In & Attendance (1:25 – 1:55)
**Visual:** Staff menu Option 1: "Front desk: check in a QR code".  
**Terminal Action:** Enter token from Alex's booking.  
**Narrator:**  
> "When the student arrives at FoodHub, front-desk staff scan the QR code.  
> The system updates the booking status from `CONFIRMED` to `ATTENDED` and timestamps attendance.  
> If the barcode is scanned a second time, the database safely recognizes that the student is already checked in, preventing duplicate attendance without throwing unhandled exceptions.  
> Un-scanned bookings are kept as CONFIRMED until 16:00 closing, allowing late arrivals without penalty before being marked ABSENT."

---

### Scene 5: Stock Counts & Analytical Reporting (1:55 – 2:25)
**Visual:** Staff menu Option 8: "Stock: record a count", then show Query Q2 or CLI reports.  
**Terminal Action:** Record CLOSING count of 88 for `STK-000001`. Run Option 7 (Day summary).  
**Narrator:**  
> "On the inventory side, every food shipment is assigned a persistent StockNumber.  
> Staff record physical opening and closing counts, creating an immutable audit trail in `stock_count` while reconciling shift balances.  
> Management queries like Query Q2 instantly aggregate food dispensing velocity across completed shifts, ensuring that donations and purchases match real student needs."

---

### Scene 6: Concurrency Safety & Empirical Validation (2:25 – 2:50)
**Visual:** Run `python concurrency_demo.py` and display test results.  
**Narrator:**  
> "Finally, let's look at concurrency safety. When two simultaneous threads race for the same student or the final session place, PostgreSQL's row-level locking (`SELECT ... FOR UPDATE`) guarantees serializability—one succeeds and the other is safely rejected.  
> Our automated test suite validates all 17 core business rules, including boundary capacity, staffing triggers, and rollback atomicity, with a 100% pass rate.  
> Thank you!"

---

## Instructions for the Student Presenter
1. **Resolution:** Record at 1080p (1920x1080) at 30fps.
2. **Font Size:** Ensure terminal font size is at least 16pt for readability.
3. **Pacing:** Practice speaking along with the timestamps above. Each section is budgeted to keep the entire showcase comfortably under the 3-minute hard limit.
