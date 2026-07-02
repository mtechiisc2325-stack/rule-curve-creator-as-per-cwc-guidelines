"""
Constants for Rule Curve Optimizer.
Indian water year: Jul I (PID 0) → Jun III (PID 35)
"""

WATER_YEAR_PERIODS = [
    'Jul-I',  'Jul-II',  'Jul-III',
    'Aug-I',  'Aug-II',  'Aug-III',
    'Sep-I',  'Sep-II',  'Sep-III',
    'Oct-I',  'Oct-II',  'Oct-III',
    'Nov-I',  'Nov-II',  'Nov-III',
    'Dec-I',  'Dec-II',  'Dec-III',
    'Jan-I',  'Jan-II',  'Jan-III',
    'Feb-I',  'Feb-II',  'Feb-III',
    'Mar-I',  'Mar-II',  'Mar-III',
    'Apr-I',  'Apr-II',  'Apr-III',
    'May-I',  'May-II',  'May-III',
    'Jun-I',  'Jun-II',  'Jun-III',
]

# Anchor period indices
UPPER_ANCHOR_PID  = 13   # Nov-II  (end of SW monsoon, upper RC target)
LOWER_ANCHOR_PID  = 32   # May-III (Rabi close, lower RC reaches MDDL)
CUSHION_START_PID =  5   # Aug-III (flood cushion zone begins)
CUSHION_END_PID   = 11   # Oct-III (flood cushion zone ends)

# 10 flood cushion cases: 0.0 ft → 4.5 ft in 0.5 ft steps
CUSHION_CASES_FT = [round(i * 0.5, 1) for i in range(10)]   # [0.0, 0.5, 1.0 … 4.5]
FT_TO_M = 0.3048

# Bhavanisagar sample data  ─ used as defaults in the UI
SAMPLE_ES_CURVE = {
    'elevation_m':  [91.00, 92.00, 93.00, 94.00, 95.00, 95.33,
                     96.00, 97.00, 98.00, 99.00,100.00,101.00,
                    102.00,103.00,104.00,105.00,106.00,107.00,107.59],
    'storage_mcm':  [10,    22,    38,    58,    82,   130,
                    130,   165,   205,   250,   300,   360,
                    425,   495,   570,   645,   720,   790,  807],
}

SAMPLE_INFLOWS_P50 = [
     72,  95, 128, 173, 232, 301,
    375, 442, 488, 420, 298, 165,
     85,  45,  32,  22,  18,  16,
     15,  18,  22,  30,  38,  42,
     38,  32,  25,  20,  16,  14,
     12,  11,  10,  10,  11,  12,
]

SAMPLE_INFLOWS_P10 = [
     15,  40,  65,  92, 125, 160,
    195, 225, 245, 200, 120,  75,
     45,  25,  15,  10,   8,   7,
      6,   8,  12,  18,  25,  30,
     25,  20,  15,  12,  10,   8,
      6,   5,   5,   5,   6,   8,
]

SAMPLE_DEMAND = [
     16,  14,  18,  24,  28,  32,
     28,  24,  20,  18,  22,  26,
     28,  30,  32,  34,  36,  36,
     34,  32,  30,  28,  26,  24,
     22,  20,  18,  16,  15,  14,
     13,  12,  12,  12,  13,  14,
]
