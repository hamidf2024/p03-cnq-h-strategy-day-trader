"""Builds the website's Project 3 goal scoreboard (ai-trading/project-03.html in
the hamidf2024.github.io repository) from the scorecard results.

    python3 src/site_goals_page/build_goals_page.py results/experiments OUT.html CURRENT_PAGE.html

  results/experiments  folder with goals_scorecard.json and goals_monthly_2024_2026.csv
  OUT.html             the page to write
  CURRENT_PAGE.html    the page as it is now on the site (its "Browse categories"
                       block is copied across unchanged)

page.css and page.js sit beside this script and are inlined. The page is static
HTML; the script only adds the hover line under the month grid and the table
filter. Model descriptions (DESC) and the buy-and-hold reference (BH) are set
by hand below and need updating when methods or the test period change."""
import csv, json, os, sys
from html import escape as E

SRC = sys.argv[1]; OUT = sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(f'{SRC}/goals_scorecard.json'))
M = {c['id']: c for c in d['methods']}
monthly = {}
for r in csv.DictReader(open(f'{SRC}/goals_monthly_2024_2026.csv')):
    monthly.setdefault(r['method'], []).append(r)

DESC = {
 'V1': 'Baseline rule: buy a bounce off a support zone on the 5-minute chart.',
 'V2': 'Exit at the next zone when the candle is weak.',
 'V3': 'Adds the opening-range zone.',
 'V4': 'At most two entries per zone per day.',
 'V5': 'Exits when there is no more strong signal.',
 'V6': 'Opening-range zone used for exits only.',
 'V7_wf': 'Zone-bounce rule with a trailing stop and exit at the next zone.',
 'V7.1_wf': 'V7 plus a filter that rejects weak bounces at the open.',
 'RuleOrModel': 'Trades when either the zone rule or a machine-learning model says yes. About 5 trades a day.',
 'V7.1_pct': 'V7.1 with its stop and target set as a percent of the share price instead of fixed cents.',
 'Donchian_long': 'Buys a breakout above the recent high and holds for weeks.',
 'Donchian_ls': 'Breakout rule that also sells short on breakdowns.',
 'A_spring_release': 'Buys when price is stretched below its trend and starts to turn. Holds 5 days.',
 'B_field_fusion_gbm': 'Machine-learning model on 33 signals. Buys its strongest forecasts and holds 5 days.',
 'C_transformer_probe': 'A small transformer reads the 5-minute bars and picks days to buy. Holds 5 days.',
 'D_fusion_gate': 'The spring-release signal, taken only when the Field-Fusion model agrees.',
 'R1_peer_fusion_gbm': 'One machine-learning model trained on six oil stocks at once, with oil and peer signals. Buys CNQ on its strongest forecasts and holds 5 days.',
 'R2_peer_oil_spring': 'Buys CNQ when it is stretched below its peers and oil and starts to turn back, and sells short in the opposite case. Holds 5 days.',
 'R3_fusion_ensemble': 'Three models voting together: gradient boosting, a linear model and a cross-asset transformer. Holds 5 days.',
 'R4_goal_shaped_exits': 'The Peer-Fusion signal with a 5% profit target and a 5% stop, for up to 10 days.',
 'R5_first_passage': 'Peer-Fusion entries with a lower bar and a 2% profit target, for up to 20 days. Built to trade in most months.',
 'R7_one_a_month_stop5': 'One trade a month, on the first day the Peer-Fusion model is at least neutral. Sells at +2%, at a 5% stop, or after 20 trading days.',
 'R8_peer_fusion_stop5': 'Model E with a 5% stop added: buys CNQ on the Peer-Fusion model\u2019s strongest forecasts and holds 5 days.',
 'R10_monthly_campaign_four_goals': 'Two trades a month, one in each half, on the first day the Peer-Fusion model is at least neutral. Sells at +6%, at a 15% stop, or after 60 trading days. Built for all four goals.',
 'R13_two_buys_stop15': 'Model M’s signal and exit with two buys at different times: on the day after the signal it buys at 10:00 and again at 1:00 pm. Sells each at +4%, at a 15% stop, or after 60 trading days.',
 'R14_dip_campaign': 'Waits each month for CNQ to fall 5% below its 10-day high (or buys on the 15th trading day if it has not), then buys twice the next day, at 10:00 and 1:00 pm. Sells each at +3%, at a 15% stop, or after 60 trading days. No machine learning.',
 'R9_one_a_month_stop15': 'One trade a month, on the first day the Peer-Fusion model is at least neutral. Sells at +4%, at a 15% stop, or after 60 trading days.',
 'R6_one_a_month': 'One trade a month, on the first day the Peer-Fusion model is at least neutral. Sells at +4%, or after 60 trading days if the target is not reached. No stop.',
}
NEW_STAGE = 13
KIND = {c['id']: ('Same-day' if c['holding'] == 'same day' else 'Multi-day') for c in d['methods']}
SHORT = {'Donchian_long': 'Donchian long-only', 'Donchian_ls': 'Donchian long+short', 'R8_peer_fusion_stop5': 'L. Peer-Fusion, 5% stop',
         'R4_goal_shaped_exits': 'H. Target and stop', 'R6_one_a_month': 'J. One-a-month, no stop'}
def nm(c): return SHORT.get(c['id'], c['name'])


ORDER = sorted(d['methods'], key=lambda c: (c.get('rank', 99), -c['progress']['overall']))
TOP5 = [M[i] for i in d['top5']]
STRICT5 = [M[i]['name'] for i in d['top5_if_scratch_is_not_a_win']]

G_MAX, WR_MAX, S_MAX = 3.5, 100.0, 12.0
MIN = '−'


def pct(v, nd=2, sign=False):
    s = f'{abs(v):.{nd}f}%'
    return (MIN if v < 0 else ('+' if sign else '')) + s


def usd(v, nd=0, sign=True):
    s = f'${abs(v):,.{nd}f}'
    return (MIN if v < -0.5 * 10 ** -nd else ('+' if sign and v > 0 else '')) + s


def NEWTAG(c):
    return ' <span class="tag newtag">New</span>' if c['stage'] == NEW_STAGE else ''


def meter(kind, value, lv, compact=False):
    """One goal meter: fill to the value, three ticks at the three levels."""
    mx, ticks = {'G': (G_MAX, (1, 2, 3)), 'WR': (WR_MAX, (50, 65, 75)), 'S': (S_MAX, (8, 10, 12)), 'GM': (S_MAX, (8, 10, 12))}[kind]
    w = max(0.0, min(100.0, 100 * value / mx))
    t = ''.join(f'<b style="left:{100 * x / mx:.2f}%"></b>' for x in ticks)
    lab = '' if compact else '<div class="m-ticks">' + ''.join(
        f'<span{" class=\"end\"" if x >= mx else ""} style="left:{100 * x / mx:.2f}%">{kind}{i + 1}</span>' for i, x in enumerate(ticks)) + '</div>'
    return f'<div class="m-track{" hit" if lv else ""}" role="img" aria-label="{kind} meter"><i style="width:{w:.2f}%"></i>{t}</div>{lab}'


def chip(kind, lv):
    return f'<span class="lv on">{kind}{lv}</span>' if lv else f'<span class="lv">below {kind}1</span>'


def sfmt(v):
    return f'{v:.0f}' if abs(v - round(v)) < 0.05 else f'{v:.1f}'


def gm_worst(c):
    return c['months_total_5pct_worst_year_per_12']


def neg_by_year(c):
    return [v['months_negative'] for v in c['by_year'].values()]


def neg_tag(c, long=False):
    """Goal 4 rule (owner, 2026-11-24): a year counts only with at most one losing month, no worse than -2%."""
    ys = list(c['by_year'].values()); n = [v['months_negative'] for v in ys]; ok = [v['gm_year_counts'] for v in ys]
    if sum(n) == 0:
        return '<span class="negtag ok">no losing month</span>'
    if all(ok):
        return '<span class="negtag ok">losses within the rule</span>'
    return f'<span class="negtag">losing months: {" / ".join(map(str, n))}</span>' if long else f'<span class="negtag">{max(n)} losing</span>'


