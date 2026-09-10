# Panel Notes

Native Markdown notes for Omarchy: one default note per app, plus named note
tabs added with +. Notes and tabs persist across app windows and restarts. The same name in
different apps refers to separate notes.
Right-click/F2 renames a named tab without changing its note identity or files.
Removing a custom tab keeps its notes in All notes. The panel stays visible when
using an adjacent app and hides on source geometry changes.

No automatic app context detection ships in the current product. Future
integrations must be discussed and designed individually before implementation.
The provider/content boundaries remain available for future work; their existence
does not authorize building or enabling integrations.

The requirements, scope, acceptance cases and implementation tracker live in
[docs/plan.md](docs/plan.md). Do not replace them with inferred product scope.
