# Updates for Next Version

These are the improvements targeted for the next release, with current progress and the intended outcome.

| # | Improvement | Status | Progress Summary | Target Outcome |
|---|-------------|--------|------------------|----------------|
| 1 | Invoice Generator EXE drops `.wpf` suffix | ✅ Done | `InvoiceGenerator.spec` already builds `Invoice Generator v{version}.exe` | Release EXE is named `Invoice Generator vX.XX.exe` with no `.wpf` |
| 2 | Invoice Generator release EXE gets an app icon | 🔨 Partial | `InvoiceGenerator.spec` will embed `icon.ico` if it exists; no `icon.ico` generated yet | Release EXE displays an embedded icon in Explorer and the taskbar |
| 3 | Student Tracker 2 allocations get unique display IDs | ✅ Done | `DisplayIdGenerator.NextDisplayId` now includes local change-tracker entries | Every imported allocation receives a unique `DisplayId` during batch migration |
| 4 | Student Tracker 2 release EXE gets an app icon | ⬜ Planned | `StudentTracker.Wpf.csproj` has no `<ApplicationIcon>`; `icon.ico` not yet generated | Compiled WPF app has an embedded icon for the EXE and window chrome |
| 5 | Reliable data import across both apps | ⬜ Planned | Import logic investigated; Invoice Generator `data_store.py` row-ID generation still needs hardening | Every imported student, course and enrolment/allocation is assigned a stable, unique ID with no collisions or skipped records |

## Notes

- The two applications are now treated as one banner. They remain separate codebases, but can be evolved to share data (e.g. via SQLite or a shared exchange format).
- Build artifacts (`.exe`, `.zip`) and the temporary `generate_icon.py` script are excluded from source control, so icons and release builds must be generated at build time or supplied manually.