def s_worst(c):
    return c['months_above_1pct_worst_year_per_12']


def s_text(c):
    return ' · '.join(f"{y}: {v['months_above_1pct']} of {v['months']}" for y, v in c['by_year'].items())


def cost_tag(c):
    return ('<span class="tag good">Still profitable after costs</span>' if c['profitable_after_1c']
            else '<span class="tag bad">Loses money after costs</span>')


# ------------------------------------------------------------------ goals
OKM = [c for c in d['methods'] if c['keeps_loss_limit']]      # levels count only inside the risk rule


def best(kind):
    if kind == 'G':
        c = max(OKM, key=lambda c: c['gross_pct_per_trade']); return c, pct(c['gross_pct_per_trade']), c['G_level']
    if kind == 'WR':
        c = max([c for c in d['methods'] if c['enough_trades_to_rank']], key=lambda c: c['win_rate']); return c, f"{c['win_rate']:.1f}%", c['WR_level']
    if kind == 'GM':
        c = max(OKM, key=lambda c: (c['GM_level'], c['progress']['GM'], gm_worst(c))); return c, f"{sfmt(c['gm_months_counted_worst_year_per_12'])} of 12", c['GM_level']
    c = max(OKM, key=lambda c: s_worst(c)); return c, f"{sfmt(s_worst(c))} of 12", c['S_level']


def goal_card(kind, title, question, steps, note):
    c, val, lv = best(kind)
    li = ''.join(f'<li class="{"on" if i < lv else ""}"><b>{kind}{i + 1}</b><span>{a}</span><small>{b}</small></li>'
                 for i, (a, b) in enumerate(steps))
    state = (f'<span class="tag good">Level {lv} of 3 reached</span>' if lv else '<span class="tag warn">No level reached yet</span>')
    return f'''<article class="card goal">
      <header><span class="code">{kind}</span><div><h3>{title}</h3><p>{question}</p></div></header>
      <ol class="ladder" aria-label="{title} levels">{li}</ol>
      <div class="best"><div><span class="k">Best so far</span><span class="v">{val}</span></div><div class="who">{E(c['name'])}<br>{c['trades']:,} trades</div></div>
      <div class="state">{state}</div>
      <p class="fine">{note}</p>
    </article>'''


goals_html = (
    goal_card('G', 'Profit per trade', 'How much does an average trade make, before costs?',
              [('1%', '$10 a trade'), ('2%', '$20 a trade'), ('over 3%', 'over $30')],
              'Average gross profit per trade as a percent of the money put into the trade.')
    + goal_card('WR', 'Win rate', 'How many trades win?',
                [('50%', '1 in 2'), ('65%', 'about 2 in 3'), ('over 75%', '3 in 4')],
                'Winning trades as a share of winning and losing trades. Break-even trades are left out.')
    + goal_card('S', 'Steady months', 'In how many months of the year does the average trade make more than 1%?',
                [('8 of 12', 'months'), ('10 of 12', 'months'), ('12 of 12', 'every month')],
                'Months in which the average gross profit per trade is above 1%. A month with no trades does not count. A level must hold in every year tested.')
    + goal_card('GM', 'Monthly profit', 'In how many months of the year do the month\u2019s trades add up to 5% or more, with almost no losing month?',
                [('8 of 12', 'months'), ('10 of 12', 'months'), ('12 of 12', 'every month')],
                'Months whose trades together make 5% or more, which is $50 or more at $1,000 per trade. A year counts only if at most one of its months ends below zero, and that month loses no more than 2% (rule set November 24, 2026). Trades opened at exactly the same time count once. A level must hold in every year tested.'))

# ------------------------------------------------------------------ top 5
def top_row(c):
    g, wr = c['gross_pct_per_trade'], c['win_rate']
    return f'''<li class="card toprow">
      <div class="rank" aria-label="Rank {c['rank']}">{c['rank']}</div>
      <div class="tw"><h3>{E(c['name'])}{NEWTAG(c)}</h3><div class="meta"><span class="kind">{KIND[c['id']]}</span><span>{c['trades']:,} trades</span></div><p>{E(DESC[c['id']])}</p></div>
      <div class="meters">
        <div class="m"><div class="m-top"><span class="m-name">Profit per trade</span><span class="m-val">{pct(g)}</span>{chip('G', c['G_level'])}</div>{meter('G', g, c['G_level'])}</div>
        <div class="m"><div class="m-top"><span class="m-name">Win rate</span><span class="m-val">{wr:.1f}%</span>{chip('WR', c['WR_level'])}</div>{meter('WR', wr, c['WR_level'])}</div>
        <div class="m"><div class="m-top"><span class="m-name">Steady months, worst year</span><span class="m-val">{sfmt(s_worst(c))} of 12</span>{chip('S', c['S_level'])}</div>{meter('S', s_worst(c), c['S_level'])}</div>
        <div class="m"><div class="m-top"><span class="m-name">Months of 5% or more, worst year</span><span class="m-val">{sfmt(gm_worst(c))} of 12</span>{chip('GM', c['GM_level'])}</div>{meter('GM', gm_worst(c), c['GM_level'])}<div class="m-note">{neg_tag(c, True)}</div></div>
      </div>
      <div class="money"><span class="k">On $1,000 per trade</span><span class="v">{usd(c['dollars_per_trade'], 2)}</span><span class="s">per trade, before costs</span><span class="s after">{usd(c['dollars_per_trade_after_1c'], 2)} after costs</span>{cost_tag(c)}</div>
    </li>'''


top_html = ''.join(top_row(c) for c in TOP5)

# ------------------------------------------------------------------ all models table
def by_year_list(c):
    """Average gross % per trade in each test year, under the G bar."""
    items = ''
    for y, v in c['by_year'].items():
        g = v['gross_pct_per_trade']
        end = 1000 + v['dollars_year']                      # $1,000 per trade, profits not reinvested
        items += (f'<span>{y}</span><b class="none">no trades</b><em>$1,000</em>' if g is None
                  else f'<span>{y}</span><b class="{"neg" if g < 0 else ""}">{pct(g, 2, True)}</b><em class="{"neg" if end < 1000 else ""}">${end:,.0f}</em>')
    return f'<div class="yr" aria-label="Average gross percent per trade by year">{items}</div>'


def by_year_simple(c, kind):
    """Each test year's own figure under the WR, S and GM bars."""
    items = ''
    for y, v in c['by_year'].items():
        if kind == 'WR':
            txt = 'no trades' if v['win_rate'] is None else f"{v['win_rate']:.1f}%"
        elif kind == 'S':
            txt = f"{v['months_above_1pct']} of {v['months']}"
        else:
            txt = f"{v['months_total_5pct']} of {v['months']}" + ('<i class="clean">clean</i>' if not v['months_negative'] else (f"<i class=\"clean\">1 small loss</i>" if v['gm_year_counts'] else f"<i class=\"lose\">{v['months_negative']} losing</i>"))
        items += f'<span>{y}</span><b class="{"none" if txt == "no trades" else ""}">{txt}</b>'
        if kind == 'GM':                                    # the year's total gross %: all its trades added up
            tot = v['gross_pct_year']
            items += f'<em class="{"neg" if tot < 0 else ""}">{pct(tot, 1, True)}</em>'
    return f'<div class="yr{"" if kind == "GM" else " two"}">{items}</div>'


