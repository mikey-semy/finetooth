"""The review tool, one module per concern. `scripts/review.py` is the command.

The modules form layers: a module imports only modules of the layers BEFORE its own in
LAYERS — the ones it stands on — and never one after. The command modules (`commands/`)
are one layer and do not import each other; `cli` dispatches to them. A test reads this
tuple and every import of the package, so the order is declared here and nowhere else.
"""

LAYERS = (
    "base", "git", "workspace", "model", "i18n", "text", "fingerprint", "blocks",
    "register", "verdicts", "coverage", "history", "seams", "journal", "gates", "importing",
    "roles", "settings", "report.sarif", "report.summary", "report.html", "refs",
    "commands", "cli",
)
