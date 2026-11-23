"""
Stage 13, round 13: model O = model M's design with TWO buys at different times.

Owner's rule (2026-11-23): trades opened at exactly the same time count as one trade; trades opened at
different times count separately, even on the same day. Model M reaches level 1 on G, WR and S but not on
GM, because one +4% trade a month cannot total 5%. Model O keeps M's signal and M's exit unchanged and buys
twice, at two different times, $1,000 each.

    signal   M's: the first day of the month on which the Peer-Fusion model's trailing rank is at least 0.5
             (known at 15:50 on that day)
    exit     M's: +4% target, 15% stop, 60 sessions, each buy on its own
    buys     one of six fixed patterns (the only thing selected):
               close+next1000     at that day's close, and at 10:00 the next session
               close+next1300     at that day's close, and at 13:00 the next session
               next0935+next1555  next session at 09:35 and at the close
               next1000+next1300  next session at 10:00 and at 13:00
               next1000+next1555  next session at 10:00 and at the close
               next1300+next1555  next session at 13:00 and at the close
             "at HH:MM" means the close of the 5-minute bar that ends at HH:MM. If both buys fall on the same
             bar (a half day), they are the same time and count as one trade.

Modes
    select   training years only; needs S13_CUTOFF=2023-12-29 so 2024-2026 is not in the data
    blind    one run on 2024-2026 of the frozen pattern; refuses to run twice
    verify   reproduces the stored blind result
    freeze   freezes the pattern the fixed order puts first (used when no pattern passes the gate and the
             owner's instruction is to test anyway; recorded as a run without passing the gate)
    dry      rehearses the blind code on 2023 with the test years removed; writes nothing

GATE for select (unchanged from rounds 11 and 12, fixed before this round):
 A. CNQ, model entry, each of 2021, 2022, 2023: S >= need + 1 and GM >= need + 1 (need = 8/12 of the months
    available, rounded up); over the three years G >= 1.25% per trade and win rate >= 55%.
 B. Same pattern, calendar signal (first trading day of the month), six stocks: S >= need and GM >= need in at
    least 14 of 18 stock-years, and at least 1.0% per trade across all six.
 Choice among passers: largest worst-year margin on the month goals, then stock-years passed, then G.
 If nothing passes, nothing is frozen and no run on 2024-2026 is made.

What a pass will and will not mean (written before the run): O is M twice. M's 2024-2026 result is already
known, so a good result for O is expected and adds little independent evidence. O puts $2,000 at risk on each
monthly entry instead of $1,000, and its two buys usually win or lose together.
"""
import hashlib
import json
import os
import pickle
import sys
import numpy as np
import pandas as pd
import s13_lib as L
import stage13_peer_fusion as P

RES = os.environ.get('S13_OUT', 'results/experiments')
NAME = 'R13_two_buys_stop15'
ART = 'stage13_frozen_R13.pkl'
M_CFG = dict(src='gbm', H=5, side='long', q=0.5, monthly=True, overlap=True, hold=60, target=4.0, stop=15.0)
TARGET, STOP, HOLD = 4.0, 15.0, 60
PATTERNS = {   # name: [(session offset from the signal day, 'HH:MM' or 'close'), ...]
    'close+next1000': [(0, 'close'), (1, '10:00')],
    'close+next1300': [(0, 'close'), (1, '13:00')],
    'next0935+next1555': [(1, '09:35'), (1, 'close')],
    'next1000+next1300': [(1, '10:00'), (1, '13:00')],
    'next1000+next1555': [(1, '10:00'), (1, 'close')],
    'next1300+next1555': [(1, '13:00'), (1, 'close')],
}
YEARS_TRAIN = [2021, 2022, 2023]
YEARS_BLIND = [2024, 2025, 2026]
MONTHS_BLIND = {2024: 12, 2025: 12, 2026: 11}