def table_row(c):
    g, wr = c['gross_pct_per_trade'], c['win_rate']
    rk = c.get('rank', '–')
    lv = ''.join(f'<span class="lv {"on" if l else ""}">{k}{l}</span>' for k, l in (('G', c['G_level']), ('WR', c['WR_level']), ('S', c['S_level']), ('GM', c['GM_level'])))
    net = c['dollars_per_trade_after_1c']
    return f'''<tr data-kind="{KIND[c['id']]}">
      <td class="num rk">{rk}</td>
      <td class="nm"><strong>{E(c['name'])}{NEWTAG(c)}</strong><span>{KIND[c['id']]} · {c['trades']:,} trades</span></td>
      <td class="mc"><div class="mv">{pct(g)}</div>{meter('G', g, c['G_level'], True)}{by_year_list(c)}</td>
      <td class="mc"><div class="mv">{wr:.1f}%<small>{c['wins_share_of_all_trades']:.0f}% of all trades</small></div>{meter('WR', wr, c['WR_level'], True)}{by_year_simple(c, 'WR')}</td>
      <td class="mc"><div class="mv">{sfmt(s_worst(c))} of 12</div>{meter('S', s_worst(c), c['S_level'], True)}{by_year_simple(c, 'S')}</td>
      <td class="mc"><div class="mv">{sfmt(gm_worst(c))} of 12 {neg_tag(c)}</div>{meter('GM', gm_worst(c), c['GM_level'], True)}{by_year_simple(c, 'GM')}</td>
      <td class="lvs">{lv}</td>
      <td class="risk"><div class="rl"><span>Worst trade</span><b>{pct(c['worst_trade_pct'], 1)}</b></div><div class="rl"><span></span><span class="lv {'on' if c['keeps_strict_loss_limit'] else ('mid' if c['keeps_loss_limit'] else 'over')}">{'within 5%' if c['keeps_strict_loss_limit'] else ('within 15%' if c['keeps_loss_limit'] else 'over 15%')}</span></div><div class="rl sep"><span>After costs, per $1,000 trade</span><b class="{"pos" if net > 0 else "neg"}">{usd(net, 2)}</b></div></td>
    </tr>'''


table_html = ''.join(table_row(c) for c in ORDER)

# ------------------------------------------------------------------ month grid
months = [r['month'] for r in monthly[ORDER[0]['id']]]
def GAP(m): return '<span></span>' if m[5:] == '01' and m[:4] != '2024' else ''


MN = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
LONG = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
head = '<div class="hm-row hm-head"><div class="hm-name"></div>' + ''.join(
    GAP(m) + f'<span class="hm-m">{MN[int(m[5:]) - 1]}</span>' for m in months) + '<div class="hm-tot">Above 1%</div></div>'
years = '<div class="hm-row hm-years"><div class="hm-name"></div>' + ''.join(
    ('<span></span>' if y != 2024 else '') + f'<span class="hm-y" style="grid-column:span {n}">{y}</span>' for y, n in ((2024, 12), (2025, 12), (2026, 11))) + '<div class="hm-tot"></div></div>'


def cell(r):
    n = int(r['trades']); m = r['month']
    v = float(r['avg_gross_pct_per_trade']) if n else 0.0
    cls = 'nt' if n == 0 else ('hit' if r['above_1pct_per_trade'] == 'True' else ('pos' if v > 0 else 'neg'))
    label = f"{LONG[int(m[5:]) - 1]} {m[:4]}"
    tip = f"{label}: no trades" if n == 0 else (f"{label}: average {pct(v, 2, True)} per trade over {n} trade{'s' if n != 1 else ''} "
                                                f"({usd(float(r['sum_dollars_per_1000']), 0)} in total at $1,000 per trade)")
    return GAP(m) + f'<span class="hm-c {cls}" data-tip="{tip}">{MIN if cls == "neg" else ""}</span>'


hm_rows = ''.join(
    f'<div class="hm-row"><div class="hm-name">{E(nm(c))}</div>' + ''.join(cell(r) for r in monthly[c['id']])
    + f'<div class="hm-tot"><b>{c["months_above_1pct_total"]}</b> of {c["months_total"]}</div></div>' for c in ORDER)

# ------------------------------------------------------------------ month grid for GM (the month's total)
def cell_gm(r):
    n = int(r['trades']); m = r['month']; v = float(r['sum_gross_pct']) if n else 0.0
    cls = 'nt' if n == 0 else ('hit' if r['total_at_least_5pct'] == 'True' else ('pos' if v > 0 else 'neg'))
    label = f"{LONG[int(m[5:]) - 1]} {m[:4]}"
    tip = f"{label}: no trades" if n == 0 else (f"{label}: total {pct(v, 2, True)} from {n} trade{'s' if n != 1 else ''} "
                                                f"({usd(float(r['sum_dollars_per_1000']), 0)} at $1,000 per trade)")
    return GAP(m) + f'<span class="hm-c {cls}" data-tip="{tip}">{MIN if cls == "neg" else ""}</span>'


head_gm = head.replace('Above 1%', '5% or more')
hm_rows_gm = ''.join(
    f'<div class="hm-row"><div class="hm-name">{E(nm(c))}</div>' + ''.join(cell_gm(r) for r in monthly[c['id']])
    + f'<div class="hm-tot"><b>{c["months_total_5pct_all"]}</b> of {c["months_total"]}<small class="{"lose" if c["months_negative_all"] else "clean"}">{c["months_negative_all"]} losing</small></div></div>' for c in ORDER)

# ------------------------------------------------------------------ $1,000 chart + table
BH = 390.0
lo, hi = -450.0, 750.0
def xpos(v): return 100 * (v - lo) / (hi - lo)
zero = xpos(0)


def bar(v, cls):
    a, b = sorted((xpos(0), xpos(max(lo, min(hi, v)))))
    return f'<i class="{cls} {"n" if v < 0 else "p"}" style="left:{a:.2f}%;width:{max(b - a, 0.3):.2f}%"></i>'


def money_row(c):
    g, n = c['dollars_total'], c['dollars_total_after_1c']
    return f'''<div class="mr"><div class="mr-name">{E(nm(c))}</div>
      <div class="mr-plot"><span class="z" style="left:{zero:.2f}%"></span>{bar(g, 'gross')}{bar(n, 'net')}</div>
      <div class="mr-val"><span>{usd(g)}</span><strong class="{"pos" if n > 0 else "neg"}">{usd(n)}</strong></div></div>'''


money_html = ''.join(money_row(c) for c in ORDER)
axis = ''.join(f'<span style="left:{xpos(v):.2f}%">{usd(v, 0, False) if v else "$0"}</span>' for v in (-400, -200, 0, 200, 400, 600))


def money_table_row(c):
    y = c['by_year']
    return (f'<tr><td><strong>{E(c["name"])}</strong></td><td class="num">{c["trades"]:,}</td><td class="num">{usd(c["dollars_per_trade"], 2)}</td>'
            + ''.join(f'<td class="num">{usd(y[k]["dollars_year"])}</td>' for k in y)
            + f'<td class="num">{usd(c["dollars_total"])}</td><td class="num">{usd(-c["cost_1c_dollars_total"])}</td>'
              f'<td class="num {"pos" if c["dollars_total_after_1c"] > 0 else "neg"}"><strong>{usd(c["dollars_total_after_1c"])}</strong></td></tr>')


money_table = ''.join(money_table_row(c) for c in ORDER)

