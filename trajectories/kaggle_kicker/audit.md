# Data card audit — demo_credit_g

Run: 2026-08-29T07:30:26+00:00 · model: claude-sonnet-5 · claims audited: 27

## Executive summary

**2 violated · 19 hold · 6 unverifiable.** Most severe violation: **demo_credit_g-c26** — "Telephone (yes,no)".

Of 27 documented claims, 19 hold and 2 are violated, with the telephone attribute the most consequential: the docs describe values as 'yes,no' but the data actually encodes 'none,yes' — any pipeline or filter written against the documented 'no' label will silently match zero rows across the whole column, corrupting downstream joins or feature encoding without raising an error. The other_parties/guarantors field also fails validation, with 41 rows carrying values outside the three documented categories (co applicant, guarantor, none), suggesting inconsistent formatting or an undocumented fourth category that needs investigation. Six prose claims (dataset origin, cost-matrix rationale, citation policy) are unverifiable from the data alone and should be confirmed against source documentation separately. Fix: update the documentation to replace 'no' with 'none' for telephone, and audit the 41 non-conforming other_parties values to determine if they're a data-entry defect or a missing category label.

## Per-claim verdicts

| # | claim (quoted from the card) | type | verdict | claimed | computed |
|---|---|---|---|---|---|
| 1 | Dr. Hans Hofmann | prose_unverifiable | unverifiable (prose) | — | — |
| 2 | [UCI](https://archive.ics.uci.edu/ml/datasets/statlog+(german+credit+data)) - 1994 | prose_unverifiable | unverifiable (prose) | — | — |
| 3 | [UCI](https://archive.ics.uci.edu/ml/citation_policy.html) | prose_unverifiable | unverifiable (prose) | — | — |
| 4 | This dataset classifies people described by a set of attributes as good or bad credit risks. | prose_unverifiable | unverifiable (prose) | — | — |
| 5 | good or bad credit risks | category_set | holds | good or bad credit risks | unique values in 'class': ['bad', 'good'] |
| 6 | This dataset comes with a cost matrix: | prose_unverifiable | unverifiable (prose) | — | — |
| 7 | It is worse to class a customer as good when they are bad (5), than it is to class a customer as bad when they are good (1). | prose_unverifiable | unverifiable (prose) | — | — |
| 8 | Status of existing checking account, in Deutsche Mark. | schema | holds | Status of existing checking account, in Deutsche Mark. | categories=['0<=X<200', '<0', '>=200', 'no checking'], unexpected=[], nulls=0 |
| 9 | Duration in months | schema | holds | Duration in months | non-numeric: 0, non-integer: 0, negative: 0, min=4, max=72 |
| 10 | Credit history (credits taken, paid back duly, delays, critical accounts) | schema | holds | Credit history (credits taken, paid back duly, delays, critical accounts) | rows=1000, nulls=0, unique_categories=5, categories=["'all paid'", "'critical/other existing credit'", "'delayed previously'", "'existing paid'", "'no credits/all paid'"] |
| 11 | Purpose of the credit (car, television,...) | schema | holds | Purpose of the credit (car, television,...) | 1000/1000 non-null; categories=["'domestic appliance'", "'new car'", "'used car'", 'business', 'education', 'furniture/equipment', 'other', 'radio/tv', 'repairs', 'retraining'] |
| 12 | Credit amount | schema | holds | Credit amount | dtype=int64, non_numeric_count=0, min=250, max=18424 |
| 13 | Status of savings account/bonds, in Deutsche Mark. | schema | holds | Status of savings account/bonds, in Deutsche Mark. | column 'savings_status' present, 1000/1000 non-null, categories=["'100<=X<500'", "'500<=X<1000'", "'<100'", "'>=1000'", "'no known savings'"] |
| 14 | Present employment, in number of years. | schema | holds | Present employment, in number of years. | values=1<=X<4, 4<=X<7, <1, >=7, unemployed |
| 15 | Installment rate in percentage of disposable income | schema | holds | Installment rate in percentage of disposable income | dtype=int64, rows=1000, non-null=1000, numeric-parseable=1000, min=1, max=4 |
| 16 | Personal status (married, single,...) and sex | schema | holds | Personal status (married, single,...) and sex | 1000/1000 rows encode both sex and marital status; nulls=0; sample_values=["'male single'", "'female div/dep/mar'", "'male div/sep'", "'male mar/wid'"] |
| 17 | Other debtors / guarantors | schema | violated | Other debtors / guarantors | unique values=["'co applicant'", 'guarantor', 'none'], nulls=0, unexpected=41 |
| 18 | Present residence since X years | schema | holds | Present residence since X years | residence_since numeric range [1, 4], non-numeric=0, non-positive=0, nulls=0 |
| 19 | Property (e.g. real estate) | schema | holds | Property (e.g. real estate) | dtype=object, non_null=1000/1000, unique_values=['car', 'life insurance', 'no known property', 'real estate'] |
| 20 | Age in years | schema | holds | Age in years | non-numeric: 0, non-integer: 0, nulls: 0, range: [19, 75] |
| 21 | Other installment plans (banks, stores) | schema | holds | Other installment plans (banks, stores) | unique values: ['bank', 'none', 'stores'] |
| 22 | Housing (rent, own,...) | schema | holds | Housing (rent, own,...) | housing values: ["'for free'", 'own', 'rent'] |
| 23 | Number of existing credits at this bank | schema | holds | Number of existing credits at this bank | min=1, max=4, unique_count=4, all_nonneg_ints=True |
| 24 | Job | schema | holds | Job | dtype=object, nulls=0, n_unique=4, values=["'high qualif/self emp/mgmt'", "'unemp/unskilled non res'", "'unskilled resident'", 'skilled'] |
| 25 | Number of people being liable to provide maintenance for | schema | holds | Number of people being liable to provide maintenance for | n_total=1000, nulls=0, non_integer_or_negative=0, min=1, max=2 |
| 26 | Telephone (yes,no) | category_set | violated | Telephone (yes,no) | values found: none, yes |
| 27 | Foreign worker (yes,no) | category_set | holds | Foreign worker (yes,no) | unique values: ['no', 'yes'] |

## Evidence for violations

### demo_credit_g-c17 — Other debtors / guarantors

Computed: `unique values=["'co applicant'", 'guarantor', 'none'], nulls=0, unexpected=41`

| other_parties |
|---|
| 'co applicant' |
| 'co applicant' |
| 'co applicant' |
| 'co applicant' |
| 'co applicant' |

### demo_credit_g-c26 — Telephone (yes,no)

Computed: `values found: none, yes`

| checking_status | duration | credit_history | purpose | credit_amount | savings_status | employment | installment_commitment | personal_status | other_parties | residence_since | property_magnitude | age | other_payment_plans | housing | existing_credits | job | num_dependents | own_telephone | foreign_worker | class |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| '0<=X<200' | 48 | 'existing paid' | radio/tv | 5951 | '<100' | '1<=X<4' | 2 | 'female div/dep/mar' | none | 2 | 'real estate' | 22 | none | own | 1 | skilled | 1 | none | yes | bad |
| 'no checking' | 12 | 'critical/other existing credit' | education | 2096 | '<100' | '4<=X<7' | 2 | 'male single' | none | 3 | 'real estate' | 49 | none | own | 1 | 'unskilled resident' | 2 | none | yes | good |
| '<0' | 42 | 'existing paid' | furniture/equipment | 7882 | '<100' | '4<=X<7' | 2 | 'male single' | guarantor | 4 | 'life insurance' | 45 | none | 'for free' | 1 | skilled | 2 | none | yes | good |
| '<0' | 24 | 'delayed previously' | 'new car' | 4870 | '<100' | '1<=X<4' | 3 | 'male single' | none | 4 | 'no known property' | 53 | none | 'for free' | 2 | skilled | 2 | none | yes | bad |
| 'no checking' | 24 | 'existing paid' | furniture/equipment | 2835 | '500<=X<1000' | '>=7' | 3 | 'male single' | none | 4 | 'life insurance' | 53 | none | own | 1 | skilled | 1 | none | yes | good |


## Abstentions

- **demo_credit_g-c01** (prose): Dr. Hans Hofmann
- **demo_credit_g-c02** (prose): [UCI](https://archive.ics.uci.edu/ml/datasets/statlog+(german+credit+data)) - 1994
- **demo_credit_g-c03** (prose): [UCI](https://archive.ics.uci.edu/ml/citation_policy.html)
- **demo_credit_g-c04** (prose): This dataset classifies people described by a set of attributes as good or bad credit risks.
- **demo_credit_g-c06** (prose): This dataset comes with a cost matrix:
- **demo_credit_g-c07** (prose): It is worse to class a customer as good when they are bad (5), than it is to class a customer as bad when they are good (1).
