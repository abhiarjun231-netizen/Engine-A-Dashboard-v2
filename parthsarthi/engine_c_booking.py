"""
engine_c_booking.py
Parthsarthi Capital - Phase 3, Item 3.3
ENGINE C - PE-EXPANSION BOOKING ENGINE (Module 2A).

This is the core mechanism of Engine C - its Path A exit.

You bought the stock cheap. You sell it in thirds as it becomes
expensive. Booking is triggered by PE EXPANSION from the entry PE,
not by price alone - because price rising on rising earnings is not
the same as price rising on a re-rating.

  PE expanded +30% from entry PE  -> book one-third
  PE expanded +50% from entry PE  -> book another one-third
  PE expanded +80% from entry PE  -> book the final third (fully out)

Example: bought at PE 12.
  PE 15.6 (+30%)  -> book 1/3
  PE 18.0 (+50%)  -> book 1/3
  PE 21.6 (+80%)  -> book final 1/3

This is the one place Engine C books partial profit - because a
value re-rating is a finite event with a natural ceiling. The engine
tracks which tranches have already been booked so each fires once.
"""

from reasoning_engine import Decision


# ---- locked booking ladder (Engine C framework) ----
BOOKING_LADDER = [
    ('first',  30.0, 1/3),    # +30% PE expansion -> book 1/3
    ('second', 50.0, 1/3),    # +50% PE expansion -> book 1/3
    ('third',  80.0, 1/3),    # +80% PE expansion -> book final 1/3
]


def pe_expansion_pct(entry_pe, current_pe):
    """How much the PE has expanded from entry, in %."""
    if entry_pe is None or entry_pe <= 0 or current_pe is None:
        return None
    return (current_pe - entry_pe) / entry_pe * 100.0


def check_booking(ticker, entry_pe, current_pe, tranches_booked=None):
    """
    Check whether a PE-expansion booking tranche should fire.

    entry_pe        - the PE TTM at the time of purchase
    current_pe      - the PE TTM now
    tranches_booked - set of tranche names already booked
                      e.g. {'first'} if the +30% third is done

    Returns a Decision:
      'BOOK-THIRD'  - a booking tranche should fire now (which one is
                      named); if it is the third tranche the position
                      fully exits
      'HOLD'        - no new booking tranche; position continues
    """
    tranches_booked = set(tranches_booked or [])
    expansion = pe_expansion_pct(entry_pe, current_pe)

    if expansion is None:
        d = Decision('C', ticker, 'HOLD', 'Module 2A - PE Booking (no data)')
        d.add_fact('Issue', 'entry or current PE missing/invalid')
        d.set_margin('cannot evaluate booking', 0)
        d.set_counterfactual('booking can only be evaluated with valid '
                              'entry and current PE values')
        return d

    # find the highest tranche whose threshold is met but not yet booked
    fire = None
    for name, threshold, fraction in BOOKING_LADDER:
        if expansion >= threshold and name not in tranches_booked:
            fire = (name, threshold, fraction)
            # do not break - we want the highest reached unbooked tranche
            # actually: book one tranche per cycle, the LOWEST unbooked
            # that is reached, so booking is orderly. Break here.
            break

    # ---- a tranche fires ----
    if fire:
        name, threshold, fraction = fire
        is_final = (name == 'third')
        after_booking = tranches_booked | {name}
        fully_out = after_booking >= {n for n, _, _ in BOOKING_LADDER}

        d = Decision('C', ticker, 'BOOK-THIRD', 'Module 2A - PE-Expansion Booking')
        d.add_fact('Entry PE', f'{entry_pe:.1f}')
        d.add_fact('Current PE', f'{current_pe:.1f}')
        d.add_fact('PE expansion', f'+{expansion:.0f}% (threshold +{threshold:.0f}%)')
        d.add_fact('Tranche', f'{name} third')
        d.add_fact('Position after', 'fully exited' if fully_out
                   else f'{len(after_booking)}/3 booked')
        d.set_margin('PE expansion past this tranche threshold by',
                     round(expansion - threshold, 1))
        if is_final:
            d.set_counterfactual('the +80% tranche is the final third - '
                                  'this booking fully exits the position')
        else:
            nxt = next((t for n, t, _ in BOOKING_LADDER
                        if n not in after_booking), None)
            d.set_counterfactual(
                f'next tranche books when PE expansion reaches +{nxt:.0f}%' if nxt
                else 'no further tranches')
        return d

    # ---- no tranche fires ----
    d = Decision('C', ticker, 'HOLD', 'Module 2A - PE Booking (no tranche)')
    d.add_fact('Entry PE', f'{entry_pe:.1f}')
    d.add_fact('Current PE', f'{current_pe:.1f}')
    d.add_fact('PE expansion', f'+{expansion:.0f}%')
    d.add_fact('Tranches booked', f'{len(tranches_booked)}/3')

    # distance to the next unbooked threshold
    nxt = next(((n, t) for n, t, _ in BOOKING_LADDER
                if n not in tranches_booked), None)
    if nxt:
        d.set_margin(f'PE expansion to the {nxt[0]} tranche (+{nxt[1]:.0f}%)',
                     round(nxt[1] - expansion, 1))
        d.set_counterfactual(
            f'-> BOOK-THIRD when PE expansion reaches +{nxt[1]:.0f}% '
            f'(the {nxt[0]} tranche)')
    else:
        d.set_margin('all tranches booked', 0)
        d.set_counterfactual('all three tranches are booked - '
                              'the position is already fully exited')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('ENGINE C PE-EXPANSION BOOKING ENGINE (Module 2A) - self-test')
    print('=' * 64)

    entry_pe = 12.0   # bought cheap at PE 12

    # Test 1: PE 14 - only +17% expansion, no tranche fires
    print('\nTest 1 - PE 12 -> 14 (+17%, below first threshold):')
    d = check_booking('PTC', entry_pe, 14.0, tranches_booked=set())
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 2: PE 15.6 - exactly +30%, first tranche fires
    print('\nTest 2 - PE 12 -> 15.6 (+30%, first tranche):')
    d = check_booking('PTC', entry_pe, 15.6, tranches_booked=set())
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: PE 18 - +50%, first already booked, second fires
    print('\nTest 3 - PE 12 -> 18 (+50%, first booked, second fires):')
    d = check_booking('PTC', entry_pe, 18.0, tranches_booked={'first'})
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 4: PE 21.6 - +80%, first+second booked, final third fires
    print('\nTest 4 - PE 12 -> 21.6 (+80%, final third, full exit):')
    d = check_booking('PTC', entry_pe, 21.6, tranches_booked={'first', 'second'})
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 5: PE 18 but first NOT yet booked - books first (orderly)
    print('\nTest 5 - PE jumped to 18 but first tranche not booked:')
    d = check_booking('JSWSTEEL', entry_pe, 18.0, tranches_booked=set())
    print(f'  verdict: {d.verdict}  -> books the FIRST tranche (orderly)')
    print(f'  {[f.render() if hasattr(f,"render") else f for f in []]}', end='')
    for k, v in d.facts:
        if k == 'Tranche':
            print(f'  tranche: {v}')

    # Test 6: all three booked - nothing left
    print('\nTest 6 - all three tranches already booked:')
    d = check_booking('PTC', entry_pe, 25.0,
                      tranches_booked={'first', 'second', 'third'})
    print(f'  verdict: {d.verdict}')

    print('\n' + '=' * 64)
    print('Self-test complete. PE-expansion booking fires one tranche')
    print('at a time, in order, at +30/+50/+80% expansion from entry PE;')
    print('the +80% tranche fully exits the position.')
    print('=' * 64)
