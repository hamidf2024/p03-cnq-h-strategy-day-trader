"""
Stage 13 preparation: download peer-stock and oil data for the CNQ project.

Sources (see docs/11_Peer_and_Oil_Data_Sources.md for why these were chosen):
  * Alpaca Market Data API, free "Basic" plan -- 5-minute bars since 2016.
    Historical requests may use the consolidated SIP feed as long as the end
    time is at least 15 minutes old. Symbols: CNQ (re-pulled on the same feed),
    SU, CVE, IMO, XOM, CVX, plus USO and XLE as intraday oil / sector proxies.
  * U.S. Energy Information Administration (EIA) -- daily WTI spot price at
    Cushing (series RWTC), public domain.

Run this on a machine that can reach data.alpaca.markets and api.eia.gov
(the cloud research environment cannot), from the repository root:

    python3 src/stage13_download_peer_oil_data.py

It asks for the Alpaca key id and secret (the secret is typed hidden). They
are used for this run only: never written to disk, never printed. To skip the
prompts, set APCA_API_KEY_ID and APCA_API_SECRET_KEY in the environment
(real values, not placeholders); set EIA_API_KEY as well to refresh the EIA
spot series (optional -- it is already saved locally).

Output: one CSV per symbol in data/raw/peers/, in the same layout as
data/raw/CNQ_5min_20200727_to_20261118.csv (US/Eastern timestamps, regular
session 09:30-15:55 bars, split-adjusted, not dividend-adjusted), plus
data/raw/peers/WTI_spot_daily_EIA.csv.

STATUS: request parameters follow Alpaca's and EIA's published API
documentation; paging, time-zone conversion and session filtering are unit
tested with mocked responses (run with `selftest`). The research environment
cannot reach the live APIs, so the first live run is the owner's.

Licence note: Alpaca states that API data may not be redistributed. Keep the
downloaded files private (do not commit them to a public repository) unless
the owner has confirmed otherwise.
"""
import csv
import getpass
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

SYMBOLS = ['CNQ', 'SU', 'CVE', 'IMO', 'XOM', 'CVX', 'USO', 'XLE']
START = '2020-07-27'
OUT_DIR = 'data/raw/peers'
ALPACA_URL = 'https://data.alpaca.markets/v2/stocks/bars'
EIA_URL = 'https://api.eia.gov/v2/petroleum/pri/spt/data/'
NY = ZoneInfo('America/New_York')


def _ssl_context():
    """Certificate verification stays ON. python.org builds of Python on macOS
    ship without a CA bundle until "Install Certificates.command" is run, so
    look for one in the usual places instead of failing."""
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx.load_verify_locations(certifi.where())
    except Exception:
        pass
    for path in ('/etc/ssl/cert.pem', '/etc/ssl/certs/ca-certificates.crt'):
        if os.path.exists(path):
            try:
                ctx.load_verify_locations(path)
            except Exception:
                pass
    return ctx


_CTX = None


def _curl_json(url, headers):
    """Fallback that uses the system curl (and so the system certificate store).
    Headers go in through stdin, not the command line, so keys never appear in
    the process list."""
    cfg = 'url = "%s"\n' % url + ''.join('header = "%s: %s"\n' % (k, v) for k, v in (headers or {}).items())
    r = subprocess.run(['curl', '-sS', '--max-time', '90', '-w', '\n%{http_code}', '-K', '-'],
                       input=cfg.encode(), capture_output=True)
    if r.returncode != 0:
        raise RuntimeError('curl failed: ' + r.stderr.decode(errors='replace').strip()[:200])
    body, _, code = r.stdout.decode('utf-8').rpartition('\n')
    if code != '200':
        raise urllib.error.HTTPError(url.split('?')[0], int(code or 0), body[:200], None, None)
    return json.loads(body)


def http_json(url, headers=None):
    global _CTX
    if _CTX is None:
        _CTX = _ssl_context()
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=90, context=_CTX) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:          # rate limit: wait and retry
                time.sleep(15)
                continue
            raise
        except urllib.error.URLError as e:
            if isinstance(e.reason, ssl.SSLCertVerificationError):
                return _curl_json(url, headers)
            if attempt < 4:
                time.sleep(3)
                continue
            raise


