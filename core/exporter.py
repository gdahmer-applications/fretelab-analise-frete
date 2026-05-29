from __future__ import annotations

from datetime import datetime
from io import BytesIO
from html import escape
from typing import Any

from .insights import build_dashboard_summary, build_executive_summary


def money(value: Any) -> str:
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"


def percent(value: Any) -> str:
    try:
        return f"{float(value) * 100:.1f}%".replace(".", ",")
    except Exception:
        return "-"


def percent_plain(value: Any) -> str:
    try:
        return f"{round(float(value) * 100)}%"
    except Exception:
        return "-"


def _number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
    except Exception:
        return None
    if out != out:
        return None
    return out


def _analysis_name(analysis: dict[str, Any]) -> str:
    return str(analysis.get("analysisName") or analysis.get("title") or "Analise sem titulo")


def _analysis_date(analysis: dict[str, Any]) -> str:
    text = str(analysis.get("analysisDate") or analysis.get("createdAt") or "-").strip()
    if "/" in text or text == "-":
        return text
    try:
        return datetime.fromisoformat(text).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return text


def _analysis_meta(analysis: dict[str, Any]) -> list[tuple[str, str]]:
    location = analysis.get("location") or {}
    cep = analysis.get("cep") or {}
    executive = analysis.get("executive") or build_executive_summary(analysis)
    best = executive.get("bestCostCarrier") or {}
    fastest = executive.get("fastestCarrier") or {}
    return [
        ("Data", _analysis_date(analysis)),
        ("Responsavel", str(analysis.get("responsible") or "-")),
        ("CEP", str(cep.get("cep") or "-")),
        ("Municipio", str(location.get("municipio") or cep.get("city") or "-")),
        ("UF", str(location.get("uf") or cep.get("uf") or "-")),
        ("ESTB", str(location.get("estb") or "-")),
        ("Melhor custo", str(best.get("label") or "-")),
        ("Menor prazo", str(fastest.get("label") or "-")),
        ("Versao", str(analysis.get("version") or 1)),
    ]


def _cell_tone(value: Any, column_values: list[float]) -> str:
    number = _number(value)
    if number is None:
        return ""
    if len(column_values) <= 1:
        return "good"
    low, high = min(column_values), max(column_values)
    if high == low:
        return "good"
    ratio = (number - low) / (high - low)
    if ratio <= .08:
        return "best"
    if ratio <= .35:
        return "good"
    if ratio <= .65:
        return "mid"
    if ratio <= .9:
        return "bad"
    return "worst"


def _comparison_table_html(analysis: dict[str, Any]) -> str:
    weights = analysis.get("weights") or []
    rows = analysis.get("rows") or []
    variations = analysis.get("variations") or []
    rep = analysis.get("representativity") or {}
    location = analysis.get("location") or {}
    cep = analysis.get("cep") or {}
    title = f"RESULTADO ANALISE - {(location.get('municipio') or cep.get('city') or '-').upper()} ({cep.get('cep') or 'CEP'})"

    columns = [
        [float(row.get("totals", [])[idx]) for row in rows if idx < len(row.get("totals", [])) and row.get("totals", [])[idx] is not None]
        for idx, _ in enumerate(weights)
    ]

    html = [
        '<table class="comparison">',
        f'<thead><tr class="title"><th colspan="{len(weights) + 1}">{escape(title)}</th></tr>',
        '<tr><th>Transportadora</th>' + ''.join(f'<th>{escape(str(weight))} KG</th>' for weight in weights) + '</tr></thead><tbody>',
    ]
    for row in rows:
        klass = "main" if row.get("role") == "main" else ""
        cells = []
        for idx, value in enumerate(row.get("totals") or []):
            tone = _cell_tone(value, columns[idx] if idx < len(columns) else [])
            cells.append(f'<td class="tone-{tone}"><span>R$</span><strong>{escape(money(value).replace("R$", "").strip())}</strong></td>')
        html.append(f'<tr class="{klass}"><td class="label">{escape(row.get("label") or "")}</td>{"".join(cells)}</tr>')
    for variation in variations:
        cells = ''.join(f'<td class="dark">{escape(percent_plain(value))}</td>' for value in variation.get("values") or [])
        html.append(f'<tr><td class="label">{escape(variation.get("label") or "")}</td>{cells}</tr>')
    if rep.get("values"):
        cells = ''.join(f'<td class="dark">{escape(percent_plain(value))}</td>' for value in rep.get("values") or [])
        html.append(f'<tr><td class="label">{escape(rep.get("label") or "REPRESENTATIVIDADE")}</td>{cells}</tr>')
    html.append("</tbody></table>")
    return "".join(html)


