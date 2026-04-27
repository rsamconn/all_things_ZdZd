"""
Plot signal efficiency vs. m_Zd from a dictionary of cutflow DataFrames.

Each cutflow DataFrame is expected to have a ``'Cuts'`` column plus any
number of "channel" columns such as ``weights_4e``, ``events_4e``,
``weights_2e2m``, ``events_2e2m``, ``weights_4m``, ``events_4m``,
``weights_All``, ``events_All``.

The signal efficiency for a given channel is

    eff[%] = 100 * <numerator row> / <denominator row>

where, by default, the numerator is the *last* cut row and the denominator
is the *first* cut row.  Both rows can be overridden, either by the value
in the ``Cuts`` column (e.g. ``'ZVeto'``) or by integer position (negative
indices supported).
"""

from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# A cut can be referred to by its label in the 'Cuts' column or by its
# integer position in the DataFrame.
CutRef = Union[str, int]

# Default extractor: 'mc23a_mZd5_p6697' -> 5.0, 'mc23d_mZd12p5_p6697' -> 12.5.
_MZD_RE = re.compile(r"mZd(\d+(?:p\d+)?)", re.IGNORECASE)


def default_mzd_from_sample_id(sample_id: str) -> Optional[float]:
    """Parse the m_Zd value (in GeV) from a sample identifier."""
    m = _MZD_RE.search(sample_id)
    if not m:
        return None
    return float(m.group(1).replace("p", "."))


def _resolve_row(df: pd.DataFrame, cut: CutRef) -> int:
    """Return the *positional* row index for a Cuts label or integer index."""
    if isinstance(cut, str):
        try:
            return df["Cuts"].tolist().index(cut)
        except ValueError as e:
            raise KeyError(
                f"Cut name {cut!r} not found in DataFrame; available cuts: "
                f"{df['Cuts'].tolist()}"
            ) from e
    if isinstance(cut, (int, np.integer)) and not isinstance(cut, bool):
        return int(cut) if cut >= 0 else len(df) + int(cut)
    raise TypeError(
        f"Cut reference must be str or int, got {type(cut).__name__}"
    )


def compute_signal_efficiency(
    cutflows: Dict[str, pd.DataFrame],
    channels: List[str],
    numerator_cut: Optional[CutRef] = None,
    denominator_cut: Optional[CutRef] = None,
    mzd_func: Callable[[str], Optional[float]] = default_mzd_from_sample_id,
) -> pd.DataFrame:
    """
    Build a tidy long-format DataFrame of signal efficiencies.

    Parameters
    ----------
    cutflows : dict[str, pandas.DataFrame]
        Mapping ``{sample_id: cutflow_dataframe}``.
    channels : list[str]
        Column names in each cutflow DataFrame to compute efficiency for
        (e.g. ``['weights_4e', 'events_All']``).
    numerator_cut, denominator_cut : str, int, or None
        Row used in the efficiency ratio.  ``None`` -> last (numerator) or
        first (denominator) row.  A string is matched against the ``Cuts``
        column; an int is a positional index (negatives count from the end).
    mzd_func : callable
        Function mapping a sample id to its m_Zd in GeV.  Samples for
        which this returns ``None`` are silently skipped.

    Returns
    -------
    pandas.DataFrame
        Long-format frame with columns
        ``['sample_id', 'mZd', 'channel', 'efficiency']``.
    """
    records = []
    for sid, df in cutflows.items():
        mzd = mzd_func(sid)
        if mzd is None:
            continue

        denom_idx = _resolve_row(df, 0 if denominator_cut is None else denominator_cut)
        num_idx = _resolve_row(df, -1 if numerator_cut is None else numerator_cut)

        for ch in channels:
            if ch not in df.columns:
                raise KeyError(
                    f"Channel {ch!r} not in cutflow for {sid!r}; "
                    f"available: {[c for c in df.columns if c != 'Cuts']}"
                )
            denom = df[ch].iloc[denom_idx]
            num = df[ch].iloc[num_idx]
            eff = 100.0 * num / denom if denom else float("nan")
            records.append(
                {"sample_id": sid, "mZd": mzd, "channel": ch, "efficiency": eff}
            )

    return (
        pd.DataFrame(records)
        .sort_values(["channel", "mZd"])
        .reset_index(drop=True)
    )


def plot_signal_efficiency(
    cutflows: Dict[str, pd.DataFrame],
    channels: List[str],
    numerator_cut: Optional[CutRef] = None,
    denominator_cut: Optional[CutRef] = None,
    mzd_func: Callable[[str], Optional[float]] = default_mzd_from_sample_id,
    ax: Optional[plt.Axes] = None,
    marker: str = "o",
    errorbar=None,
    **lineplot_kwargs,
) -> plt.Axes:
    """
    Plot signal efficiency vs. m_Zd for each channel as a seaborn lineplot.

    All channels are drawn on the same axis (one line per channel via
    ``hue='channel'``).  Returns the matplotlib ``Axes`` so the caller can
    further customise (legend placement, log scale, save, ...).

    Parameters
    ----------
    cutflows, channels, numerator_cut, denominator_cut, mzd_func
        See :func:`compute_signal_efficiency`.
    ax : matplotlib.axes.Axes, optional
        Existing axes to draw on.  A new figure/axes is created if omitted.
    marker : str, optional
        Marker style passed to seaborn (default ``'o'``).
    errorbar : seaborn errorbar spec, optional
        Defaults to ``None`` (no error band) since cutflow efficiencies
        are point estimates per sample.  Pass e.g. ``'ci'`` to enable.
    **lineplot_kwargs
        Forwarded to :func:`seaborn.lineplot`.
    """
    eff_df = compute_signal_efficiency(
        cutflows,
        channels,
        numerator_cut=numerator_cut,
        denominator_cut=denominator_cut,
        mzd_func=mzd_func,
    )

    if eff_df.empty:
        raise ValueError(
            "No signal-efficiency points to plot. Check that the sample "
            "identifiers contain an m_Zd value parsable by mzd_func, and "
            "that the requested channels exist in the cutflow DataFrames."
        )

    if ax is None:
        _, ax = plt.subplots(figsize=(7, 5))

    sns.lineplot(
        data=eff_df,
        x="mZd",
        y="efficiency",
        hue="channel",
        marker=marker,
        errorbar=errorbar,
        ax=ax,
        **lineplot_kwargs,
    )

    # Human-readable labels for the ratio used.
    num_label = "last cut" if numerator_cut is None else str(numerator_cut)
    den_label = "first cut" if denominator_cut is None else str(denominator_cut)

    ax.set_xlabel(r"$m_{Z_d}$ [GeV]")
    ax.set_ylabel(f"Signal efficiency [%]  ({num_label} / {den_label})")
    ax.set_title(r"Signal efficiency vs. $m_{Z_d}$")
    ax.legend(title="channel")
    ax.grid(True, alpha=0.3)

    return ax