import csv, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import train_real as T

ROOT = os.path.dirname(HERE)
CREW = ["C001", "C002", "C003", "C004"]

def band(p):
    return math.exp(p["log_mean"] - T.Z95 * p["sd"]), math.exp(p["log_mean"] + T.Z95 * p["sd"])

def r(x, n=4):
    return float(f"{x:.{n}g}")

def main():
    d = json.load(open(T.IN, encoding="utf-8"))
    rows, nulls = [], []
    for a in d["analytes"]:
        sig = T.sigma_log(a["cvi"])
        vals = {c: a["crew"][c]["values"] for c in CREW}
        bases = {c: [vals[c][i] for i in T.PRE] for c in CREW}
        for held in CREW:
            train = [c for c in CREW if c != held]
            sigc = T.calib_sigma(sig, [bases[c] for c in train])
            pairs = []
            for c in train:
                p = T.predict(bases[c], sigc)
                v = vals[c][T.R1]
                if p and v and v > 0:
                    pairs.append((p["expected"], v))
            sh = T.learn_shift(pairs, sigc, 3)
            obs = vals[held][T.R1]
            p1 = T.predict(bases[held], sig)
            if not p1 or not obs or obs <= 0:
                continue
            p1c = T.predict(bases[held], sigc)
            p2 = T.predict(bases[held], sigc, sh)
            row = {"marker": a["label"], "unit": a.get("unit", ""), "astronaut": held,
                   "preflight_L92": bases[held][0], "preflight_L44": bases[held][1], "preflight_L3": bases[held][2],
                   "real_value_R1": obs, "flight_shift_learned_pct": r((math.exp(sh["shift"]) - 1) * 100, 3)}
            for name, p in (("own_average_only", p1), ("plus_natural_variation", p1c), ("sage", p2)):
                lo, hi = band(p)
                z = T.zscore(obs, p)
                row.update({f"{name}_expected": r(p["expected"]), f"{name}_low95": r(lo), f"{name}_high95": r(hi),
                            f"{name}_inside": "yes" if abs(z) <= T.Z95 else "no"})
            rows.append(row)
        for c in CREW:
            v = vals[c][2]
            p = T.predict([vals[c][0], vals[c][1]], sig)
            pc = T.predict([vals[c][0], vals[c][1]], T.calib_sigma(sig, [bases[o] for o in CREW if o != c]))
            if p and v and v > 0:
                nulls.append({"marker": a["label"], "unit": a.get("unit", ""), "astronaut": c,
                              "preflight_L92": vals[c][0], "preflight_L44": vals[c][1], "real_value_L3": v,
                              "textbook_low95": r(band(p)[0]), "textbook_high95": r(band(p)[1]),
                              "textbook_alert": "yes" if abs(T.zscore(v, p)) > T.Z95 else "no",
                              "calibrated_low95": r(band(pc)[0]), "calibrated_high95": r(band(pc)[1]),
                              "calibrated_alert": "yes" if abs(T.zscore(v, pc)) > T.Z95 else "no"})
    for path, data in (("predictions.csv", rows), ("null_test.csv", nulls)):
        with open(os.path.join(ROOT, "results", path), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)
    n = len(rows)
    count = lambda k: sum(1 for x in rows if x[k] == "yes")
    print(f"predictions.csv: {n} rows. Inside the 95% range: own average {count('own_average_only_inside')}, "
          f"+ natural variation {count('plus_natural_variation_inside')}, SAGE {count('sage_inside')}")
    print(f"null_test.csv: {len(nulls)} rows. False alarms: textbook {sum(1 for x in nulls if x['textbook_alert'] == 'yes')}, "
          f"calibrated {sum(1 for x in nulls if x['calibrated_alert'] == 'yes')}")

if __name__ == "__main__":
    main()
