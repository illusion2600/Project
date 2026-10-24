# Campus Pantry Group 94 canonical submission package

Prepared on 24 October 2026 for Ziyue Wu, Nikhil Khatri and Samowel Aboud.

This ZIP is the single canonical handover for the revised university project. Use these versions together. It includes the final application, full project report, one-page poster and editable PowerPoint, narrated showcase video, a prepared contribution form, and the change/validation evidence.

**Before Canvas submission:** each group member must review the contribution summary, confirm its reported allocation and provide their own required signature. The form is prepared but unsigned. No signature or declaration has been made on anyone's behalf. Review the AI acknowledgement and the final work as a group. This package has not been submitted to Canvas.

## The four assignment items

| Item | Canonical file | Status |
| --- | --- | --- |
| Project report | submission/Project_Report.pdf | Complete; four required sections, full ER and relational mapping, final validation |
| One-page poster | submission/Poster.pdf | Complete; editable original is submission/Poster.pptx |
| Recorded video | submission/Showcase.mp4 | Complete; under three minutes, narrated synthetic-data walkthrough |
| Contribution summary | submission/Contribution_Summary.pdf | Prepared from the existing group statement; member confirmation and signatures remain |

The contribution summary is also editable as a Word document. The video transcript identifies the computer-generated narration. Showcase_Notes.txt supplies speaking points and likely questions. SUBMISSION_READINESS.txt records the final handover status.

## Application and evidence

Start with README.md for installation. Python and a running PostgreSQL server are prerequisites. Run `python showcase.py` for the isolated after-hours demo and `python tests/run_tests.py` for the regression suite after configuring TEST_PG settings as documented. The ordinary CLI is `python campus_pantry_app/cli.py` with its own initialized database and normal PG settings.

The final application passed 44 of 44 tests twice on PostgreSQL 16.15 with Python 3.12.14 and psycopg2-binary 2.9.10. Ten concurrency scenarios are included. Raw JSON and text logs are in evidence/. The SQL failure suite contains 23 assertions. Read docs/VALIDATION.md for the test scope and reproduction instructions.

docs/Foodhub_Changes_and_Validation.pdf explains all completed changes and why they were needed. It supplements the full project report. docs/CHANGELOG.md is the searchable change list. The application source folders, requirements, tests and safe SQL setup remain at the package root so documented commands work unchanged.

## Scope and responsible use

This is a local university showcase using synthetic sample identities. UniKey selection is simulated sign-in, and token entry is simulated scanning. SSO, email delivery and QR-image generation are not integrated. Targeted tests are not a production security audit or load certification.

The contribution form contains the student identities supplied in the existing group statement. Share the package with the group and authorised assessment recipients. No passwords, database clusters, PostgreSQL binaries, Git history or virtual environments are included.

AI assistance is disclosed in the report, contribution form and AI_ASSISTANCE.md. The generated revision and video do not prove that an individual member performed or reviewed the work. Members remain responsible for their declarations and submitted content.

SHA256SUMS.txt lists every packaged file except itself. To verify a file in PowerShell, use `Get-FileHash -Algorithm SHA256 <file>` and compare its value with the manifest.
