# AGENTS.md — CS2 Map Balance Simulator

This file defines the durable working rules for AI coding agents. It is an operating contract, not a project-status report. Keep current progress, measurements, and next steps in the project documentation rather than copying them here.

## 1. Mission

Build and maintain CS2 Map Balance Simulator: a local, reproducible toolchain that turns Counter-Strike 2 map resources into validated geometry/navigation data and uses that data for explainable route, movement, and balance analysis.

The project is not merely a map viewer or shortest-path calculator. Correctness, traceability, reproducibility, security, and honest uncertainty matter more than feature count or impressive-looking output.

## 2. Language and communication

- Use **English for internal problem-solving, technical decisions, code, identifiers, comments, tests, documentation, commit messages, and all agent reports/final responses**.
- Preserve existing Russian/English product localization and established user-facing wording. Do not translate or rewrite unrelated UI copy merely to satisfy this language rule.
- Do not expose private chain-of-thought. Give concise conclusions, relevant reasoning summaries, assumptions, evidence, and test results.
- Prefer precise, direct technical English. Avoid filler, repeated summaries, marketing language, and claims unsupported by the repository or test output.

## 3. Source of truth and session start

- Read this file first. Consult `docs/STATE.md` for the latest project state and active objective; consult other project documents only when relevant to the task.
- Treat source code, tests, current configuration, and reproducible command output as stronger evidence than old notes or remembered assumptions.
- `docs/STATE.md` is the evolving project-state record. Research, architecture, decisions, validation, risks, release scope, and security details belong in their relevant documents.
- Do not keep dated implementation snapshots, long metric dumps, or temporary TODO lists in this file. Update the appropriate project document instead.
- At the start of a coding session, inspect the Git working tree and recent history. Preserve existing user changes; never assume the working tree is clean.
- There is **no fixed directory whitelist for development**. Work in whichever repository files are appropriate for the task, following the actual architecture and existing conventions. Do not invent local machine paths or assume a particular clone location.

## 4. Engineering workflow

Use a tight, evidence-driven loop:

1. **Understand:** identify the requested outcome, current behavior, relevant implementation, callers, data formats, tests, and documented constraints.
2. **Scope:** choose the smallest complete change. State a brief plan for complex work; do not spend tokens narrating trivial steps.
3. **Implement:** preserve established interfaces and behavior unless the task requires changing them. Avoid unrelated refactors, speculative abstractions, and feature creep.
4. **Verify:** run focused checks first, then broader tests and security checks in proportion to the change's risk.
5. **Record:** update relevant documentation and project state when behavior, assumptions, measurements, decisions, or release scope changes.
6. **Report:** summarize what changed, what was actually checked, what remains uncertain, and any follow-up required.

Do not stop at a plan when the requested implementation is clear and safe to perform. If an important requirement is ambiguous, prefer a conservative, reversible interpretation and state it. Ask only when a decision materially affects product behavior, data safety, cost, or external side effects.

## 5. Token and context efficiency

Treat context and tool usage as engineering resources, not as a reason to skip essential work.

- Read only the files and documentation needed for the current task. Use targeted search and relevant line ranges instead of dumping entire files or the whole repository.
- Do not repeatedly reread files, rediscover facts, or rerun identical commands without a reason. Reuse verified results while checking whether they could have become stale.
- Do not copy project-state details into prompts, reports, or this file when a concise reference to the authoritative document is sufficient.
- Prefer small, focused diffs and existing project utilities over large rewrites or new dependencies.
- Keep command output bounded. Summarize long logs and show only relevant errors, warnings, and results.
- Avoid exhaustive web research when repository code, tests, or primary technical documentation already answer the question. When external research is necessary, prioritize authoritative and primary sources.
- Choose checks by risk: a documentation-only edit does not require an expensive full test run; a parser, upload, path-handling, process, or server-security change deserves focused adversarial tests and the broader relevant suite.
- Never reduce verification below what correctness or security requires just to save tokens. A short, honest report is better than a long transcript of tool activity.

## 6. Evidence, accuracy, and scientific discipline

Label claims when their status could be misunderstood:

- **FACT** — directly supported by source code, a primary source, or verified data.
- **TESTED** — reproduced by a named test or command; include the conditions when relevant.
- **INFERENCE** — reasoned conclusion based on stated evidence.
- **HYPOTHESIS** — plausible but not yet verified.
- **COMMUNITY** — reported by users or community sources, not independently established.

Rules:

