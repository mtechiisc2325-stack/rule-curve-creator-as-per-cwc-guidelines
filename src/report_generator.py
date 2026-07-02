"""
report_generator.py
Generates a professional PDF report from rule curve results.
Uses ReportLab (no external dependencies beyond pip install reportlab).
"""

from io import BytesIO
from datetime import datetime
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)


# ── colour palette ────────────────────────────────────────────────────
C_BLUE      = colors.HexColor('#0055A5')
C_LTBLUE    = colors.HexColor('#D6E4F7')
C_ORANGE    = colors.HexColor('#FF6600')
C_GREEN     = colors.HexColor('#00802B')
C_GREY      = colors.HexColor('#F2F2F2')
C_DARKGREY  = colors.HexColor('#555555')
C_WHITE     = colors.white
C_BLACK     = colors.black


def _styles():
    S = getSampleStyleSheet()
    S.add(ParagraphStyle('RCTitle',
        parent=S['Title'], fontSize=20, textColor=C_BLUE,
        spaceAfter=6, spaceBefore=0, leading=24))
    S.add(ParagraphStyle('RCSubtitle',
        parent=S['Normal'], fontSize=11, textColor=C_DARKGREY,
        spaceAfter=12, alignment=1))
    S.add(ParagraphStyle('RCH2',
        parent=S['Heading2'], fontSize=13, textColor=C_BLUE,
        spaceBefore=14, spaceAfter=4))
    S.add(ParagraphStyle('RCH3',
        parent=S['Heading3'], fontSize=11, textColor=C_ORANGE,
        spaceBefore=8, spaceAfter=2))
    S.add(ParagraphStyle('RCNormal',
        parent=S['Normal'], fontSize=9, leading=13))
    S.add(ParagraphStyle('RCSmall',
        parent=S['Normal'], fontSize=8, leading=11, textColor=C_DARKGREY))
    S.add(ParagraphStyle('RCBold',
        parent=S['Normal'], fontSize=9, leading=13, fontName='Helvetica-Bold'))
    return S


