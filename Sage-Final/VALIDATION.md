# How we tested SAGE on real NASA astronaut data


**Short answer:** we hid one astronaut at a time and asked SAGE to predict their blood values on the day after landing, using only the information it had gathered from the other three. SAGE's "95% range" picked up 120 of the 128 actual values (93.8%) as opposed to 91 of the 128 (71.1%) from the astronaut's own pre-flight average. On a normal pre-flight day the calibration would have reduced the number of false alarms from 39 to 20 out of 128.

Everything below can be re-run with one command (see [Reproduce it](#reproduce-it-yourself)).

## The data

NASA's Inspiration4 mission (September 2021, 3 days in orbit, 4 civilian crew) collected blood before and after flight and published it in NASA's Open Science Data Repository (OSDR):

- [OSD-569](https://osdr.nasa.gov/bio/repo/data/studies/OSD-569): complete blood count
- [OSD-575](https://osdr.nasa.gov/bio/repo/data/studies/OSD-575): metabolic, cardiovascular and immune panels

| Before flight | After landing |
|---|---|
| 92, 44 and 3 days before launch (L-92, L-44, L-3) | 1, 45, 82 and 194 days after return (R+1, R+45, R+82, R+194) |

We used **32 blood markers** and **894 real measurements**. No value is simulated, estimated or made up. The prepared values are in [`analysis/i4_blood.json`](analysis/i4_blood.json).

## The reason behind it

Can SAGE predict a person's blood values on the day after landing, from only their own pre-flight tests plus what it learned from other astronauts, and is it honest about how sure it is?

## A fair test: leave one astronaut out

1. Hide an astronaut.
2. SAGE learns from the other 3 astronauts what is the typical variation of each marker post-landing and the variation in healthy people.
3. SAGE will predict the 32 values for the hidden astronaut for the day post-landing with a 95% confidence interval.
4. Repeat this for each astronaut.

4 Astronauts x 32 Markers = 128 predictions for individuals that SAGE has never seen before.

## What a "95% range" means

For each value SAGE says: "I am 95% sure the real value will land between this low number and this high number." If that promise is honest, about 95 of every 100 real values should land inside. If far fewer do, the range is overconfident, and overconfident ranges cause false alarms.

## The three methods compared

| Method | What it does |
|---|---|
| Own pre-flight average only | The astronaut's own average from the three pre-flight tests, with the textbook day-to-day variation for healthy people (EFLM Biological Variation Database, plus a standard allowance for lab error). It knows nothing about spaceflight. |
| + natural variation | The same, but SAGE first measures how much these crew members actually varied across their pre-flight tests, and widens the range to match (the textbook value counts as 4 extra data points). |
| SAGE | All of the above, plus the change spaceflight causes, learned from the other three astronauts. The learned change is shrunk towards zero when the astronauts disagreed, so SAGE never over-trusts a pattern seen in three people. |

## Results

| Method | Real values inside the 95% range | Share |
|---|---|---|
| Own pre-flight average only | 91 of 128 | 71.1% |
| + natural variation | 107 of 128 | 83.6% |
| **SAGE** | **120 of 128** | **93.8%** (target 95%) |

**The same result counted as alarms:** after landing, 37 values fell outside the plain range but only 8 outside SAGE's. Spaceflight changes blood in normal ways (for example, inflammation markers rise and lymphocytes fall); SAGE expects those changes, so it does not raise alarms for them. With an honest 95% range about 6 of 128 values would fall outside by chance, so 8 is close to that. (The standard lab reference range flags only 5, because it is built for the whole population and is wide enough to hide a big change in one person.)

**A separate test with no flight at all:** each astronaut's L-92 and L-44 tests predicted their L-3 test. Nothing happened in between, so every alert is a false alarm. Textbook variation raised **39** of 128; after SAGE's calibration, **20**.

## Worked example: glucose, astronaut C004 (mg/dL)

1. Pre-flight values 100, 83, 56. Average of 77.5.
2. Actual value the day after landing was 97.
3. Predicted values for other 3 astronauts were around 77, 73, 71. Actual values were 90, 83, 103. Showing an increase in glucose levels of approximately 24.5% after landing. SAGE reduces this to +21.5% due to only 3 individuals.
3. Three methods of:
   
| Method | Expected | 95% range | Is 97 inside? |
|---|---|---|---|
| Own average only | 77.5 | 68.5 to 87.7 | No |
| + natural variation | 77.5 | 64.4 to 93.2 | No |
| SAGE | 94.1 | 70.2 to 126.2 | **Yes** |

This row, and all 127 others, are in [`results/predictions.csv`](results/predictions.csv). Count the "yes" answers in each "inside" column to get 91, 107 and 120.

## What these results do not show

Little data: only 4 astronauts and 3 days worth of data. Not including longer flight times, in flight blood results and Mars like durations.
Only looking at blood values: The daily vital signs were calculated using the same principle of your own baseline and change expected in space. This has not been applied to the data from the astronauts.
Little improvement: The average error has been reduced from 20.7% to 20.0%. In 14 instances, the SAGE model performed better than the simple baseline out of 32 measurements. This doesn’t really improve the accuracy but does give reliable ranges and reduce false positives.
Not completely accurate: There was still 20 false positives on a normal day. Ideally we would like to get down to around 6.
No diagnosis: Whilst it can be seen there are less alerts for normal changes in space, there is no indication that the SAGE model has improved at detecting sickness.

## Reproduce it yourself

Needs Python 3 (no extra packages).

```
python3 analysis/train_real.py          # writes results/evaluation.json (and the model the app uses)
python3 analysis/export_predictions.py  # writes results/predictions.csv and results/null_test.csv
```

Expected output of the second command:

```
predictions.csv: 128 rows. Inside the 95% range: own average 91, + natural variation 107, SAGE 120
null_test.csv: 128 rows. False alarms: textbook 39, calibrated 20
```

| File | What it holds |
|---|---|
| `analysis/i4_blood.json` | The real Inspiration4 values used (32 markers × 4 astronauts × 7 visits), read from the OSDR tables linked above. |
| `analysis/train_real.py` | The test and the model the app uses. |
| `analysis/export_predictions.py` | Writes every prediction as a table. |
| `results/evaluation.json` | Every number quoted in our slides. |
| `results/predictions.csv` | All 128 predictions, one row each. |
| `results/null_test.csv` | All 128 rows of the no-flight test. |