n_models = len(d['methods'])
gbest = max(d['methods'], key=lambda c: c['gross_pct_per_trade'])
# ---- stop-size study on the training years (round 12 search); the section is left out if the file is absent
STOP_SECTION = ''
SHOW_STOP_SECTION = False        # owner, 2026-11-24: taken off the scoreboard; the study stays in docs/12 (Section 13) and the research record
_sf = f'{SRC}/stage13_round12_stop_range_search.json'
if SHOW_STOP_SECTION and os.path.exists(_sf):
    _r = json.load(open(_sf)); _S = _r['settings']
    def _row(st, T=5.5, H=60):
        return _S[json.dumps(dict(second='none', target=T, stop=float(st), hold=H), sort_keys=True)]
    _stops = [1, 2, 3, 4, 5, 6, 8, 10, 12, 15]
    _rows = {st: _row(st) for st in _stops}
    _best = max(_stops, key=lambda st: (min(min(a, b) - n for a, b, n in zip(_rows[st]['S'], _rows[st]['GM'], _rows[st]['need'])), _rows[st]['G']))
    _need = _rows[15]['need']
    def _tr(st):
        v = _rows[st]; ok = lambda xs: all(x >= n for x, n in zip(xs, v['need']))
        tag = ' <span class="lv on">Best</span>' if st == _best else ''
        cls = ' class="stop-best"' if st == _best else ''
        return (f'<tr{cls}><td><strong>{st}%</strong>{tag}</td>'
                f'<td class="num {"pos" if v["G"] >= 1 else ""}">{pct(v["G"], 2, True)}</td>'
                f'<td class="num {"pos" if v["WR"] >= 50 else ""}">{v["WR"]:.0f}%</td>'
                f'<td class="num">{v["stops"]} of {v["n"]}</td>'
                f'<td class="num {"pos" if ok(v["S"]) else ""}">{" / ".join(str(x) for x in v["S"])}</td>'
                f'<td class="num {"pos" if ok(v["GM"]) else ""}">{" / ".join(str(x) for x in v["GM"])}</td></tr>')
    _bs = _r['by_stop']
    _wr_none = [st for st in _stops if _bs[str(float(st))]['share_with_WR50'] == 0]
    STOP_SECTION = f"""
  <section id="stops">
    <h2>Which stop size works best?</h2>
    <p class="sub">The owner asked for every stop from 1% to 15% to be tried, to find the best one. This was done on the training years only (2021 to 2023); the test years were removed from the data first.</p>
    <div class="card" style="padding:6px 0 0">
      <p class="swipe" style="padding:10px 16px 0">Swipe sideways to see every column.</p><div class="table-scroll"><table>
        <thead><tr><th>Stop size</th><th class="num">Profit per trade</th><th class="num">Win rate</th><th class="num">Trades stopped out</th><th class="num">S months 2021 / 2022 / 2023</th><th class="num">GM months 2021 / 2022 / 2023</th></tr></thead>
        <tbody>{''.join(_tr(st) for st in _stops)}</tbody>
      </table></div>
    </div>
    <p class="fine" style="margin-top:10px">Same rule on every line, only the stop changes: one trade a month, sell at +5.5%, or after 60 trading days. Level 1 needs {_need[0]} / {_need[1]} / {_need[2]} months (2023 has 10 usable months). Green marks a figure that reaches the month count for level 1. This study was made before the losing-month rule was added to goal 4 on November 24, 2026.</p>
    <div class="note2">
      <h3>What the stop study shows</h3>
      <ul>
        <li><strong>The best stop is {_best}%, the widest one allowed.</strong> Profit per trade is highest there, and the win rate and both month goals fall step by step as the stop gets tighter. CNQ often dips a few percent before it rises, so a tight stop sells many trades that would have ended as winners.</li>
        <li><strong>Stops of 5% or less cut the win rate sharply.</strong> With a 1% stop, {_rows[1]['stops']} of {_rows[1]['n']} trades were stopped out and the win rate was {_rows[1]['WR']:.0f}%. With 15%, {_rows[15]['stops']} of {_rows[15]['n']} were stopped and the win rate was {_rows[15]['WR']:.0f}%.</li>
        <li><strong>No stop size passes the test for a new model.</strong> {_r['n_eligible']:,} settings were tried: ten stop sizes, six profit targets, three time limits and nine entry patterns (one trade a month, or a second trade added later, on a dip, on a rise, or after a stop). None reached level 1 on all four goals with one month to spare in every training year, so nothing new was run on the test years.</li>
        <li><strong>These are rising years.</strong> CNQ rose in 2021, 2022 and 2023. In a falling year a wide stop loses more on each losing trade, which is what the 5% and 15% loss limits are for.</li>
      </ul>
    </div>
  </section>
"""

LOOKS = int(sys.argv[4]) if len(sys.argv) > 4 else 8
# ---- Stage 14: new information (training years only); left out if the files are absent
S14_SECTION = ''
_i14 = f'{SRC}/stage14_information_test.json'; _m14 = f'{SRC}/stage14_macro_fusion_selection.json'
if os.path.exists(_i14) and os.path.exists(_m14):
    _i = json.load(open(_i14))['summary']; _m = json.load(open(_m14))
    def _ir(lbl, key):
        o, n = _i[key]['OLD'], _i[key]['NEW']; dlt = n['all'] - o['all']; up = dlt >= 0.03
        return (f'<tr><td>{lbl}</td><td class="num">{o["all"]:.3f}</td><td class="num {"pos" if up else ""}">{n["all"]:.3f}</td>'
                f'<td class="num">{pct(o["top_minus_bottom_pct"], 2, True)}</td><td class="num {"pos" if up else ""}">{pct(n["top_minus_bottom_pct"], 2, True)}</td><td>{"Better" if up else ("Worse" if dlt <= -0.02 else "Little change")}</td></tr>')
    _BUY = {'next1000+next1300': '10:00 and 1:00 pm next day', 'close+next1000': 'Close and 10:00 next day'}
    _PART = {'A': 'spare month', 'B': 'beats buying every day', 'C': 'peer stocks', 'D': 'entry shifted', 'E': 'beats old forecast'}
    def _mr(k, v):
        c = json.loads(k); miss = [_PART[x] for x, ok in v['gate'].items() if not ok]
        return (f'<tr><td>{c["q"]}</td><td class="num">{c["target"]:.0f}%</td><td>{_BUY[c["buys"]]}</td><td class="num pos">{pct(v["G"], 2, True)}</td>'
                f'<td class="num">{pct(v["old_information"]["G"], 2, True)}</td><td class="num">{v["WR"]:.1f}%</td><td class="num">{" / ".join(map(str, v["S"]))}</td>'
                f'<td class="num">{" / ".join(map(str, v["GM"]))}</td><td>{", ".join(miss) if miss else "passes"}</td></tr>')
    _rows = sorted(_m['settings'].items(), key=lambda kv: (-sum(kv[1]['gate'].values()), -kv[1]['G']))[:4]
    _need = _rows[0][1]['need']
    S14_SECTION = f"""
  <section id="stage14">
    <h2>New data: does it help?</h2>
    <p class="sub">Eighteen more symbols were added on November 24, 2026: the slope of the oil futures curve, the Brent&ndash;WTI gap, natural gas, refiners, pipelines, the Canadian dollar, the stock market and its volatility, bonds and gold. Everything below uses the training years only (2021 to 2023); the test years were removed from the data first.</p>
    <div class="statstrip" style="margin-bottom:16px">
      <div class="primary"><div class="k">Month-ahead forecast, CNQ</div><div class="v">{_i['H20 CNQ']['OLD']['all']:.2f} &rarr; {_i['H20 CNQ']['NEW']['all']:.2f}</div><div class="s">match between forecast and result (0 = none, 1 = perfect)</div></div>
      <div><div class="k">Campaign timed by it</div><div class="v">{pct(_rows[0][1]['old_information']['G'], 2, True)} &rarr; {pct(_rows[0][1]['G'], 2, True)}</div><div class="s">profit per trade, old forecast &rarr; new</div></div>
      <div><div class="k">Settings that pass the test</div><div class="v">{len(_m['passers'])} of {_m['n_settings']}</div><div class="s">so nothing was run on 2024&ndash;2026</div></div>
      <div><div class="k">Runs on the test years</div><div class="v">{LOOKS}</div><div class="s">unchanged</div></div>
    </div>
    <div class="card" style="padding:6px 0 0">
      <h3 style="padding:14px 16px 0;margin:0">1. Is the forecast better with the new data?</h3>
      <p class="swipe" style="padding:10px 16px 0">Swipe sideways to see every column.</p><div class="table-scroll"><table>
        <thead><tr><th>Forecast</th><th class="num">Match, old data</th><th class="num">Match, old + new</th><th class="num">Best fifth minus worst fifth, old</th><th class="num">Old + new</th><th>Verdict</th></tr></thead>
        <tbody>{_ir('One week ahead, CNQ', 'H5 CNQ')}{_ir('One week ahead, six stocks', 'H5 all six')}{_ir('One month ahead, CNQ', 'H20 CNQ')}{_ir('One month ahead, six stocks', 'H20 all six')}</tbody>
      </table></div>
    </div>
    <div class="card" style="padding:6px 0 0;margin-top:16px">
      <h3 style="padding:14px 16px 0;margin:0">2. Model R: a monthly campaign timed by the month-ahead forecast</h3>
      <p class="swipe" style="padding:10px 16px 0">Swipe sideways to see every column.</p><div class="table-scroll"><table>
        <thead><tr><th>Entry bar</th><th class="num">Target</th><th>Buys</th><th class="num">Profit per trade</th><th class="num">Same, old forecast</th><th class="num">Win rate</th><th class="num">S months</th><th class="num">GM months</th><th>What it fails</th></tr></thead>
        <tbody>{''.join(_mr(k, v) for k, v in _rows)}</tbody>
      </table></div>
    </div>
    <p class="fine" style="margin-top:10px">Level 1 needs {_need[0]} / {_need[1]} / {_need[2]} months in these training years (2021 starts in March, when the forecast has enough history). To be run on the test years a setting must pass five checks: one spare month in every year, more profit than buying after every day, the same result on the five peer stocks, the same result with the buys moved to other times, and more profit than the same campaign timed by the old forecast. The four closest settings are shown. These checks counted months of 5% or more; the losing-month rule added to goal 4 later on November 24 is stricter and will apply to the next models.</p>
    <div class="note2">
      <h3>What this shows</h3>
      <ul>
        <li><strong>The new data helps where the goals need it.</strong> It makes little or no difference to a one-week forecast and clearly improves the one-month forecast, for CNQ and for the six stocks together.</li>
        <li><strong>The gain carries into trading.</strong> In all {_m['n_settings']} settings the campaign makes more when timed by the new forecast than by the old one.</li>
        <li><strong>It is not yet enough.</strong> No setting passes all five checks; the closest fails one and the next two fail two. Nothing was run on the test years.</li>
        <li><strong>Caution.</strong> Three training years hold about 37 separate one-month periods, and they were rising years. The size of the gain is uncertain.</li>
      </ul>
    </div>
  </section>
"""

