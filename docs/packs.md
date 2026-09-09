# Versioned packs

`app/packs.py` separates descriptive market assumptions from jurisdiction policy. The active TorontoMarketPack admits multifamily, residential portfolios and mixed use in an explicit GTA city list, uses CAD, requires annual rent/expenses/vacancy/asking-price evidence and expires those claims after 90 days. Interest, amortization, LTV, cap rate and reserves are illustrative configurable underwriting defaults, not current lender offers or market evidence.

CanadaJurisdictionPack and OntarioJurisdictionPack are explicitly simulation-only. They do not encode a legal opinion or complete securities, mortgage, privacy or professional-licensing rules. Legal priority always requires qualified human review. Live capital execution is disabled.

A future pack change needs a version bump, migration/compatibility decision, scenario regression evidence and an explicit account of which existing proposals or snapshots it affects. Historical snapshots retain their original formula and assumptions. A future UK or other Canadian market can add a market taxonomy and evidence conventions without changing the property/deal distinction; the associated jurisdiction policy must separately govern eligibility, disclosure, regulated activities and approvals.

The next production design should persist exact jurisdiction policy content hashes with every sensitive action. Today action records store a policy version and simulation decision, while pack definitions live in version-controlled source. Re-running arbitrary historical policy code is not implemented.
