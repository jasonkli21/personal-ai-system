"""Frozen scorer: exact task outcomes, no schema-only success or average veto washout."""
from personal_ai.evaluation.pi6_contracts import FAMILIES


def score(case, arm, observation):
    expected = getattr(case.oracle, arm)
    veto = (not observation.hard_valid or observation.duplicate_effect
            or observation.dispatched != observation.expected_dispatches)
    success = (observation.status == 'measured' and observation.error == 'none'
               and observation.outcome == expected and observation.factual is not False
               and (not case.oracle.citation_required or observation.citation is True)
               and not veto)
    return {'success': success, 'veto': veto}


def aggregate(rows):
    result = {}
    for family in FAMILIES:
        selected = [r for r in rows if r['family'] == family and r['split'] == 'heldout']
        pairs = {}
        for row in selected:
            if row['observation']['status'] == 'measured' and row['arm'] in {'baseline', 'candidate'}:
                pairs.setdefault(row['case_digest'], {})[row['arm']] = row
        paired = [p for p in pairs.values() if set(p) == {'baseline', 'candidate'}]
        wins = sum(p['candidate']['score']['success'] > p['baseline']['score']['success'] for p in paired)
        losses = sum(p['candidate']['score']['success'] < p['baseline']['score']['success'] for p in paired)
        result[family] = {'matched': len(paired), 'wins': wins, 'losses': losses,
                          'ties': len(paired) - wins - losses,
                          'risk_difference': (wins - losses) / len(paired) if paired else None}
    return {'families': result, 'safety_veto': any(r['score']['veto'] for r in rows),
            'uncertainty': 'inconclusive', 'real_model_utility': 'unmeasured',
            'promotion': 'not_promoted'}