# a model can lead the ranking and still lose money: say so when it happens
_losers = [c for c in TOP5 if c['gross_pct_per_trade'] < 0]
RANK_NOTE = ('<li><strong>Rank is not profit.</strong> ' + ' '.join(
    f"{E(c['name'])} is ranked {TOP5.index(c) + 1} because of its win rate and its months on S and GM, but its average trade lost "
    f"{abs(c['gross_pct_per_trade']):.2f}% and it lost {usd(abs(c['dollars_total']), 0, False)} in all at $1,000 a trade." for c in _losers)
    + ' The ranking measures progress toward the four goals, not money made.</li>') if _losers else \
    '<li><strong>Rank is not profit.</strong> The ranking measures progress toward the four goals, not money made; check the profit column as well.</li>'

all3 = [M[i] for i in d.get('level1_on_all_three', [])]
ALL3_NOTES = {
 'R9_one_a_month_stop15': [
  'What it is. Model J with a 15% stop added: one trade a month, sold at +4%, at the stop, or after 60 trading days.',
  'How it gets there. 31 of its 35 trades reached +4%. A month with one +4% trade counts toward S, wins toward WR, and lifts the average toward G.',
  'What it gives up. The 4 trades that missed were stopped at about 15% each (the worst, 15.7%, gapped through the stop). Four such losses cancel about fifteen winners.',
  'It does not reach the monthly-profit goal (GM). With one trade a month sold at +4%, a month\u2019s total reached 5% only once in 35 months.',
  'It does not keep the 5% limit. With a 5% stop the same idea (model K) averaged +0.02% per trade.',
  'More than $1,000 can be at work: a new trade opens each month while old ones may still be open, up to three at once.',
  'The average is not yet proven. Its likely range runs from about \u22120.4% to +3.5% per trade, and on the 2021\u20132023 training years it lost money in one year of three (2022). It was the ninth new model run on 2024\u20132026 in this stage, so it needs confirming on trades after November 2026.',
 ],
 'R6_one_a_month': [
  'How it gets there. It sells every trade at +4%, and 31 of its 35 trades reached that. A month with one +4% trade counts toward S, wins toward WR, and lifts the average toward G.',
  'What it gives up. The 4 trades that missed the target were held with no stop and lost 12%, 17%, 0.4% and 17%. One of them was still open, 17% down, when the data ended on November 20, 2026.',
  'More than $1,000 can be at work. A new trade opens each month while old ones may still be open: up to three at once, two or more on about one day in six.',
  'How much is the model and how much is the exit rule. Entering on any day with the same exit rule made about +1.0% per trade over these years. The model\u2019s choice of day added about +1.2%. On the 2021\u20132023 training years its choice of day added nothing, so that part is not yet proven.',
  'It was the sixth new model run on 2024\u20132026 in this round, and it was designed after seeing the fifth. The result needs confirming on trades after November 2026 before it is relied on.',
 ]}
n_keep = sum(c['keeps_loss_limit'] for c in d['methods']); n_keep5 = sum(c['keeps_strict_loss_limit'] for c in d['methods'])
all3_5 = d.get('level1_on_all_three_within_5pct', [])
broke = [M[i] for i in d.get('level1_but_breaks_loss_limit', [])]
ALL3_CARD = ''
if broke and not all3:
    blocks = ''.join(f'<h3>{E(c["name"])} reaches G{c["G_level"]}, WR{c["WR_level"]}, S{c["S_level"]} but breaks the risk rule</h3><ul>' + ''.join(f'<li>{t}</li>' for t in ALL3_NOTES.get(c['id'], [])) + '</ul>' for c in broke)
    ALL3_CARD = f'<div class="note2"><div class="eyebrow">Reached the three levels, outside the risk rule</div>{blocks}</div>'
if all3:
    blocks = ''.join(f'<h3>{E(c["name"])}: G{c["G_level"]}, WR{c["WR_level"]}, S{c["S_level"]}</h3><ul>' + ''.join(f'<li>{t}</li>' for t in ALL3_NOTES.get(c['id'], [])) + '</ul>' for c in all3)
    ALL3_CARD = f'<div class="note2 reached"><div class="eyebrow">Level 1 reached on G, WR and S, inside the 15% loss limit</div>{blocks}</div>'
HERO_TAG = (f'<span class="tag good">Level 1 reached on G, WR and S within the 15% loss limit: {", ".join(E(c["name"]) for c in all3)}</span> ' + ('' if any(c['GM_level'] for c in OKM) else '<span class="tag warn">GM1 not reached yet</span> ')
            + ('' if d.get('level1_on_all_three_within_5pct') else '<span class="tag warn">Not yet within the 5% limit</span>') if all3
            else '<span class="tag warn">No model reaches level 1 on all goals within the loss limits yet</span>')
# the model with the most months of 5% or more (model O), and what it showed about M
THREE_NOTES = {
 'R13_two_buys_stop15': [
  'What it is. Model M’s signal and exit with two $1,000 buys on the day after the signal, at 10:00 and at 1:00 pm.',
  'What it reaches. S 9 / 10 / 8 of 11, a 78.6% win rate, and the most months of 5% or more of any model: 8 / 10 / 8 of 11.',
  'Why it is not GM1. Since November 24, 2026 a year counts for goal 4 only if it has at most one losing month, and that month loses no more than 2%. O has 3, 2 and 3 losing months, most of them months in which both buys were stopped (−30%).',
  'What else it misses. Its average trade made +0.23%; G1 needs 1%. 13 of its 70 trades were stopped at 15%, and the likely range of the average runs from about −1.6% to +1.9%.',
  'What it shows about model M. O buys a few hours after M on the same signals. In 7 of 35 months M’s trade reached +4% while at least one of O’s did not. In three of them (January 2025, February 2025, June 2026) M won on an overnight jump, and both of O’s buys, made after the jump, were stopped. M’s 88.6% win rate depends on its exact entry price.',
  'How it was run. It reached level 1 on the training years with no spare month, which did not pass the stricter training test; it was run once at the owner’s standing instruction to test each trained model. This was run 22 on the test years.',
 ]}
_noted = [M[i] for i in THREE_NOTES if i in M]
if _noted:
    _lv = lambda c: ', '.join(f'{k}{c[k + "_level"]}' for k in ('G', 'WR', 'S', 'GM') if c[k + '_level']) or 'no level'
    _b = ''.join(f'<h3>{E(c["name"])}: {_lv(c)}</h3><ul>' + ''.join(f'<li>{t}</li>' for t in THREE_NOTES[c['id']]) + '</ul>' for c in _noted)
    ALL3_CARD += f'<div class="note2 rule"><div class="eyebrow" style="margin-bottom:6px">Most months of 5% or more, but with losing months</div>{_b}</div>'
