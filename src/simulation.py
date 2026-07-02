"""
simulation.py
Forward simulation (mass balance) for Cases 1, 5, and 10.
Mirrors Sheets 8_SIM_CASE1, 9_SIM_CASE5, 10_SIM_CASE10.

Mass balance:
    Available[t]  = S_start[t] + Q_P50[t]
    Normal_Rel[t] = MIN(Demand, MAX(0, Available - MDDL_S))
    Forced_Rel[t] = MAX(0, Available - URC[t])   ← only during cushion zone
    Release[t]    = MAX(Normal_Rel, Forced_Rel)
    Spill[t]      = MAX(0, Available - Release - FRL_S)
    S_end[t]      = Available - Release - Spill
"""

import numpy as np
import pandas as pd
from typing import Dict

from src.es_curve import ElevationStorageCurve
from src.rule_curve_calc import RuleCurveCase
from src.constants import (
    WATER_YEAR_PERIODS,
    CUSHION_START_PID, CUSHION_END_PID,
)


class SimulationResult:
    """Holds forward-simulation output for one case."""

    def __init__(self, case_number: int, cushion_ft: float, df: pd.DataFrame,
                 frl_s: float, mddl_s: float):
        self.case_number  = case_number
        self.cushion_ft   = cushion_ft
        self.df           = df          # 36-row timeseries
        self.total_spill  = df['Spill_MCM'].sum()
        self.total_release = df['Release_MCM'].sum()
        self.total_demand  = df['Demand_MCM'].sum()
        self.avg_satisfaction = (
            (df['Release_MCM'] / df['Demand_MCM'].replace(0, np.nan))
            .fillna(1.0)
            .clip(upper=1.0)
            .mean() * 100
        )
        self.end_storage  = df['Storage_End_MCM'].iloc[-1]
        self.frl_s        = frl_s
        self.mddl_s       = mddl_s

    def summary_dict(self) -> Dict:
        return {
            'Case':               self.case_number,
            'Cushion (ft)':       self.cushion_ft,
            'Total Release (MCM)': round(self.total_release, 0),
            'Total Spill (MCM)':  round(self.total_spill, 0),
            'Avg Satisfaction (%)': round(self.avg_satisfaction, 1),
            'End Storage (MCM)':  round(self.end_storage, 0),
        }


class ForwardSimulator:
    """
    Runs forward simulation for a given RuleCurveCase.

    Parameters
    ----------
    es_curve        : ElevationStorageCurve
    frl_level_m     : FRL level (m)
    mddl_level_m    : MDDL level (m)
    inflows_p50     : 36-element array (MCM/decade)
    demand          : 36-element array (MCM/decade)
    initial_storage : starting storage (MCM) – default = FRL_S
    """

    def __init__(
        self,
        es_curve:        ElevationStorageCurve,
        frl_level_m:     float,
        mddl_level_m:    float,
        inflows_p50:     np.ndarray,
        demand:          np.ndarray,
        initial_storage: float = None,
    ):
        self.es    = es_curve
        self.frl_s  = es_curve.level_to_storage(frl_level_m)
        self.mddl_s = es_curve.level_to_storage(mddl_level_m)
        self.q50   = np.asarray(inflows_p50, dtype=float)
        self.demand = np.asarray(demand, dtype=float)
        self.initial_storage = initial_storage if initial_storage is not None else self.frl_s

    # ------------------------------------------------------------------ #

    def simulate(self, case: RuleCurveCase) -> SimulationResult:
        """Run one water-year forward simulation for the given case."""
        urc_storage = case.upper_rc['Storage_MCM'].values   # 36 values
        rows = []
        s_start = self.initial_storage

        for pid in range(36):
            Q = self.q50[pid]
            D = self.demand[pid]
            available = s_start + Q

            # Normal release (meet demand but stay above MDDL)
            normal_rel = min(D, max(0.0, available - self.mddl_s))

            # Forced release during cushion zone to maintain URC target
            if CUSHION_START_PID <= pid <= CUSHION_END_PID:
                forced_rel = max(0.0, available - urc_storage[pid])
            else:
                forced_rel = 0.0

            release = max(normal_rel, forced_rel)
            spill   = max(0.0, available - release - self.frl_s)
            s_end   = available - release - spill
            s_end   = max(self.mddl_s, s_end)           # Never below MDDL
            level   = self.es.storage_to_level(s_end)

            satisfaction = min(100.0, (release / D * 100) if D > 0 else 100.0)

            rows.append({
                'PID':             pid,
                'Period':          WATER_YEAR_PERIODS[pid],
                'Inflow_MCM':      round(Q, 2),
                'Demand_MCM':      round(D, 2),
                'URC_Storage_MCM': round(urc_storage[pid], 2),
                'Available_MCM':   round(available, 2),
                'Normal_Rel_MCM':  round(normal_rel, 2),
                'Forced_Rel_MCM':  round(forced_rel, 2),
                'Release_MCM':     round(release, 2),
                'Spill_MCM':       round(spill, 2),
                'Storage_End_MCM': round(s_end, 2),
                'Level_End_m':     round(level, 3),
                'Satisfaction_%':  round(satisfaction, 1),
                'Storage_Start_MCM': round(s_start, 2),
            })

            s_start = s_end

        df = pd.DataFrame(rows)
        return SimulationResult(
            case_number=case.case_number,
            cushion_ft=case.cushion_ft,
            df=df,
            frl_s=self.frl_s,
            mddl_s=self.mddl_s,
        )

    # ------------------------------------------------------------------ #

    def simulate_cases_1_5_10(
        self,
        all_cases,           # List[RuleCurveCase]
    ) -> Dict[int, SimulationResult]:
        """Simulate Cases 1, 5, 10 (indices 0, 4, 9)."""
        target_case_numbers = {1, 5, 10}
        results = {}
        for case in all_cases:
            if case.case_number in target_case_numbers:
                results[case.case_number] = self.simulate(case)
        return results
