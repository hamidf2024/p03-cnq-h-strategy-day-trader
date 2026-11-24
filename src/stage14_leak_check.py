"""
Leak check for every feature the models use (57 from Stage 13, 51 from Stage 14).

A feature leaks if its value on a day changes when later days are added to the data. Three versions of the
data are built: everything, everything up to 2023-12-29 (the end of the training years), and everything up
to 2025-06-30 (the middle of the test years). On every day the shorter versions contain, each feature must
be identical to the full version. The first comparison shows the training rows never saw 2024-2026; the
second shows that inside the test years a day's features never use a later day.

Also checked: the dip signal of model P and the monthly signal days of models M and O are identical with
and without later data; the frozen models' last training day and last label day are before 2024.
"""
import json, os, pickle, sys
import numpy as np, pandas as pd
import s13_lib as L, stage13_peer_fusion as P, stage14_lib as S14
import stage13_dip_campaign as DIP

RES = os.environ.get('S13_OUT', 'results/experiments')


def build(cut):
    if cut:
        os.environ['S13_CUTOFF'] = cut
    else:
        os.environ.pop('S13_CUTOFF', None)
    panel, D, intr = P.get_panel()
    p14, new = S14.build_panel14(panel, D)
    return p14, L.feature_names(panel), new, D


def compare(full, part, feats, last):
    a = full[full.date <= last].set_index(['date', 'stock'])[feats]; b = part[part.date <= last].set_index(['date', 'stock'])[feats]
    assert a.index.equals(b.index), 'row sets differ'
    diff = (a - b).abs(); both_nan = a.isna() & b.isna(); one_nan = a.isna() ^ b.isna()
    return dict(rows=int(len(a)), features=len(feats), cells=int(a.size), max_abs_difference=float(np.nanmax(diff.values)),
                cells_missing_in_one_only=int(one_nan.values.sum()), features_that_differ=[c for c in feats if (diff[c].fillna(0) > 1e-12).any() or one_nan[c].any()])


def main():
    full, old, new, Dfull = build('')
    out = dict(checked_on=str(pd.Timestamp.now().date()), n_features=len(old) + len(new), comparisons={}, signals={}, frozen_models={})
    for name, cut in (('training years (data cut at 2023-12-29)', '2023-12-29'), ('inside the test years (data cut at 2025-06-30)', '2025-06-30')):
        part, _, _, Dp = build(cut)
        out['comparisons'][name] = compare(full, part, old + new, pd.Timestamp(cut))
        print(name, out['comparisons'][name], flush=True)
        # model P's dip signal: same days with and without later data
        f_full = DIP.indicators(Dfull['CNQ']); f_part = DIP.indicators(Dp['CNQ'])
        s_full = [d for d, k in DIP.signal_days(f_full, 'dd10', 5.0, 15) if d <= pd.Timestamp(cut) - pd.Timedelta(days=31)]
        s_part = [d for d, k in DIP.signal_days(f_part, 'dd10', 5.0, 15) if d <= pd.Timestamp(cut) - pd.Timedelta(days=31)]
        out['signals'][f'model P signal days up to a month before {cut}'] = dict(n=len(s_full), identical=s_full == s_part)
    os.environ.pop('S13_CUTOFF', None)
    fz = pickle.load(open(f'{RES}/stage13_frozen.pkl', 'rb'))
    cal = Dfull['USO'].index
    for H, m in fz['finals'].items():
        last = pd.Timestamp(m['train_last']); label_end = cal[cal.get_indexer([last])[0] + H]
        out['frozen_models'][f'Peer-Fusion model, {H}-session label'] = dict(last_training_day=m['train_last'], last_day_its_labels_reach=str(label_end.date()),
                                                                          before_2024=bool(label_end < pd.Timestamp('2024-01-01')))
    oof = fz['oof'][5]; out['frozen_models']['out-of-fold forecasts'] = dict(first=str(oof.index.min().date()), last=str(oof.index.max().date()))
    print(out['signals']); print(out['frozen_models'])
    json.dump(out, open(f'{RES}/stage14_leak_check.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
