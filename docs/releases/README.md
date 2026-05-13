# Release notes

One markdown file per tag: `vX.Y.Z.md`. These files are the **body**
pasted into GitHub Releases (`https://github.com/kusanagi0x/fmg-api-client/releases`).

This is the long-form announcement of a release — intended for someone
landing on the GitHub release page who needs install steps, supported
versions, and a feature overview without reading the README first.

Distinct from `CHANGELOG.md` at the repo root, which is the canonical
terse list of changes per version (Keep-a-Changelog format). Both have
a place; keep them in sync but do not duplicate prose between them.

## Workflow per release

1. Land all commits for the release on `main` (CI green).
2. Update `CHANGELOG.md`: move `[Unreleased]` items into a new
   `[X.Y.Z] - YYYY-MM-DD` section.
3. Create `docs/releases/vX.Y.Z.md` from the previous release as a
   template; edit headings and content.
4. Commit + push.
5. Tag: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.
6. On GitHub: **Releases → Draft a new release**, select the tag,
   paste the contents of `docs/releases/vX.Y.Z.md` into the body.
7. Publish.
