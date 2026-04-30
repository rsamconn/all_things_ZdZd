#!/usr/bin/env python3
"""
This script aggregates cutflow tables from many ZdZdPostProcessing log files into a single output file.

Input - file list
-----
A plain-text file (*list_path*) with one log-file path per line (blank lines and lines commented out with ``#`` are ignored).

Each log file is expected to contain a cutflow table in the format produced by ZdZdPostProcessing, along with a line naming the input ROOT file.

The sample ID for each cutflow is taken as the directory immediately above the ROOT file in that path.

Output - cutflow list
------
A single text file containing a sample ID and cutflow table for each input log.

Example cutflow block in the output file:
-------------------------------------------
The first line is the sample ID, followed by the cutflow table (only some cuts shown here - ZdZdPostprocessing typically has ~20 cuts).
`
mc23a_mZd5_p6697
|               |#==561504           |#==5615041        |#==5615042        |#==5615043        |
-----------------------------------------------------------------------------------------------
|All            |23162.109375 (23158)|0.000000 (0)      |0.000000 (0)      |0.000000 (0)      |
|Cleaning       |23162.109375 (23158)|0.000000 (0)      |0.000000 (0)      |0.000000 (0)      |
...
|HWindow        |0.000000 (0)        |45.348930 (49)    |490.486542 (519)  |891.753357 (952)  |
|ZVeto          |0.000000 (0)        |25.357410 (28)    |490.486542 (519)  |477.725403 (510)  |
-----------------------------------------------------------------------------------------------
`

Usage
-----
    python aggregate_cutflows.py <list_file> [-o OUTPUT]

Member functions
----------------
1. `agcf_version()` - Returns the version string for this script.
2. `extract_cutflow()` - Returns a tuple of the extracted cutflow table lines and a sample ID from an input ZdZdPostProcessing log file.
3. `read_filelist()` - Returns the list of paths from *list_path*.
4. `aggregate_cutflows()` - Calls `read_filelist()` and `extract_cutflow()` to read and extract cutflows and sample IDs to an output file.
5. `_warn_on_duplicates()` - Prints a warning to stderr for duplicate sample IDs.
6. `_parse_args()` - Parses command-line arguments and returns a namespace with the parsed values.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
import re
from pathlib import Path
from typing import List, Optional, Pattern, Tuple, Union

def agcf_version() -> str:
    """Version string for this script."""
    return "1.0"

def _as_pattern(p: Union[str, Pattern[str]]) -> Pattern[str]:
    """Compile *p* if it is a string, otherwise return it unchanged."""
    return re.compile(p) if isinstance(p, str) else p


def extract_cutflow(
    filepath: str | Path,
    sampleID_re: Union[str, Pattern[str]] = re.compile(r"Processing\s+(\S+\.root)\b"),
    header_marker: str = '#==',
    sep_re: Union[str, Pattern[str]] = re.compile(r"^-{3,}\s*$"),
) -> Tuple[Optional[str], Optional[List[str]]]:
    """
    Extract the cutflow table lines and sample ID from an input ZdZdPostProcessing log file.
    Optionally set the table header, separator and sample-ID-locator patterns.
    """
    sampleID_re = _as_pattern(sampleID_re) #Regex for locating the sample ID line.
    sep_re = _as_pattern(sep_re) #Regex for locating the cutflow table separator lines (dashed lines).

    sample_id: Optional[str] = None
    cutflow_lines: Optional[List[str]] = None

    in_table = False
    buf: List[str] = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n")

            # --- sample ID ---------------------------------------
            if sample_id is None:
                m = sampleID_re.search(line)
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


def aggregate_cutflows(list_path: Union[str, Path], output_path: Union[str, Path]) -> int:
    """
    Aggregate extracted cutflow & sampled IDs from files in *list_path* to *output_path*.
    Returns the number of cutflows written.
    """
    files = read_filelist(list_path)

    # (sample_id, cutflow_lines, source_path)
    blocks: List[Tuple[str, List[str], Path]] = []

    for f in files:
        if not f.exists():
            print(f"WARNING: file not found, skipping: {f}", file=sys.stderr)
            continue

        sID, cf = extract_cutflow(f)

        # Warnings if sample ID or cutflow are missing
        if cf is None:
            print(f"WARNING: no cutflow table in {f}, skipping",
                  file=sys.stderr)
            continue
        if sID is None:
            print(f"WARNING: no sample ID in {f}; "
                  f"using '<unknown:{f.name}>'", file=sys.stderr)
            sID = f"<unknown:{f.name}>"

        blocks.append((sID, cf, f))

    # Warn if duplicate sample ID occurs (but still write all to output)
    _warn_on_duplicates(blocks)

    with open(output_path, "w", encoding="utf-8") as out:
        for i, (sID, cf, _src) in enumerate(blocks):
            if i > 0:
                out.write("\n")  # blank line between blocks
            out.write(sID + "\n")
            out.write("\n".join(cf) + "\n")

    print(f"Wrote {len(blocks)} cutflow(s) to {output_path}")
    return len(blocks)


def _warn_on_duplicates(blocks: List[Tuple[str, List[str], Path]]) -> None:
    """Print a warning to stderr for any sample ID seen >1 time."""

    # Create dictionary of duplicate sample IDs and their counts
    counts = Counter(sID for sID, _, _ in blocks)
    dups = {s: n for s, n in counts.items() if n > 1}
    if not dups:
        return

    # Get the file corresponding to each duplicate sample ID
    sources = defaultdict(list)
    for sID, _, src in blocks:
        if sID in dups:
            sources[sID].append(src)

    # Print warnings for each sample ID and corresponding files
    print("WARNING: duplicate sample ID(s) detected:",
          file=sys.stderr)
    for sID, n in dups.items():
        print(f"  '{sID}' appears {n} times in the file:", file=sys.stderr)
        for src in sources[sID]:
            print(f"    - {src}", file=sys.stderr)


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Aggregate ZdZdPostProcessing cutflow tables into one file.",
    )
    p.add_argument(
        "list_file",
        help="text file with one log-file path per line",
    )
    p.add_argument(
        "-o", "--output",
        default="cutflows.txt",
        help="output file to contain list of sample IDs and cutflow tables (default: cutflows.txt)",
    )
    return p.parse_args(argv)


if __name__ == "__main__":
    args = _parse_args(sys.argv[1:])
    aggregate_cutflows(args.list_file, args.output)