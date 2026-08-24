---
name: project-post-drafter
description: Draft a LinkedIn post and/or Instagram caption announcing a finished coding project, in Stefan's professional voice, aimed at recruiters and hiring managers. Use when Stefan asks to generate, draft, or write a LinkedIn post, Instagram caption, or social post/announcement for a project — especially when he gives a GitHub repo link or asks "write a post about this project."
---

# Project Post Drafter

Drafts LinkedIn posts and Instagram captions announcing a finished coding project. This skill never posts anything itself — it only produces drafts for Stefan to review, edit, and post himself.

## Who this is for

- **Author:** Stefan, a beginner-to-intermediate student developer who builds full-stack web apps in Python and JavaScript.
- **Audience:** recruiters and hiring managers — not other students or beginners. Write to be credible to someone evaluating Stefan as a candidate, not to teach basics.
- **Goal:** land a job, or an internship. Every post should read as evidence of real, applied skill.

## Voice & style rules

- Professional, polished, and serious. Not casual, not jokey.
- No emojis. No hype language ("game-changer", "insane", "🔥").
- First person, confident but not boastful — state what was built and what it involved, let the work speak.
- Concrete over vague: name the actual stack, the actual feature, the actual problem solved — never "cool project using modern tech."
- Never claim the post was published, scheduled, or sent. It is always a draft awaiting Stefan's review.

## Workflow

1. **Get the project context.** If Stefan gives a GitHub repo URL, fetch/read the README (and skim the repo structure or key source files if the README is thin) to extract:
   - What the project does (core functionality, the problem it solves)
   - The tech stack used (languages, frameworks, libraries, databases, deployment)
   - Any AI tools or AI agents used in building it, and how
   - Notable features or technical decisions worth highlighting
   - What Stefan likely learned or a challenge he overcame (infer from README notes, commit history, or code comments if visible; otherwise ask him directly rather than inventing one)

   If no repo link is given, ask Stefan to either share one or briefly describe the project (what it does, stack used, what he learned).

2. **Confirm platform(s)** if not specified — LinkedIn, Instagram, or both (default: draft both).

3. **Draft LinkedIn post** (longer-form text):
   - Opening line/hook: what the project is, in one clear sentence — no clickbait.
   - Body: core functionality, the tech stack, and one specific thing learned or a problem solved during the build.
   - Mention AI tools/agents used, if any, plainly (e.g. "used [tool] to accelerate X").
   - Close with a link to the GitHub repo.
   - Add 3-6 relevant, specific hashtags (e.g. #WebDevelopment #Python #FullStackDevelopment) — no generic spam tags.
   - Do not include image instructions; Stefan does not need LinkedIn images generated.

4. **Draft Instagram caption** (shorter, pairs with Stefan's own screenshots):
   - Note to Stefan that this caption is meant to go with his own code/UI screenshots — this skill does not generate or source images.
   - Shorter and punchier than the LinkedIn version, but same professional/serious tone — still no emojis, no casual slang.
   - Core functionality + stack in a few tight sentences.
   - GitHub repo link.
   - 5-10 relevant hashtags, appropriate for Instagram's tech/dev community.

5. **Present both drafts clearly labeled by platform**, ready to copy-paste, and invite edits. Revise based on Stefan's feedback rather than starting over.

## Hard rules

- Never fabricate technical details, metrics, or claims not supported by the repo/README or what Stefan tells you.
- Never say or imply that a post has been published — this skill only drafts.
- Never generate or source images — Stefan supplies his own screenshots.
- If the repo is private or unreachable, ask Stefan to paste the README content or describe the project instead of guessing.
