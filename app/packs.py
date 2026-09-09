"""Versioned configuration, not a representation of legal advice or current law."""
TORONTO_MARKET = {
    'id': 'TorontoMarketPack', 'version': '0.1.0-demo',
    'cities': ['Toronto', 'Mississauga', 'Brampton', 'Vaughan', 'Markham', 'Richmond Hill', 'Oakville', 'Burlington', 'Pickering', 'Ajax', 'Whitby', 'Oshawa', 'Milton', 'Newmarket', 'Aurora'],
    'property_types': ['MULTIFAMILY', 'RESIDENTIAL_PORTFOLIO', 'MIXED_USE', 'INDUSTRIAL_LOGISTICS', 'OFFICE', 'RETAIL', 'HOSPITALITY', 'DEVELOPMENT', 'LAND'],
    'currency': 'CAD',
    'required_underwriting': ['annual_gross_rent', 'annual_expenses', 'vacancy_rate', 'asking_price'],
    'evidence_max_age_days': 90,
    'defaults': {'rate': 0.055, 'amortization_years': 30, 'ltv': 0.65, 'cap_rate': 0.05, 'reserves': 12000},
    'disclosure': 'Illustrative assumptions, not market evidence or a professional valuation.'
}
CANADA_JURISDICTION = {'id': 'CanadaJurisdictionPack', 'version': '0.1.0-simulation', 'live_capital_enabled': False, 'production_legal_review': 'NOT_COMPLETED'}
ONTARIO_JURISDICTION = {'id': 'OntarioJurisdictionPack', 'version': '0.1.0-simulation', 'eligibility_provider': 'SIMULATION_ONLY', 'live_capital_enabled': False, 'legal_priority': 'HUMAN_LEGAL_REVIEW_REQUIRED'}
POLICY_VERSION = 'CA-ON-SIMULATION/0.1.0'
ROLES = ['visitor','investor','broker','owner','mortgage_professional','appraiser','inspector','property_manager','lawyer','capital_partner','admin']
AGENTS = [
    ('intake','Intake Agent','Validates GTA property intake','deterministic'),
    ('document-parser','Document Parser','Extracts numeric claims from accepted text/CSV','deterministic'),
    ('evidence','Evidence Agent','Finds missing and stale claims','deterministic'),
    ('rent-comps','Rent / Comps Agent','Proposes adapter queries; no market feed connected','contract_only'),
    ('underwriting','Underwriting Agent','Produces reproducible scenario snapshots','deterministic'),
    ('contradiction','Contradiction Agent','Detects conflicting facts and overlapping asset claims','deterministic'),
    ('counterparty','Counterparty Agent','Private-core adapter contract, no public dataset import','contract_only'),
    ('disclosure','Disclosure Agent','Proposes allowlisted public fields','deterministic'),
    ('property-page','Property-Page Agent','Displays reviewed factual projections','deterministic'),
    ('investor-support','Investor-Support Agent','Reports simulation status; no investment advice','contract_only'),
]
