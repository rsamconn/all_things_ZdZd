#!/usr/bin/env python3
"""
Aggregate cutflow tables from many ZdZdPostProcessing log files into a
single output file.

Input
-----
A plain-text file (the *list file*) with one log-file path per line.
Blank lines and lines whose first non-whitespace character is ``#`` are
ignored, so lines can be commented out with ``#``.

Output
------
A single text file containing, for each input log:

    <sample identifier>
    <cutflow table>
    <blank line>
    <sample identifier>
    <cutflow table>
    ...

A warning is printed to stderr if any sample identifier appears more
than once across the inputs.

Usage
-----
    python aggregate_cutflows.py <list_file> [-o OUTPUT]
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
import re
from pathlib import Path
from typing import List, Optional, Pattern, Tuple, Union

def _as_pattern(p: Union[str, Pattern[str]]) -> Pattern[str]:
    """Compile *p* if it is a string, otherwise return it unchanged."""
    return re.compile(p) if isinstance(p, str) else p


def extract_cutflow(
    filepath: str | Path,
    processing_re: Union[str, Pattern[str]] = re.compile(r"Processing\s+(\S+\.root)\b"),
    header_marker: str = '#==',
    sep_re: Union[str, Pattern[str]] = re.compile(r"^-{3,}\s*$"),
) -> Tuple[Optional[str], Optional[List[str]]]:
    """
    Extract the cutflow table lines from an input ZdZdPostProcessing log file, along with a sample ID.
    Optionally set the table header and separator pattern, as well as the patter for locating the sample ID.
        processing_re : str or compiled regex, optional
        Regex used to locate the line that names the input ROOT file.  Its
        first capture group must be the full path to the ``*.root`` file;
        the sample identifier is taken as the directory immediately above
        that file.  Defaults to :data:`DEFAULT_PROCESSING_RE`.
    """
    processing_re = _as_pattern(processing_re)
    sep_re = _as_pattern(sep_re)

    sample_id: Optional[str] = None
    cutflow_lines: Optional[List[str]] = None

    in_table = False
    buf: List[str] = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")

            # --- sample identifier ---------------------------------------
            if sample_id is None:
                m = processing_re.search(line)
                if m:
                    parts = m.group(1).split("/")
                    if len(parts) >= 2:
                        sample_id = parts[-2]

            # --- cutflow table -------------------------------------------
            if cutflow_lines is None:
                if not in_table:
                    # Detect the header row.
                    if line.startswith("|") and header_marker in line:
                        buf = [line]
                        in_table = True
                else:
                    buf.append(line)
                    # The closing separator is the *second* dashed line we
                    # see (the first one sits right under the header).
                    if sep_re.match(line) and len(buf) > 2:
                        cutflow_lines = buf
                        in_table = False

            # Early exit once we have everything.
            if sample_id is not None and cutflow_lines is not None:
                break

    return sample_id, cutflow_lines


def read_filelist(list_path: Union[str, Path]) -> List[Path]:
    """
    Return the list of paths in *list_path*, skipping blank lines and
    lines whose first non-whitespace character is ``#``.
    """
    paths: List[Path] = []
    with open(list_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            paths.append(Path(line))
    return paths


def aggregate_cutflows(
    list_path: Union[str, Path],
    output_path: Union[str, Path],
) -> int:
    """
    Read the file list at *list_path*, extract the cutflow from each
    referenced log file, and write everything to *output_path*.

    Returns the number of cutflows written.
    """
    files = read_filelist(list_path)

    # (sample_id, cutflow_lines, source_path)
    blocks: List[Tuple[str, List[str], Path]] = []

    for f in files:
        if not f.exists():
            print(f"WARNING: file not found, skipping: {f}", file=sys.stderr)
            continue

        sid, cf = extract_cutflow(f)

        if cf is None:
            print(f"WARNING: no cutflow table in {f}, skipping",
                  file=sys.stderr)
            continue
        if sid is None:
            print(f"WARNING: no sample identifier in {f}; "
                  f"using '<unknown:{f.name}>'", file=sys.stderr)
            sid = f"<unknown:{f.name}>"

        blocks.append((sid, cf, f))

    _warn_on_duplicates(blocks)

    with open(output_path, "w", encoding="utf-8") as out:
        for i, (sid, cf, _src) in enumerate(blocks):
            if i > 0:
                out.write("\n")  # blank line between blocks
            out.write(sid + "\n")
            out.write("\n".join(cf) + "\n")

    print(f"Wrote {len(blocks)} cutflow(s) to {output_path}")
    return len(blocks)


def _warn_on_duplicates(
    blocks: List[Tuple[str, List[str], Path]],
) -> None:
    """Print a warning to stderr for any sample identifier seen >1 time."""
    counts = Counter(sid for sid, _, _ in blocks)
    dups = {s: n for s, n in counts.items() if n > 1}
    if not dups:
        return

    sources = defaultdict(list)
    for sid, _, src in blocks:
        if sid in dups:
            sources[sid].append(src)

    print("WARNING: duplicate sample identifier(s) detected:",
          file=sys.stderr)
    for sid, n in dups.items():
        print(f"  '{sid}' appears {n} times in:", file=sys.stderr)
        for src in sources[sid]:
            print(f"    - {src}", file=sys.stderr)


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Aggregate ZdZdPostProcessing cutflow tables into one file.",
    )
    p.add_argument(
        "list_file",
        help="text file with one log-file path per line ('#' for comments)",
    )
    p.add_argument(
        "-o", "--output",
        default="cutflows.txt",
        help="output file (default: cutflows.txt)",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    aggregate_cutflows(args.list_file, args.output)