"""Parameter-driven tax calculation helpers; inputs must be verified for each lot."""
from __future__ import annotations


def calculate_bphtb(
    bid_price: float, njop: float, rate_pct: float, npoptkp: float, basis_mode: str
) -> tuple[float, float]:
    """Return (tax_base, simulated_BPHTB). Does not decide which rule legally applies."""
    bid = max(0.0, float(bid_price or 0))
    assessed_njop = max(0.0, float(njop or 0))
    if basis_mode == "Maksimum harga bid dan NJOP":
        tax_base = max(bid, assessed_njop)
    elif basis_mode == "NJOP":
        tax_base = assessed_njop
    else:
        tax_base = bid
    deduction = max(0.0, float(npoptkp or 0))
    rate = max(0.0, float(rate_pct or 0)) / 100.0
    return tax_base, max(0.0, tax_base - deduction) * rate
