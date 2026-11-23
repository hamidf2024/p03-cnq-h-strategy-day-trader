"""
Stage 12, candidate C: a small PatchTST-style transformer encoder, pretrained
by masked-patch reconstruction on 5-minute bars (self-supervised, so it can
learn from every bar rather than from one label per day), then used as a
frozen feature extractor with a linear (ridge) probe on top.

Why this shape: the project has ~860 training days but ~62,000 training
5-minute bars. A transformer trained end-to-end on 860 labels would simply
memorise them; self-supervised pretraining uses the bars, and the linear
probe keeps the supervised part to a handful of parameters.
"""
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

SLOTS = 78          # 09:30 .. 15:55 five-minute slots
PATCH = 13          # 65 minutes per patch -> 6 patches per day
DAYS = 10           # context window in trading days
NTOK = DAYS * SLOTS // PATCH
CH = 3              # channels: return, range, relative volume


def day_tensor(df5, vol20):
    """Per-day array [SLOTS, CH] on a fixed 5-minute grid. Returns dict
    date -> array. Channel scaling uses vol20 of that day (known before the
    open) so nothing is fitted to future data."""
    out = {}
    prev_close = None
    for date, g in df5.groupby('date', sort=True):
        arr = np.zeros((SLOTS, CH), dtype=np.float32)
        v20 = vol20.get(date, np.nan)
        if not np.isfinite(v20) or v20 <= 0:
            prev_close = g.Close.values[-1]
            out[date] = None
            continue
        slot = ((g.Datetime.dt.hour * 60 + g.Datetime.dt.minute) - 570) // 5
        slot = slot.values.astype(int)
        ok = (slot >= 0) & (slot < SLOTS)
        c = g.Close.values; h = g.High.values; l = g.Low.values; v = g.Volume.values.astype(float)
        ref = np.concatenate([[prev_close if prev_close else g.Open.values[0]], c[:-1]])
        bar_sd = v20 / np.sqrt(SLOTS)
        ret = np.log(c / ref) / bar_sd
        rng = np.log(h / l) / bar_sd
        vm = max(v.mean(), 1.0)
        rv = np.log1p(v / vm)
        arr[slot[ok], 0] = np.clip(ret[ok], -8, 8)
        arr[slot[ok], 1] = np.clip(rng[ok], 0, 8)
        arr[slot[ok], 2] = rv[ok]
        out[date] = arr
        prev_close = c[-1]
    return out


def window(day_arrs, dates, i, mask_final_bar=True):
    """[NTOK, PATCH*CH] window of the DAYS days ending at dates[i]. The final
    5-minute slot of the last day is zeroed: it is not known at decision time."""
    if i < DAYS - 1:
        return None
    arrs = [day_arrs[dates[k]] for k in range(i - DAYS + 1, i + 1)]
    if any(a is None for a in arrs):
        return None
    x = np.stack(arrs).copy()                 # [DAYS, SLOTS, CH]
    if mask_final_bar:
        x[-1, -1, :] = 0.0
    return x.reshape(NTOK, PATCH * CH)


class PatchEncoder(nn.Module):
    def __init__(self, d_model=48, nhead=4, layers=2, ff=96, dropout=0.2):
        super().__init__()
        self.inp = nn.Linear(PATCH * CH, d_model)
        self.pos = nn.Parameter(torch.zeros(1, NTOK, d_model))
        self.mask_token = nn.Parameter(torch.zeros(1, 1, d_model))
        enc = nn.TransformerEncoderLayer(d_model, nhead, ff, dropout, batch_first=True, norm_first=True)
        self.enc = nn.TransformerEncoder(enc, layers)
        self.norm = nn.LayerNorm(d_model)
        self.recon = nn.Linear(d_model, PATCH * CH)
        nn.init.normal_(self.pos, std=0.02); nn.init.normal_(self.mask_token, std=0.02)

    def forward(self, x, mask=None):
        h = self.inp(x)
        if mask is not None:
            h = torch.where(mask.unsqueeze(-1), self.mask_token.expand_as(h), h)
        h = self.norm(self.enc(h + self.pos))
        return h

    def embed(self, x):
        h = self.forward(x)
        # mean over all tokens + mean over the last day's tokens
        return torch.cat([h.mean(1), h[:, -SLOTS // PATCH:].mean(1)], dim=1)


def pretrain(windows, epochs=40, seed=0, mask_ratio=0.4, lr=1e-3, bs=64, verbose=False):
    torch.manual_seed(seed); np.random.seed(seed)
    torch.set_num_threads(2)
    X = torch.tensor(np.stack(windows), dtype=torch.float32)
    model = PatchEncoder()
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
    n = len(X)
    g = torch.Generator().manual_seed(seed)
    hist = []
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(n, generator=g)
        tot = 0.0
        for s in range(0, n, bs):
            xb = X[perm[s:s + bs]]
            mask = torch.rand(xb.shape[0], NTOK, generator=g) < mask_ratio
            h = model(xb, mask)
            rec = model.recon(h)
            loss = ((rec - xb) ** 2)[mask].mean()
            opt.zero_grad(); loss.backward(); opt.step()
            tot += loss.item() * len(xb)
        hist.append(tot / n)
        if verbose and (ep % 10 == 0 or ep == epochs - 1):
            print(f'    pretrain epoch {ep:2d} masked-MSE {tot / n:.4f}')
    model.eval()
    return model, hist


def embed_all(model, wins):
    with torch.no_grad():
        X = torch.tensor(np.stack(wins), dtype=torch.float32)
        return model.embed(X).numpy()
