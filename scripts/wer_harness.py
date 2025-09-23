# path: scripts/wer_harness.py
from __future__ import annotations

import glob
import os
from typing import List, Tuple


def _tokenize(s: str) -> List[str]:
    return [t for t in s.lower().strip().split() if t]


def _levenshtein(a: List[str], b: List[str]) -> int:
    # classic DP
    n, m = len(a), len(b)
    dp = [[0]*(m+1) for _ in range(n+1)]
    for i in range(n+1):
        dp[i][0] = i
    for j in range(m+1):
        dp[0][j] = j
    for i in range(1, n+1):
        for j in range(1, m+1):
            cost = 0 if a[i-1] == b[j-1] else 1
            dp[i][j] = min(dp[i-1][j]+1, dp[i][j-1]+1, dp[i-1][j-1]+cost)
    return dp[n][m]


def wer(ref: str, hyp: str) -> float:
    r = _tokenize(ref)
    h = _tokenize(hyp)
    if not r:
        return 0.0 if not h else 1.0
    return _levenshtein(r, h) / float(len(r))


def corpus_wer(ref_dir: str, hyp_dir: str) -> Tuple[float, int]:
    """
    Expects matching filenames in ref_dir and hyp_dir (e.g., clip01.txt in both).
    """
    refs = sorted(glob.glob(os.path.join(ref_dir, "*.txt")))
    scores = []
    count = 0
    for rp in refs:
        name = os.path.basename(rp)
        hp = os.path.join(hyp_dir, name)
        if not os.path.exists(hp):
            continue
        with open(rp, "r", encoding="utf-8") as fr, open(hp, "r", encoding="utf-8") as fh:
            w = wer(fr.read(), fh.read())
            scores.append(w)
            count += 1
    return (sum(scores)/len(scores) if scores else 0.0, count)


def main():
    import argparse
    p = argparse.ArgumentParser(description="WER harness (target ≤ 12%)")
    p.add_argument("--refs", required=True, help="Directory of reference .txt")
    p.add_argument("--hyps", required=True, help="Directory of hypothesis .txt")
    args = p.parse_args()
    w, n = corpus_wer(args.refs, args.hyps)
    print(f"Files compared: {n}")
    print(f"Corpus WER: {w*100:.2f}% — {'PASS' if w <= 0.12 else 'FAIL'} (target ≤ 12%)")
    print("Method: WER over word tokens with classic Levenshtein; lower is better.")

if __name__ == "__main__":
    main()