- Never invent measurements, movement parameters, map properties, benchmark results, test outcomes, sources, or tool capabilities.
- Never say a command, test, audit, build, or manual review passed unless it was actually run and its result was inspected.
- Distinguish missing data from a negative result. Explain limitations and confidence where they affect conclusions.
- Keep provenance for important external data and generated map bundles: source, game/build version when known, tool/version, input identity, and hashes where appropriate.
- Make assumptions explicit and test important assumptions with reproducible fixtures or experiments.
- A visual result is not proof that geometry, collision, navigation, or simulation is correct.

## 7. Project-specific technical principles

Keep the following concepts separate; do not treat one as a substitute for another:

1. **Visual:** render geometry, models, and materials.
2. **Geometric:** coordinates, polygons, triangles, and spatial relationships.
3. **Collision:** walkable surfaces, walls, player clips, clearance, and line of sight.
4. **Navigation:** nav areas, directed connections, one-way transitions, components, and ladders.
5. **Movement:** acceleration, friction, speed limits, jumping, crouching, and ladders.
6. **Gameplay data:** spawns, bombsites, buy zones, callouts, and other entities.
7. **Scenarios and balance:** multiple players, routes, timings, encounters, and team-level analysis.

For every result, be clear about which layer produced it and which layers were not modeled.

Preserve the existing architectural boundaries unless a documented decision justifies changing them:

- ingestion converts source resources into validated, reproducible data;
- analysis operates on prepared data rather than silently re-reading game files;
- navigation, collision, movement, simulation, and visualization remain distinct responsibilities;
- visualization must not alter analytical results;
- intermediate data formats should be explicit and versioned where compatibility requires it.

Further rules:

- Model navigation as directed where the source data requires it; preserve one-way links, disconnected components, ladders, and vertical relationships.
- Do not equate geometric distance with travel time.
- Do not present a movement estimate as measured unless it was measured under stated conditions.
- Keep jump, turn, landing, combat, utility, visibility, and player-choice assumptions separate. Do not silently add uncalibrated behavior to a time-only model.
- Do not collapse multi-dimensional balance evidence into a definitive verdict without justified methodology and limitations.
- Follow the current roadmap and documented scope. Do not jump to deferred features or introduce ML, combat, or full 3D work merely because it seems attractive.

## 8. Security and privacy — mandatory for every change

Use a defense-in-depth mindset. Treat uploaded files, map resources, archives, filenames, browser requests, configuration, environment variables, and third-party tools as untrusted until validated.

### Input and file handling

- Validate type, structure, size, count, and resource cost. File extensions alone are not validation.
- Resolve and normalize paths before access. Prevent traversal, unintended symlink escapes, and reads/writes outside the intended target.
- Bound memory, CPU, recursion, archive expansion, parser work, and job duration for untrusted or malformed inputs.
- Handle malformed data with controlled errors. Do not expose stack traces, secrets, or sensitive local paths to users.

### Processes and dependencies

- Never build shell commands by concatenating untrusted input. Use argument arrays and avoid `shell=True`.
- Validate executable identity and arguments; use timeouts and controlled working directories/environment where applicable.
- Do not download and execute tools automatically. Prefer trusted upstream releases, pinned versions, license review, and hash verification.
- Avoid new dependencies when the standard library or an existing dependency is sufficient. Before adding a dependency or downloading an executable, establish the concrete need, source, maintenance status, license, and security implications; obtain user approval.
- Never request administrator privileges unless strictly necessary and explicitly justified.

### Local server and browser surface

- Preserve loopback-only binding by default. Do not expose the server to a LAN or internet, weaken origin checks, or add permissive CORS without explicit approval and a security design.
- Preserve upload limits, path restrictions, job timeouts, and response security headers.
- Keep generated viewers self-contained and offline unless an explicitly approved feature requires network access.
- Escape untrusted data at the output context. Avoid unsafe HTML/JavaScript execution, dynamic code evaluation, and unsafe DOM insertion.
- Treat CSP, origin checks, content-type protections, framing restrictions, and same-origin controls as security boundaries, not cosmetic settings.

### CS2 and anti-cheat boundaries

- Game installation data is read-only. Never modify, delete, patch, or write generated files into the CS2/Steam installation.
- Do not launch CS2 or Steam, inspect or manipulate game processes or memory, inject or hook code, create overlays, automate gameplay/input, interact with matches, bypass anti-cheat, or attempt to evade VAC.
- Do not connect to game servers or anti-cheat services for this project.
- Keep the application useful with the game closed wherever the existing workflow permits.
- Do not commit or redistribute proprietary game resources or extracted assets. This includes VPKs, NAV files, demos, extracted entity/physics resources, glTF collision exports, binary sidecars, and other non-project game data.