def explain_http_error(e, what):
    code = getattr(e, 'code', None)
    if code in (401, 403):
        return (f'{what}: Alpaca did not accept the keys (HTTP {code}). Check that the first value is the one '
                'labelled "Key" and the second the one labelled "Secret", both copied whole from the same '
                '"API Keys" box, with no spaces. If the secret was lost, use "Regenerate" to get a new pair. '
                'If paper-account keys keep being refused, generate keys under the live account instead.')
    if code == 422:
        return f'{what}: the server rejected the request parameters (HTTP 422): {getattr(e, "reason", "")}'
    return f'{what}: HTTP {code}: {getattr(e, "reason", "")}'


PLACEHOLDERS = {'', 'your_key_id', 'your_secret', '...', 'xxx'}


def key_problem(kid, sec):
    """Plain-language reason a pasted value cannot be a key, or None."""
    for name, v in (('key id', kid), ('secret', sec)):
        if v in PLACEHOLDERS:
            return f'The {name} is empty.'
        if '://' in v or '/' in v or 'alpaca.markets' in v.lower():
            return (f'That {name} is a web address. In the API Keys box, "Endpoint" is the address -- do not use it. '
                    'The key id is the value labelled "Key" (usually starts with PK or AK); '
                    'the secret is the longer value labelled "Secret".')
        if any(ch.isspace() for ch in v):
            return f'The {name} contains a space or line break -- copy only the value itself.'
    if kid == sec:
        return 'The key id and the secret are the same value -- they are two different strings.'
    return None


def get_keys():
    kid = os.environ.get('APCA_API_KEY_ID', '').strip()
    sec = os.environ.get('APCA_API_SECRET_KEY', '').strip()
    if key_problem(kid, sec) is None:
        return
    print('Alpaca API keys are needed (Alpaca dashboard, Paper Trading, "API Keys" box).')
    print('The box shows three things: Endpoint (a web address -- NOT needed), Key, and Secret.')
    print('They are used for this run only and are not saved or shown.')
    for _ in range(3):
        kid = input('  Key (usually starts with PK): ').strip()
        sec = getpass.getpass('  Secret (typing is hidden): ').strip()
        problem = key_problem(kid, sec)
        if problem is None:
            os.environ['APCA_API_KEY_ID'], os.environ['APCA_API_SECRET_KEY'] = kid, sec
            return
        print('  ' + problem + ' Try again.' if kid or sec else '')
        if not kid and not sec:
            break
    sys.exit('No usable keys given -- nothing downloaded.')


def alpaca_bars(symbol, start, end, fetch=http_json, feed='sip'):
    """All 5-minute bars for one symbol, following next_page_token."""
    headers = {'APCA-API-KEY-ID': os.environ.get('APCA_API_KEY_ID', ''),
               'APCA-API-SECRET-KEY': os.environ.get('APCA_API_SECRET_KEY', '')}
    bars, token, pages = [], None, 0
    while True:
        q = {'symbols': symbol, 'timeframe': '5Min', 'start': start, 'end': end,
             'limit': 10000, 'adjustment': 'split', 'feed': feed, 'sort': 'asc'}
        if token:
            q['page_token'] = token
        data = fetch(ALPACA_URL + '?' + urllib.parse.urlencode(q), headers)
        bars.extend((data.get('bars') or {}).get(symbol, []))
        token = data.get('next_page_token')
        pages += 1
        if not token:
            return bars, pages
        time.sleep(0.35)          # stay well under 200 requests / minute


def to_session_rows(bars):
    """UTC bars -> US/Eastern rows, regular session only (09:30 .. 15:55)."""
    rows = []
    for b in bars:
        t = datetime.fromisoformat(b['t'].replace('Z', '+00:00')).astimezone(NY)
        minutes = t.hour * 60 + t.minute
        if t.weekday() < 5 and 570 <= minutes <= 955:
            rows.append([t.strftime('%Y-%m-%d %H:%M:%S'), b['o'], b['h'], b['l'], b['c'], b['v'], 0.0, 0.0])
    return rows


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def eia_wti_spot(start, fetch=http_json):
    key = os.environ.get('EIA_API_KEY', '')
    rows, offset = [], 0
    while True:
        q = [('api_key', key), ('frequency', 'daily'), ('data[0]', 'value'), ('facets[series][]', 'RWTC'),
             ('start', start), ('sort[0][column]', 'period'), ('sort[0][direction]', 'asc'),
             ('offset', offset), ('length', 5000)]
        data = fetch(EIA_URL + '?' + urllib.parse.urlencode(q))
        page = (data.get('response') or {}).get('data', [])
        rows.extend([[d['period'], d['value']] for d in page if d.get('value') is not None])
        if len(page) < 5000:
            return rows
        offset += 5000


