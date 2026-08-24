---
name: commit-and-push
description: Review current git changes, generate a clear commit message, then run git add, git commit, and git push.
---

# Commit and Push

Use this skill when the user asks to commit, create a GitHub commit, save changes to git, or push changes.

## Steps

1. Check the current git status:

```powershell
git status
```

2. Review the changes before committing:

```powershell
git diff
```

If there are staged changes, also check:

```powershell
git diff --cached
```

3. Generate a short, descriptive commit message based on the actual changes.

Use a message like:

```text
Add task management page
```

or:

```text
Style task form and dashboard layout
```

Do not use vague messages like:

```text
Update files
```

4. Make sure sensitive files are not being committed.

Especially check that `.env` is not staged. If `.env` appears in `git status`, stop and warn the user.

5. Run these commands one after the other:

```powershell
git add .
git commit -m "Generated commit message here"
git push
```

Replace `"Generated commit message here"` with an appropriate commit message based on the diff.

6. After pushing, summarize:
- commit message used
- files changed
- whether push succeeded