import pandas as pd

# =========================
# FILE PATHS
# =========================
ICU_FILE = "dataset/icustays.csv.gz"
DX_FILE = "dataset/diagnoses_icd.csv.gz"
DX_DICT_FILE = "dataset/d_icd_diagnoses.csv.gz"

# =========================
# LOAD DATA
# =========================
icu = pd.read_csv(ICU_FILE)
dx = pd.read_csv(DX_FILE)
dx_dict = pd.read_csv(DX_DICT_FILE)

print("ICU records:", icu.shape)
print("Diagnosis records:", dx.shape)

# =========================
# 1. FIRST ICU STAY ONLY
# =========================
icu["intime"] = pd.to_datetime(icu["intime"])
icu["outtime"] = pd.to_datetime(icu["outtime"])

icu = icu.sort_values(["subject_id", "intime"])
first_icu = icu.drop_duplicates(subset=["subject_id"], keep="first")

print("First ICU only:", first_icu.shape)

# =========================
# 2. ICU STAY > 24 HOURS
# =========================
first_icu["icu_los_hours"] = (
    first_icu["outtime"] - first_icu["intime"]
).dt.total_seconds() / 3600

first_icu = first_icu[first_icu["icu_los_hours"] > 24]

print("ICU stay > 24h:", first_icu.shape)

# =========================
# 3. IDENTIFY SEPSIS PATIENTS
# using diagnosis title keyword
# =========================
dx_full = dx.merge(
    dx_dict,
    on=["icd_code", "icd_version"],
    how="left"
)

sepsis_dx = dx_full[
    dx_full["long_title"].str.contains("sepsis|septicemia|septic shock", case=False, na=False)
]

sepsis_hadm = sepsis_dx[["subject_id", "hadm_id"]].drop_duplicates()

print("Sepsis admissions:", sepsis_hadm.shape)

sepsis_cohort = first_icu.merge(
    sepsis_hadm,
    on=["subject_id", "hadm_id"],
    how="inner"
)

print("Sepsis ICU cohort:", sepsis_cohort.shape)

# =========================
# 4. EXCLUDE ESRD + MALIGNANCY
# =========================
exclude_dx = dx_full[
    dx_full["long_title"].str.contains(
        "end stage renal|end-stage renal|malignant|neoplasm|cancer|tumor|tumour",
        case=False,
        na=False
    )
]

exclude_hadm = exclude_dx[["subject_id", "hadm_id"]].drop_duplicates()

sepsis_cohort = sepsis_cohort.merge(
    exclude_hadm.assign(exclude_flag=1),
    on=["subject_id", "hadm_id"],
    how="left"
)

sepsis_cohort = sepsis_cohort[sepsis_cohort["exclude_flag"].isna()]
sepsis_cohort = sepsis_cohort.drop(columns=["exclude_flag"])

print("After exclusions:", sepsis_cohort.shape)

# =========================
# SAVE
# =========================
sepsis_cohort.to_csv("dataset/sepsis_cohort.csv", index=False)

print("Saved dataset/sepsis_cohort.csv")
print(sepsis_cohort.head())