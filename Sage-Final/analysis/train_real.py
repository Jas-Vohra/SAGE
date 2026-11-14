import json, math, os, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
IN = os.path.join(HERE, "i4_blood.json")
OUT_MODEL = os.path.join(ROOT, "results", "sage_blood_model.json")
OUT_EVAL = os.path.join(ROOT, "results", "evaluation.json")

VISITS = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"]
PRE = [0, 1, 2]
R1 = 3
Z95 = 1.96

def sigma_log(cvi):
    cv = math.sqrt(cvi ** 2 + (cvi / 2.0) ** 2) / 100.0
    return math.sqrt(math.log(1.0 + cv * cv))

NU0 = 4

def calib_sigma(sig_eflm, base_lists):
    ss, df = 0.0, 0
    for vals in base_lists:
        lv = [math.log(v) for v in vals if v is not None and v > 0]
        if len(lv) >= 2:
            m = st.mean(lv)
            ss += sum((x - m) ** 2 for x in lv)
            df += len(lv) - 1
    return math.sqrt((NU0 * sig_eflm ** 2 + ss) / (NU0 + df))
def learn_shift(pairs, sig, k):
    d = [math.log(v / b) for b, v in pairs if b and v and b > 0 and v > 0]
    n = len(d)
    if n == 0:
        return {"n": 0, "shift": 0.0, "raw": 0.0, "w": 0.0, "tau2": 0.0, "se2": 0.0}
    mean = st.mean(d)
    noise = sig * sig * (1.0 + 1.0 / k)
    s2 = st.variance(d) if n >= 2 else noise
    tau2 = max(0.0, s2 - noise)
    se2 = s2 / n
    w = mean * mean / (mean * mean + se2) if (mean * mean + se2) > 0 else 0.0
    return {"n": n, "shift": w * mean, "raw": mean, "w": w, "tau2": tau2, "se2": se2}

def predict(base_vals, sig, shift=None):
    pre = [v for v in base_vals if v is not None and v > 0]
    k = len(pre)
    if k == 0:
        return None
    lb = st.mean(math.log(v) for v in pre)
    var = sig * sig * (1.0 + 1.0 / k)
    mu = lb
    if shift is not None:
        mu += shift["shift"]
        var += shift["tau2"] + shift["se2"] * shift["w"] ** 2
    return {"log_mean": mu, "sd": math.sqrt(var), "expected": math.exp(mu), "k": k}

def zscore(obs, pred):
    return (math.log(obs) - pred["log_mean"]) / pred["sd"]
