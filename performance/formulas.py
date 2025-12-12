from __future__ import annotations


PCS_FORMULA_1_KEY = "pcs.formula1_yield_pct"

PCS_F1_MSALES = "pcs.f1.msales_tm"
PCS_F1_MSALMUERA = "pcs.f1.msalmuera_tm"
PCS_F1_XSOLIDS = "pcs.f1.xsolids_frac"


def pcs_formula_1_variable_keys() -> list[str]:
    return [PCS_F1_MSALES, PCS_F1_MSALMUERA, PCS_F1_XSOLIDS]