def _executive_cards_html(executive: dict[str, Any]) -> str:
    best = executive.get("bestCostCarrier") or {}
    fastest = executive.get("fastestCarrier") or {}
    balance = executive.get("bestBalanceCarrier") or {}
    saving = executive.get("potentialSaving") or {}
    cards = [
        ("Melhor custo", best.get("label") or "-", money(best.get("averageCost"))),
        ("Menor prazo", fastest.get("label") or "-", f"{fastest.get('averageDeadline'):.1f} dia(s)" if fastest.get("averageDeadline") is not None else "-"),
        ("Custo x prazo", balance.get("label") or "-", money(balance.get("averageCost"))),
        ("Economia potencial", money(saving.get("amount")), percent(saving.get("percent"))),
    ]
    return '<div class="cards">' + ''.join(
        f'<div class="card"><span>{escape(label)}</span><strong>{escape(str(value))}</strong><em>{escape(str(detail))}</em></div>'
        for label, value, detail in cards
    ) + '</div>'


def _ranking_html(executive: dict[str, Any]) -> str:
    rows = executive.get("ranking") or []
    if not rows:
        return ""
    body = "".join(
        f'<tr><td>{escape(str(item.get("position") or ""))}</td><td>{escape(str(item.get("label") or "-"))}</td><td>{escape(money(item.get("averageCost")))}</td><td>{escape(str(round(float(item.get("averageDeadline")), 1)) if item.get("averageDeadline") is not None else "-")}</td><td>{escape(percent(item.get("savingVsMainPct")))}</td></tr>'
        for item in rows[:8]
    )
    return f'<div class="mini"><h3>Ranking executivo</h3><table class="ranking"><thead><tr><th>#</th><th>Transportadora</th><th>Custo medio</th><th>Prazo medio</th><th>Economia vs principal</th></tr></thead><tbody>{body}</tbody></table></div>'


def _insights_html(executive: dict[str, Any]) -> str:
    insights = executive.get("insights") or []
    if not insights:
        return ""
    return '<div class="insights"><h3>Insights e oportunidades</h3>' + ''.join(f'<p>{escape(str(item))}</p>' for item in insights[:6]) + '</div>'


def _analysis_block_html(analysis: dict[str, Any]) -> str:
    executive = analysis.get("executive") or build_executive_summary(analysis)
    meta = "".join(
        f'<span class="meta-pill"><b>{escape(label)}:</b> {escape(value)}</span>'
        for label, value in _analysis_meta(analysis)
    )
    warnings = analysis.get("warnings") or []
    warning_html = ""
    if warnings:
        warning_html = f'<div class="notice"><b>Diagnostico:</b> {escape("; ".join(str(item) for item in warnings))}</div>'
    return f"""
    <article class="analysis-block">
      <header class="analysis-header">
        <p>COMPARATIVO TRANSPORTADORAS</p>
        <h1>{escape(_analysis_name(analysis))}</h1>
        <div class="meta-row">{meta}</div>
      </header>
      {_executive_cards_html(executive)}
      <div class="report-grid">
        {_ranking_html(executive)}
        {_insights_html(executive)}
      </div>
      <div class="table-wrap">{_comparison_table_html(analysis)}</div>
      {warning_html}
    </article>
    """