if not d.get('level1_on_all_four'):
    HERO_TAG += ' <span class="tag warn">No model reaches level 1 on all four goals yet</span>'
# combinations put together after the test (not results), re-scored with the no-losing-month rule
_cf = f'{SRC}/stage13_after_the_fact_combinations.json'
if os.path.exists(_cf):
    _c = json.load(open(_cf))['combinations']
    def _crow(k, v):
        was = v.get('level1_all_four_before_2026_11_24_rule')
        return (f'<tr{" class=\'stop-best\'" if v["level1_all_four"] else ""}><td>{E(k)}</td><td class="num">{v["trades"]}</td><td class="num {"pos" if v["G"] >= 1 else ""}">{pct(v["G"], 2, True)}</td>'
                f'<td class="num pos">{v["WR"]:.1f}%</td><td class="num {"pos" if min(v["S"]) >= 8 else ""}">{" / ".join(map(str, v["S"]))}</td>'
                f'<td class="num">{" / ".join(map(str, v["GM"]))}</td><td class="num {"neg" if sum(v["negative_months"]) else "pos"}">{" / ".join(map(str, v["negative_months"]))}</td>'
                f'<td>{"Yes" if v["level1_all_four"] else ("No (yes before the new rule)" if was else "No")}</td></tr>')
    _any = any(v['level1_all_four'] for v in _c.values())
    ALL3_CARD += '' if not _any else f"""<div class="note2" id="afterfact"><h3>Combining M&rsquo;s and O&rsquo;s buys: {'one arrangement shows level 1 on all four goals, and why it is not counted' if _any else 'no arrangement reaches level 1 on all four goals'}</h3>
      <p style="margin:0 0 10px;font-size:14.5px">Models M and O use the same signals and the same exit; they differ only in when they buy. Their tested trades can be put together afterwards in several ways. No new run was made for this table.</p>
      <div class="table-scroll" style="background:var(--surface);border-radius:10px"><table>
        <thead><tr><th>Buys</th><th class="num">Trades</th><th class="num">Profit per trade</th><th class="num">Win rate</th><th class="num">S months</th><th class="num">Months of 5% or more</th><th class="num">Losing months</th><th>Level 1 on all four</th></tr></thead>
        <tbody>{''.join(_crow(k, v) for k, v in _c.items())}</tbody>
      </table></div>
      <ul style="margin-top:12px">
        <li><strong>Under goal 4 as it now stands, none passes.</strong> Every arrangement has two or more losing months in each year except M alone in 2025, and a year counts only with at most one losing month of no more than 2%.</li>
        <li><strong>Before the no-losing-month rule, one did.</strong> M&rsquo;s buy at the close plus a second buy at 10:00 the next day showed +1.05%, 82.9%, S 9 / 10 / 8 and 8 / 10 / 8 months of 5% or more. It was not counted then either: it was picked with the answers in view, the training years chose a different arrangement (model O), and it had no room to spare.</li>
        <li><strong>Forward test.</strong> M, O, L and that arrangement were frozen on November 23, 2026 for trades opened after that date. Only new trades can confirm any of them.</li>
      </ul></div>"""
sbest = max(d['methods'], key=lambda c: (s_worst(c), c['progress']['S']))
gbm_best = max(OKM, key=lambda c: (gm_worst(c), c['progress']['GM']))
same_best = max((c['best_month_avg_pct_per_trade'] for c in d['methods'] if KIND[c['id']] == 'Same-day'))
any_s = [c for c in d['methods'] if c['S_level'] > 0]
GM_LEAD = (f"GM1 needs 8 such months in every year, with at most one losing month of no more than 2%. It is reached by" if gbm_best['GM_level'] else "No model reaches GM1, which needs 8 such months in every year, with at most one losing month of no more than 2%. The most months of 5% or more inside the loss limits:")
GM_TAIL = '' if gbm_best['GM_level'] else (" It has " + ' / '.join(str(v['months_negative']) for v in gbm_best['by_year'].values()) + " losing months, so none of its years counts.")
_clean = [c for c in OKM if c['years_that_count_for_gm']]
GM_TAIL += (" Only " + ', '.join(f"{E(c['name'])} ({c['years_that_count_for_gm']} of 3 years)" for c in _clean) + " has a year that keeps the losing-month rule." if _clean else " No ranked model has a year that keeps the losing-month rule.")
S_NOTE = ((f"{E(any_s[0]['name'])} reaches level S{any_s[0]['S_level']}. " if any_s else "No model reaches level S1. ")
          + f"The closest is {E(sbest['name'])}, with {s_text(sbest)} months above 1% per trade. "
          + f"The same-day models never have such a month: their best month averages {same_best:.2f}% per trade. "
          + "The multi-day models trade a few times a year, so many of their months are empty. "
          + f"The monthly-profit goal (GM) looks at each month\u2019s total instead: the closest is {E(gbm_best['name'])}, with "
          + ' \u00b7 '.join(f"{y}: {v['months_total_5pct']} of {v['months']}" for y, v in gbm_best['by_year'].items()) + " months of 5% or more. " + (f"It reaches GM{gbm_best['GM_level']}." if gbm_best['GM_level'] else "No model reaches GM1, which also needs a year with at most one small losing month."))

multi_top = [c for c in TOP5 if KIND[c['id']] == 'Multi-day']
FEW_NOTE = (f"{', '.join(E(c['name']) for c in multi_top)} made {', '.join(str(c['trades']) for c in multi_top)} trades in almost three years. "
            "With so few trades their averages can change a lot with a handful of results, and one or two large trades can make a month count."
            if multi_top else "All five have more than a thousand trades.")
n_profit = sum(c['profitable_after_1c'] for c in d['methods'])
rom = M['RuleOrModel']; bgbm = M['B_field_fusion_gbm']; pctm = M['V7.1_pct']
top_names = ', '.join(c['name'] for c in TOP5)

CSS = open(f'{HERE}/page.css').read()
JS = open(f'{HERE}/page.js').read()

html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CNQ 5-Minute Zone Day Trading — Hamid Faghidi</title>
<meta name="description" content="Project 3: {n_models} models and methods for trading CNQ, scored against four goals (profit per trade, win rate, steady months, monthly profit) on 2024-2026, with $1,000 invested per trade.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,600&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../style.css">
<style>
{CSS}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <a class="brand" href="../">Hamid Faghidi</a>
  <nav><a href="../#categories">Projects</a><a href="./">AI Trading</a></nav>
</div></header>

