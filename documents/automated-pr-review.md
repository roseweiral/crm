# Automated pull-request review

The repository uses Anthropic's Claude Code GitHub Action to review non-draft pull
requests. The workflow is stored at `.github/workflows/claude-pr-review.yml`, the
location GitHub Actions requires for workflow discovery.

## Repository setup

Add an Actions repository secret named `ANTHROPIC_API_KEY`:

1. Open the GitHub repository's **Settings**.
2. Select **Secrets and variables**, then **Actions**.
3. Create a repository secret named `ANTHROPIC_API_KEY` containing the Anthropic
   API key.

Do not put the key in an environment file, workflow file, issue, or pull request.

## When it runs

The review starts when a non-draft pull request is opened, reopened, marked ready
for review, or updated with new commits. A newer run cancels an older in-progress
review for the same pull request.

The workflow does not run for draft pull requests. It has a 20-minute timeout and
limits Claude to 15 turns.

## Permissions and behavior

The job receives:

- read access to repository contents;
- write access to pull-request comments.

The action receives the workflow's built-in, short-lived `GITHUB_TOKEN`. This
allows it to read the pull request and post review comments without requiring the
Claude GitHub App to be installed. Comments therefore appear from
`github-actions[bot]` rather than `claude[bot]`.

The review prompt explicitly prohibits code changes, commits, pushes, merges, and
approvals. Allowed tools are limited to reading PR details and diffs and posting
the summary or inline review comments. Findings use P0 through P3 priorities.

The workflow is an advisory reviewer. It does not replace the project's API,
TypeScript, or Playwright checks and does not count as a formal PR approval.

## Verifying the integration

1. Confirm `ANTHROPIC_API_KEY` exists in the repository's Actions secrets.
2. Push a branch containing a small reviewable change.
3. Open a non-draft pull request into `dev`.
4. Open the pull request's **Checks** tab and select **Claude PR Review**.
5. Confirm that Claude posts a summary and, when applicable, inline findings.

If the check is absent, first confirm the workflow is present beneath
`.github/workflows` in the pull request. If Anthropic authentication fails, verify
the `ANTHROPIC_API_KEY` secret. The repository's built-in `GITHUB_TOKEN` requires no
separate secret or Claude GitHub App installation.