def main():
    get_keys()
    # SIP history is free only when the end time is at least 15 minutes old
    end = (datetime.now(timezone.utc) - timedelta(minutes=20)).strftime('%Y-%m-%dT%H:%M:%SZ')
    done, failed = [], []
    for s in SYMBOLS:
        try:
            bars, pages = alpaca_bars(s, START, end)
        except urllib.error.HTTPError as e:
            print(explain_http_error(e, s))
            if e.code in (401, 403):
                sys.exit(1)
            failed.append(s)
            continue
        rows = to_session_rows(bars)
        if not rows:
            print(f'{s}: no bars returned')
            failed.append(s)
            continue
        days = len({r[0][:10] for r in rows})
        path = f'{OUT_DIR}/{s}_5min_sip_{START.replace("-", "")}_to_{rows[-1][0][:10].replace("-", "")}.csv'
        write_csv(path, ['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits'], rows)
        print(f'{s}: {len(bars):,} bars fetched in {pages} requests -> {len(rows):,} session bars, {days} days -> {path}')
        done.append(s)
    if os.environ.get('EIA_API_KEY', '').strip():
        try:
            rows = eia_wti_spot('2020-07-01')
            write_csv(f'{OUT_DIR}/WTI_spot_daily_EIA.csv', ['Date', 'WTI_spot_USD_per_bbl'], rows)
            print(f'WTI spot (EIA RWTC): {len(rows)} days, {rows[0][0]} .. {rows[-1][0]}')
        except Exception as e:
            print('EIA refresh skipped:', str(e)[:150])
    print(f'Finished: {len(done)} of {len(SYMBOLS)} symbols saved in {OUT_DIR}/' + (f'; failed: {", ".join(failed)}' if failed else ''))
    print('Next: python3 src/stage13_check_peer_data.py')


def selftest():
    """Mocked responses: paging, time zone, session filter, EIA paging."""
    pages = [
        {'bars': {'SU': [{'t': '2020-07-27T13:25:00Z', 'o': 1, 'h': 1, 'l': 1, 'c': 1, 'v': 5},      # 09:25 ET pre-market
                         {'t': '2020-07-27T13:30:00Z', 'o': 16.0, 'h': 16.2, 'l': 15.9, 'c': 16.1, 'v': 100}]},
         'next_page_token': 'abc'},
        {'bars': {'SU': [{'t': '2020-07-27T19:55:00Z', 'o': 16.1, 'h': 16.3, 'l': 16.0, 'c': 16.2, 'v': 200},   # 15:55 ET
                         {'t': '2020-07-27T20:00:00Z', 'o': 2, 'h': 2, 'l': 2, 'c': 2, 'v': 7},                 # 16:00 ET after close
                         {'t': '2021-01-04T14:30:00Z', 'o': 17.0, 'h': 17.1, 'l': 16.9, 'c': 17.0, 'v': 300}]},  # winter: 09:30 EST
         'next_page_token': None},
    ]
    seen = []

    def fake(url, headers=None):
        seen.append(url)
        return pages[len(seen) - 1]
    bars, n = alpaca_bars('SU', '2020-07-27', '2021-01-05T00:00:00Z', fetch=fake)
    assert n == 2 and len(bars) == 5
    assert 'page_token=abc' in seen[1] and 'feed=sip' in seen[0] and 'adjustment=split' in seen[0] and 'timeframe=5Min' in seen[0]
    rows = to_session_rows(bars)
    assert [r[0] for r in rows] == ['2020-07-27 09:30:00', '2020-07-27 15:55:00', '2021-01-04 09:30:00'], rows
    assert rows[0][1:6] == [16.0, 16.2, 15.9, 16.1, 100]
    e = [{'response': {'data': [{'period': '2020-07-01', 'value': 39.8}, {'period': '2020-07-02', 'value': None}]}}]
    assert eia_wti_spot('2020-07-01', fetch=lambda u, h=None: e[0]) == [['2020-07-01', 39.8]]
    ctx = _ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname      # verification is never switched off
    assert 'HTTP 401' in explain_http_error(urllib.error.HTTPError('u', 401, 'x', None, None), 'SU')
    print('selftest passed: paging, feed/adjustment/timeframe parameters, US/Eastern conversion across DST, session filter, EIA parsing')


if __name__ == '__main__':
    selftest() if (len(sys.argv) > 1 and sys.argv[1] == 'selftest') else main()