<main class="wrap">
  <div class="crumbs" style="padding-top:20px"><a href="../">Home</a><span class="sep">/</span><a href="./">AI Trading</a><span class="sep">/</span><span>Project 3</span></div>
  <section class="hero" style="padding-top:28px">
    <div class="eyebrow">Project 3 &middot; CNQ 5-Minute Zone Day Trading</div>
    <h1>{n_models} trading models, scored against four goals</h1>
    <p class="lede">Every model and method built in this project for trading Canadian Natural Resources (CNQ) is scored here on the same four goals. Scores use January 2024 to November 2026, years the models were not trained on. Dollar figures assume $1,000 invested in each trade.</p>
    <p style="margin-top:14px">{HERO_TAG} <span class="tag muted">Research only, hypothetical backtests</span> <span class="tag muted">Updated Nov 23, 2026</span></p>
    <nav class="toc" aria-label="On this page"><a href="#goals">The goals</a><a href="#top5">Top 5</a><a href="#all">All {n_models} models</a><a href="#months">Steady months</a><a href="#gm-months">Monthly profit</a>{'<a href="#stops">Stop size</a>' if STOP_SECTION else ''}{'<a href="#stage14">New data</a>' if S14_SECTION else ''}<a href="#money">$1,000 per trade</a><a href="#measure">How it is measured</a><a href="project-03-research.html">Research record</a></nav>
  </section>

  <section id="goals">
    <h2>The goals</h2>
    <p class="sub">Four goals, each with three levels. A filled step means at least one model has reached that level inside the 15% loss limit.</p>
    <div class="goals">{goals_html}</div>
    <div class="note2 rule"><h3>Risk rule: two limits on the worst trade, 5% and 15%</h3><p>Set by the owner on November 23, 2026. A model must carry a stop, and the scoreboard shows which limit it keeps: 5% ($50 on a $1,000 trade) or 15% ($150). A model's levels count, and it is ranked, only inside the 15% limit. {n_keep5} of {n_models} models keep the 5% limit and {n_keep} keep the 15% limit. A price gap through the stop can still make one loss a little larger; the worst trade is shown for every model.</p></div>
    {ALL3_CARD}
    <div class="statstrip" style="margin-top:16px">
      <div class="primary"><div class="k">Models scored</div><div class="v">{n_models}</div><div class="s">{sum(KIND[c['id']] == 'Same-day' for c in d['methods'])} same-day, {sum(KIND[c['id']] == 'Multi-day' for c in d['methods'])} multi-day</div></div>
      <div><div class="k">Test period</div><div class="v">35 months</div><div class="s">Jan 2024 to Nov 18, 2026</div></div>
      <div><div class="k">Money per trade</div><div class="v">$1,000</div><div class="s">about 28 CNQ shares</div></div>
      <div><div class="k">Profitable after costs</div><div class="v">{n_profit} of {n_models}</div><div class="s">at 1&cent; per share</div></div>
    </div>
  </section>

  <section id="top5">
    <h2>Top 5 models</h2>
    <p class="sub">Ranked by overall progress: how far a model is toward the top level of each goal (3% per trade, 75% win rate, and 12 of 12 months on each of the two month goals), averaged over the four. For goal 4 a year counts as zero unless it has at most one losing month of no more than 2%. Only models inside the 15% loss limit are ranked; the table shows which also keep 5%. The marks on each bar are levels 1, 2 and 3.</p>
    <ol class="top5">{top_html}</ol>
    <div class="note2">
      <h3>Four things to know before relying on this ranking</h3>
      <ul>
        {RANK_NOTE}
        <li><strong>Few trades.</strong> {FEW_NOTE}</li>
        <li><strong>Costs.</strong> The same-day models make about $0.20 per $1,000 trade. A cost of 1&cent; per share is about $0.28 per trade, so they lose money once it is charged. The models that keep a profit after costs are {', '.join(E(c['name']) for c in ORDER if c['profitable_after_1c'])}.</li>
        <li><strong>Break-even trades.</strong> The win rate leaves out trades that end within half a cent of the entry price. The same-day models have many of these: {E(pctm['name'])} wins {pctm['win_rate']:.0f}% of decided trades but {pctm['wins_share_of_all_trades']:.0f}% of all trades. If a break-even trade is not counted as a win, the top five becomes {', '.join(E(n) for n in STRICT5)}.</li>
      </ul>
    </div>
  </section>

  <section id="all">
    <h2>All {n_models} models against the goals</h2>
    <p class="sub">One row per model. Each bar runs toward the top level; the three marks are levels 1, 2 and 3.</p>
    <div class="tabs" role="group" aria-label="Filter models"><button type="button" id="f-all" aria-pressed="true" data-f="">All</button><button type="button" id="f-same" aria-pressed="false" data-f="Same-day">Same-day</button><button type="button" id="f-multi" aria-pressed="false" data-f="Multi-day">Multi-day</button></div>
    <div class="card" style="padding:6px 0 0">
      <p class="swipe" style="padding:10px 16px 0">Swipe sideways to see every column.</p><div class="table-scroll"><table class="score" id="score">
        <thead><tr><th class="num">Rank</th><th>Model</th><th>G &middot; profit per trade; then each year: average, and $1,000 at year end</th><th>WR &middot; win rate; then each year</th><th>S &middot; steady months; then each year</th><th>GM &middot; months of 5% or more; then each year: months, losing months, and the year&rsquo;s total gross %</th><th>Levels</th><th>Worst trade, and profit after costs</th></tr></thead>
        <tbody>{table_html}</tbody>
      </table></div>
    </div>
    <p class="fine" style="margin-top:10px">Same-day models buy and sell within one trading day on 5-minute bars. Multi-day models hold for about 5 days or longer. Under each profit-per-trade bar are two figures for 2024, 2025 and 2026: the average gross % per trade in that year, and what $1,000 would stand at by the end of that year when $1,000 goes into every trade and profits are not reinvested ($1,098 means $98 of profit; each year starts again from $1,000; before costs). The win rate, steady months and monthly profit columns show each year's own figure in the same way. A GM level needs a year with at most one losing month, of no more than 2%, so each year also shows how many of its months ended below zero (&ldquo;clean&rdquo; means none). In the monthly profit column the last figure on each line is the year's total gross %: every trade of that year added up (the average per trade times the number of trades). The headline steady-months and monthly-profit figures are the worst of the three years on a 12-month basis, counting months whose average trade made more than 1%. The small figure beside each win rate counts wins as a share of all trades, break-even ones included. Models with fewer than 15 trades, or that break the 15% loss limit, are scored but not ranked. V1 to V6 use rules set by hand on six weeks of mid-2026, which fall inside the test period, so their scores are flattering.</p>
  </section>

  <section id="months">
    <h2>Steadiness, month by month</h2>
    <p class="sub">Each square is one month. A month counts toward the S goal when the trades opened in it average more than 1% profit each, before costs.</p>
    <div class="card">
      <div class="hm-legend"><span><i class="hm-c hit"></i>Average above 1% per trade (counts)</span><span><i class="hm-c pos"></i>Average profit, 1% or less</span><span><i class="hm-c neg">{MIN}</i>Average loss</span><span><i class="hm-c nt"></i>No trades</span></div>
      <p class="swipe">Swipe sideways to see all 35 months.</p><div class="hm-scroll"><div class="hm" id="hm">{years}{head}{hm_rows}</div></div>
      <div class="tipbox" id="tip" role="status" aria-live="polite">Point at a square to see that month.</div>
    </div>
    <p class="fine" style="margin-top:10px">{S_NOTE}</p>
  </section>

  <section id="gm-months">
    <h2>Monthly profit, month by month</h2>
    <p class="sub">Each square is one month. A month counts toward the GM goal when all the trades opened in it, winners and losers together, add up to 5% or more. That is $50 or more at $1,000 per trade. Since November 24, 2026 a year counts only if it has at most one losing month, and that month loses no more than 2%. Two red squares in a year, or one large one, rule that year out.</p>
    <div class="card">
      <div class="hm-legend"><span><i class="hm-c hit"></i>Total of 5% or more</span><span><i class="hm-c pos"></i>Profit under 5%</span><span><i class="hm-c neg">{MIN}</i>Loss for the month</span><span><i class="hm-c nt"></i>No trades</span></div>
      <p class="swipe">Swipe sideways to see all 35 months.</p><div class="hm-scroll"><div class="hm">{years}{head_gm}{hm_rows_gm}</div></div>
      <div class="tipbox" role="status" aria-live="polite">Point at a square to see that month.</div>
    </div>
    <p class="fine" style="margin-top:10px">{GM_LEAD} {E(gbm_best['name'])}, with {' &middot; '.join(f"{y}: {v['months_total_5pct']} of {v['months']}" for y, v in gbm_best['by_year'].items())}.{GM_TAIL} Models that take one trade a month and sell at +4% rarely total 5% in a month; models with many small trades have more profitable months but few as large as 5%.</p>
  </section>

