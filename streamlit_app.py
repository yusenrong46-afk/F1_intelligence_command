"""Streamlit Cloud entrypoint for the F1 command center."""

from __future__ import annotations

from dashboard.f1_command_center import main


if __name__ == "__main__":  # pragma: no cover - exercised by deployment/runtime path
    main()