def main():
    d = json.load(open(IN, encoding="utf-8"))
    crew_ids = ["C001", "C002", "C003", "C004"]
    rows = []
    null_rows = []
    model = {"analytes": [], "crew": crew_ids, "visits": VISITS}
    dq = []

    for a in d["analytes"]:
        cvi = a["cvi"]
        sig = sigma_log(cvi)
        vals = {c: a["crew"][c]["values"] for c in crew_ids}
        bases = {c: [vals[c][i] for i in PRE] for c in crew_ids}

        for c in crew_ids:
            rs = [tuple(r) for r in (a["crew"][c].get("ranges") or []) if r]
            if len(set(rs)) > 1:
                dq.append({"analyte": a["key"], "label": a["label"], "crew": c,
                           "ranges": [list(r) if r else None for r in a["crew"][c]["ranges"]]})

        for held in crew_ids:
            train = [c for c in crew_ids if c != held]
            sigc = calib_sigma(sig, [bases[c] for c in train])
            pairs = []
            for c in train:
                p = predict(bases[c], sigc)
                v = vals[c][R1]
                if p and v and v > 0:
                    pairs.append((p["expected"], v))
            k_typ = 3
            sh = learn_shift(pairs, sigc, k_typ)
            sh_raw = dict(sh, shift=sh["raw"], w=1.0)
            obs = vals[held][R1]
            p1 = predict(bases[held], sig)
            if not p1 or not obs or obs <= 0:
                continue
            p1c = predict(bases[held], sigc)
            p2 = predict(bases[held], sigc, sh)
            p2u = predict(bases[held], sigc, sh_raw)
            rng = a["crew"][held]["range"]
            rows.append({
                "analyte": a["key"], "crew": held,
                "obs": obs,
                "m1_err": abs(math.log(obs) - p1["log_mean"]),
                "m2_err": abs(math.log(obs) - p2["log_mean"]),
                "m2u_err": abs(math.log(obs) - p2u["log_mean"]),
                "m1_z": zscore(obs, p1), "m1c_z": zscore(obs, p1c),
                "m2_z": zscore(obs, p2), "m2u_z": zscore(obs, p2u),
                "m0_flag": (rng is not None and not (rng[0] <= obs <= rng[1])),
            })

        for c in crew_ids:
            v = vals[c][2]
            p = predict([vals[c][0], vals[c][1]], sig)
            pc = predict([vals[c][0], vals[c][1]], calib_sigma(sig, [bases[o] for o in crew_ids if o != c]))
            if p and v and v > 0:
                rng = (a["crew"][c].get("ranges") or [None] * 7)[2]
                null_rows.append({"analyte": a["key"], "crew": c, "z": zscore(v, p), "zc": zscore(v, pc),
                                  "m0_flag": (rng is not None and not (rng[0] <= v <= rng[1]))})
        sig_all = calib_sigma(sig, [bases[c] for c in crew_ids])
        pairs_all = []
        for c in crew_ids:
            p = predict(bases[c], sig_all)
            v = vals[c][R1]
            if p and v and v > 0:
                pairs_all.append((p["expected"], v))
        sh_all = learn_shift(pairs_all, sig_all, 3)
        per_crew = {}
        for c in crew_ids:
            p1 = predict(bases[c], sig_all)
            if not p1:
                continue
            p2 = predict(bases[c], sig_all, sh_all)
            zs = {}
            for i in range(3, 7):
                v = vals[c][i]
                if v and v > 0:
                    zs[VISITS[i]] = round(zscore(v, p1), 3)
            r1 = vals[c][R1]
            per_crew[c] = {
                "values": vals[c],
                "ranges": a["crew"][c].get("ranges"),
                "baseline": round(p1["expected"], 4),
                "baseline_band": [round(p1["expected"] * math.exp(-Z95 * p1["sd"]), 4),
                                  round(p1["expected"] * math.exp(Z95 * p1["sd"]), 4)],
                "z_vs_baseline": zs,
                "expected_r1": round(p2["expected"], 4),
                "expected_r1_band": [round(p2["expected"] * math.exp(-Z95 * p2["sd"]), 4),
                                     round(p2["expected"] * math.exp(Z95 * p2["sd"]), 4)],
                "z_r1_vs_expected": round(zscore(r1, p2), 3) if r1 and r1 > 0 else None,
            }
        model["analytes"].append({
            "key": a["key"], "label": a["label"], "unit": a["unit"], "panel": a["panel"],
            "system": a["system"], "system_label": a["system_label"], "study": a["study"],
            "cvi": cvi, "cvi_source": a.get("cvi_source"), "sigma_log_eflm": round(sig, 6),
            "sigma_log": round(sig_all, 6),
            "rcv_pct": round(a["rcv"], 2) if a.get("rcv") else None,
            "shift": {k: round(v, 6) if isinstance(v, float) else v for k, v in sh_all.items()},
            "shift_pct": round((math.exp(sh_all["shift"]) - 1) * 100, 2),
            "crew": per_crew,
        })

    def frac(xs):
        return sum(xs) / len(xs) if xs else None

    n = len(rows)
    mae = lambda key: st.mean(r[key] for r in rows)
    by_an = {}
    for r in rows:
        by_an.setdefault(r["analyte"], []).append(r)
    wins2 = sum(1 for k, rs in by_an.items() if st.mean(x["m2_err"] for x in rs) < st.mean(x["m1_err"] for x in rs))
    wins2u = sum(1 for k, rs in by_an.items() if st.mean(x["m2u_err"] for x in rs) < st.mean(x["m1_err"] for x in rs))
    cov = lambda key: frac([abs(r[key]) <= Z95 for r in rows])
    flags = lambda key: sum(1 for r in rows if abs(r[key]) > Z95)

    recovery = {}
    for vi in [4, 5, 6]:
        within, tot = 0, 0
        for a in model["analytes"]:
            for c, pc in a["crew"].items():
                z = pc["z_vs_baseline"].get(VISITS[vi])
                if z is not None:
                    tot += 1
                    within += abs(z) <= Z95
        recovery[VISITS[vi]] = [within, tot]
    r1_beyond = sum(1 for a in model["analytes"] for c, pc in a["crew"].items()
                    if pc["z_vs_baseline"].get("R+1") is not None and abs(pc["z_vs_baseline"]["R+1"]) > Z95)
    r1_tot = sum(1 for a in model["analytes"] for c, pc in a["crew"].items() if pc["z_vs_baseline"].get("R+1") is not None)
    strongest = sorted(model["analytes"], key=lambda a: -abs(a["shift"]["shift"]))[:8]
    ev = {
        "data": {
            "source": "NASA OSDR OSD-569 + OSD-575 (Inspiration4, Sept 2021, 3-day flight)",
            "astronauts": 4, "visits": VISITS, "markers": len(model["analytes"]),
            "measurements_used": sum(1 for a in model["analytes"] for c in a["crew"].values() for v in c["values"] if v is not None),
            "simulated_values": 0,
        },
        "method": "Leave-one-astronaut-out. Shift learned from 3 astronauts, tested on the 4th, repeated 4 times.",
        "held_out_predictions": n,
        "forecast_error_pct": {
            "M1_baseline_only": round(mae("m1_err") * 100, 2),
            "M2_SAGE_shrunk_shift": round(mae("m2_err") * 100, 2),
            "M2u_unshrunk_shift": round(mae("m2u_err") * 100, 2),
            "note": "Mean absolute log error x 100, about equal to the average % miss on the held-out astronaut's R+1 value.",
        },
        "markers_where_model_beats_baseline": {"M2_SAGE": [wins2, len(by_an)], "M2u_unshrunk": [wins2u, len(by_an)]},
        "interval_coverage_95": {"M1_baseline_only": round(cov("m1_z"), 3),
                                 "M1c_calibrated_baseline": round(cov("m1c_z"), 3), "M2_SAGE": round(cov("m2_z"), 3),
                                 "M2u_unshrunk": round(cov("m2u_z"), 3),
                                 "note": "Share of held-out R+1 values inside the 95% expected band. Closer to 0.95 = honest uncertainty."},
        "alerts_on_return_day": {
            "M0_outside_lab_range": [sum(1 for r in rows if r["m0_flag"]), n],
            "M1_beyond_personal_baseline": [flags("m1_z"), n],
            "M1c_beyond_calibrated_baseline": [flags("m1c_z"), n],
            "M2_beyond_SAGE_expected": [flags("m2_z"), n],
        },
        "ground_null_test": {
            "what": "L-92 and L-44 predict L-3. No flight happened, so every alert here is a false alert.",
            "personal_baseline_false_alerts_EFLM_only": [sum(1 for r in null_rows if abs(r["z"]) > Z95), len(null_rows)],
            "personal_baseline_false_alerts_SAGE_calibrated": [sum(1 for r in null_rows if abs(r["zc"]) > Z95), len(null_rows)],
            "lab_range_flags_on_ordinary_day": [sum(1 for r in null_rows if r["m0_flag"]), len(null_rows)],
        },
        "return_day_changes_beyond_personal_baseline": [r1_beyond, r1_tot],
        "recovery_within_personal_baseline": recovery,
        "largest_learned_shifts": [{"marker": a["label"], "shift_pct": a["shift_pct"], "weight": round(a["shift"]["w"], 3)} for a in strongest],
        "data_quality_findings": {
            "lab_range_changed_between_visits_same_person": dq,
            "hemoglobin_unit": "OSD-569 transformed header says 'percent'; the original submitted file says g/dL. g/dL used.",
        },
        "limits": [
            "4 astronauts, one 3-day commercial flight: not long-duration ISS, Moon or Mars.",
            "Blood tests only (no daily vitals are public for these crew).",
            "No clinical diagnosis labels exist, so this measures prediction and alert behaviour, not disease detection.",
            "CVA = CVI/2 is an assumption (desirable analytical performance), not the lab's measured imprecision.",
            "EFLM within-person variation alone was too narrow for these crew and assays (see ground null test), so SAGE calibrates it on the crew's own pre-flight repeats (prior weight NU0 = 4 df, a stated setting).",
        ],
    }
    os.makedirs(os.path.dirname(OUT_MODEL), exist_ok=True)
    json.dump(model, open(OUT_MODEL, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(ev, open(OUT_EVAL, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({k: ev[k] for k in ["forecast_error_pct", "markers_where_model_beats_baseline",
                                          "interval_coverage_95", "alerts_on_return_day", "ground_null_test",
                                          "return_day_changes_beyond_personal_baseline", "recovery_within_personal_baseline",
                                          "largest_learned_shifts"]}, indent=1))
    print("data-quality range switches:", [(x["analyte"], x["crew"]) for x in dq])

if __name__ == "__main__":
    main()
