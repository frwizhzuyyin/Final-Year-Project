import pandas as pd

# =========================
# FILE PATHS
# =========================
LAB_FILE = "dataset/labevents.csv.gz"
COHORT_FILE = "dataset/sepsis_cohort.csv"

# =========================
# ITEMIDS (CONFIRMED)
# =========================
CREATININE_ID = 50912
LACTATE_ID = 50813
PH_ID = 50820
BUN_ID = 51006

chunksize = 500000

# =========================
# LOAD COHORT
# =========================
cohort = pd.read_csv(COHORT_FILE)[["subject_id", "hadm_id"]].drop_duplicates()

print("Sepsis cohort size:", cohort.shape)

# =========================
# STORAGE
# =========================
creatinine_list = []
lactate_list = []
ph_list = []
bun_list = []

# =========================
# READ LAB EVENTS (CHUNKED)
# =========================
for i, chunk in enumerate(pd.read_csv(LAB_FILE, chunksize=chunksize)):

    print(f"Processing chunk {i+1}")

    # filter only cohort patients
    chunk = chunk.merge(cohort, on=["subject_id", "hadm_id"], how="inner")

    # =====================
    # CREATININE
    # =====================
    c = chunk[chunk["itemid"] == CREATININE_ID][["subject_id", "hadm_id", "valuenum"]].dropna()
    creatinine_list.append(c)

    # =====================
    # LACTATE
    # =====================
    l = chunk[chunk["itemid"] == LACTATE_ID][["subject_id", "hadm_id", "valuenum"]].dropna()
    lactate_list.append(l)

    # =====================
    # PH
    # =====================
    p = chunk[chunk["itemid"] == PH_ID][["subject_id", "hadm_id", "valuenum"]].dropna()
    ph_list.append(p)

    # =====================
    # BUN
    # =====================
    b = chunk[chunk["itemid"] == BUN_ID][["subject_id", "hadm_id", "valuenum"]].dropna()
    bun_list.append(b)

# =========================
# COMBINE
# =========================
creatinine = pd.concat(creatinine_list)
lactate = pd.concat(lactate_list)
ph = pd.concat(ph_list)
bun = pd.concat(bun_list)

# =========================
# AGGREGATION (mean per patient)
# =========================
creatinine = creatinine.groupby(["subject_id", "hadm_id"])["valuenum"].mean().reset_index()
creatinine.rename(columns={"valuenum": "creatinine"}, inplace=True)

lactate = lactate.groupby(["subject_id", "hadm_id"])["valuenum"].mean().reset_index()
lactate.rename(columns={"valuenum": "lactate"}, inplace=True)

ph = ph.groupby(["subject_id", "hadm_id"])["valuenum"].mean().reset_index()
ph.rename(columns={"valuenum": "ph"}, inplace=True)

bun = bun.groupby(["subject_id", "hadm_id"])["valuenum"].mean().reset_index()
bun.rename(columns={"valuenum": "bun"}, inplace=True)

# =========================
# MERGE ALL FEATURES
# =========================
merged = cohort.merge(creatinine, on=["subject_id", "hadm_id"], how="left")
merged = merged.merge(lactate, on=["subject_id", "hadm_id"], how="left")
merged = merged.merge(ph, on=["subject_id", "hadm_id"], how="left")
merged = merged.merge(bun, on=["subject_id", "hadm_id"], how="left")

print("\nBefore imputation:", merged.shape)
print(merged.isna().sum())

# =========================
# IMPUTATION (IMPORTANT)
# =========================
for col in ["creatinine", "lactate", "ph", "bun"]:
    merged[col] = merged[col].fillna(merged[col].median())

print("\nAfter imputation:", merged.shape)

# =========================
# SAVE
# =========================
merged.to_csv("dataset/final_4features.csv", index=False)

print("\nSaved dataset/final_4features.csv")
print("Final dataset size:", merged.shape)