### Secrets and privacy

- Never hardcode, print, commit, or include API keys, access tokens, passwords, cookies, private URLs, or personal machine paths in code, logs, screenshots, test fixtures, or documentation.
- Keep local configuration, credentials, generated data, caches, binaries, and user uploads out of version control.
- Do not add telemetry, analytics, external uploads, or unexpected network requests.
- Before finishing, inspect the diff and staged files for secrets, private data, generated artifacts, and unintended changes.

A security scanner is useful but is not a security proof. Review the changed code and its call paths manually, especially when handling paths, uploads, subprocesses, HTTP requests, parsers, HTML, or JavaScript.

## 9. Testing and validation

Set acceptance criteria before implementing non-trivial behavior. Select tests that can falsify the expected behavior, not just confirm the happy path.

Use the repository's existing test and validation commands. The standard project checks currently documented are:

```powershell
python -m unittest discover -s tests -v
python tools\security_scan.py
```

Check that a command or script still exists before relying on it; adapt to the current repository and active Python environment where necessary.

Testing principles:

- Run focused tests for the changed behavior, including boundary and failure cases.
- For parsers and file processing, test malformed, truncated, oversized, and inconsistent inputs where practical.
- For path and server changes, test traversal, origin/CSRF behavior, upload limits, malformed requests, timeouts, and error handling as applicable.
- For algorithms, use synthetic fixtures with known answers and regression/golden tests for previously validated behavior.
- For numerical or simulation changes, test units, coordinate conventions, edge cases, reproducibility, and sensitivity to assumptions.
- For frontend changes, validate HTML/CSS/JavaScript structure and interactions. Do not claim visual/browser verification unless it was actually performed.
- Run the full relevant suite after meaningful changes. If a check cannot be run, report exactly why and what remains unverified.
- Do not change tests merely to make an implementation pass. Update expected results only when the behavior change is intentional, justified, and documented.

## 10. Documentation and project memory

Update documentation when a change affects behavior, architecture, formats, security, installation, validation, measurements, assumptions, or release scope.

- Keep current state and next steps in `docs/STATE.md`.
- Keep research and source provenance in the relevant research documentation.
- Record material architecture choices and trade-offs as decisions.
- Keep security claims aligned with the current implementation and tests; never carry forward an old audit result as proof of the current code.
- Preserve valuable prior research. Correct outdated statements in place rather than replacing detailed evidence with generic templates.
- Do not update unrelated documentation simply to create activity.

## 11. Git and change safety

- Inspect status and the diff before and after editing. Preserve unrelated user work and never overwrite changes you did not create.
- Make focused changes and stage only the intended files.
- Never use destructive cleanup or history-rewriting commands such as `git reset --hard`, broad `git clean`, force push, or branch deletion without explicit approval.
- Do not commit, push, publish a release, change repository settings, or modify remotes unless the user explicitly requests that action or it is unambiguously part of the requested task.
- Never commit secrets, local configuration, binaries, generated artifacts, or extracted game data.
- Use clear, factual English commit messages when a commit is requested.

## 12. Actions requiring explicit approval

Ask before taking actions with material external, destructive, privacy, or cost impact, including:

- installing or upgrading dependencies, downloading executable tools, or changing system configuration;
- modifying or launching CS2/Steam, or accessing data beyond the established read-only workflow;
- exposing the local server beyond loopback or adding external network services/telemetry;
- deleting or overwriting user data, performing broad refactors, or changing established public interfaces;
- publishing releases, changing repository settings/remotes, rewriting Git history, or force-pushing;
- committing or redistributing game assets or other third-party copyrighted material.

Routine inspection, focused code edits, local tests, and reversible documentation updates within the requested scope do not require repeated confirmation.

## 13. Definition of done and final report

A task is complete when the requested change is implemented, relevant behavior is verified to an appropriate level, security implications are reviewed, and affected documentation is updated.

Every final report must be in English and briefly state:

1. **Changes:** what was changed and why.
2. **Verification:** exact tests/checks run and their observed outcomes.
3. **Security:** relevant risks reviewed or any remaining concerns.
4. **Limitations:** what was not tested, unavailable, or still uncertain.
5. **Next step:** only when a concrete follow-up is necessary.

Be candid. Never imply that a task is fully verified when only static inspection or partial tests were performed.
