"""
Stage 13 preparation: quality checks on the downloaded peer and oil data
(docs/11_Peer_and_Oil_Data_Sources.md, Section 4). Run from the repository
root after src/stage13_download_peer_oil_data.py:

    python3 src/stage13_check_peer_data.py

It reports on whatever is present in data/raw/peers/ and says what is still
missing, so it can be run before the stock files arrive. The raw files stay
local; only this script's summary (no prices) is written to
results/experiments/stage13_data_checks.json.

Checks
  1. inventory        which expected files are missing
  2. completeness     empty cells, non-positive prices, zero-volume bars,
                      trading days vs the CNQ reference file, bars per day,
                      gap days (under 20 bars), duplicate timestamps, session
                      bounds
  3. splits           largest overnight close-to-open move per symbol
  4. feed comparison  CNQ on the consolidated feed vs the existing IEX file
  5. oil              EIA spot coverage; spot vs USO and vs CNQ daily returns
"""
import glob
import json
import os
import numpy as np
import pandas as pd

REF = 'data/raw/CNQ_5min_20200727_to_20261118.csv'
PEERS = 'data/raw/peers'
SYMBOLS = ['CNQ', 'SU', 'CVE', 'IMO', 'XOM', 'CVX', 'USO', 'XLE']
OUT = 'results/experiments/stage13_data_checks.json'


def load_5min(path):
    df = pd.read_csv(path, parse_dates=['Datetime'])
    df['date'] = df.Datetime.dt.normalize()
    return df


def daily(df):
    g = df.groupby('date')
    return pd.DataFrame({'o': g.Open.first(), 'h': g.High.max(), 'l': g.Low.min(),
                         'c': g.Close.last(), 'v': g.Volume.sum(), 'n': g.Close.size()})


def main():
    rep = {'symbols': {}, 'missing': []}
    ref = load_5min(REF)
    ref_d = daily(ref)
    ref_days = set(ref_d.index)
    rep['reference'] = {'file': REF, 'days': len(ref_d), 'first': str(ref_d.index[0].date()), 'last': str(ref_d.index[-1].date())}
    dailies = {}
    for s in SYMBOLS:
        files = sorted(glob.glob(f'{PEERS}/{s}_5min_sip_*.csv'))
        if not files:
            rep['missing'].append(f'{s} 5-minute bars')
            continue
        df = load_5min(files[-1])
        d = daily(df)
        dailies[s] = d
        tm = df.Datetime.dt.hour * 60 + df.Datetime.dt.minute
        days = set(d.index)
        common = sorted(days & ref_days)
        jump = (np.log(d.o / d.c.shift(1))).abs()
        rec = {'file': os.path.basename(files[-1]), 'bars': int(len(df)), 'days': int(len(d)),
               'first': str(d.index[0].date()), 'last': str(d.index[-1].date()),
               'days_missing_vs_reference': int(len(ref_days - days)),
               'days_extra_vs_reference': int(len(days - ref_days)),
               'bars_per_day_median': float(d.n.median()), 'days_under_70_bars': int((d.n < 70).sum()),
               'empty_cells': int(df[['Open', 'High', 'Low', 'Close', 'Volume']].isna().sum().sum()),
               'non_positive_prices': int((df[['Open', 'High', 'Low', 'Close']] <= 0).sum().sum()),
               'zero_volume_bars': int((df.Volume <= 0).sum()),
               'gap_days_under_20_bars': [str(x.date()) for x in d.index[d.n < 20]],
               'duplicate_timestamps': int(df.Datetime.duplicated().sum()),
               'bars_outside_0930_1555': int(((tm < 570) | (tm > 955)).sum()),
               'bad_ohlc_rows': int(((df.High < df.Low) | (df.Close > df.High) | (df.Close < df.Low)).sum()),
               'largest_overnight_move_pct': round(float(jump.max() * 100), 2),
               'largest_overnight_move_date': str(jump.idxmax().date()),
               'overnight_moves_over_20pct': int((jump > 0.20).sum())}
        if s == 'CNQ':
            a = d.c.reindex(common); b = ref_d.c.reindex(common)
            diff = (a / b - 1).abs() * 100
            m = df.merge(ref, on='Datetime', suffixes=('_sip', '_iex'))
            bdiff = (m.Close_sip / m.Close_iex - 1).abs() * 100
            rec['sip_vs_iex'] = {'common_days': len(common),
                                 'daily_close_diff_pct_median': round(float(diff.median()), 4),
                                 'daily_close_diff_pct_max': round(float(diff.max()), 3),
                                 'common_5min_bars': int(len(m)), 'iex_bars': int(len(ref)), 'sip_bars': int(len(df)),
                                 'bar_close_diff_pct_median': round(float(bdiff.median()), 4),
                                 'bar_close_diff_pct_p99': round(float(bdiff.quantile(0.99)), 3),
                                 'daily_return_correlation': round(float(np.log(a).diff().corr(np.log(b).diff())), 5)}
        rep['symbols'][s] = rec
    # oil
    wpath = f'{PEERS}/WTI_spot_daily_EIA.csv'
    if os.path.exists(wpath):
        w = pd.read_csv(wpath, parse_dates=['Date']).set_index('Date').iloc[:, 0]
        wr = np.log(w.where(w > 0)).diff()
        oil = {'days': int(len(w)), 'first': str(w.index[0].date()), 'last': str(w.index[-1].date()),
               'non_positive_prices': int((w <= 0).sum()), 'largest_daily_move_pct': round(float(wr.abs().max() * 100), 2),
               'reference_trading_days_without_spot': int(len([x for x in ref_days if x not in w.index and x >= w.index[0] and x <= w.index[-1]]))}
        cnq_r = np.log(ref_d.c).diff()
        j = pd.concat([wr.rename('w'), cnq_r.rename('c')], axis=1, sort=True).dropna()
        oil['corr_spot_vs_CNQ_daily_returns'] = round(float(j.w.corr(j.c)), 3)
        oil['corr_spot_vs_CNQ_by_year'] = {int(y): round(float(g.w.corr(g.c)), 3) for y, g in j.groupby(j.index.year)}
        if 'USO' in dailies:
            u = np.log(dailies['USO'].c).diff()
            k = pd.concat([wr.rename('w'), u.rename('u')], axis=1, sort=True).dropna()
            oil['corr_spot_vs_USO_daily_returns'] = round(float(k.w.corr(k.u)), 3)
            oil['days_spot_and_USO_differ_by_over_5pct'] = int(((k.w - k.u).abs() > 0.05).sum())
        rep['oil'] = oil
    else:
        rep['missing'].append('EIA WTI spot')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(rep, open(OUT, 'w'), indent=1)
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()
