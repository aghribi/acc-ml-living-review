"""
logs.py
=======

Logging utilities for the **Living Review** project.

This module manages:
- Persistent scan logs (`scan_log.json`) storing metadata about each run.
- Error logs (`errors.log`) with stack traces.
- Retrieval of the last scanned date range.

Contents
--------
- append_scan_log: record metadata about a scan (papers, chunks, status).
- log_error: record exceptions and stack traces in a log file.
- get_last_scan: retrieve the last recorded scan range.

Typical Usage
-------------
>>> from living_review import logs
>>> logs.append_scan_log("logs", start, end, npapers=42)
>>> logs.log_error("logs", Exception("Something went wrong"))
>>> last = logs.get_last_scan("logs")
"""

import json
from pathlib import Path
from datetime import datetime
import traceback


def append_scan_log(logdir, start, end, npapers, nchunks=1, status="ok", error_msg=None):
    """
    Append an entry to the scan log (`scan_log.json`).

    Parameters
    ----------
    logdir : str or Path
        Directory where the log files are stored.
    start : datetime.date or str
        Start date of the scan.
    end : datetime.date or str
        End date of the scan.
    npapers : int
        Number of papers processed.
    nchunks : int, optional
        Number of chunks processed (default=1).
    status : str, optional
        Status string for the run (default="ok").
    error_msg : str, optional
        Error message if the scan encountered an issue.

    Returns
    -------
    None
        Updates `scan_log.json` with a new entry.
    """
    logdir = Path(logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    logfile = logdir / "scan_log.json"

    if logfile.exists():
        with open(logfile, "r", encoding="utf-8") as f:
            log = json.load(f)
    else:
        log = []

    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "scanned_range": {"start": str(start), "end": str(end)},
        "papers": npapers,
        "chunks": nchunks,
        "status": status,
    }
    if error_msg:
        entry["error"] = error_msg

    log.append(entry)

    with open(logfile, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)


def log_error(logdir, exc: Exception):
    """
    Append an error entry with stack trace to `errors.log`.

    Parameters
    ----------
    logdir : str or Path
        Directory where the error log is stored.
    exc : Exception
        Exception object to log.

    Returns
    -------
    None
        Writes a timestamped error entry to `errors.log`.
    """
    logdir = Path(logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    errfile = logdir / "errors.log"

    with open(errfile, "a", encoding="utf-8") as f:
        f.write("="*60 + "\n")
        f.write(f"[{datetime.utcnow().isoformat()}] ERROR: {type(exc).__name__}\n")
        f.write("".join(traceback.format_exception(exc)))
        f.write("\n")


def get_last_scan(logdir):
    """
    Retrieve the last scan range from `scan_log.json`.

    Parameters
    ----------
    logdir : str or Path
        Directory containing the scan log file.

    Returns
    -------
    dict or None
        Dictionary with keys `{"start": str, "end": str}` if available,
        otherwise `None`.
    """
    logfile = Path(logdir) / "scan_log.json"
    if not logfile.exists():
        return None
    with open(logfile, "r", encoding="utf-8") as f:
        log = json.load(f)
    if not log:
        return None
    return log[-1]["scanned_range"]
