"""
rule_curve_calc.py
Backward calculation for Upper RC (10 cases) and Lower RC (1 curve).
Mirrors Sheets 5_UPPER_RC_CALC and 6_LOWER_RC_CALC from the Excel workbook.

Backward formula (general):
    S[t] = MIN(cap, MAX(MDDL_S, S[t+1] - Q[t+1] + D[t+1]))

where:
    cap = FRL_S            outside flood cushion zone
    cap = Case_Target_S    inside flood cushion zone (PIDs 5–11)

Upper RC → P50 inflows,  anchor = Nov-II  (PID 13)
Lower RC → P10 inflows,  anchor = May-III (PID 32), target = MDDL_S
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Dict

from src.es_curve import ElevationStorageCurve
from src.constants import (
    WATER_YEAR_PERIODS,
    UPPER_ANCHOR_PID, LOWER_ANCHOR_PID,
    CUSHION_START_PID, CUSHION_END_PID,
    CUSHION_CASES_FT, FT_TO_M,
)


@dataclass
class RuleCurveCase:
    """Result container for one flood-cushion case."""
    case_number:     int
    cushion_ft:      float
    cushion_m:       float
    target_level_m:  float
    target_storage:  float
    flood_space_mcm: float
    upper_rc:        pd.DataFrame   # 36 rows × [PID, Period, Storage_MCM, Level_m]
    lower_rc:        pd.DataFrame   # 36 rows × same (shared across cases)


class RuleCurveCalculator:
    """
    Computes Upper and Lower Rule Curves for all 10 flood-cushion cases.

    Parameters
    ----------
    es_curve      : ElevationStorageCurve
    frl_level_m   : Full Reservoir Level (m)
    mddl_level_m  : Minimum Drawdown Level (m)
    inflows_p50   : array of 36 decade inflows (MCM) – P50
    inflows_p10   : array of 36 decade inflows (MCM) – P10
    demand        : array of 36 decade demands  (MCM)
    cushion_cases_ft : list of 10 cushion values in feet (default: 0.0–4.5)
    """

    def __init__(
        self,
        es_curve:       ElevationStorageCurve,
        frl_level_m:    float,
        mddl_level_m:   float,
        inflows_p50:    np.ndarray,
        inflows_p10:    np.ndarray,
        demand:         np.ndarray,
        cushion_cases_ft: List[float] = None,
    ):
        self.es   = es_curve
        self.frl  = frl_level_m
        self.mddl = mddl_level_m
        self.frl_s  = es_curve.level_to_storage(frl_level_m)
        self.mddl_s = es_curve.level_to_storage(mddl_level_m)

        self.q50   = np.asarray(inflows_p50, dtype=float)
        self.q10   = np.asarray(inflows_p10, dtype=float)
        self.demand = np.asarray(demand, dtype=float)

        self.cushion_cases_ft = cushion_cases_ft if cushion_cases_ft else CUSHION_CASES_FT

        # Pre-compute Lower RC (shared by all cases)
        self._lower_rc = self._calc_lower_rc()

    # ------------------------------------------------------------------ #
    #  PUBLIC API                                                          #
    # ------------------------------------------------------------------ #

    def run_all_cases(self) -> List[RuleCurveCase]:
        """Return list of RuleCurveCase objects for all 10 cushion cases."""
        results = []
        for i, ft in enumerate(self.cushion_cases_ft):
            results.append(self._calc_one_case(i + 1, ft))
        return results

    def get_lower_rc(self) -> pd.DataFrame:
        return self._lower_rc.copy()

    # ------------------------------------------------------------------ #
    #  INTERNAL                                                            #
    # ------------------------------------------------------------------ #

    def _calc_one_case(self, case_number: int, cushion_ft: float) -> RuleCurveCase:
        cushion_m = cushion_ft * FT_TO_M
        target_level = self.frl - cushion_m
        target_storage = self.es.level_to_storage(target_level)
        flood_space = self.frl_s - target_storage

        upper_rc = self._backward_chain(
            anchor_pid=UPPER_ANCHOR_PID,
            anchor_storage=target_storage,
            inflows=self.q50,
            cushion_cap=target_storage,
        )

        return RuleCurveCase(
            case_number=case_number,
            cushion_ft=cushion_ft,
            cushion_m=cushion_m,
            target_level_m=target_level,
            target_storage=target_storage,
            flood_space_mcm=flood_space,
            upper_rc=upper_rc,
            lower_rc=self._lower_rc,
        )

    def _calc_lower_rc(self) -> pd.DataFrame:
        """Lower RC: P10 basis, anchor at May-III (MDDL)."""
        return self._backward_chain(
            anchor_pid=LOWER_ANCHOR_PID,
            anchor_storage=self.mddl_s,
            inflows=self.q10,
            cushion_cap=None,   # No flood cushion zone for lower RC
        )

    def _backward_chain(
        self,
        anchor_pid:      int,
        anchor_storage:  float,
        inflows:         np.ndarray,
        cushion_cap:     float,          # None → use FRL_S as cap throughout
    ) -> pd.DataFrame:
        """
        Core backward calculation (wraps around the 36-period water year).

        Starting at anchor_pid with anchor_storage, chain backwards
        period-by-period for the full 36 periods.
        """
        n = 36
        storage = np.full(n, np.nan)
        storage[anchor_pid] = anchor_storage

        # Iterate backwards: anchor_pid → 0, then 35 → anchor_pid+1
        pids_backward = list(range(anchor_pid, -1, -1)) + list(range(35, anchor_pid, -1))

        for idx, pid in enumerate(pids_backward):
            if idx == 0:
                # Anchor – already set
                continue

            # The period AFTER pid in the chain is pids_backward[idx-1]
            next_pid = pids_backward[idx - 1]
            Q_next = inflows[next_pid]
            D_next = self.demand[next_pid]

            S_unconstrained = storage[next_pid] - Q_next + D_next

            # Cap selection
            if (cushion_cap is not None and
                    CUSHION_START_PID <= pid <= CUSHION_END_PID):
                cap = cushion_cap
            else:
                cap = self.frl_s

            storage[pid] = min(cap, max(self.mddl_s, S_unconstrained))

        # Post anchor_pid periods (Nov-III onward) → allow full reservoir
        for pid in range(anchor_pid + 1, n):
            storage[pid] = min(self.frl_s, max(self.mddl_s, storage[pid]))

        levels = np.array([self.es.storage_to_level(s) for s in storage])

        return pd.DataFrame({
            'PID':        np.arange(n),
            'Period':     WATER_YEAR_PERIODS,
            'Storage_MCM': np.round(storage, 2),
            'Level_m':    np.round(levels, 3),
            'Inflow_MCM': np.round(inflows, 2),
            'Demand_MCM': np.round(self.demand, 2),
        })

    # ------------------------------------------------------------------ #
    #  RELIABILITY SUMMARY TABLE (for all 10 cases)                       #
    # ------------------------------------------------------------------ #

    def reliability_summary(self, cases: List[RuleCurveCase]) -> pd.DataFrame:
        """
        Build the Sheet 13_RELIABILITY style table.
        P50 demand satisfaction (inflow-based, case-independent).
        """
        # Inflow-based satisfaction (P50)
        supply_p50 = np.minimum(self.q50, self.demand)
        sat_p50 = np.where(self.demand > 0, supply_p50 / self.demand * 100, 100)
        avg_sat_p50 = sat_p50.mean()

        supply_p10 = np.minimum(self.q10, self.demand)
        sat_p10 = np.where(self.demand > 0, supply_p10 / self.demand * 100, 100)
        avg_sat_p10 = sat_p10.mean()

        rows = []
        for case in cases:
            nov_ii_s = case.upper_rc.loc[
                case.upper_rc['PID'] == UPPER_ANCHOR_PID, 'Storage_MCM'
            ].values[0]
            may_iii_s = case.lower_rc.loc[
                case.lower_rc['PID'] == LOWER_ANCHOR_PID, 'Storage_MCM'
            ].values[0]

            rows.append({
                'Case':             case.case_number,
                'Cushion (ft)':     case.cushion_ft,
                'Nov-II Level (m)': round(case.target_level_m, 2),
                'Nov-II Stor(MCM)': round(nov_ii_s, 0),
                'Flood Space(MCM)': round(case.flood_space_mcm, 0),
                'Sat P50 (%)':      round(avg_sat_p50, 1),
                'Sat P10 (%)':      round(avg_sat_p10, 1),
            })

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------ #
    #  TRADEOFF TABLE (Sheet 14 equivalent)                               #
    # ------------------------------------------------------------------ #

    def tradeoff_table(self, cases: List[RuleCurveCase]) -> pd.DataFrame:
        """
        Flood risk score (0–10) vs drought risk qualitative label.
        """
        max_flood_space = max(c.flood_space_mcm for c in cases)
        drought_labels  = [
            'Minimum','Very Low','Low','Low-Moderate','Moderate',
            'Moderate-High','High','High','Very High','Maximum',
        ]
        rows = []
        for i, case in enumerate(cases):
            flood_score = round((case.flood_space_mcm / max_flood_space) * 10, 1) if max_flood_space > 0 else 0
            rows.append({
                'Case':              case.case_number,
                'Cushion (ft)':      case.cushion_ft,
                'Flood Space (MCM)': round(case.flood_space_mcm, 0),
                'Flood Risk Score':  flood_score,
                'Drought Risk':      drought_labels[i],
                'Recommended':       '★ Recommended' if case.case_number == 5 else '',
            })
        return pd.DataFrame(rows)
