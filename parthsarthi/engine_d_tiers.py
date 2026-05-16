"""
engine_d_tiers.py
Parthsarthi Capital - Phase 4, Item 4.3
ENGINE D - PROMOTION-TIER STATE MACHINE (Module 3).

Once a compounder is HELD (incubation passed), it earns promotion
tiers over time. The tiers are FUNCTIONAL - they change how the
system treats the position - not decorative badges.

  SEEDLING    0-12 months held    standard monitoring; thesis
                                  checked every screen
  ESTABLISHED 12+ months          LTCG threshold passed; standard
                                  monitoring continues
  IMMORTAL    24+ months          wider tolerance: a soft thesis
                                  trigger needs 2 consecutive
                                  readings before it fires
  LEGENDARY   48+ months          widest tolerance: reviewed only
                                  on a HARD thesis-break trigger,
                                  not on soft metric drift

The principle: the longer a compounder proves itself, the more
benefit of the doubt it earns. A LEGENDARY holding has shown
durability across years and cycles - the system should not shake
it out over one noisy quarter. This encodes "let winners run".

This module decides a position's tier from its months held, and
exposes how the tier modifies thesis-break sensitivity (used by the
exit module, item 4.4).
"""

from reasoning_engine import Decision


# ---- tier names and the months-held threshold for each ----
SEEDLING    = 'SEEDLING'
ESTABLISHED = 'ESTABLISHED'
IMMORTAL    = 'IMMORTAL'
LEGENDARY   = 'LEGENDARY'

TIER_THRESHOLDS = [          # (tier, minimum months held)
    (LEGENDARY,   48),
    (IMMORTAL,    24),
    (ESTABLISHED, 12),
    (SEEDLING,     0),
]

# how many consecutive bad readings a SOFT thesis trigger needs
# before it fires, per tier
SOFT_TRIGGER_READINGS = {
    SEEDLING:    1,          # fires on first occurrence
    ESTABLISHED: 1,          # fires on first occurrence
    IMMORTAL:    2,          # needs 2 consecutive readings
    LEGENDARY:   2,          # needs 2 consecutive readings
}

# tiers for which soft metric drift is monitored at all.
# LEGENDARY is reviewed only on HARD triggers - soft drift is ignored.
SOFT_MONITORED = {SEEDLING, ESTABLISHED, IMMORTAL}


def tier_for_months(months_held):
    """Return the promotion tier for a position held this many months."""
    for tier, threshold in TIER_THRESHOLDS:
        if months_held >= threshold:
            return tier
    return SEEDLING


def soft_trigger_threshold(tier):
    """Consecutive bad readings a soft trigger needs to fire, for this tier."""
    return SOFT_TRIGGER_READINGS.get(tier, 1)


def soft_drift_monitored(tier):
    """True if soft metric drift is monitored for this tier at all."""
    return tier in SOFT_MONITORED


def assess_tier(ticker, months_held):
    """
    Decide a held position's promotion tier and describe what the
    tier changes. Returns a Decision.
    """
    tier = tier_for_months(months_held)
    readings = soft_trigger_threshold(tier)
    monitored = soft_drift_monitored(tier)

    # what changes at this tier
    if tier == SEEDLING:
        effect = ('standard monitoring; thesis checked every screen, '
                  'soft triggers fire on first occurrence')
    elif tier == ESTABLISHED:
        effect = ('LTCG threshold passed; standard monitoring continues, '
                  'soft triggers fire on first occurrence')
    elif tier == IMMORTAL:
        effect = ('wider tolerance; a soft thesis trigger now needs 2 '
                  'consecutive readings before it fires')
    else:  # LEGENDARY
        effect = ('widest tolerance; reviewed only on hard thesis-break '
                  'triggers - soft metric drift is no longer monitored')

    d = Decision('D', ticker, tier, 'Module 3 - Promotion Tier')
    d.add_fact('Months held', str(months_held))
    d.add_fact('Tier', tier)
    d.add_fact('Soft-trigger readings needed', str(readings))
    d.add_fact('Soft drift monitored', 'yes' if monitored else 'no')
    d.add_fact('Effect', effect)

    # margin = months until the next promotion
    next_tier = None
    for t, threshold in reversed(TIER_THRESHOLDS):   # ascending order
        if threshold > months_held:
            next_tier = (t, threshold)
            break
    if next_tier:
        d.set_margin(f'months to {next_tier[0]}',
                     next_tier[1] - months_held)
        d.set_counterfactual(
            f'-> promoted to {next_tier[0]} after '
            f'{next_tier[1]} months held, if the thesis stays intact')
    else:
        d.set_margin('at the highest tier', 0)
        d.set_counterfactual('LEGENDARY is the highest tier - a proven '
                              'multi-year compounder, given the widest trust')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE D PROMOTION-TIER STATE MACHINE (Module 3) - self-test')
    print('=' * 64)

    # Test 1: tier mapping across the lifespan
    print('\nTest 1 - tier for months held:')
    for months in [0, 6, 12, 18, 24, 36, 48, 72]:
        tier = tier_for_months(months)
        readings = soft_trigger_threshold(tier)
        monitored = soft_drift_monitored(tier)
        print(f'  {months:3} months -> {tier:12} '
              f'(soft trigger needs {readings} reading(s), '
              f'soft drift monitored: {monitored})')

    # Test 2: a SEEDLING position
    print('\nTest 2 - SEEDLING (held 5 months):')
    d = assess_tier('HINDZINC', months_held=5)
    print(f'  tier: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: an IMMORTAL position
    print('\nTest 3 - IMMORTAL (held 30 months):')
    d = assess_tier('LUPIN', months_held=30)
    print(f'  tier: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: a LEGENDARY position
    print('\nTest 4 - LEGENDARY (held 60 months):')
    d = assess_tier('TITAN', months_held=60)
    print(f'  tier: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: boundary - exactly 24 months
    print('\nTest 5 - boundary (exactly 24 months):')
    d = assess_tier('FORCEMOT', months_held=24)
    print(f'  tier: {d.verdict}  '
          f'(soft trigger needs {soft_trigger_threshold(d.verdict)} readings)')

    print('\n' + '=' * 64)
    print('Self-test complete. Tiers are functional: IMMORTAL+ positions')
    print('need 2 readings for a soft trigger, and LEGENDARY positions')
    print('are reviewed only on hard thesis-break triggers.')
    print('=' * 64)
