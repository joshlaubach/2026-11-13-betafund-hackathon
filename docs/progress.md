# Progress

Submission deadline: Friday 2026-11-13, 4:00 PM Pacific.

## 2026-11-12 — current worksheet flow

**Built**

- The browser page accepts a finished worksheet photo. A live vision read returns questions, final answers, and shared setup. Replay uses a saved reading for the same photo. Fake mode uses scripted data.
- The grading route tries an eligible bank match, then SymPy computation, then blind AI solves or AI judgment. Low-confidence reads are not marked in live and fake grading. Each mark has a method label.
- SymPy routes cover supported derivatives, limits, values, definite and indefinite integrals, tangent lines, equations, and solution sets. A blind AI cross-check can confirm a computed mark or make it unsure.
- The page shows marks, a per-topic skill picture, ranked recommendations, practice problems, and a Regrade button. Live Regrade makes a fresh AI solve for AI marks. Replay and fake mode keep the mark.
- The `power_rule` gate is built into the API image. It is the only Echo-checked generated practice topic. Other usable topics serve labeled bank problems.
- Uploads pass through metadata stripping before reading. Echo's own code keeps image bytes in memory; replay files contain readings and grades. The API checks local Host and write Origin headers and caps request bodies. Compose publishes ports 8000 and 3000 on `127.0.0.1`.

**Next**

1. Add a way to correct an unclear reading before marking it. Typed correction is planned; voice is optional.
2. Check the final demo photos in live and replay mode. A replay needs a saved reading for that photo and saved grades to reproduce AI marks.
3. Rebuild and smoke-check the Docker demo, then rehearse before the submission deadline.

## 2026-11-12 — earlier foundation

- The Calculus I and II bank, bank audit, strict reader, and `power_rule` practice checker were already in place. The gate enables the checker only when it matches the current bank hash.
- The drafting entry point supports live, replay, fake, and bank sources. Bank problems carry the label “bank-verified, not Echo-checked.”
- The checking code in `app/` was reused from the author's earlier math tutor. The worksheet marking routes use `core/` instead.