def _table_style_header():
    return TableStyle([
        ('BACKGROUND',  (0, 0), (-1, 0),  C_BLUE),
        ('TEXTCOLOR',   (0, 0), (-1, 0),  C_WHITE),
        ('FONTNAME',    (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, 0),  8),
        ('FONTSIZE',    (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C_WHITE, C_GREY]),
        ('GRID',        (0, 0), (-1, -1), 0.4, C_DARKGREY),
        ('ALIGN',       (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN',       (0, 0), (0, -1),  'LEFT'),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',  (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0,0), (-1, -1), 3),
    ])


def generate_pdf_report(
    reservoir_name:  str,
    river_name:      str,
    frl_m:           float,
    mddl_m:          float,
    frl_storage:     float,
    mddl_storage:    float,
    all_cases,                   # List[RuleCurveCase]
    simulations,                 # Dict[int, SimulationResult]
    reliability_df,              # pd.DataFrame
    tradeoff_df,                 # pd.DataFrame
    upper_rc_case5,              # pd.DataFrame (36 rows)
    lower_rc,                    # pd.DataFrame (36 rows)
) -> bytes:
    """
    Build and return the PDF as bytes.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    S = _styles()
    story = []

    # ── COVER ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("Rule Curve Optimization Report", S['RCTitle']))
    story.append(Paragraph(
        f"Reservoir: <b>{reservoir_name}</b> &nbsp;|&nbsp; River: <b>{river_name}</b>",
        S['RCSubtitle']))
    story.append(HRFlowable(width="100%", thickness=2, color=C_BLUE))
    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%d %B %Y, %H:%M')} &nbsp;|&nbsp; "
        f"Tool: Rule Curve Optimizer v2.0", S['RCSmall']))
    story.append(Spacer(1, 0.6*cm))

    # ── SECTION 1: RESERVOIR PARAMETERS ───────────────────────────────
    story.append(Paragraph("1. Reservoir Parameters", S['RCH2']))

    live_storage = frl_storage - mddl_storage
    param_data = [
        ['Parameter', 'Value'],
        ['Full Reservoir Level (FRL)',    f"{frl_m:.2f} m"],
        ['Minimum Drawdown Level (MDDL)', f"{mddl_m:.2f} m"],
        ['FRL Storage',                   f"{frl_storage:.0f} MCM"],
        ['MDDL Storage',                  f"{mddl_storage:.0f} MCM"],
        ['Live Storage Capacity',         f"{live_storage:.0f} MCM"],
        ['Water Year Convention',         "Jul-I (PID 0) → Jun-III (PID 35)"],
        ['Decade Convention',             "36 ten-day periods per year"],
        ['Upper RC Anchor',               "Nov-II (PID 13) – end of SW monsoon"],
        ['Lower RC Anchor',               "May-III (PID 32) – Rabi season close"],
        ['Flood Cushion Zone',            "Aug-III to Oct-III (PIDs 5–11)"],
    ]
    t = Table(param_data, colWidths=[10*cm, 6.5*cm])
    t.setStyle(_table_style_header())
    story.append(t)
    story.append(Spacer(1, 0.5*cm))

    # ── SECTION 2: RULE CURVE METHODOLOGY ─────────────────────────────
    story.append(Paragraph("2. Methodology", S['RCH2']))
    story.append(Paragraph(
        "<b>Backward Calculation (Upper RC, P50 basis):</b><br/>"
        "S[t] = MIN(Cap, MAX(MDDL_S, S[t+1] − Q[t+1] + D[t+1]))<br/>"
        "Cap = Case Target Storage (during flood cushion zone, PIDs 5–11)<br/>"
        "Cap = FRL Storage (outside flood cushion zone)<br/><br/>"
        "<b>Backward Calculation (Lower RC, P10 basis):</b><br/>"
        "Same formula with P10 drought inflows; anchor at MDDL (May-III).",
        S['RCNormal']))
    story.append(Spacer(1, 0.4*cm))

    # ── SECTION 3: RELIABILITY SUMMARY (All 10 Cases) ─────────────────
    story.append(Paragraph("3. Reliability Summary – All 10 Cases", S['RCH2']))
    rel_data = [list(reliability_df.columns)] + reliability_df.values.tolist()
    rel_table = Table(rel_data, repeatRows=1)
    rel_table.setStyle(_table_style_header())
    story.append(rel_table)
    story.append(Spacer(1, 0.3*cm))

    # ── SECTION 4: TRADEOFF ANALYSIS ──────────────────────────────────
    story.append(Paragraph("4. Flood Risk vs Drought Risk Tradeoff", S['RCH2']))
    tf_data = [list(tradeoff_df.columns)] + tradeoff_df.values.tolist()
    tf_table = Table(tf_data, repeatRows=1)
    ts = _table_style_header()
    # Highlight recommended row (Case 5 → row index 5 in table, 0-indexed)
    ts.add('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#FFF0D0'))
    ts.add('FONTNAME',   (0, 5), (-1, 5), 'Helvetica-Bold')
    tf_table.setStyle(ts)
    story.append(tf_table)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "★ Initial recommendation: Case 5 (2.0 ft cushion). "
        "Engineer should review downstream flood risk and override if required.",
        S['RCSmall']))

    # ── SECTION 5: UPPER RC TABLE (Case 5) ────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("5. Upper Rule Curve Levels – Case 5 (2.0 ft Cushion)", S['RCH2']))

    urc_data = [['PID', 'Period', 'URC Storage (MCM)', 'URC Level (m)',
                 'P50 Inflow (MCM)', 'Demand (MCM)']]
    for _, row in upper_rc_case5.iterrows():
        urc_data.append([
            int(row['PID']),
            row['Period'],
            f"{row['Storage_MCM']:.0f}",
            f"{row['Level_m']:.3f}",
            f"{row['Inflow_MCM']:.0f}",
            f"{row['Demand_MCM']:.0f}",
        ])
    urc_table = Table(urc_data, repeatRows=1,
                      colWidths=[1.2*cm, 2*cm, 3.2*cm, 2.8*cm, 3.2*cm, 2.5*cm])
    ts2 = _table_style_header()
    # Highlight anchor period (Nov-II = PID 13, table row 14)
    ts2.add('BACKGROUND', (0, 14), (-1, 14), colors.HexColor('#FFE0E0'))
    ts2.add('FONTNAME',   (0, 14), (-1, 14), 'Helvetica-Bold')
    # Highlight flood cushion zone (PIDs 5–11 = rows 6–12)
    for r in range(6, 13):
        ts2.add('BACKGROUND', (0, r), (-1, r), colors.HexColor('#E0F0FF'))
    urc_table.setStyle(ts2)
    story.append(urc_table)
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "Blue shading = Flood cushion zone (Aug-III to Oct-III). "
        "Red shading = Upper RC anchor (Nov-II).",
        S['RCSmall']))

    # ── SECTION 6: LOWER RC TABLE ─────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("6. Lower Rule Curve Levels (P10, Shared by All Cases)", S['RCH2']))

    lrc_data = [['PID', 'Period', 'LRC Storage (MCM)', 'LRC Level (m)',
                 'P10 Inflow (MCM)', 'Demand (MCM)']]
    for _, row in lower_rc.iterrows():
        lrc_data.append([
            int(row['PID']),
            row['Period'],
            f"{row['Storage_MCM']:.0f}",
            f"{row['Level_m']:.3f}",
            f"{row['Inflow_MCM']:.0f}",
            f"{row['Demand_MCM']:.0f}",
        ])
    lrc_table = Table(lrc_data, repeatRows=1,
                      colWidths=[1.2*cm, 2*cm, 3.2*cm, 2.8*cm, 3.2*cm, 2.5*cm])
    ts3 = _table_style_header()
    # Highlight anchor period (May-III = PID 32, row 33)
    ts3.add('BACKGROUND', (0, 33), (-1, 33), colors.HexColor('#FFE0E0'))
    ts3.add('FONTNAME',   (0, 33), (-1, 33), 'Helvetica-Bold')
    lrc_table.setStyle(ts3)
    story.append(lrc_table)

    # ── SECTION 7: SIMULATION RESULTS ─────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("7. Forward Simulation Results – Cases 1, 5, 10", S['RCH2']))

    for cn in [1, 5, 10]:
        if cn not in simulations:
            continue
        sim = simulations[cn]
        story.append(Paragraph(
            f"Case {cn} ({sim.cushion_ft:.1f} ft cushion)", S['RCH3']))

        sim_summary = [
            ['Metric', 'Value'],
            ['Total Annual Release (MCM)',   f"{sim.total_release:.0f}"],
            ['Total Annual Spill (MCM)',      f"{sim.total_spill:.0f}"],
            ['Avg Demand Satisfaction (%)',   f"{sim.avg_satisfaction:.1f}"],
            ['End-of-Year Storage (MCM)',     f"{sim.end_storage:.0f}"],
        ]
        st = Table(sim_summary, colWidths=[10*cm, 6.5*cm])
        st.setStyle(_table_style_header())
        story.append(st)
        story.append(Spacer(1, 0.3*cm))

        # Period-wise table (condensed)
        period_data = [['Period', 'Inflow', 'Demand', 'Release',
                        'Spill', 'End Storage', 'Satisfaction %']]
        for _, row in sim.df.iterrows():
            period_data.append([
                row['Period'],
                f"{row['Inflow_MCM']:.0f}",
                f"{row['Demand_MCM']:.0f}",
                f"{row['Release_MCM']:.0f}",
                f"{row['Spill_MCM']:.0f}",
                f"{row['Storage_End_MCM']:.0f}",
                f"{row['Satisfaction_%']:.0f}%",
            ])
        pt = Table(period_data, repeatRows=1,
                   colWidths=[2*cm, 2.2*cm, 2.2*cm, 2.2*cm, 1.8*cm, 2.6*cm, 3*cm])
        pt.setStyle(_table_style_header())
        story.append(pt)
        story.append(Spacer(1, 0.5*cm))

    # ── SECTION 8: CONCLUSIONS ─────────────────────────────────────────
    story.append(Paragraph("8. Conclusions", S['RCH2']))
    story.append(Paragraph(
        "1. The backward calculation method (P50 for Upper RC, P10 for Lower RC) "
        "was used as per CWC reservoir operation guidelines.<br/>"
        "2. Ten flood cushion cases (0.0 ft to 4.5 ft below FRL) were evaluated.<br/>"
        "3. Case 5 (2.0 ft cushion) is the initial recommendation, balancing flood "
        "protection and supply reliability.<br/>"
        "4. The Dam Safety Authority should review and approve the recommended case "
        "considering downstream flood damage potential and inter-state obligations.<br/>"
        "5. Rule curves should be updated every 5 years or after major bathymetric surveys.<br/>"
        "6. This report was generated using Rule Curve Optimizer v2.0 "
        "(rulecurveoptimizer.com).",
        S['RCNormal']))

    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=C_DARKGREY))
    story.append(Paragraph(
        "DISCLAIMER: This report is generated by Rule Curve Optimizer v2.0, "
        "an independent engineering tool. Not an official product of WRD Tamil Nadu "
        "or SDSO. All results must be reviewed and endorsed by a qualified engineer "
        "before use in official submissions. Methodology follows published CWC guidelines.",
        S['RCSmall']))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
