"""
es_curve.py
Elevation-Storage curve: piecewise linear interpolation.
Mirrors the VLOOKUP / interpolation logic in Sheet 3_ES_CURVE.
"""

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d


class ElevationStorageCurve:
    """
    Level ↔ Storage conversion using piecewise linear interpolation.

    Parameters
    ----------
    elevation_m  : array-like, sorted ascending
    storage_mcm  : array-like, sorted ascending, same length
    """

    def __init__(self, elevation_m, storage_mcm):
        elev = np.asarray(elevation_m, dtype=float)
        stor = np.asarray(storage_mcm, dtype=float)

        # Remove duplicate elevations (keep last)
        _, unique_idx = np.unique(elev, return_index=True)
        elev = elev[unique_idx]
        stor = stor[unique_idx]

        # Sort ascending
        order = np.argsort(elev)
        self.elevation_m = elev[order]
        self.storage_mcm = stor[order]

        # Build interpolators (clamp at boundaries)
        self._l2s = interp1d(self.elevation_m, self.storage_mcm,
                             kind='linear', bounds_error=False,
                             fill_value=(self.storage_mcm[0], self.storage_mcm[-1]))
        self._s2l = interp1d(self.storage_mcm, self.elevation_m,
                             kind='linear', bounds_error=False,
                             fill_value=(self.elevation_m[0], self.elevation_m[-1]))

    # ------------------------------------------------------------------
    def level_to_storage(self, level_m: float) -> float:
        return float(self._l2s(level_m))

    def storage_to_level(self, storage_mcm: float) -> float:
        return float(self._s2l(storage_mcm))

    # ------------------------------------------------------------------
    def validate(self):
        """Return list of error strings, or empty list if valid."""
        errors = []
        if len(self.elevation_m) < 3:
            errors.append("ES curve needs at least 3 elevation-storage pairs.")
        if not np.all(np.diff(self.elevation_m) > 0):
            errors.append("Elevations are not strictly ascending.")
        if not np.all(np.diff(self.storage_mcm) >= 0):
            errors.append("Storage values are not monotonically increasing.")
        return errors

    # ------------------------------------------------------------------
    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame({
            'Elevation (m)': self.elevation_m,
            'Storage (MCM)': self.storage_mcm,
        })

    # ------------------------------------------------------------------
    @classmethod
    def from_dataframe(cls, df: pd.DataFrame):
        """
        Accept a DataFrame whose first two columns are elevation and storage.
        Column names can vary; we use position.
        """
        arr = df.dropna().values
        return cls(arr[:, 0], arr[:, 1])

    @classmethod
    def from_sample(cls):
        from src.constants import SAMPLE_ES_CURVE
        return cls(SAMPLE_ES_CURVE['elevation_m'], SAMPLE_ES_CURVE['storage_mcm'])