class Tape:
    """5-minute bars of one symbol; a buy at a given bar, then M's exit checked bar by bar."""
    def __init__(self, intr, D):
        self.days = list(D.index[D.close.notna()]); self.pos = {d: i for i, d in enumerate(self.days)}
        self.bars = {}
        for d, x in intr.groupby('date'):
            mins = (x.Datetime.dt.hour * 60 + x.Datetime.dt.minute).values
            self.bars[d] = (mins, x.Open.values, x.High.values, x.Low.values, x.Close.values)

    def bar_index(self, day, when):
        mins = self.bars[day][0]
        if when == 'close':
            return len(mins) - 1
        h, m = map(int, when.split(':')); stamp = h * 60 + m - 5          # the bar that ENDS at HH:MM
        ok = np.where(mins <= stamp)[0]
        return int(ok[-1]) if len(ok) else 0

    def buy(self, day, k, hold=HOLD, target=TARGET, stop=STOP):
        """Buy at the close of bar k on `day`. Exit at the target or the stop (a bar that touches both counts
        as the stop; a gap through a level fills at the open) or at the close `hold` sessions later."""
        i = self.pos[day]; entry = float(self.bars[day][4][k])
        tp = entry * (1 + target / 100); sl = entry * (1 - stop / 100)
        last = min(i + hold, len(self.days) - 1)
        for j in range(i, last + 1):
            d = self.days[j]; mins, o, h, l, c = self.bars[d]
            for b in range(k + 1 if j == i else 0, len(o)):
                if l[b] <= sl:
                    return entry, d, min(o[b], sl), 'stop'
                if h[b] >= tp:
                    return entry, d, max(o[b], tp), 'target'
        d = self.days[last]
        return entry, d, float(self.bars[d][4][-1]), 'time'

    def campaign(self, signal_days, pattern, last_signal_day=None):
        """Two buys per signal day; buys on the same bar are the same time and count once."""
        rows = []
        for sd in signal_days:
            i = self.pos[sd]
            if last_signal_day is not None and sd > last_signal_day:
                continue
            seen = set()
            for off, when in PATTERNS[pattern]:
                if i + off >= len(self.days) - 1:
                    continue
                d = self.days[i + off]; k = self.bar_index(d, when)
                if (d, k) in seen:
                    continue
                seen.add((d, k))
                entry, xd, px, why = self.buy(d, k)
                mins = self.bars[d][0][k] + 5
                rows.append(dict(signal_day=sd, entry_date=d, entry_time=f'{mins // 60:02d}:{mins % 60:02d}', exit_date=xd, side=1,
                                 entry_price=entry, exit_price=px, pnl=px - entry, ret=(px / entry - 1) * 100, reason=why,
                                 days=self.pos[xd] - self.pos[d]))
        return pd.DataFrame(rows)


def month_stats(t, years, months_avail):
    per = {}
    for y in years:
        ty = t[t.entry_date.dt.year == y]; g = ty.groupby(ty.entry_date.dt.month).ret; avail = months_avail[y]
        per[y] = dict(n=int(len(ty)), G=round(float(ty.ret.mean()), 3) if len(ty) else None,
                      WR=round(float((ty.ret > 0).mean() * 100), 1) if len(ty) else None,
                      S=int((g.mean() > 1).sum()), GM=int((g.sum() >= 5).sum()), months=avail, need=int(np.ceil(8 / 12 * avail)),
                      total_pct=round(float(ty.ret.sum()), 1))
    return per


def monthly_signal_days(days, valid, score=None, q=0.5):
    out = {}
    for d in days:
        if not valid.get(d, False):
            continue
        m = (d.year, d.month)
        if m not in out and (score is None or (not np.isnan(score.get(d, np.nan)) and score[d] >= q)):
            out[m] = d
    return list(out.values())