{STOP_SECTION}
{S14_SECTION}
  <section id="money">
    <h2>What $1,000 per trade would have made</h2>
    <p class="sub">Each trade buys $1,000 of CNQ. When it is sold, the same $1,000 is used for the next trade; profits are not reinvested. Totals cover January 2024 to November 18, 2026.</p>
    <div class="card">
      <div class="chart-title"><h3>Total profit, before and after trading costs</h3><div class="legend-inline"><span style="--c:var(--pale)">Before costs</span><span style="--c:var(--accent)">After costs, profit</span><span style="--c:var(--loss)">After costs, loss</span></div></div>
      <p class="chart-note">Costs are 1&cent; per share for buying and selling together. For reference, buying $1,000 of CNQ on the first day and holding it made about {usd(BH)} (price change only).</p>
      <div class="mchart"><div class="mr mr-axis"><div class="mr-name"></div><div class="mr-plot">{axis}</div><div class="mr-val"><span>Before</span><strong>After</strong></div></div>{money_html}</div>
    </div>
    <details class="card tv">
      <summary>Show the numbers as a table</summary>
      <div class="table-scroll"><table>
        <thead><tr><th>Model</th><th class="num">Trades</th><th class="num">Avg per trade</th><th class="num">2024</th><th class="num">2025</th><th class="num">2026</th><th class="num">Total before costs</th><th class="num">Costs</th><th class="num">Total after costs</th></tr></thead>
        <tbody>{money_table}</tbody>
      </table></div>
    </details>
    <p class="fine" style="margin-top:10px">{E(rom['name'])} shows why costs matter: {rom['trades']:,} trades made {usd(rom['dollars_total'], 0, False)} before costs, and the cost of those trades comes to about {usd(rom['cost_1c_dollars_total'], 0, False)}. {E(gbest['name'])} made {usd(gbest['dollars_total'], 0, False)} from {gbest['trades']} trades and paid about {usd(gbest['cost_1c_dollars_total'], 0, False)} in costs.</p>
  </section>

  <section id="measure">
    <h2>How it is measured</h2>
    <div class="grid g3">
      <div class="card"><h3>Fair test</h3><p>Models were trained and tuned on 2020 to 2023, then frozen and run once on 2024 to 2026. No model was adjusted after its run. A check repeated on November 24, 2026 rebuilt all 108 model inputs twice, once with 2024 to 2026 removed and once with the data cut in the middle of the test years, and got identical values both times: no input can see a later day. Models M, O and P were re-run from their frozen files and gave the same results. What the check cannot remove: the designer had seen earlier test results. Every model from I onward (I to R) was designed after earlier results on 2024 to 2026 were known, and V1 to V6 use rules set by hand on weeks that fall inside the test period. That is why the number of runs on the test years is shown and why the latest results need confirming on new data.</p></div>
      <div class="card"><h3>Gross and after costs</h3><p>The goals are gross, before costs. Robinhood and Schwab charge no commission on CNQ, but each trade still loses a little to the bid-ask spread. The page uses 1&cent; per share for that.</p></div>
      <div class="card"><h3>Ranking rule</h3><p>Overall progress is the average of four fractions: profit per trade out of 3%, win rate out of 75%, the share of months whose average trade is above 1%, and the share of months whose total is 5% or more. The rule was fixed before the scores were computed.</p></div>
    </div>
    <div class="card" style="margin-top:16px">
      <h3>Limits of these results</h3>
      <ul>
        <li>One stock. All results are for CNQ only and are backtests, not real trades. Models E onward use consolidated-market prices; earlier models use one exchange's feed (IEX).</li>
        <li>Few trades for the multi-day models. {E(gbest['name'])} has {gbest['trades']} trades in almost three years. Its average of {pct(gbest['gross_pct_per_trade'])} per trade has a likely range of {pct(gbest['gross_pct_per_trade_ci95'][0], 1, True)} to {pct(gbest['gross_pct_per_trade_ci95'][1], 1, True)}.</li>
        <li>The test years have now been looked at {LOOKS} times by different models. Each extra look makes a lucky result more likely, so the newest results need confirming on data after November 2026.</li>
        <li>A rising stock helps long trades. CNQ rose about 39% over the test period, and a randomly timed 5-day purchase made +0.35% on average.</li>
        <li>Higher levels. A search of 135 settings on the 2021 to 2023 training years, with the test years removed from the data, found none that reaches level 2 on all three goals in every year, and none that reaches level 3. No new model was run on the test years for those levels.</li>
        <li>Level 1 on all four goals. After model N a new model must pass its training-years test with a margin of one month on S and on GM, and the same rule must hold on the five peer stocks. 1,620 settings were tried on 2021 to 2023 with the test years removed, with stops from 1% to 15%. None passed, so nothing new was run on the test years.</li>
        <li>Trades opened at the same time. By the owner's rule, trades opened at exactly the same time count as one trade; trades opened at different times count separately, even on the same day. No score on this page changed when the rule was applied.</li>
        <li>Model P, run once and not level 1. P passed a stricter training-years test by a wide margin (95.6% of its trades won there) and was then run once on the test years, the twenty-first such run. There 80% won, which is below the 83% it needs to break even with a +3% target and a 15% stop. Waiting for a dip added nothing on the test years.</li>
        <li>Forward test. Models M, O and L, and one arrangement that puts M&rsquo;s and O&rsquo;s buys together, were frozen on November 23, 2026. They will be scored on trades opened after that date when new price data is added. Nothing about them may be changed in the meantime.</li>
        <li>Model R, not run. A campaign timed by a month-ahead forecast that uses the new data did better on the training years than the same campaign with the old forecast, but no setting passed all five checks, so it was not run on the test years.</li>
        <li>Model Q, not run. A version that sells short when the trend is down was tested on the training years. None of its 24 settings passed, and most did worse than always buying, so it was not run on the test years.</li>
        <li>2026 has 11 months of data. Its months are judged on the same fractions (8/12, 10/12, 12/12).</li>
      </ul>
    </div>
    <a class="card research-link" href="project-03-research.html">
      <div class="eyebrow">Research record</div>
      <h3>How each model was built and tested, stage by stage</h3>
      <p>Rules for V1 to V7.1, the root-cause audits, the machine-learning experiments, walk-forward training, the Stage 11 and Stage 12 swing models, data sources and lessons learned.</p>
      <span class="research-cta">Open the research record &rarr;</span>
    </a>
  </section>

  <section id="disclosure">
    <h2>Disclosures</h2>
    <div class="card"><p style="margin:0">Research and education only, not investment advice; the author isn't a licensed financial advisor. All results are hypothetical backtests on one stock (CNQ). Gross figures exclude all trading costs; after-cost figures include only a 1&cent; per share allowance. Real fills, spreads and fees can reduce results further. Past backtested performance does not guarantee future results.</p></div>
  </section>

  <section>
    <h2>Sources</h2>
    <div class="card"><ul class="sources" style="margin:0">
      <li><a href="https://github.com/hamidf2024/p03-cnq-h-strategy-day-trader">Project 3 repository</a>: charter, test protocol, strategy rules, code and result summaries</li>
      <li><a href="https://github.com/hamidf2024/p03-cnq-h-strategy-day-trader/blob/main/docs/07_Goals_and_Targets.md">Goals &amp; Targets</a>: the three goal ladders, definitions and the full scorecard</li>
      <li><a href="https://github.com/hamidf2024/p03-cnq-h-strategy-day-trader/blob/main/results/experiments/goals_scorecard.json">goals_scorecard.json</a> and <a href="https://github.com/hamidf2024/p03-cnq-h-strategy-day-trader/blob/main/results/experiments/goals_monthly_2024_2026.csv">goals_monthly_2024_2026.csv</a>: every number on this page, produced by <a href="https://github.com/hamidf2024/p03-cnq-h-strategy-day-trader/blob/main/src/goals_scorecard.py">src/goals_scorecard.py</a></li>
      <li><a href="https://github.com/hamidf2024/p03-cnq-h-strategy-day-trader/blob/main/docs/10_Stage12_Field_Fusion_Research.md">Stage 12: Field-Fusion Swing Research</a> and <a href="https://github.com/hamidf2024/p03-cnq-h-strategy-day-trader/blob/main/docs/09_Stage11_Per_Trade_Target_Research.md">Stage 11: Per-Trade Target Research</a></li>
    </ul></div>
  </section>

  <a class="back" href="./">&larr; Back to AI Trading</a>
  __CATNAV__
</main>
<footer><div class="wrap">&copy; 2026 Hamid Faghidi &middot; Trading results are hypothetical backtests. Nothing on this site is investment advice.</div></footer>
<script>
{JS}
</script>
</body>
</html>
'''
old = open(sys.argv[3]).read()
a = old.index('<section><h2 style="text-align:center">Browse categories</h2>'); b = old.index('</main>')
html = html.replace('__CATNAV__', old[a:b].rstrip())
open(OUT, 'w').write(html)
print('wrote', OUT, len(html))