def _dashboard_html(analyses: list[dict[str, Any]]) -> str:
    dashboard = build_dashboard_summary(analyses)
    totals = dashboard.get("totals") or {}
    best = dashboard.get("bestCostCarrier") or {}
    fastest = dashboard.get("fastestCarrier") or {}
    cards = [
        ("Analises", totals.get("analyses", 0), "ativas no historico"),
        ("Custo medio", money(totals.get("averageCost")), "frete analisado"),
        ("Economia potencial", money(totals.get("totalPotentialSaving")), "soma das oportunidades"),
        ("Melhor custo geral", best.get("label") or "-", money(best.get("averageCost"))),
        ("Menor prazo geral", fastest.get("label") or "-", f"{fastest.get('averageDeadline'):.1f} dia(s)" if fastest.get("averageDeadline") is not None else "-"),
    ]
    opportunities = dashboard.get("opportunities") or []
    return f"""
    <section class="cover">
      <p>RELATORIO EXECUTIVO</p>
      <h1>Comparativo de Transportadoras</h1>
      <span>Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</span>
      <div class="cards cover-cards">{''.join(f'<div class="card"><span>{escape(str(a))}</span><strong>{escape(str(b))}</strong><em>{escape(str(c))}</em></div>' for a, b, c in cards)}</div>
      <div class="insights cover-insights"><h3>Principais oportunidades</h3>{''.join(f'<p>{escape(str(item))}</p>' for item in opportunities[:5]) or '<p>Nenhuma oportunidade calculada ainda.</p>'}</div>
    </section>
    """