def select():
    cut = os.environ.get('S13_CUTOFF', '')
    assert cut and cut <= '2023-12-31', 'run the selection with S13_CUTOFF=2023-12-29'
    panel, D, intr = P.get_panel(); cal = D['USO'].index
    assert cal.max() <= pd.Timestamp('2023-12-31')
    frozen = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    cnq = panel[panel.stock == 'CNQ'].set_index('date')
    sig = P.signal_from_cfg(M_CFG, cnq, frozen['oof']).reindex(cal).fillna(0)          # M's own signal, unchanged
    tapes = {s: Tape(intr[s], D[s]) for s in L.STOCKS}
    valid = {s: panel[panel.stock == s].set_index('date').valid.to_dict() for s in L.STOCKS}
    end = tapes['CNQ'].days[-HOLD - 2]                                                  # room for the next-session buy and the full hold
    avail = {2021: 12, 2022: 12, 2023: int(end.month)}
    sig_days = [d for d in sig.index[sig > 0] if d.year in YEARS_TRAIN and d in tapes['CNQ'].pos]
    path = L.Path(intr['CNQ'], D['CNQ'])
    for d in sig_days[:12]:                                                             # a buy at the close must reproduce the Stage 13 simulator
        e, xd, px, why = tapes['CNQ'].buy(d, tapes['CNQ'].bar_index(d, 'close')); xd2, px2, why2 = path.trade(d, 1, HOLD, TARGET, STOP)
        assert (xd, round(px, 6), why) == (xd2, round(px2, 6), why2), (d, xd, px, why, xd2, px2, why2)
    res = {}
    for pat in PATTERNS:
        t = tapes['CNQ'].campaign(sig_days, pat, last_signal_day=end)
        per = month_stats(t, YEARS_TRAIN, avail)
        G = float(t.ret.mean()); WR = float((t.ret > 0).mean() * 100)
        margin = min(min(p['S'], p['GM']) - p['need'] for p in per.values())
        a_ok = margin >= 1 and G >= 1.25 and WR >= 55
        passed = 0; allr = []; xs = {}
        for s in L.STOCKS:
            cd = [d for d in monthly_signal_days(tapes[s].days, valid[s]) if d.year in YEARS_TRAIN]
            ts = tapes[s].campaign(cd, pat, last_signal_day=end); ps = month_stats(ts, YEARS_TRAIN, avail); allr.append(ts.ret)
            xs[s] = {y: [p['S'], p['GM'], p['need']] for y, p in ps.items()}
            passed += sum(p['S'] >= p['need'] and p['GM'] >= p['need'] for p in ps.values())
        Gx = float(pd.concat(allr).mean()); b_ok = passed >= 14 and Gx >= 1.0
        res[pat] = dict(n=int(len(t)), G=round(G, 3), WR=round(WR, 1), worst=round(float(t.ret.min()), 1), stops=int((t.reason == 'stop').sum()),
                        per_year=per, margin=int(margin), cross_passed=int(passed), cross_G=round(Gx, 3), cross_per_stock=xs,
                        gate_A=bool(a_ok), gate_B=bool(b_ok), passes=bool(a_ok and b_ok))
        print(f"{pat:18s} n {len(t):3d} G {G:5.2f} WR {WR:5.1f} worst {t.ret.min():6.1f} stops {(t.reason == 'stop').sum():2d} | S {[p['S'] for p in per.values()]} "
              f"GM {[p['GM'] for p in per.values()]} need {[p['need'] for p in per.values()]} margin {margin:+d} | cross {passed}/18 G {Gx:.2f} | "
              f"{'A' if a_ok else '-'} {'B' if b_ok else '-'}", flush=True)
    passers = {k: v for k, v in res.items() if v['passes']}
    out = dict(cutoff=cut, data_last_day=str(cal.max().date()), exit=dict(target=TARGET, stop=STOP, hold=HOLD), signal=M_CFG, patterns=res,
               passers=sorted(passers), gate=__doc__.split('GATE for select')[1].split('What a pass will')[0].strip())
    if passers:
        best = max(passers, key=lambda k: (passers[k]['margin'], passers[k]['cross_passed'], passers[k]['G']))
        out['chosen'] = best
        blob = pickle.dumps(dict(chosen={NAME: dict(pattern=best, **M_CFG)}, finals=frozen['finals'], oof=frozen['oof'], feats=frozen['feats']))
        open(f'{RES}/{ART}', 'wb').write(blob); out['frozen_sha256'] = hashlib.sha256(blob).hexdigest()
        print('CHOSEN', best, out['frozen_sha256'][:16], flush=True)
    else:
        print('No pattern clears the gate: nothing frozen, no run on 2024-2026.', flush=True)
    json.dump(out, open(f'{RES}/stage13_round13_two_buys_selection.json', 'w'), indent=1, default=str)


