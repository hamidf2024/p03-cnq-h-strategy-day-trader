"""
Stage 14, step 1 (training years only): does the new information help?

Walk-forward on 2021, 2022, 2023 (each year predicted by a model trained only on earlier rows, with the label
horizon purged). Two pooled gradient-boosted models per horizon, same settings and seeds as Stage 13's model E:
    OLD   the 57 Stage 13 features
    NEW   the same plus the Stage 14 features
Compared by the rank correlation between forecast and realised forward return, out of sample, for CNQ and
for all six stocks, at 5 and 20 sessions. Run with S13_CUTOFF=2023-12-29; nothing here touches 2024-2026.
"""
import json, os, pickle, sys
import numpy as np, pandas as pd
import s13_lib as L, stage13_peer_fusion as P, stage14_lib as S14

RES = os.environ.get('S13_OUT', 'results/experiments')


def main():
    cut = os.environ.get('S13_CUTOFF', ''); assert cut and cut <= '2023-12-31'
    panel, D, intr = P.get_panel(); cal = D['USO'].index
    assert cal.max() <= pd.Timestamp('2023-12-31')
    old = L.feature_names(panel)
    p14, new = S14.build_panel14(panel, D)
    print('old features', len(old), '| new features', len(new), '| rows', len(p14), flush=True)
    cover = p14[p14.date >= '2021-01-01'][new].notna().mean().round(3)
    print('new-feature coverage 2021-2023 (lowest five):', cover.sort_values().head(5).to_dict(), flush=True)
    out = dict(cutoff=cut, n_old=len(old), n_new=len(new), new_features=new, folds={}, summary={})
    preds = {}
    for H in (5, 20):
        for name, feats in (('OLD', old), ('NEW', old + new)):
            parts = []
            for y in P.VAL_YEARS:
                days = cal[cal.year == y]
                tr = P.train_rows(p14, cal, days[0], H)
                mu = float(p14.loc[tr, f'fwd{H}'].mean()); yl = P.label(p14, H, mu)
                ms = P.fit_gbm(p14.loc[tr, feats], yl[tr])
                te = p14[p14.date.isin(days) & p14.valid]
                parts.append(te[['date', 'stock', f'fwd{H}']].assign(pred=np.mean([m.predict(te[feats]) for m in ms], axis=0)))
                if name == 'NEW' and y == 2023:
                    imp = pd.Series(np.mean([m.feature_importances_ for m in ms], axis=0), index=feats).sort_values(ascending=False)
                    out.setdefault('importance_2023_fold', {})[H] = {k: round(float(v), 1) for k, v in imp.head(15).items()}
                    out.setdefault('share_of_importance_from_new', {})[H] = round(float(imp[new].sum() / imp.sum()), 3)
            preds[(H, name)] = pd.concat(parts)
        for scope in ('CNQ', 'all six'):
            row = {}
            for name in ('OLD', 'NEW'):
                q = preds[(H, name)]; q = q[q.stock == 'CNQ'] if scope == 'CNQ' else q
                ic = {int(y): round(float(g.pred.corr(g[f'fwd{H}'], method='spearman')), 3) for y, g in q.groupby(q.date.dt.year)}
                ic['all'] = round(float(q.pred.corr(q[f'fwd{H}'], method='spearman')), 3)
                # top-fifth minus bottom-fifth forward return, per year, by daily cross-section-free quintile of the forecast
                qs = q.dropna().copy(); qs['q'] = qs.groupby(qs.date.dt.year).pred.transform(lambda s: pd.qcut(s, 5, labels=False, duplicates='drop'))
                ic['top_minus_bottom_pct'] = round(float(qs[qs.q == 4][f'fwd{H}'].mean() - qs[qs.q == 0][f'fwd{H}'].mean()), 2)
                row[name] = ic
            out['summary'][f'H{H} {scope}'] = row
            print(f'H={H:2d} {scope:8s} OLD', row['OLD'], '| NEW', row['NEW'], flush=True)
    print('share of model importance from the new features:', out['share_of_importance_from_new'])
    print('top features, 20-session model, 2023 fold:', list(out['importance_2023_fold'][20].items())[:10])
    pickle.dump({k: v for k, v in preds.items()}, open(f'{RES}/stage14_oof_predictions_LOCAL_ONLY.pkl', 'wb'))       # no prices: forecasts and forward returns
    json.dump(out, open(f'{RES}/stage14_information_test.json', 'w'), indent=1)


if __name__ == '__main__':
    main()
