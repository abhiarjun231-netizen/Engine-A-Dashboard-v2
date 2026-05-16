"""
portfolio_capital.py
Parthsarthi Capital - Phase 5, Item 5.1
PORTFOLIO MASTER - CAPITAL SPLIT ALLOCATOR.

Engine A (the Director) decides how much of the total portfolio is
in equity at all. The Portfolio Master then divides that equity
budget across the three engines on a locked split:

  Engine B - Momentum     30% of the equity budget
  Engine C - Value        30% of the equity budget
  Engine D - Compounders  40% of the equity budget

This module turns an Engine A regime score into concrete rupee
budgets per engine, and tracks how much each engine has deployed
versus how much it still has free.

It is the first piece of the Portfolio Master - the layer that
makes three engines behave as one coherent portfolio.
"""

from reasoning_engine import Decision


# ---- locked equity split (Portfolio Master framework) ----
ENGINE_SPLIT = {'B': 0.30, 'C': 0.30, 'D': 0.40}

# ---- Engine A regime -> equity exposure (from the Engine A framework) ----
# (score_floor, regime_name, equity_fraction)
REGIME_BANDS = [
    (75, 'Full Deploy', 0.85),
    (60, 'Aggressive',  0.70),
    (45, 'Active',      0.55),
    (35, 'Cautious',    0.40),
    (25, 'Freeze',      0.25),
    (0,  'Exit All',    0.10),
]


def regime_for_score(engine_a_score):
    """Map an Engine A score to (regime_name, equity_fraction)."""
    for floor, name, fraction in REGIME_BANDS:
        if engine_a_score >= floor:
            return name, fraction
    return 'Exit All', 0.10


def allocate(total_portfolio, engine_a_score):
    """
    Given the total portfolio value and the Engine A score, compute
    the equity budget and the per-engine split.

    Returns a dict:
      {regime, equity_fraction, equity_budget, non_equity,
       engine_budgets: {B, C, D}}
    """
    regime, fraction = regime_for_score(engine_a_score)
    equity_budget = total_portfolio * fraction
    non_equity = total_portfolio - equity_budget

    engine_budgets = {eng: equity_budget * share
                      for eng, share in ENGINE_SPLIT.items()}

    return {
        'regime': regime,
        'equity_fraction': fraction,
        'equity_budget': equity_budget,
        'non_equity': non_equity,
        'engine_budgets': engine_budgets,
    }


def allocation_decision(total_portfolio, engine_a_score,
                        deployed=None):
    """
    Produce a Decision describing the capital allocation, optionally
    showing how much each engine has deployed vs free.

    deployed - optional {engine: amount_deployed}
    """
    deployed = deployed or {}
    alloc = allocate(total_portfolio, engine_a_score)

    d = Decision('PM', 'CAPITAL', 'ALLOCATE',
                 'Portfolio Master - Capital Split')
    d.add_fact('Total portfolio', f'{total_portfolio:,.0f}')
    d.add_fact('Engine A score', str(engine_a_score))
    d.add_fact('Regime', f"{alloc['regime']} "
               f"({alloc['equity_fraction']*100:.0f}% equity)")
    d.add_fact('Equity budget', f"{alloc['equity_budget']:,.0f}")
    d.add_fact('Non-equity (Engine E)', f"{alloc['non_equity']:,.0f}")
    for eng in ['B', 'C', 'D']:
        budget = alloc['engine_budgets'][eng]
        dep = deployed.get(eng, 0)
        free = budget - dep
        d.add_fact(f'Engine {eng}',
                   f'budget {budget:,.0f} | deployed {dep:,.0f} | '
                   f'free {free:,.0f}')

    d.set_margin('equity exposure percent',
                 round(alloc['equity_fraction'] * 100, 1))
    d.set_counterfactual(
        'the equity budget rises or falls with the Engine A regime '
        'score; the 30/30/40 split across B/C/D is fixed')
    return d


# ---- self-test ----
if __name__ == '__main__':
    print('=' * 64)
    print('PORTFOLIO MASTER - CAPITAL SPLIT ALLOCATOR (5.1) - self-test')
    print('=' * 64)

    portfolio = 1000000   # Rs 10 lakh

    # Test 1: allocation across different regimes
    print('\nTest 1 - capital split across Engine A regimes (Rs 10L):')
    for score in [80, 65, 50, 40, 28, 15]:
        a = allocate(portfolio, score)
        eb = a['engine_budgets']
        print(f'  A={score:3} {a["regime"]:12} equity {a["equity_fraction"]*100:.0f}% '
              f'-> B {eb["B"]:>9,.0f}  C {eb["C"]:>9,.0f}  D {eb["D"]:>9,.0f}')

    # Test 2: full allocation decision with deployed capital
    print('\nTest 2 - allocation decision, Active regime, some deployed:')
    d = allocation_decision(portfolio, engine_a_score=55,
                            deployed={'B': 100000, 'C': 80000, 'D': 150000})
    print(f'  verdict: {d.verdict}')
    print(' ', d.reason_string())

    # Test 3: verify the split sums correctly
    print('\nTest 3 - split integrity check:')
    a = allocate(portfolio, 55)
    total_engine = sum(a['engine_budgets'].values())
    print(f'  equity budget:        {a["equity_budget"]:,.0f}')
    print(f'  sum of engine budgets: {total_engine:,.0f}')
    print(f'  match: {abs(total_engine - a["equity_budget"]) < 0.01}')
    print(f'  equity + non-equity = {a["equity_budget"]+a["non_equity"]:,.0f} '
          f'(should equal portfolio {portfolio:,.0f})')

    print('\n' + '=' * 64)
    print('Self-test complete. Engine A sets the equity budget; the')
    print('Portfolio Master splits it 30/30/40 across B/C/D. The split')
    print('is fixed; only the equity budget moves with the regime.')
    print('=' * 64)