def freeze():
    """Freezes the pattern that the fixed order puts first (largest worst-year margin on the month goals, then peer
    stock-years, then G), read from the saved training-years selection. No pattern passed the gate (every one has zero
    spare months in 2021, a year in which the forecasting model has no signal before March, so only ten months are
    traded). The run is made under the owner's standing instruction to train on 2020-2023, test on 2024-2026 and
    repeat, and is recorded as a run WITHOUT passing the gate."""
    sel = json.load(open(f'{RES}/stage13_round13_two_buys_selection.json')); pats = sel['patterns']
    best = max(pats, key=lambda k: (pats[k]['margin'], pats[k]['cross_passed'], pats[k]['G']))
    frozen = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    note = ('did not pass the training gate (zero spare months in 2021); run under the owner\'s standing instruction to '
            'test each trained model on 2024-2026; model M twice, so a good result is expected and adds little independent evidence')
    blob = pickle.dumps(dict(chosen={NAME: dict(pattern=best, **M_CFG)}, finals=frozen['finals'], oof=frozen['oof'], feats=frozen['feats'],
                             gate_passed=False, gate_note=note, selection_stats=pats[best]))
    open(f'{RES}/{ART}', 'wb').write(blob)
    print('FROZEN', best, pats[best]['G'], pats[best]['WR'], [p['S'] for p in pats[best]['per_year'].values()], hashlib.sha256(blob).hexdigest()[:16], flush=True)


def freeze_forward(pattern='close+next1000'):
    """Freezes a pattern for a FORWARD test only (trades after the data end of 2026-11-20). It was picked after the
    test years had been seen, so it must never be reported as a result on 2024-2026; blind() refuses to run it."""
    assert pattern in PATTERNS
    frozen = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    note = ('picked on 2026-11-23 by looking at published 2024-2026 results (model M plus the 10:00 leg of model O); '
            'not a test result; valid only for trades opened after 2026-11-20')
    blob = pickle.dumps(dict(chosen={'R13F_close_next1000': dict(pattern=pattern, **M_CFG)}, finals=frozen['finals'], oof=frozen['oof'], feats=frozen['feats'],
                             gate_passed=False, forward_only=True, selected_after_test=True, gate_note=note))
    f = f'{RES}/stage13_frozen_FORWARD_close_next1000.pkl'; open(f, 'wb').write(blob)
    print('FROZEN FOR FORWARD TEST', pattern, hashlib.sha256(blob).hexdigest(), flush=True)


