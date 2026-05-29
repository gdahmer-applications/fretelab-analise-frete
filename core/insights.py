from __future__ import annotations

from collections import defaultdict
from typing import Any


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except Exception:
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _avg(values: list[Any]) -> float | None:
    nums = [_to_float(value) for value in values]
    nums = [value for value in nums if value is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _fmt_money(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    return f"R$ {number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_pct(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "-"
    return f"{number * 100:.1f}%".replace(".", ",")


def _safe_label(row: dict[str, Any] | None) -> str:
    if not row:
        return "-"
    return str(row.get("label") or row.get("key") or "-")


def _row_deadline_avg(row: dict[str, Any]) -> float | None:
    deadlines = row.get("deadlines") or []
    return _avg(deadlines)


def _row_average_cost(row: dict[str, Any]) -> float | None:
    return _avg(row.get("totals") or [])


def _role_badges(row: dict[str, Any], best_cost_key: str | None, fastest_key: str | None, balance_key: str | None) -> list[str]:
    badges: list[str] = []
    if row.get("role") == "main":
        badges.append("Principal")
    if row.get("key") == best_cost_key:
        badges.append("Melhor custo")
    if fastest_key and row.get("key") == fastest_key:
        badges.append("Menor prazo")
    if balance_key and row.get("key") == balance_key:
        badges.append("Custo x prazo")
    return badges


def build_executive_summary(analysis: dict[str, Any]) -> dict[str, Any]:
    """Create executive indicators without changing the freight calculation itself."""
    rows = [row for row in (analysis.get("rows") or []) if row]
    weights = analysis.get("weights") or []
    main_row = next((row for row in rows if row.get("role") == "main"), rows[0] if rows else None)

    ranking_raw: list[dict[str, Any]] = []
    for row in rows:
        avg_cost = _row_average_cost(row)
        avg_deadline = _row_deadline_avg(row)
        ranking_raw.append({
            "key": row.get("key"),
            "label": _safe_label(row),
            "role": row.get("role") or "secondary",
            "averageCost": avg_cost,
            "averageDeadline": avg_deadline,
        })

    ranking_by_cost = sorted(
        [item for item in ranking_raw if item.get("averageCost") is not None],
        key=lambda item: float(item["averageCost"]),
    )
    ranking_by_deadline = sorted(
        [item for item in ranking_raw if item.get("averageDeadline") is not None],
        key=lambda item: (float(item["averageDeadline"]), float(item.get("averageCost") or 0)),
    )

    best_cost = ranking_by_cost[0] if ranking_by_cost else None
    worst_cost = ranking_by_cost[-1] if ranking_by_cost else None
    fastest = ranking_by_deadline[0] if ranking_by_deadline else None

    min_cost = float(best_cost["averageCost"]) if best_cost and best_cost.get("averageCost") is not None else None
    max_cost = float(worst_cost["averageCost"]) if worst_cost and worst_cost.get("averageCost") is not None else None
    min_deadline = float(fastest["averageDeadline"]) if fastest and fastest.get("averageDeadline") is not None else None
    max_deadline = max((float(item["averageDeadline"]) for item in ranking_by_deadline), default=None)

    def balance_score(item: dict[str, Any]) -> float:
        cost = _to_float(item.get("averageCost"))
        deadline = _to_float(item.get("averageDeadline"))
        if cost is None:
            return 10_000.0
        cost_score = 0.0 if min_cost is None or max_cost in (None, min_cost) else (cost - min_cost) / (max_cost - min_cost)
        if deadline is None or min_deadline is None or max_deadline in (None, min_deadline):
            deadline_score = 0.5
        else:
            deadline_score = (deadline - min_deadline) / (max_deadline - min_deadline)
        return (cost_score * 0.65) + (deadline_score * 0.35)

    balance = min(ranking_by_cost, key=balance_score) if ranking_by_cost else None
    best_cost_key = best_cost.get("key") if best_cost else None
    fastest_key = fastest.get("key") if fastest else None
    balance_key = balance.get("key") if balance else None

    main_avg = _row_average_cost(main_row) if main_row else None
    best_avg = _to_float(best_cost.get("averageCost")) if best_cost else None
    potential_saving = None
    potential_saving_pct = None
    if main_avg is not None and best_avg is not None and best_avg < main_avg:
        potential_saving = main_avg - best_avg
        potential_saving_pct = potential_saving / main_avg if main_avg else None
    else:
        potential_saving = 0.0 if main_avg is not None and best_avg is not None else None
        potential_saving_pct = 0.0 if main_avg is not None and best_avg is not None else None

    ranking: list[dict[str, Any]] = []
    for idx, item in enumerate(ranking_by_cost, start=1):
        source_row = next((row for row in rows if row.get("key") == item.get("key")), {})
        saving_vs_main = None
        saving_vs_main_pct = None
        if main_avg is not None and item.get("averageCost") is not None:
            saving_vs_main = main_avg - float(item["averageCost"])
            saving_vs_main_pct = saving_vs_main / main_avg if main_avg else None
        ranking.append({
            **item,
            "position": idx,
            "savingVsMain": saving_vs_main,
            "savingVsMainPct": saving_vs_main_pct,
            "badges": _role_badges(source_row, best_cost_key, fastest_key, balance_key),
        })

    weight_highlights: list[dict[str, Any]] = []
    for idx, weight in enumerate(weights):
        candidates: list[dict[str, Any]] = []
        for row in rows:
            totals = row.get("totals") or []
            deadlines = row.get("deadlines") or []
            if idx >= len(totals):
                continue
            value = _to_float(totals[idx])
            if value is None:
                continue
            deadline = _to_float(deadlines[idx]) if idx < len(deadlines) else None
            candidates.append({
                "key": row.get("key"),
                "label": _safe_label(row),
                "role": row.get("role") or "secondary",
                "cost": value,
                "deadline": deadline,
            })
        if not candidates:
            continue
        best_item = min(candidates, key=lambda item: item["cost"])
        worst_item = max(candidates, key=lambda item: item["cost"])
        fast_candidates = [item for item in candidates if item.get("deadline") is not None]
        fastest_item = min(fast_candidates, key=lambda item: (float(item["deadline"]), item["cost"])) if fast_candidates else None
        main_candidate = next((item for item in candidates if item.get("role") == "main"), None)
        saving_from_main = None
        saving_from_main_pct = None
        if main_candidate:
            saving_from_main = main_candidate["cost"] - best_item["cost"]
            saving_from_main_pct = saving_from_main / main_candidate["cost"] if main_candidate["cost"] else None
        spread = worst_item["cost"] - best_item["cost"]
        spread_pct = spread / worst_item["cost"] if worst_item["cost"] else None
        weight_highlights.append({
            "weight": weight,
            "bestCarrier": best_item["label"],
            "bestCarrierKey": best_item["key"],
            "bestCost": best_item["cost"],
            "worstCarrier": worst_item["label"],
            "worstCost": worst_item["cost"],
            "fastestCarrier": fastest_item["label"] if fastest_item else None,
            "fastestDeadline": fastest_item.get("deadline") if fastest_item else None,
            "mainCost": main_candidate.get("cost") if main_candidate else None,
            "savingFromMain": saving_from_main,
            "savingFromMainPct": saving_from_main_pct,
            "spread": spread,
            "spreadPct": spread_pct,
        })

    opportunities = [item for item in weight_highlights if _to_float(item.get("savingFromMain")) and float(item["savingFromMain"]) > 0]
    top_opportunities = sorted(opportunities, key=lambda item: float(item.get("savingFromMainPct") or 0), reverse=True)[:5]

    location = analysis.get("location") or {}
    cep = analysis.get("cep") or {}
    place = f"{location.get('municipio') or cep.get('city') or '-'} / {location.get('uf') or cep.get('uf') or '-'}"
    cep_text = str(cep.get("cep") or "-")

    insights: list[str] = []
    if best_cost and main_row:
        if potential_saving and potential_saving > 0:
            insights.append(
                f"Para {place}, CEP {cep_text}, {_safe_label(main_row)} pode ser substituída por {best_cost.get('label')} com economia média de {_fmt_pct(potential_saving_pct)} ({_fmt_money(potential_saving)}) nas faixas analisadas."
            )
        else:
            insights.append(
                f"Para {place}, CEP {cep_text}, a transportadora principal ja está alinhada ao melhor custo medio entre as opções selecionadas."
            )
    if fastest:
        deadline_text = f"{fastest.get('averageDeadline'):.1f} dia(s)" if fastest.get("averageDeadline") is not None else "prazo nao informado"
        insights.append(f"Menor prazo médio: {fastest.get('label')} com {deadline_text}.")
    if balance:
        insights.append(f"Melhor equilíbrio custo x prazo: {balance.get('label')}.")
    if top_opportunities:
        item = top_opportunities[0]
        insights.append(
            f"Maior oportunidade por faixa: {item.get('weight')} kg, economia de {_fmt_pct(item.get('savingFromMainPct'))} usando {item.get('bestCarrier')}."
        )
    if worst_cost and best_cost and worst_cost.get("key") != best_cost.get("key"):
        spread = (float(worst_cost["averageCost"]) - float(best_cost["averageCost"])) if worst_cost.get("averageCost") is not None and best_cost.get("averageCost") is not None else None
        if spread is not None:
            insights.append(f"Amplitude média entre melhor e pior custo: {_fmt_money(spread)}.")

    return {
        "averageCost": _avg([item.get("averageCost") for item in ranking_by_cost]),
        "mainCarrier": {
            "key": main_row.get("key") if main_row else None,
            "label": _safe_label(main_row),
            "averageCost": main_avg,
            "averageDeadline": _row_deadline_avg(main_row) if main_row else None,
        },
        "bestCostCarrier": best_cost,
        "worstCostCarrier": worst_cost,
        "fastestCarrier": fastest,
        "bestBalanceCarrier": balance,
        "potentialSaving": {
            "amount": potential_saving,
            "percent": potential_saving_pct,
        },
        "ranking": ranking,
        "weightHighlights": weight_highlights,
        "topOpportunities": top_opportunities,
        "insights": insights[:6],
        "statusTags": [
            tag for tag, enabled in [
                ("Economia potencial", bool(potential_saving and potential_saving > 0)),
                ("Melhor custo", bool(best_cost)),
                ("Menor prazo", bool(fastest)),
                ("Custo x prazo", bool(balance)),
            ] if enabled
        ],
    }


def build_dashboard_summary(records: list[dict[str, Any]], archived_count: int = 0) -> dict[str, Any]:
    active = [record for record in records if record and not record.get("archived")]
    carrier_costs: dict[str, list[float]] = defaultdict(list)
    carrier_deadlines: dict[str, list[float]] = defaultdict(list)
    carrier_labels: dict[str, str] = {}
    locations: list[dict[str, Any]] = []
    insights: list[str] = []
    total_saving = 0.0
    saving_count = 0
    avg_costs: list[float] = []

    for record in active:
        executive = record.get("executive") or build_executive_summary(record)
        avg_cost = _to_float(executive.get("averageCost"))
        if avg_cost is not None:
            avg_costs.append(avg_cost)
        saving = _to_float((executive.get("potentialSaving") or {}).get("amount"))
        if saving is not None:
            total_saving += saving
            saving_count += 1
        for item in executive.get("ranking") or []:
            key = str(item.get("key") or item.get("label") or "-")
            carrier_labels[key] = str(item.get("label") or key)
            cost = _to_float(item.get("averageCost"))
            deadline = _to_float(item.get("averageDeadline"))
            if cost is not None:
                carrier_costs[key].append(cost)
            if deadline is not None:
                carrier_deadlines[key].append(deadline)
        location = record.get("location") or {}
        cep = record.get("cep") or {}
        if avg_cost is not None:
            locations.append({
                "analysisId": record.get("id"),
                "name": record.get("analysisName") or record.get("title") or "Analise",
                "label": f"{location.get('municipio') or cep.get('city') or '-'} / {location.get('uf') or cep.get('uf') or '-'}",
                "cep": cep.get("cep") or "-",
                "averageCost": avg_cost,
            })
        insights.extend(executive.get("insights") or [])

    carrier_ranking = []
    for key, values in carrier_costs.items():
        carrier_ranking.append({
            "key": key,
            "label": carrier_labels.get(key, key),
            "averageCost": sum(values) / len(values),
            "analyses": len(values),
            "averageDeadline": (sum(carrier_deadlines.get(key, [])) / len(carrier_deadlines[key])) if carrier_deadlines.get(key) else None,
        })
    carrier_ranking.sort(key=lambda item: item["averageCost"])
    locations.sort(key=lambda item: item["averageCost"], reverse=True)
    fastest = sorted([item for item in carrier_ranking if item.get("averageDeadline") is not None], key=lambda item: item["averageDeadline"])

    recent = []
    for record in active[:5]:
        executive = record.get("executive") or build_executive_summary(record)
        location = record.get("location") or {}
        cep = record.get("cep") or {}
        recent.append({
            "id": record.get("id"),
            "analysisName": record.get("analysisName") or record.get("title") or "Analise sem titulo",
            "date": record.get("analysisDate") or record.get("createdAt") or "-",
            "place": f"{location.get('municipio') or cep.get('city') or '-'} / {location.get('uf') or cep.get('uf') or '-'}",
            "cep": cep.get("cep") or "-",
            "bestCarrier": (executive.get("bestCostCarrier") or {}).get("label") or "-",
            "saving": (executive.get("potentialSaving") or {}).get("amount"),
        })

    return {
        "totals": {
            "analyses": len(active),
            "archived": archived_count,
            "averageCost": _avg(avg_costs),
            "totalPotentialSaving": total_saving if saving_count else None,
            "analysesWithSaving": saving_count,
        },
        "bestCostCarrier": carrier_ranking[0] if carrier_ranking else None,
        "fastestCarrier": fastest[0] if fastest else None,
        "highestCostLocations": locations[:5],
        "carrierRanking": carrier_ranking[:8],
        "opportunities": list(dict.fromkeys(insights))[:8],
        "recent": recent,
    }
