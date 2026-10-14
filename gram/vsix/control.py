"""
VSIX Diagnostic State Controller (`gram.vsix.control`).
=======================================================
Adapts the standalone `Diagnostics` telemetry stack to VSIX analysis, rule inspection,
and language server schema indexing.
"""
from __future__ import annotations

from gram import config, utilities


class VSIXState(utilities.Diagnostics):
    """
    Diagnostic telemetry controller for VSIX analysis and language server indexing.
    """

    def __init__(self, logfile: str | None = None) -> None:
        super().__init__(
            logfile or "vsix-analysis",
            "VSIX",
            "pending",
            True,
            config.INFO_GENERATE_LOGFILE,
            config.INFO_GENERATE_LOGFILE_ON_ERROR,
        )


__all__ = ["VSIXState"]