# Security and privacy

Personalized books may contain children’s names, likenesses, family details,
and generated media. Treat every client project as private data.

- Keep client folders outside the workflow repository.
- Never commit `personas/`, `input/`, `output/`, `clients/`, credentials, or
  source-book corpora.
- Obtain guardian consent and the right to use every supplied photo before any
  external image-generation call.
- Do not reuse a child’s images or story in another project, marketing, model
  training, or a public example without separate explicit permission.
- Use the Codex image-generation lane documented by this workflow; do not add
  API keys or provider exports to the repository.
- If sensitive data is committed accidentally, stop sharing the repository,
  rotate exposed credentials, remove the data from Git history, and notify the
  affected owner. A later `.gitignore` entry does not erase Git history.

Report a suspected vulnerability privately to the repository owner. Do not put
real child data or credentials in a public issue.