def blind(verify=False, dry=False):
    """dry=True rehearses every step on 2023 with the test years removed (S13_CUTOFF set); it writes nothing."""
    logf = f'{RES}/stage13_BLIND_RUN_LOG.json'; resf = f'{RES}/stage13_blind_results.json'
    log = json.load(open(logf)) if os.path.exists(logf) else {}
    allres = json.load(open(resf)) if os.path.exists(resf) else {}
    if not dry and (NAME in log) != verify:
        sys.exit('Refused: this model has already had its one run on 2024-2026 (use "verify").' if not verify else 'Nothing to verify yet.')
    assert bool(os.environ.get('S13_CUTOFF')) == dry, 'blind/verify need the full data (unset S13_CUTOFF); dry needs S13_CUTOFF=2023-12-29'
    W0, W1, YRS, MAV = (L.BLIND_START, L.BLIND_END, YEARS_BLIND, MONTHS_BLIND) if not dry else ('2023-01-01', '2023-09-29', [2023], {2023: 9})
    blob = open(f'{RES}/{ART}', 'rb').read(); sha = hashlib.sha256(blob).hexdigest(); frozen = pickle.loads(blob)
    assert not frozen.get('forward_only'), 'this artefact is for the forward test only; it must not be run on 2024-2026'
    cfg = frozen['chosen'][NAME]; pat = cfg['pattern']
    panel, D, cal, feats, cnq, path, bench, T = P.setup()
    assert feats == frozen['feats']
    days = cal[(cal >= L.BLIND_START)]
    preds = frozen['oof'] if dry else {H: pd.concat([frozen['oof'][H], P.predict_cnq(m, panel, cal, T, days, feats)]) for H, m in frozen['finals'].items()}
    sig = P.signal_from_cfg({k: v for k, v in cfg.items() if k != 'pattern'}, cnq, preds).reindex(cal).fillna(0)
    tape = Tape(P.get_panel()[2]['CNQ'], D['CNQ'])
    sd = [d for d in sig.index[sig > 0] if pd.Timestamp(W0) <= d <= pd.Timestamp(W1) and d in tape.pos]
    t = tape.campaign(sd, pat)
    per = month_stats(t, YRS, MAV); r = t.ret.values
    rng = np.random.default_rng(0); bs = [rng.choice(r, len(r)).mean() for _ in range(5000)]
    # no-skill line: the same two buys and the same exit after EVERY day of the year
    allday = [d for d in cnq.index[cnq.valid] if pd.Timestamp(W0) <= d <= pd.Timestamp(W1) and d in tape.pos]
    tb = tape.campaign(allday, pat); by = tb.groupby(tb.entry_date.dt.year).ret.mean()
    excess = float(np.mean([x - by[y] for x, y in zip(t.ret, t.entry_date.dt.year)]))
    ev = sorted([(a, 1) for a in t.entry_date] + [(b, -1) for b in t.exit_date], key=lambda z: (z[0], -z[1])); cur = mx = 0
    for _, s in ev:
        cur += s; mx = max(mx, cur)
    both = t.groupby('signal_day').reason.apply(lambda x: (len(x), int((x == 'target').sum())))
    st = dict(setting=cfg, n=int(len(t)), signals=int(len(sd)), G=round(float(r.mean()), 3), WR=round(float((r > 0).mean() * 100), 1),
              S=[per[y]['S'] for y in YRS], GM=[per[y]['GM'] for y in YRS], per_year=per,
              G_ci95=[round(float(np.percentile(bs, 2.5)), 2), round(float(np.percentile(bs, 97.5)), 2)], median=round(float(np.median(r)), 3),
              worst_trade=round(float(r.min()), 2), best_trade=round(float(r.max()), 2), exits=t.reason.value_counts().to_dict(),
              net_after_1c=round(float(((t.pnl - 0.01) / t.entry_price * 100).mean()), 3), avg_days_held=round(float(t.days.mean()), 1),
              excess=round(excess, 3), no_skill_line_by_year={int(k): round(float(v), 3) for k, v in by.items()},
              max_open_at_once=int(mx), signals_with_two_buys=int(sum(a == 2 for a, _ in both)),
              signals_both_hit_target=int(sum(a == 2 and b == 2 for a, b in both)), signals_one_hit=int(sum(a == 2 and b == 1 for a, b in both)),
              signals_none_hit=int(sum(b == 0 for a, b in both)))
    payload = json.dumps(st, sort_keys=True, default=str)
    if dry:
        print('DRY RUN on 2023 (nothing written):', {k: st[k] for k in ('n', 'signals', 'G', 'WR', 'S', 'GM', 'exits', 'excess', 'max_open_at_once', 'signals_both_hit_target')}); return
    if verify:
        print('VERIFY', NAME, 'identical' if json.dumps(allres[NAME], sort_keys=True, default=str) == payload else 'DIFFERENT'); return
    allres[NAME] = json.loads(payload)
    log[NAME] = dict(frozen_artefact=ART, frozen_sha256=sha, ran_on=str(pd.Timestamp.now()), blind_window=[L.BLIND_START, L.BLIND_END],
                     blind_look_number=len(log) + 1, result_sha256=hashlib.sha256(payload.encode()).hexdigest(),
                     gate_passed=frozen.get('gate_passed', True), note=frozen.get('gate_note', ''))
    json.dump(allres, open(resf, 'w'), indent=1); json.dump(log, open(logf, 'w'), indent=1)
    t.insert(0, 'model', NAME)
    t.drop(columns=['entry_price', 'exit_price', 'pnl']).to_csv(f'{RES}/stage13_round13_blind_trades.csv', index=False)         # published: no prices
    t.rename(columns={'model': 'method'})[['method', 'entry_date', 'entry_time', 'entry_price', 'pnl']].to_csv(
        f'{RES}/stage13_round13_blind_trades_LOCAL_ONLY.csv', index=False)
    print(NAME, pat, {k: st[k] for k in ('n', 'G', 'WR', 'S', 'GM', 'G_ci95', 'worst_trade', 'exits', 'excess', 'max_open_at_once')}, flush=True)
    print({y: (p['n'], p['G'], p['WR'], p['S'], p['GM'], p['total_pct']) for y, p in per.items()}, flush=True)


if __name__ == '__main__':
    os.makedirs(RES, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == 'select':
        select()
    elif mode == 'blind':
        blind()
    elif mode == 'freeze_forward':
        freeze_forward()
    elif mode == 'freeze':
        freeze()
    elif mode == 'dry':
        blind(dry=True)
    elif mode == 'verify':
        blind(verify=True)
    else:
        print(__doc__)