def build_final_html(analyses: list[dict[str, Any]]) -> bytes:
    active = [analysis for analysis in analyses if not analysis.get("archived")]
    blocks = [_analysis_block_html(analysis) for analysis in active]
    body = _dashboard_html(active) + ("\n".join(blocks) if blocks else "<p>Nenhuma analise disponivel.</p>")
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8" />
  <title>Comparativo Transportadoras</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 24px; background: #0c0d10; color: #eef1f5; font-family: "Segoe UI", Arial, sans-serif; }}
    .cover, .analysis-block {{ page-break-inside: avoid; margin: 0 0 24px; border: 1px solid #2b313d; border-radius: 8px; padding: 18px; background: #14161b; box-shadow: 0 22px 70px rgba(0, 0, 0, .35); }}
    .cover p, .analysis-header p {{ margin: 0 0 6px; color: #57c7b6; font-size: 11px; letter-spacing: .11em; font-weight: 900; }}
    .cover h1, .analysis-header h1 {{ margin: 0 0 10px; font-size: 22px; overflow-wrap: anywhere; }}
    .cover span {{ color: #9aa3b2; font-size: 12px; }}
    .meta-row {{ display: flex; flex-wrap: wrap; gap: 7px; margin-top: 10px; }}
    .meta-pill {{ border: 1px solid #2b313d; background: #101319; border-radius: 999px; padding: 5px 9px; font-size: 12px; color: #cfd5df; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin: 14px 0; }}
    .cover-cards {{ grid-template-columns: repeat(5, minmax(0, 1fr)); }}
    .card {{ border: 1px solid #2b313d; border-radius: 8px; padding: 12px; background: #101319; min-height: 90px; }}
    .card span {{ display: block; color: #9aa3b2; font-size: 11px; text-transform: uppercase; letter-spacing: .07em; }}
    .card strong {{ display: block; margin-top: 6px; font-size: 15px; color: #eef1f5; overflow-wrap: anywhere; }}
    .card em {{ display: block; margin-top: 5px; color: #9aa3b2; font-size: 12px; font-style: normal; }}
    .report-grid {{ display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(280px, .85fr); gap: 12px; margin-bottom: 14px; }}
    .mini, .insights {{ border: 1px solid #2b313d; border-radius: 8px; padding: 12px; background: #101319; }}
    h3 {{ margin: 0 0 9px; font-size: 13px; color: #dce2ec; }}
    .insights p {{ margin: 7px 0; color: #cfd5df; font-size: 12px; line-height: 1.45; }}
    .table-wrap {{ width: 100%; overflow-x: auto; border: 1px solid #2b313d; border-radius: 8px; }}
    table {{ border-collapse: collapse; }}
    .comparison {{ width: max-content; min-width: 100%; table-layout: auto; font-size: 12px; }}
    th, td {{ border: 1px solid #2b313d; padding: 6px 8px; vertical-align: middle; }}
    th {{ background: #415c70; color: #fff; text-align: center; }}
    .title th {{ background: #006ead; font-size: 15px; }}
    .label {{ background: #3f5b70; color: #fff; text-align: left; font-weight: 800; min-width: 230px; max-width: 330px; white-space: normal; overflow-wrap: anywhere; }}
    .comparison td {{ text-align: right; font-weight: 700; min-width: 96px; color: #fff; }}
    .comparison td span {{ float: left; margin-right: 8px; }}
    tr.main td {{ font-weight: 900; }}
    .tone-best {{ background: #007828; }} .tone-good {{ background: #395d2e; }} .tone-mid {{ background: #6b5930; }} .tone-bad {{ background: #87442c; }} .tone-worst {{ background: #c8002d; }}
    .dark {{ background: #242424; text-align: center; }}
    .ranking {{ width: 100%; font-size: 12px; }} .ranking th {{ background: #202530; color: #dce2ec; }} .ranking td {{ color: #eef1f5; background: #101319; }}
    .notice {{ margin-top: 12px; border: 1px solid #2b313d; background: #101319; border-radius: 8px; padding: 10px; color: #cfd5df; font-size: 12px; }}
    @media print {{ body {{ background: #0c0d10; padding: 10px; }} .table-wrap {{ overflow: visible; }} .cover, .analysis-block {{ box-shadow: none; }} }}
    @media (max-width: 900px) {{ .cards, .cover-cards, .report-grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
{body}
</body>
</html>"""
    return html.encode("utf-8")


def _weight_chunks(weights: list[Any], max_cols: int) -> list[tuple[int, int]]:
    if not weights:
        return [(0, 0)]
    return [(start, min(start + max_cols, len(weights))) for start in range(0, len(weights), max_cols)]


def build_final_pdf(analyses: list[dict[str, Any]]) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A3, A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    active_analyses = [analysis for analysis in analyses if not analysis.get("archived")]
    max_weights = max((len(analysis.get("weights") or []) for analysis in active_analyses), default=0)
    page_size = landscape(A3 if max_weights > 8 else A4)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=page_size, leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=20)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("FreteTitle", parent=styles["Title"], textColor=colors.HexColor("#111827"), fontSize=18, leading=22, spaceAfter=6)
    subtitle_style = ParagraphStyle("FreteSubtitle", parent=styles["Normal"], textColor=colors.HexColor("#526173"), fontSize=8.2, leading=10)
    section_style = ParagraphStyle("FreteSection", parent=styles["Heading2"], textColor=colors.HexColor("#111827"), fontSize=12, leading=15, spaceAfter=4)
    cell_style = ParagraphStyle("FreteCell", parent=styles["Normal"], fontSize=6.7, leading=7.8, textColor=colors.white, alignment=TA_CENTER)
    label_style = ParagraphStyle("FreteLabel", parent=cell_style, alignment=TA_LEFT, fontName="Helvetica-Bold")
    header_style = ParagraphStyle("FreteHeader", parent=cell_style, fontName="Helvetica-Bold")
    dark_style = ParagraphStyle("FreteDark", parent=cell_style, fontName="Helvetica-Bold")
    body_style = ParagraphStyle("FreteBody", parent=styles["Normal"], textColor=colors.HexColor("#334155"), fontSize=8, leading=10)
    small_style = ParagraphStyle("FreteSmall", parent=body_style, fontSize=7.2, leading=9)

    def para(value: Any, style: ParagraphStyle = cell_style) -> Paragraph:
        return Paragraph(escape(str(value if value is not None else "-")), style)

    def add_footer(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(doc.leftMargin, 9, f"FreteLab - gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        canvas.drawRightString(page_size[0] - doc.rightMargin, 9, f"Pagina {_doc.page}")
        canvas.restoreState()

    tone_colors = {
        "best": colors.HexColor("#007828"),
        "good": colors.HexColor("#395d2e"),
        "mid": colors.HexColor("#6b5930"),
        "bad": colors.HexColor("#87442c"),
        "worst": colors.HexColor("#c8002d"),
    }

    story: list[Any] = []
    story.append(Paragraph("<b>RELATORIO EXECUTIVO - COMPARATIVO TRANSPORTADORAS</b>", title_style))
    story.append(Paragraph(f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", subtitle_style))
    story.append(Spacer(1, 8))

    dashboard = build_dashboard_summary(active_analyses)
    totals = dashboard.get("totals") or {}
    best = dashboard.get("bestCostCarrier") or {}
    fastest = dashboard.get("fastestCarrier") or {}
    summary_data = [
        [para("Analises", header_style), para("Custo medio", header_style), para("Economia potencial", header_style), para("Melhor custo geral", header_style), para("Menor prazo geral", header_style)],
        [
            para(totals.get("analyses", 0), body_style),
            para(money(totals.get("averageCost")), body_style),
            para(money(totals.get("totalPotentialSaving")), body_style),
            para(best.get("label") or "-", body_style),
            para(f"{fastest.get('label') or '-'} ({fastest.get('averageDeadline'):.1f}d)" if fastest.get("averageDeadline") is not None else fastest.get("label") or "-", body_style),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[doc.width / 5] * 5, hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#40586a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(summary_table)
    if dashboard.get("opportunities"):
        story.append(Spacer(1, 7))
        story.append(Paragraph("<b>Principais oportunidades</b>", section_style))
        for item in (dashboard.get("opportunities") or [])[:5]:
            story.append(Paragraph(f"- {escape(str(item))}", small_style))
    story.append(Spacer(1, 12))

    if not active_analyses:
        story.append(Paragraph("Nenhuma analise disponivel.", styles["Normal"]))

    for index, analysis in enumerate(active_analyses, start=1):
        if index > 1:
            story.append(PageBreak())
        executive = analysis.get("executive") or build_executive_summary(analysis)
        location = analysis.get("location") or {}
        cep = analysis.get("cep") or {}
        title = _analysis_name(analysis)
        subtitle = f"{(location.get('municipio') or cep.get('city') or '-').upper()} | CEP {cep.get('cep') or '-'} | UF {location.get('uf') or cep.get('uf') or '-'}"
        meta_text = " | ".join(f"<b>{escape(label)}:</b> {escape(value)}" for label, value in _analysis_meta(analysis))
        story.append(Paragraph(f"<b>{escape(title)}</b>", section_style))
        story.append(Paragraph(escape(subtitle), subtitle_style))
        story.append(Paragraph(meta_text, subtitle_style))
        story.append(Spacer(1, 6))

        cards = [
            ("Melhor custo", (executive.get("bestCostCarrier") or {}).get("label") or "-", money((executive.get("bestCostCarrier") or {}).get("averageCost"))),
            ("Menor prazo", (executive.get("fastestCarrier") or {}).get("label") or "-", f"{(executive.get('fastestCarrier') or {}).get('averageDeadline'):.1f} dia(s)" if (executive.get("fastestCarrier") or {}).get("averageDeadline") is not None else "-"),
            ("Custo x prazo", (executive.get("bestBalanceCarrier") or {}).get("label") or "-", money((executive.get("bestBalanceCarrier") or {}).get("averageCost"))),
            ("Economia potencial", money((executive.get("potentialSaving") or {}).get("amount")), percent((executive.get("potentialSaving") or {}).get("percent"))),
        ]
        card_data = [[para(label, header_style) for label, _value, _detail in cards], [para(f"{value}\n{detail}", body_style) for _label, value, detail in cards]]
        card_table = Table(card_data, colWidths=[doc.width / 4] * 4, hAlign="LEFT")
        card_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#40586a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(card_table)
        if executive.get("insights"):
            story.append(Spacer(1, 5))
            for item in (executive.get("insights") or [])[:4]:
                story.append(Paragraph(f"- {escape(str(item))}", small_style))
        story.append(Spacer(1, 8))

        weights = analysis.get("weights") or []
        rows = analysis.get("rows") or []
        variations = analysis.get("variations") or []
        rep = analysis.get("representativity") or {}
        max_cols = 10 if page_size == landscape(A3) else 7
        for start, end in _weight_chunks(weights, max_cols):
            chunk_weights = weights[start:end]
            if not chunk_weights:
                continue
            value_columns = []
            for idx in range(start, end):
                values = []
                for row in rows:
                    totals = row.get("totals") or []
                    if idx < len(totals) and totals[idx] is not None:
                        values.append(float(totals[idx]))
                value_columns.append(values)

            matrix: list[list[Any]] = [[para("Transportadora", header_style)] + [para(f"{weight} KG", header_style) for weight in chunk_weights]]
            for row in rows:
                totals = row.get("totals") or []
                matrix.append([para(row.get("label") or "", label_style)] + [para(money(totals[idx]) if idx < len(totals) and totals[idx] is not None else "-", cell_style) for idx in range(start, end)])
            for variation in variations:
                values = variation.get("values") or []
                matrix.append([para(variation.get("label") or "", label_style)] + [para(percent_plain(values[idx]) if idx < len(values) else "-", dark_style) for idx in range(start, end)])
            if rep.get("values"):
                values = rep.get("values") or []
                matrix.append([para(rep.get("label") or "REPRESENTATIVIDADE", label_style)] + [para(percent_plain(values[idx]) if idx < len(values) else "-", dark_style) for idx in range(start, end)])

            first_width = min(230, max(170, doc.width * .24))
            weight_width = (doc.width - first_width) / max(len(chunk_weights), 1)
            table = Table(matrix, repeatRows=1, colWidths=[first_width] + [weight_width] * len(chunk_weights), splitByRow=1, hAlign="LEFT")
            style_commands = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#40586a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#a5adb8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 6.5),
                ("LEADING", (0, 0), (-1, -1), 7.6),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 1), (0, -1), colors.HexColor("#3f5b70")),
                ("TEXTCOLOR", (0, 1), (0, -1), colors.white),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ]
            for row_idx, row in enumerate(rows, start=1):
                if row.get("role") == "main":
                    style_commands.append(("FONTNAME", (0, row_idx), (-1, row_idx), "Helvetica-Bold"))
                for local_col, idx in enumerate(range(start, end), start=1):
                    totals = row.get("totals") or []
                    value = totals[idx] if idx < len(totals) else None
                    tone = _cell_tone(value, value_columns[local_col - 1] if local_col - 1 < len(value_columns) else [])
                    if tone:
                        style_commands.append(("BACKGROUND", (local_col, row_idx), (local_col, row_idx), tone_colors[tone]))
                        style_commands.append(("TEXTCOLOR", (local_col, row_idx), (local_col, row_idx), colors.white))
            first_metric_row = 1 + len(rows)
            if first_metric_row < len(matrix):
                style_commands.extend([
                    ("BACKGROUND", (0, first_metric_row), (-1, -1), colors.HexColor("#242424")),
                    ("TEXTCOLOR", (0, first_metric_row), (-1, -1), colors.white),
                    ("FONTNAME", (0, first_metric_row), (0, -1), "Helvetica-Bold"),
                ])
            table.setStyle(TableStyle(style_commands))
            story.append(Paragraph(f"Faixas de peso: {chunk_weights[0]} kg a {chunk_weights[-1]} kg", subtitle_style))
            story.append(table)
            story.append(Spacer(1, 9))

    doc.build(story, onFirstPage=add_footer, onLaterPages=add_footer)
    return buffer.getvalue()


def build_analysis_pdf(analysis: dict[str, Any]) -> bytes:
    return build_final_pdf([analysis])
