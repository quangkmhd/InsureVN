"""AI-assisted schema discovery for Vietnamese insurance policy documents."""

from __future__ import annotations

import asyncio
import csv
import json
import re
import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Literal, Protocol

from src.core.config import Settings, settings
from src.core.logger import get_logger
from src.core.vietnamese_text import slugify_vietnamese, transliterate_vietnamese
from src.services.observability import service_observe

SchemaDiscoveryProvider = Literal["ollama", "openrouter", "nvidia", "gemini"]

logger = get_logger(__name__)

CORE_SCHEMA_NODE_LABELS = frozenset(
    {
        "Accident",
        "Beneficiary",
        "Benefit",
        "BenefitCategory",
        "BenefitLimit",
        "BodyPart",
        "Claim",
        "ClaimDocument",
        "Country",
        "Exclusion",
        "Hospital",
        "HospitalType",
        "InsuranceBenefit",
        "InsuranceCompany",
        "InsuranceContract",
        "InsuranceEvent",
        "InsuranceExclusion",
        "InsurancePlan",
        "InsurancePolicy",
        "InsurancePremium",
        "InsuranceProduct",
        "InsuredPerson",
        "Insurer",
        "Location",
        "MedicalCondition",
        "MedicalExpense",
        "MedicalFacility",
        "MedicalProvider",
        "MedicalService",
        "MedicalTreatment",
        "PolicyHolder",
        "WaitingPeriod",
    }
)
CORE_SCHEMA_RELATIONSHIP_LABELS = frozenset(
    {
        "APPLIES_TO",
        "COVERS",
        "COVERS_EXPENSE",
        "COVERS_PERSON",
        "HAS_BENEFIT",
        "HAS_EXCLUSION",
        "HAS_LIMIT",
        "HAS_PREMIUM",
        "HAS_WAITING_PERIOD",
        "IS_A",
        "ISSUES",
        "LOCATED_IN",
        "PART_OF",
        "PAYS_BENEFIT_TO",
        "PROVIDES_BENEFIT",
        "PROVIDES_SERVICE",
        "PURCHASES",
        "SIGNS",
        "TREATS",
    }
)

FINAL_SCHEMA_V1_NODE_LABELS = (
    "InsuranceCompany",
    "InsurancePolicy",
    "InsuranceDocument",
    "InsuranceProduct",
    "InsurancePlan",
    "PolicyHolder",
    "InsuredPerson",
    "Beneficiary",
    "FamilyMember",
    "AgeGroup",
    "Benefit",
    "BenefitCategory",
    "Exclusion",
    "WaitingPeriod",
    "InsurancePeriod",
    "Premium",
    "PaymentTerm",
    "CoverageLimit",
    "SumInsured",
    "Deductible",
    "PayoutRate",
    "MedicalCondition",
    "Injury",
    "Disability",
    "BodyPart",
    "AnatomicalPart",
    "MedicalService",
    "MedicalServiceType",
    "MedicalProcedure",
    "MedicalTreatment",
    "MedicalExpense",
    "Medication",
    "MedicalDevice",
    "MedicalFacility",
    "HospitalType",
    "MedicalProfessional",
    "MedicalDepartment",
    "Claim",
    "ClaimDocument",
    "InsuranceEvent",
    "Location",
    "EligibilityCondition",
    "CompensationBasis",
)
FINAL_SCHEMA_V1_RELATIONSHIP_TYPES = (
    "ISSUES",
    "OFFERS",
    "HAS_PLAN",
    "HAS_BENEFIT",
    "INCLUDES",
    "COVERS",
    "COVERS_PERSON",
    "COVERS_EXPENSE",
    "COVERS_SERVICE",
    "COVERS_CONDITION",
    "COVERS_TREATMENT",
    "APPLIES_TO",
    "HAS_WAITING_PERIOD",
    "HAS_LIMIT",
    "HAS_SUM_INSURED",
    "HAS_PREMIUM",
    "HAS_PAYOUT_RATE",
    "HAS_EXCLUSION",
    "EXCLUDES",
    "EXCLUDES_CONDITION",
    "EXCLUDES_TREATMENT",
    "PROVIDES_BENEFIT",
    "PROVIDES_SERVICE",
    "TREATS",
    "PERFORMED_AT",
    "PERFORMED_BY",
    "TREATED_AT",
    "LOCATED_AT",
    "IS_A",
    "PART_OF",
    "HAS_CATEGORY",
    "HAS_CONDITION",
    "REQUIRES_DOCUMENT",
    "PROVIDES_DOCUMENT",
    "SUBMITS_CLAIM",
    "FILES_CLAIM",
    "PAYS",
    "PAYS_BENEFIT_TO",
    "PAYS_PREMIUM",
    "PURCHASES",
    "SIGNS",
    "HOLDS_POLICY",
    "HAS_BENEFICIARY",
    "DESIGNATES_BENEFICIARY",
    "TRIGGERS_CLAIM",
    "TRIGGERS_PAYMENT",
    "TRIGGERS_BENEFIT",
    "AFFECTS_BODY_PART",
    "OCCURS_AT",
    "EXPERIENCES",
    "UNDERGOES",
    "DIAGNOSES",
    "PRESCRIBES",
    "USES_DEVICE",
    "SUBJECT_TO_WAITING_PERIOD",
    "DEFINED_IN",
    "GOVERNED_BY",
    "SUPPORTS_DIRECT_BILLING",
    "EXCLUDES_DIRECT_BILLING",
    "PROVIDES_GUARANTEE",
    "EXCLUDES_GUARANTEE",
    "HAS_GEOGRAPHIC_SCOPE",
    "HAS_EFFECTIVE_DATE",
    "REQUIRES",
    "CONTAINS",
    "DEFINES",
    "DETERMINES",
    "CALCULATED_BY",
)
FINAL_SCHEMA_V1_NODE_MERGE_MAP = {
    "InsuranceContract": "InsurancePolicy",
    "InsuranceProvider": "InsuranceCompany",
    "Insurer": "InsuranceCompany",
    "PolicyDocument": "InsuranceDocument",
    "Certificate": "InsuranceDocument",
    "Schedule": "InsuranceDocument",
    "Plan": "InsurancePlan",
    "HealthProgram": "InsurancePlan",
    "InsuranceBenefit": "Benefit",
    "OptionalBenefit": "Benefit",
    "Coverage": "Benefit",
    "BenefitLimit": "CoverageLimit",
    "InsuranceLimit": "CoverageLimit",
    "SubLimit": "CoverageLimit",
    "SumAssured": "SumInsured",
    "InsurancePremium": "Premium",
    "Rate": "PayoutRate",
    "CoverageRate": "PayoutRate",
    "DisabilityRate": "PayoutRate",
    "ImpairmentPercentage": "PayoutRate",
    "Disease": "MedicalCondition",
    "DiseaseGroup": "MedicalCondition",
    "CongenitalDisease": "MedicalCondition",
    "PreExistingCondition": "MedicalCondition",
    "InsuranceCondition": "MedicalCondition",
    "BodilyInjury": "Injury",
    "InjuryCategory": "Injury",
    "InjurySeverity": "Injury",
    "PermanentDisability": "Disability",
    "TotalPermanentDisability": "Disability",
    "DisabilityCategory": "Disability",
    "DisabilityType": "Disability",
    "BodyRegion": "BodyPart",
    "Bone": "BodyPart",
    "HealthService": "MedicalService",
    "InsuranceService": "MedicalService",
    "Service": "MedicalService",
    "ServiceType": "MedicalServiceType",
    "Surgery": "MedicalProcedure",
    "SurgeryProcedure": "MedicalProcedure",
    "SurgicalProcedure": "MedicalProcedure",
    "TreatmentEpisode": "MedicalTreatment",
    "TreatmentMethod": "MedicalTreatment",
    "TreatmentType": "MedicalTreatment",
    "MedicalCost": "MedicalExpense",
    "HealthcareFacility": "MedicalFacility",
    "HealthcareProvider": "MedicalFacility",
    "MedicalProvider": "MedicalFacility",
    "MedicalOrganization": "MedicalFacility",
    "MedicalUnit": "MedicalFacility",
    "HospitalClass": "HospitalType",
    "Doctor": "MedicalProfessional",
    "InsuranceClaim": "Claim",
    "ClaimDossier": "ClaimDocument",
    "MedicalDocument": "ClaimDocument",
    "InsuredEvent": "InsuranceEvent",
    "MedicalEvent": "InsuranceEvent",
    "Accident": "InsuranceEvent",
    "GeographicScope": "Location",
    "Region": "Location",
    "CoverageScope": "Location",
    "CoverageZone": "Location",
    "Customer": "InsuredPerson",
    "Insured": "InsuredPerson",
    "Person": "InsuredPerson",
    "Dependent": "FamilyMember",
    "LegalHeir": "Beneficiary",
}
FINAL_SCHEMA_V1_RELATIONSHIP_MERGE_MAP = {
    "OFFERS_PRODUCT": "OFFERS",
    "OFFERS_SERVICE": "PROVIDES_SERVICE",
    "APPLICABLE_TO": "APPLIES_TO",
    "HAS_CLASSIFICATION": "HAS_CATEGORY",
    "CATEGORIZED_AS": "HAS_CATEGORY",
    "BELONGS_TO_CATEGORY": "HAS_CATEGORY",
    "BELONGS_TO_REGION": "HAS_CATEGORY",
    "HAS_SUBTYPE": "HAS_CATEGORY",
    "SUBTYPE_OF": "HAS_CATEGORY",
    "LOCATED_IN": "LOCATED_AT",
    "LOCATED_IN_COUNTRY": "LOCATED_AT",
    "OCCURRED_AT": "OCCURS_AT",
    "HAS_SUB_LIMIT": "HAS_LIMIT",
    "DEFINES_LIMIT": "HAS_LIMIT",
    "HAS_PERCENTAGE": "HAS_PAYOUT_RATE",
    "HAS_PAYMENT_RATE": "HAS_PAYOUT_RATE",
    "HAS_COMPENSATION_RATE": "HAS_PAYOUT_RATE",
    "HAS_BENEFIT_RATE": "HAS_PAYOUT_RATE",
    "HAS_PAYOUT_PERCENTAGE": "HAS_PAYOUT_RATE",
    "PAY_PREMIUM": "PAYS_PREMIUM",
    "PAYS_PREMIUM_TO": "PAYS_PREMIUM",
    "PAYS_BENEFIT": "PAYS_BENEFIT_TO",
    "PAYS_TO": "PAYS_BENEFIT_TO",
    "SUBMITS": "SUBMITS_CLAIM",
    "SUBMITS_CLAIM_TO": "SUBMITS_CLAIM",
    "SUBMITS_CLAIM_WITH": "SUBMITS_CLAIM",
    "REQUIRES_DOCUMENTATION": "REQUIRES_DOCUMENT",
    "EXCLUDES_COVERAGE": "EXCLUDES",
    "EXCLUDES_COVERAGE_FOR": "EXCLUDES",
    "EXCLUDED_FROM": "EXCLUDES",
    "EXCLUDED_BY": "EXCLUDES",
    "COVERED_BY": "COVERS",
    "HAS_CONTRACT": "HOLDS_POLICY",
    "HOLDER_OF": "HOLDS_POLICY",
    "HOLDS": "HOLDS_POLICY",
    "OWNS_POLICY": "HOLDS_POLICY",
    "OWNS": "PURCHASES",
}

COMMON_FINAL_SCHEMA_V1_NODE_PROPERTIES = (
    ("id", "string", True, "Stable unique node id."),
    ("name", "string", True, "Canonical display name for the entity."),
    ("source_document_id", "string", True, "Source document id."),
    ("source_chunk_id", "string", False, "Source chunk id when available."),
    ("source_path", "string", True, "Original source file path."),
    ("evidence_text", "string", True, "Source text span supporting the entity."),
    ("confidence", "float", True, "Extraction confidence from 0 to 1."),
    ("extraction_method", "string", True, "Extractor or model that produced it."),
    ("ingestion_version", "string", True, "Schema/import version."),
)
COMMON_FINAL_SCHEMA_V1_RELATIONSHIP_PROPERTIES = (
    ("source_document_id", "string", True, "Source document id."),
    ("source_chunk_id", "string", False, "Source chunk id when available."),
    ("source_path", "string", True, "Original source file path."),
    ("evidence_text", "string", True, "Source text span supporting the relationship."),
    ("confidence", "float", True, "Extraction confidence from 0 to 1."),
    ("condition_text", "string", False, "Condition limiting when this edge applies."),
    ("valid_from", "date", False, "Start date when the edge is effective."),
    ("valid_to", "date", False, "End date when the edge is effective."),
    ("extraction_method", "string", True, "Extractor or model that produced it."),
    ("ingestion_version", "string", True, "Schema/import version."),
)
FINAL_SCHEMA_V1_NODE_SPECIFIC_PROPERTIES = {
    "InsuranceCompany": (
        ("company_code", "string", False, "Short insurance company code."),
        ("legal_name", "string", False, "Registered legal company name."),
        ("website", "string", False, "Company website."),
        ("hotline", "string", False, "Customer support hotline."),
    ),
    "InsurancePolicy": (
        ("policy_number", "string", False, "Policy or contract number."),
        ("issue_date", "date", False, "Policy issue date."),
        ("effective_date", "date", False, "Policy effective date."),
        ("expiry_date", "date", False, "Policy expiry date."),
        ("status", "string", False, "Policy status."),
    ),
    "InsuranceDocument": (
        ("document_id", "string", True, "Stable document id."),
        ("document_name", "string", True, "Document title or file name."),
        ("document_type", "string", False, "Policy, brochure, form, or guide."),
        ("version", "string", False, "Document version when available."),
        ("publish_date", "date", False, "Document publication date."),
    ),
    "InsuranceProduct": (
        ("product_code", "string", False, "Product code."),
        ("product_name", "string", False, "Product name."),
        ("product_type", "string", False, "Insurance product category."),
        ("target_segment", "string", False, "Target customer segment."),
    ),
    "InsurancePlan": (
        ("plan_code", "string", False, "Plan code."),
        ("plan_name", "string", False, "Plan name."),
        ("tier", "string", False, "Plan tier or package level."),
        ("currency", "string", False, "Default plan currency."),
    ),
    "PolicyHolder": (
        ("person_id", "string", False, "Stable person id."),
        ("full_name", "string", False, "Policy holder full name."),
        ("date_of_birth", "date", False, "Policy holder date of birth."),
        ("identifier_number", "string", False, "Personal or business identifier."),
        ("phone", "string", False, "Contact phone number."),
    ),
    "InsuredPerson": (
        ("person_id", "string", False, "Stable person id."),
        ("full_name", "string", False, "Insured person full name."),
        ("date_of_birth", "date", False, "Insured person date of birth."),
        ("gender", "string", False, "Gender when stated."),
        ("occupation", "string", False, "Occupation when stated."),
    ),
    "Beneficiary": (
        ("person_id", "string", False, "Stable person id."),
        ("full_name", "string", False, "Beneficiary full name."),
        ("relationship_to_insured", "string", False, "Relationship to insured."),
        ("payout_percentage", "float", False, "Allocated payout percentage."),
    ),
    "FamilyMember": (
        ("person_id", "string", False, "Stable person id."),
        ("full_name", "string", False, "Family member full name."),
        ("relationship_to_insured", "string", False, "Relationship to insured."),
        ("date_of_birth", "date", False, "Family member date of birth."),
    ),
    "AgeGroup": (
        ("min_age", "integer", False, "Minimum age."),
        ("max_age", "integer", False, "Maximum age."),
        ("age_unit", "string", False, "Age unit such as year or day."),
    ),
    "Benefit": (
        ("benefit_code", "string", False, "Benefit code."),
        ("benefit_type", "string", False, "Benefit category."),
        ("description", "string", False, "Benefit description."),
        ("covered_amount_text", "string", False, "Raw covered amount text."),
    ),
    "BenefitCategory": (
        ("category_code", "string", False, "Benefit category code."),
        ("category_name", "string", False, "Benefit category name."),
    ),
    "Exclusion": (
        ("exclusion_code", "string", False, "Exclusion code."),
        ("exclusion_type", "string", False, "Exclusion category."),
        ("description", "string", False, "Exclusion description."),
    ),
    "WaitingPeriod": (
        ("duration_value", "integer", False, "Waiting period duration."),
        ("duration_unit", "string", False, "Duration unit."),
        ("condition_text", "string", False, "Condition requiring waiting period."),
    ),
    "InsurancePeriod": (
        ("start_date", "date", False, "Coverage start date."),
        ("end_date", "date", False, "Coverage end date."),
        ("duration_value", "integer", False, "Coverage duration."),
        ("duration_unit", "string", False, "Coverage duration unit."),
    ),
    "Premium": (
        ("amount", "float", False, "Premium amount."),
        ("currency", "string", False, "Premium currency."),
        ("payment_frequency", "string", False, "Payment frequency."),
        ("premium_type", "string", False, "Premium type."),
    ),
    "PaymentTerm": (
        ("frequency", "string", False, "Payment frequency."),
        ("due_date_rule", "string", False, "Due date rule."),
        ("grace_period_days", "integer", False, "Grace period in days."),
    ),
    "CoverageLimit": (
        ("amount", "float", False, "Limit amount."),
        ("currency", "string", False, "Limit currency."),
        ("period", "string", False, "Limit period."),
        ("limit_type", "string", False, "Limit type."),
    ),
    "SumInsured": (
        ("amount", "float", False, "Sum insured amount."),
        ("currency", "string", False, "Sum insured currency."),
        ("basis", "string", False, "Basis for sum insured."),
    ),
    "Deductible": (
        ("amount", "float", False, "Deductible amount."),
        ("currency", "string", False, "Deductible currency."),
        ("percentage", "float", False, "Deductible percentage."),
        ("applies_per", "string", False, "Per claim, event, or policy period."),
    ),
    "PayoutRate": (
        ("rate_value", "float", False, "Payout rate value."),
        ("rate_unit", "string", False, "Rate unit."),
        ("basis", "string", False, "Rate basis."),
    ),
    "MedicalCondition": (
        ("condition_code", "string", False, "Medical condition code."),
        ("condition_name", "string", False, "Medical condition name."),
        ("icd_code", "string", False, "ICD code when available."),
        ("pre_existing", "boolean", False, "Whether condition is pre-existing."),
    ),
    "Injury": (
        ("injury_type", "string", False, "Injury type."),
        ("severity", "string", False, "Injury severity."),
        ("cause", "string", False, "Cause of injury."),
    ),
    "Disability": (
        ("disability_type", "string", False, "Disability type."),
        ("severity", "string", False, "Disability severity."),
        ("percentage", "float", False, "Disability percentage."),
    ),
    "BodyPart": (
        ("body_part_name", "string", False, "Body part name."),
        ("body_region", "string", False, "Body region."),
    ),
    "AnatomicalPart": (
        ("anatomical_name", "string", False, "Anatomical part name."),
        ("parent_part", "string", False, "Parent anatomical part."),
    ),
    "MedicalService": (
        ("service_code", "string", False, "Medical service code."),
        ("service_name", "string", False, "Medical service name."),
        ("service_type", "string", False, "Medical service type."),
        ("inpatient_outpatient", "string", False, "Inpatient or outpatient."),
    ),
    "MedicalServiceType": (
        ("service_type_code", "string", False, "Service type code."),
        ("service_type_name", "string", False, "Service type name."),
    ),
    "MedicalProcedure": (
        ("procedure_code", "string", False, "Procedure code."),
        ("procedure_name", "string", False, "Procedure name."),
        ("surgical", "boolean", False, "Whether procedure is surgical."),
        ("inpatient_outpatient", "string", False, "Inpatient or outpatient."),
    ),
    "MedicalTreatment": (
        ("treatment_name", "string", False, "Treatment name."),
        ("treatment_type", "string", False, "Treatment type."),
        ("duration_value", "integer", False, "Treatment duration."),
        ("duration_unit", "string", False, "Treatment duration unit."),
    ),
    "MedicalExpense": (
        ("expense_type", "string", False, "Medical expense type."),
        ("amount", "float", False, "Expense amount."),
        ("currency", "string", False, "Expense currency."),
        ("expense_date", "date", False, "Expense date."),
    ),
    "Medication": (
        ("medication_name", "string", False, "Medication name."),
        ("dosage", "string", False, "Medication dosage."),
        ("route", "string", False, "Administration route."),
    ),
    "MedicalDevice": (
        ("device_name", "string", False, "Medical device name."),
        ("device_type", "string", False, "Medical device type."),
        ("rental_or_purchase", "string", False, "Rental or purchase."),
    ),
    "MedicalFacility": (
        ("facility_code", "string", False, "Medical facility code."),
        ("facility_name", "string", False, "Medical facility name."),
        ("facility_type", "string", False, "Medical facility type."),
        ("address", "string", False, "Facility address."),
        ("direct_billing_supported", "boolean", False, "Direct billing support."),
    ),
    "HospitalType": (
        ("type_name", "string", False, "Hospital type name."),
        ("public_private", "string", False, "Public or private."),
        ("level", "string", False, "Hospital level."),
    ),
    "MedicalProfessional": (
        ("professional_name", "string", False, "Medical professional name."),
        ("license_number", "string", False, "Medical license number."),
        ("specialty", "string", False, "Medical specialty."),
    ),
    "MedicalDepartment": (
        ("department_name", "string", False, "Medical department name."),
        ("specialty", "string", False, "Department specialty."),
    ),
    "Claim": (
        ("claim_id", "string", False, "Claim id."),
        ("claim_date", "date", False, "Claim submission date."),
        ("claim_status", "string", False, "Claim status."),
        ("requested_amount", "float", False, "Requested claim amount."),
        ("approved_amount", "float", False, "Approved claim amount."),
    ),
    "ClaimDocument": (
        ("document_id", "string", False, "Claim document id."),
        ("document_type", "string", False, "Claim document type."),
        ("document_name", "string", False, "Claim document name."),
        ("submitted_date", "date", False, "Submission date."),
        ("issuer", "string", False, "Document issuer."),
    ),
    "InsuranceEvent": (
        ("event_id", "string", False, "Insurance event id."),
        ("event_type", "string", False, "Insurance event type."),
        ("event_date", "date", False, "Insurance event date."),
        ("description", "string", False, "Event description."),
    ),
    "Location": (
        ("location_name", "string", False, "Location name."),
        ("location_type", "string", False, "Country, province, district, or address."),
        ("country", "string", False, "Country."),
        ("province", "string", False, "Province or city."),
        ("district", "string", False, "District."),
    ),
    "EligibilityCondition": (
        ("condition_text", "string", False, "Eligibility condition text."),
        ("min_age", "integer", False, "Minimum eligible age."),
        ("max_age", "integer", False, "Maximum eligible age."),
        ("occupation_class", "string", False, "Occupation class."),
    ),
    "CompensationBasis": (
        ("basis_type", "string", False, "Compensation basis type."),
        ("formula_text", "string", False, "Compensation formula text."),
        ("currency", "string", False, "Currency."),
        ("rate_value", "float", False, "Compensation rate value."),
    ),
}


@dataclass(frozen=True)
class SchemaDiscoveryChunk:
    """A resumable markdown text unit for schema discovery."""

    chunk_id: str
    file_path: str
    chunk_index: int
    text: str
    content_hash: str


@dataclass(frozen=True)
class SchemaDiscoveryProviderSlot:
    """One concurrent schema discovery worker backed by one provider credential."""

    slot_id: str
    provider: SchemaDiscoveryProvider
    model: str
    api_key: str = ""
    base_url: str = ""


@dataclass(frozen=True)
class SchemaNodeProposal:
    """A candidate graph node schema proposed from source text."""

    label: str
    vietnamese_aliases: list[str]
    description: str
    evidence_text: str
    confidence: float


@dataclass(frozen=True)
class SchemaRelationshipProposal:
    """A candidate graph relationship schema proposed from source text."""

    source_label: str
    relationship_label: str
    target_label: str
    vietnamese_aliases: list[str]
    description: str
    evidence_text: str
    confidence: float


@dataclass(frozen=True)
class SchemaChunkDiscoveryResult:
    """Schema discovery output for a single markdown chunk."""

    chunk_id: str
    file_path: str
    content_hash: str
    provider_slot_id: str
    nodes: list[SchemaNodeProposal]
    relationships: list[SchemaRelationshipProposal]
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AggregatedSchemaItem:
    """Aggregated schema proposal counts and lineage."""

    label: str
    occurrence_count: int
    source_files: list[str]
    aliases: list[str]
    examples: list[str]
    average_confidence: float


@dataclass(frozen=True)
class FileSchemaSummary:
    """Per-file schema labels after canonicalization."""

    node_labels: list[str]
    relationship_labels: list[str]


@dataclass(frozen=True)
class SchemaDiscoverySummary:
    """Corpus-level schema discovery summary."""

    nodes: dict[str, AggregatedSchemaItem]
    relationships: dict[str, AggregatedSchemaItem]
    per_file: dict[str, FileSchemaSummary]


@dataclass(frozen=True)
class SchemaCanonicalizationMap:
    """AI-proposed canonical schema label mappings."""

    node_map: dict[str, str]
    relationship_map: dict[str, str]


class SchemaDiscoveryClient(Protocol):
    """Client interface used by the resumable discovery runner."""

    async def discover_chunk_schema(
        self,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaChunkDiscoveryResult:
        """Discover candidate schema from one chunk using one provider slot."""


class SchemaCanonicalizationClient(Protocol):
    """Client interface for merging similar schema labels."""

    async def canonicalize_schema_labels(
        self,
        *,
        node_items: list[AggregatedSchemaItem],
        relationship_items: list[AggregatedSchemaItem],
        slot: SchemaDiscoveryProviderSlot,
    ) -> SchemaCanonicalizationMap:
        """Return canonical labels for similar node and relationship proposals."""


class MarkdownSchemaDiscoveryChunker:
    """Split markdown files into stable, large chunks for AI schema discovery."""

    def __init__(self, *, max_chunk_chars: int, overlap_chars: int = 0) -> None:
        """Initialize the chunker."""
        if max_chunk_chars <= 0:
            raise ValueError("max_chunk_chars must be positive.")
        if overlap_chars < 0:
            raise ValueError("overlap_chars cannot be negative.")
        if overlap_chars >= max_chunk_chars:
            raise ValueError("overlap_chars must be smaller than max_chunk_chars.")
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars

    @service_observe(
        name="service.knowledge_graph.insurance_graph_schema_discovery.chunk_files",
        component="insurance_graph_schema_discovery",
    )
    def chunk_files(self, file_paths: list[Path]) -> list[SchemaDiscoveryChunk]:
        """Load markdown files and return resumable AI scan chunks."""
        chunks: list[SchemaDiscoveryChunk] = []
        for file_path in sorted(file_paths):
            text = unicodedata.normalize(
                "NFC",
                file_path.read_text(encoding="utf-8"),
            )
            for chunk_index, chunk_text in enumerate(self._split_text(text)):
                content_hash = sha256(chunk_text.encode("utf-8")).hexdigest()
                stable_path = file_path.as_posix()
                chunks.append(
                    SchemaDiscoveryChunk(
                        chunk_id=f"{_stable_slug(stable_path)}:{chunk_index}",
                        file_path=stable_path,
                        chunk_index=chunk_index,
                        text=chunk_text,
                        content_hash=content_hash,
                    )
                )
        return chunks

    def _split_text(self, text: str) -> list[str]:
        sections = _split_markdown_sections(text)
        chunks: list[str] = []
        current = ""
        for section in sections:
            if not current:
                current = section
                continue
            if len(current) + len(section) + 2 <= self.max_chunk_chars:
                current = f"{current}\n\n{section}"
                continue
            chunks.extend(self._split_oversized_text(current))
            current = section
        if current:
            chunks.extend(self._split_oversized_text(current))
        return [chunk for chunk in chunks if chunk.strip()]

    def _split_oversized_text(self, text: str) -> list[str]:
        if len(text) <= self.max_chunk_chars:
            return [text.strip()]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.max_chunk_chars, len(text))
            chunks.append(text[start:end].strip())
            if end == len(text):
                break
            start = max(end - self.overlap_chars, start + 1)
        return chunks


class SchemaDiscoveryCheckpointStore:
    """JSONL checkpoint store for resumable schema discovery runs."""

    def __init__(self, path: Path) -> None:
        """Initialize checkpoint storage."""
        self.path = path

    @service_observe(
        name="service.knowledge_graph.insurance_graph_schema_discovery.record_success",
        component="insurance_graph_schema_discovery",
    )
    def record_success(
        self,
        chunk: SchemaDiscoveryChunk,
        result: SchemaChunkDiscoveryResult,
    ) -> None:
        """Persist a successful chunk result."""
        self._append_record(
            {
                "status": "success",
                "chunk_id": chunk.chunk_id,
                "content_hash": chunk.content_hash,
                "file_path": chunk.file_path,
                "provider_slot_id": result.provider_slot_id,
                "result": _chunk_result_to_dict(result),
            }
        )

    @service_observe(
        name="service.knowledge_graph.insurance_graph_schema_discovery.record_error",
        component="insurance_graph_schema_discovery",
    )
    def record_error(
        self,
        chunk: SchemaDiscoveryChunk,
        *,
        provider_slot_id: str,
        error_message: str,
        error_type: str | None = None,
    ) -> None:
        """Persist a failed chunk attempt."""
        self._append_record(
            {
                "status": "error",
                "chunk_id": chunk.chunk_id,
                "content_hash": chunk.content_hash,
                "file_path": chunk.file_path,
                "provider_slot_id": provider_slot_id,
                "error_type": error_type,
                "error_message": error_message,
            }
        )

    def successful_chunk_ids(self, chunks: list[SchemaDiscoveryChunk]) -> set[str]:
        """Return chunk IDs with matching latest successful records."""
        latest_records = self._latest_records()
        successful_ids: set[str] = set()
        for chunk in chunks:
            record = latest_records.get(chunk.chunk_id)
            if (
                record
                and record.get("status") == "success"
                and record.get("content_hash") == chunk.content_hash
            ):
                successful_ids.add(chunk.chunk_id)
        return successful_ids

    def result_for_chunk(
        self,
        chunk: SchemaDiscoveryChunk,
    ) -> SchemaChunkDiscoveryResult | None:
        """Return the latest successful result for a chunk, if still current."""
        record = self._latest_records().get(chunk.chunk_id)
        if (
            not record
            or record.get("status") != "success"
            or record.get("content_hash") != chunk.content_hash
        ):
            return None
        result_payload = record.get("result")
        if not isinstance(result_payload, dict):
            return None
        return _chunk_result_from_dict(result_payload)

    def _append_record(self, record: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as checkpoint_file:
            checkpoint_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _latest_records(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        records: dict[str, dict[str, Any]] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunk_id = record.get("chunk_id")
            if isinstance(chunk_id, str):
                records[chunk_id] = record
        return records


class SchemaDiscoveryRunner:
    """Run schema discovery concurrently while respecting checkpoint state."""

    def __init__(
        self,
        *,
        checkpoint_store: SchemaDiscoveryCheckpointStore,
        provider_slots: list[SchemaDiscoveryProviderSlot],
        max_concurrency: int,
        max_retries: int = 2,
        attempt_timeout_seconds: float = 90.0,
    ) -> None:
        """Initialize the runner."""
        if not provider_slots:
            raise ValueError("At least one schema discovery provider slot is required.")
        if max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive.")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative.")
        if attempt_timeout_seconds <= 0:
            raise ValueError("attempt_timeout_seconds must be positive.")
        self.checkpoint_store = checkpoint_store
        self.provider_slots = provider_slots[:max_concurrency]
        self.max_retries = max_retries
        self.attempt_timeout_seconds = attempt_timeout_seconds

    @service_observe(
        name="service.knowledge_graph.insurance_graph_schema_discovery.run",
        component="insurance_graph_schema_discovery",
    )
    async def run(
        self,
        *,
        chunks: list[SchemaDiscoveryChunk],
        client: SchemaDiscoveryClient,
    ) -> list[SchemaChunkDiscoveryResult]:
        """Process only chunks without a current successful checkpoint."""
        queue: asyncio.Queue[SchemaDiscoveryChunk] = asyncio.Queue()
        completed_results: dict[str, SchemaChunkDiscoveryResult] = {}
        for chunk in chunks:
            existing_result = self.checkpoint_store.result_for_chunk(chunk)
            if existing_result is not None:
                completed_results[chunk.chunk_id] = existing_result
                continue
            queue.put_nowait(chunk)

        async def worker(slot: SchemaDiscoveryProviderSlot) -> None:
            while True:
                try:
                    chunk = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    result = await self._discover_with_retries(
                        chunk=chunk,
                        slot=slot,
                        client=client,
                    )
                    self.checkpoint_store.record_success(chunk, result)
                    completed_results[chunk.chunk_id] = result
                except Exception as exc:
                    self.checkpoint_store.record_error(
                        chunk,
                        provider_slot_id=slot.slot_id,
                        error_type=type(exc).__name__,
                        error_message=_error_message(exc),
                    )
                    logger.warning(
                        "schema discovery chunk failed",
                        extra={
                            "component": "insurance_graph_schema_discovery",
                            "chunk_id": chunk.chunk_id,
                            "file_path": chunk.file_path,
                            "provider_slot_id": slot.slot_id,
                            "error_type": type(exc).__name__,
                        },
                    )
                finally:
                    queue.task_done()

        await asyncio.gather(*(worker(slot) for slot in self.provider_slots))
        return [
            completed_results[chunk.chunk_id]
            for chunk in chunks
            if chunk.chunk_id in completed_results
        ]

    async def _discover_with_retries(
        self,
        *,
        chunk: SchemaDiscoveryChunk,
        slot: SchemaDiscoveryProviderSlot,
        client: SchemaDiscoveryClient,
    ) -> SchemaChunkDiscoveryResult:
        for attempt_index in range(self.max_retries + 1):
            try:
                async with asyncio.timeout(self.attempt_timeout_seconds):
                    return await client.discover_chunk_schema(chunk, slot)
            except TimeoutError as exc:
                timeout_message = (
                    "schema discovery provider attempt exceeded "
                    f"{self.attempt_timeout_seconds:g}s"
                )
                if attempt_index >= self.max_retries:
                    raise TimeoutError(timeout_message) from exc
                logger.warning(
                    "schema discovery chunk attempt timed out; retrying",
                    extra={
                        "component": "insurance_graph_schema_discovery",
                        "chunk_id": chunk.chunk_id,
                        "file_path": chunk.file_path,
                        "provider_slot_id": slot.slot_id,
                        "attempt_number": attempt_index + 1,
                        "max_retries": self.max_retries,
                        "timeout_seconds": self.attempt_timeout_seconds,
                    },
                )
            except Exception as exc:
                if attempt_index >= self.max_retries:
                    raise
                logger.warning(
                    "schema discovery chunk attempt failed; retrying",
                    extra={
                        "component": "insurance_graph_schema_discovery",
                        "chunk_id": chunk.chunk_id,
                        "file_path": chunk.file_path,
                        "provider_slot_id": slot.slot_id,
                        "attempt_number": attempt_index + 1,
                        "max_retries": self.max_retries,
                        "error_type": type(exc).__name__,
                    },
                )
        raise RuntimeError("unreachable schema discovery retry state")


class SchemaDiscoveryAggregator:
    """Aggregate raw schema proposals into per-file and corpus summaries."""

    @service_observe(
        name="service.knowledge_graph.insurance_graph_schema_discovery.aggregate",
        component="insurance_graph_schema_discovery",
    )
    def aggregate(
        self,
        results: list[SchemaChunkDiscoveryResult],
        *,
        canonical_node_map: dict[str, str] | None = None,
        canonical_relationship_map: dict[str, str] | None = None,
    ) -> SchemaDiscoverySummary:
        """Aggregate raw chunk results using optional AI-provided canonical maps."""
        node_map = canonical_node_map or {}
        relationship_map = canonical_relationship_map or {}
        node_buckets: dict[str, list[SchemaNodeProposal]] = {}
        relationship_buckets: dict[str, list[SchemaRelationshipProposal]] = {}
        node_files: dict[str, list[str]] = {}
        relationship_files: dict[str, list[str]] = {}
        per_file_nodes: dict[str, list[str]] = {}
        per_file_relationships: dict[str, list[str]] = {}

        for result in results:
            for node in result.nodes:
                canonical_label = node_map.get(node.label, node.label)
                node_buckets.setdefault(canonical_label, []).append(node)
                _append_unique(
                    node_files.setdefault(canonical_label, []),
                    result.file_path,
                )
                _append_unique(
                    per_file_nodes.setdefault(result.file_path, []),
                    canonical_label,
                )

            for relationship in result.relationships:
                canonical_label = relationship_map.get(
                    relationship.relationship_label,
                    relationship.relationship_label,
                )
                relationship_buckets.setdefault(canonical_label, []).append(
                    relationship
                )
                _append_unique(
                    relationship_files.setdefault(canonical_label, []),
                    result.file_path,
                )
                _append_unique(
                    per_file_relationships.setdefault(result.file_path, []),
                    canonical_label,
                )

        per_file = {
            file_path: FileSchemaSummary(
                node_labels=sorted(set(per_file_nodes.get(file_path, []))),
                relationship_labels=sorted(
                    set(per_file_relationships.get(file_path, []))
                ),
            )
            for file_path in sorted(set(per_file_nodes) | set(per_file_relationships))
        }
        return SchemaDiscoverySummary(
            nodes={
                label: _aggregate_nodes(label, proposals, node_files[label])
                for label, proposals in sorted(node_buckets.items())
            },
            relationships={
                label: _aggregate_relationships(
                    label,
                    proposals,
                    relationship_files[label],
                )
                for label, proposals in sorted(relationship_buckets.items())
            },
            per_file=per_file,
        )


class SchemaDiscoveryCanonicalizer:
    """Ask AI to merge similar schema labels into canonical labels."""

    @service_observe(
        name="service.knowledge_graph.insurance_graph_schema_discovery.canonicalize",
        component="insurance_graph_schema_discovery",
    )
    async def canonicalize(
        self,
        *,
        raw_summary: SchemaDiscoverySummary,
        client: SchemaCanonicalizationClient,
        slot: SchemaDiscoveryProviderSlot,
        fallback_to_identity: bool = False,
    ) -> SchemaCanonicalizationMap:
        """Canonicalize discovered node and relationship labels using AI."""
        try:
            return await client.canonicalize_schema_labels(
                node_items=list(raw_summary.nodes.values()),
                relationship_items=list(raw_summary.relationships.values()),
                slot=slot,
            )
        except Exception as exc:
            if not fallback_to_identity:
                raise
            logger.warning(
                "schema canonicalization failed; using identity map",
                extra={
                    "component": "insurance_graph_schema_discovery",
                    "slot_id": slot.slot_id,
                    "provider": slot.provider,
                    "model": slot.model,
                    "error_type": type(exc).__name__,
                },
            )
            return SchemaCanonicalizationMap(
                node_map={label: label for label in raw_summary.nodes},
                relationship_map={label: label for label in raw_summary.relationships},
            )

    @service_observe(
        name="service.knowledge_graph.insurance_graph_schema_discovery.canonicalize_in_batches",
        component="insurance_graph_schema_discovery",
    )
    async def canonicalize_in_batches(
        self,
        *,
        raw_summary: SchemaDiscoverySummary,
        client: SchemaCanonicalizationClient,
        slot: SchemaDiscoveryProviderSlot,
        batch_size: int = 80,
        batch_timeout_seconds: float = 90.0,
        fallback_to_normalized_identity: bool = True,
    ) -> SchemaCanonicalizationMap:
        """Canonicalize labels in smaller batches so providers do not time out."""
        if batch_size <= 0:
            raise ValueError("batch_size must be positive.")
        if batch_timeout_seconds <= 0:
            raise ValueError("batch_timeout_seconds must be positive.")

        node_items = _ordered_schema_items_for_batching(
            list(raw_summary.nodes.values()),
            kind="node",
        )
        relationship_items = _ordered_schema_items_for_batching(
            list(raw_summary.relationships.values()),
            kind="relationship",
        )
        normalized_map = build_normalized_schema_canonical_map(raw_summary)
        node_map = dict(normalized_map.node_map)
        relationship_map = dict(normalized_map.relationship_map)
        node_batches = _batch_items(node_items, batch_size)
        relationship_batches = _batch_items(relationship_items, batch_size)
        batch_count = max(len(node_batches), len(relationship_batches))

        for batch_index in range(batch_count):
            node_batch = (
                node_batches[batch_index] if batch_index < len(node_batches) else []
            )
            relationship_batch = (
                relationship_batches[batch_index]
                if batch_index < len(relationship_batches)
                else []
            )
            try:
                async with asyncio.timeout(batch_timeout_seconds):
                    batch_map = await client.canonicalize_schema_labels(
                        node_items=node_batch,
                        relationship_items=relationship_batch,
                        slot=slot,
                    )
            except Exception as exc:
                if not fallback_to_normalized_identity:
                    raise
                logger.warning(
                    "schema canonicalization batch failed; using normalized identity",
                    extra={
                        "component": "insurance_graph_schema_discovery",
                        "slot_id": slot.slot_id,
                        "provider": slot.provider,
                        "model": slot.model,
                        "batch_index": batch_index,
                        "error_type": type(exc).__name__,
                    },
                )
                continue

            for item in node_batch:
                node_map[item.label] = _normalize_node_schema_label(
                    batch_map.node_map.get(item.label, node_map[item.label])
                )
            for item in relationship_batch:
                relationship_map[item.label] = _normalize_relationship_schema_label(
                    batch_map.relationship_map.get(
                        item.label,
                        relationship_map[item.label],
                    )
                )

        return SchemaCanonicalizationMap(
            node_map=node_map,
            relationship_map=relationship_map,
        )


def build_provider_slots_from_settings(
    app_settings: Settings = settings,
) -> list[SchemaDiscoveryProviderSlot]:
    """Build provider slots from configured Ollama/API-key lists."""
    slots: list[SchemaDiscoveryProviderSlot] = []
    ollama_base_urls = app_settings.KG_SCHEMA_DISCOVERY_OLLAMA_BASE_URLS
    ollama_api_keys = app_settings.KG_SCHEMA_DISCOVERY_OLLAMA_API_KEYS
    if ollama_api_keys:
        for index, api_key in enumerate(ollama_api_keys):
            base_url = ollama_base_urls[index % len(ollama_base_urls)]
            slots.append(
                SchemaDiscoveryProviderSlot(
                    slot_id=f"ollama-{index}",
                    provider="ollama",
                    model=app_settings.KG_SCHEMA_DISCOVERY_OLLAMA_MODEL,
                    api_key=api_key,
                    base_url=base_url,
                )
            )
    for index, base_url in enumerate([] if ollama_api_keys else ollama_base_urls):
        slots.append(
            SchemaDiscoveryProviderSlot(
                slot_id=f"ollama-{index}",
                provider="ollama",
                model=app_settings.KG_SCHEMA_DISCOVERY_OLLAMA_MODEL,
                base_url=base_url,
            )
        )
    for index, api_key in enumerate(
        app_settings.KG_SCHEMA_DISCOVERY_OPENROUTER_API_KEYS
    ):
        slots.append(
            SchemaDiscoveryProviderSlot(
                slot_id=f"openrouter-{index}",
                provider="openrouter",
                model=app_settings.KG_SCHEMA_DISCOVERY_OPENROUTER_MODEL,
                api_key=api_key,
                base_url=app_settings.KG_SCHEMA_DISCOVERY_OPENROUTER_BASE_URL,
            )
        )
    for index, api_key in enumerate(app_settings.KG_SCHEMA_DISCOVERY_NVIDIA_API_KEYS):
        slots.append(
            SchemaDiscoveryProviderSlot(
                slot_id=f"nvidia-{index}",
                provider="nvidia",
                model=app_settings.KG_SCHEMA_DISCOVERY_NVIDIA_MODEL,
                api_key=api_key,
                base_url=app_settings.KG_SCHEMA_DISCOVERY_NVIDIA_BASE_URL,
            )
        )
    for index, api_key in enumerate(app_settings.KG_SCHEMA_DISCOVERY_GEMINI_API_KEYS):
        slots.append(
            SchemaDiscoveryProviderSlot(
                slot_id=f"gemini-{index}",
                provider="gemini",
                model=app_settings.KG_SCHEMA_DISCOVERY_GEMINI_MODEL,
                api_key=api_key,
                base_url=app_settings.KG_SCHEMA_DISCOVERY_GEMINI_BASE_URL,
            )
        )
    return slots


def find_markdown_files(input_path: Path) -> list[Path]:
    """Find markdown and text files under the input path."""
    if input_path.is_file():
        return [input_path]
    return sorted(
        file_path
        for file_path in input_path.rglob("*")
        if file_path.suffix.lower() in {".md", ".markdown", ".txt"}
    )


def write_summary_json(summary: SchemaDiscoverySummary, path: Path) -> None:
    """Write schema discovery summary JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_schema_discovery_markdown_report(
    summary: SchemaDiscoverySummary,
    path: Path,
) -> None:
    """Write a human-readable schema discovery report."""
    lines = [
        "# Knowledge Graph Schema Discovery Report",
        "",
        "## Nodes",
        "",
        "| Label | Occurrences | Files | Avg Confidence | Aliases |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for item in summary.nodes.values():
        lines.append(
            "| "
            + " | ".join(
                [
                    item.label,
                    str(item.occurrence_count),
                    str(len(item.source_files)),
                    f"{item.average_confidence:.4f}",
                    ", ".join(item.aliases),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Relationships",
            "",
            "| Label | Occurrences | Files | Avg Confidence | Aliases |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for item in summary.relationships.values():
        lines.append(
            "| "
            + " | ".join(
                [
                    item.label,
                    str(item.occurrence_count),
                    str(len(item.source_files)),
                    f"{item.average_confidence:.4f}",
                    ", ".join(item.aliases),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Per File",
            "",
            "| File | Nodes | Relationships |",
            "| --- | --- | --- |",
        ]
    )
    for file_path, file_summary in summary.per_file.items():
        lines.append(
            "| "
            + " | ".join(
                [
                    file_path,
                    ", ".join(file_summary.node_labels),
                    ", ".join(file_summary.relationship_labels),
                ]
            )
            + " |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_summary_json(path: Path) -> SchemaDiscoverySummary:
    """Load a schema discovery summary JSON file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SchemaDiscoverySummary(
        nodes={
            label: _aggregated_item_from_dict(item)
            for label, item in dict(payload.get("nodes", {})).items()
            if isinstance(item, dict)
        },
        relationships={
            label: _aggregated_item_from_dict(item)
            for label, item in dict(payload.get("relationships", {})).items()
            if isinstance(item, dict)
        },
        per_file={
            file_path: FileSchemaSummary(
                node_labels=[
                    str(label) for label in dict(file_summary).get("node_labels", [])
                ],
                relationship_labels=[
                    str(label)
                    for label in dict(file_summary).get("relationship_labels", [])
                ],
            )
            for file_path, file_summary in dict(payload.get("per_file", {})).items()
            if isinstance(file_summary, dict)
        },
    )


def apply_canonical_map_to_summary(
    summary: SchemaDiscoverySummary,
    canonical_map: SchemaCanonicalizationMap,
) -> SchemaDiscoverySummary:
    """Merge a schema summary using canonical node and relationship maps."""
    nodes = _merge_aggregated_schema_items(
        summary.nodes.values(),
        canonical_map.node_map,
        label_normalizer=_normalize_node_schema_label,
    )
    relationships = _merge_aggregated_schema_items(
        summary.relationships.values(),
        canonical_map.relationship_map,
        label_normalizer=_normalize_relationship_schema_label,
    )
    per_file: dict[str, FileSchemaSummary] = {}
    for file_path, file_summary in summary.per_file.items():
        node_labels = sorted(
            {
                _normalize_node_schema_label(canonical_map.node_map.get(label, label))
                for label in file_summary.node_labels
                if label in summary.nodes
            }
        )
        relationship_labels = sorted(
            {
                _normalize_relationship_schema_label(
                    canonical_map.relationship_map.get(label, label)
                )
                for label in file_summary.relationship_labels
                if label in summary.relationships
            }
        )
        if node_labels or relationship_labels:
            per_file[file_path] = FileSchemaSummary(
                node_labels=node_labels,
                relationship_labels=relationship_labels,
            )
    return SchemaDiscoverySummary(
        nodes=nodes,
        relationships=relationships,
        per_file=per_file,
    )


def build_normalized_schema_canonical_map(
    summary: SchemaDiscoverySummary,
) -> SchemaCanonicalizationMap:
    """Build a deterministic ASCII-safe identity canonical map."""
    return SchemaCanonicalizationMap(
        node_map={
            label: _normalize_node_schema_label(label) for label in summary.nodes
        },
        relationship_map={
            label: _normalize_relationship_schema_label(label)
            for label in summary.relationships
        },
    )


def filter_schema_summary(
    summary: SchemaDiscoverySummary,
    *,
    min_node_occurrences: int = 5,
    min_relationship_occurrences: int = 5,
    min_source_files: int = 3,
    protected_node_labels: frozenset[str] = CORE_SCHEMA_NODE_LABELS,
    protected_relationship_labels: frozenset[str] = CORE_SCHEMA_RELATIONSHIP_LABELS,
) -> SchemaDiscoverySummary:
    """Keep stable schema labels and core insurance concepts."""
    kept_nodes = {
        label: item
        for label, item in sorted(summary.nodes.items())
        if (
            item.occurrence_count >= min_node_occurrences
            or len(item.source_files) >= min_source_files
            or label in protected_node_labels
        )
    }
    kept_relationships = {
        label: item
        for label, item in sorted(summary.relationships.items())
        if (
            item.occurrence_count >= min_relationship_occurrences
            or len(item.source_files) >= min_source_files
            or label in protected_relationship_labels
        )
    }
    per_file: dict[str, FileSchemaSummary] = {}
    for file_path, file_summary in summary.per_file.items():
        node_labels = sorted(
            label for label in file_summary.node_labels if label in kept_nodes
        )
        relationship_labels = sorted(
            label
            for label in file_summary.relationship_labels
            if label in kept_relationships
        )
        if node_labels or relationship_labels:
            per_file[file_path] = FileSchemaSummary(
                node_labels=node_labels,
                relationship_labels=relationship_labels,
            )
    return SchemaDiscoverySummary(
        nodes=kept_nodes,
        relationships=kept_relationships,
        per_file=per_file,
    )


def build_final_schema_v1(
    summary: SchemaDiscoverySummary,
    *,
    max_node_labels: int = 60,
    max_relationship_labels: int = 90,
) -> SchemaDiscoverySummary:
    """Select the bounded v1 schema from cleaned AI-discovered labels."""
    if max_node_labels <= 0:
        raise ValueError("max_node_labels must be positive.")
    if max_relationship_labels <= 0:
        raise ValueError("max_relationship_labels must be positive.")

    canonical_map = SchemaCanonicalizationMap(
        node_map={
            label: FINAL_SCHEMA_V1_NODE_MERGE_MAP.get(label, label)
            for label in summary.nodes
        },
        relationship_map={
            label: FINAL_SCHEMA_V1_RELATIONSHIP_MERGE_MAP.get(label, label)
            for label in summary.relationships
        },
    )
    merged_summary = apply_canonical_map_to_summary(summary, canonical_map)
    selected_node_labels = _select_final_schema_labels(
        merged_summary.nodes,
        FINAL_SCHEMA_V1_NODE_LABELS,
        max_node_labels,
    )
    selected_relationship_labels = _select_final_schema_labels(
        merged_summary.relationships,
        FINAL_SCHEMA_V1_RELATIONSHIP_TYPES,
        max_relationship_labels,
    )
    return _subset_schema_summary(
        merged_summary,
        node_labels=selected_node_labels,
        relationship_labels=selected_relationship_labels,
    )


def build_final_schema_v1_contract(
    summary: SchemaDiscoverySummary,
) -> dict[str, object]:
    """Build the schema contract used to constrain later triple extraction."""
    node_properties = {
        label: _property_definitions_to_dicts(_node_property_definitions(label))
        for label in summary.nodes
    }
    relationship_properties = {
        relationship_type: _property_definitions_to_dicts(
            _relationship_property_definitions(relationship_type)
        )
        for relationship_type in summary.relationships
    }
    return {
        "schema_name": "health_insurance_kg_schema_v1",
        "schema_version": "v1",
        "node_count": len(summary.nodes),
        "relationship_count": len(summary.relationships),
        "allowed_node_labels": list(summary.nodes),
        "allowed_relationship_types": list(summary.relationships),
        "node_properties": node_properties,
        "relationship_properties": relationship_properties,
    }


def write_final_schema_v1_property_csvs(
    contract: dict[str, object],
    output_dir: Path,
) -> dict[str, Path]:
    """Write final schema v1 node and relationship property CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    node_properties_path = output_dir / "final_schema_v1_node_properties.csv"
    relationship_properties_path = (
        output_dir / "final_schema_v1_relationship_properties.csv"
    )
    node_properties = dict(contract.get("node_properties", {}))
    relationship_properties = dict(contract.get("relationship_properties", {}))

    with node_properties_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "node_label",
                "property_name",
                "data_type",
                "required",
                "description",
            ],
        )
        writer.writeheader()
        for node_label in contract.get("allowed_node_labels", []):
            for property_definition in node_properties.get(str(node_label), []):
                writer.writerow(
                    {
                        "node_label": str(node_label),
                        "property_name": str(property_definition["name"]),
                        "data_type": str(property_definition["data_type"]),
                        "required": _csv_bool(property_definition["required"]),
                        "description": str(property_definition["description"]),
                    }
                )

    with relationship_properties_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "relationship_type",
                "property_name",
                "data_type",
                "required",
                "description",
            ],
        )
        writer.writeheader()
        for relationship_type in contract.get("allowed_relationship_types", []):
            for property_definition in relationship_properties.get(
                str(relationship_type),
                [],
            ):
                writer.writerow(
                    {
                        "relationship_type": str(relationship_type),
                        "property_name": str(property_definition["name"]),
                        "data_type": str(property_definition["data_type"]),
                        "required": _csv_bool(property_definition["required"]),
                        "description": str(property_definition["description"]),
                    }
                )

    return {
        "node_properties": node_properties_path,
        "relationship_properties": relationship_properties_path,
    }


def _aggregated_item_from_dict(payload: dict[str, Any]) -> AggregatedSchemaItem:
    return AggregatedSchemaItem(
        label=str(payload["label"]),
        occurrence_count=int(payload["occurrence_count"]),
        source_files=[str(item) for item in payload.get("source_files", [])],
        aliases=[str(item) for item in payload.get("aliases", [])],
        examples=[str(item) for item in payload.get("examples", [])],
        average_confidence=float(payload.get("average_confidence", 0.0)),
    )


def _node_property_definitions(label: str) -> tuple[tuple[str, str, bool, str], ...]:
    return _deduplicate_property_definitions(
        (
            *COMMON_FINAL_SCHEMA_V1_NODE_PROPERTIES,
            *FINAL_SCHEMA_V1_NODE_SPECIFIC_PROPERTIES.get(label, ()),
        )
    )


def _relationship_property_definitions(
    relationship_type: str,
) -> tuple[tuple[str, str, bool, str], ...]:
    return _deduplicate_property_definitions(
        (
            *COMMON_FINAL_SCHEMA_V1_RELATIONSHIP_PROPERTIES,
            *_relationship_specific_property_definitions(relationship_type),
        )
    )


def _relationship_specific_property_definitions(
    relationship_type: str,
) -> tuple[tuple[str, str, bool, str], ...]:
    properties: list[tuple[str, str, bool, str]] = []
    if relationship_type.startswith("COVERS") or relationship_type in {
        "HAS_BENEFIT",
        "PROVIDES_BENEFIT",
        "TRIGGERS_BENEFIT",
    }:
        properties.extend(
            [
                ("coverage_scope", "string", False, "Covered scope."),
                ("benefit_amount_text", "string", False, "Raw benefit amount text."),
            ]
        )
    if relationship_type in {
        "HAS_LIMIT",
        "HAS_SUM_INSURED",
        "HAS_PREMIUM",
        "PAYS",
        "PAYS_BENEFIT_TO",
        "PAYS_PREMIUM",
        "COVERS_EXPENSE",
    }:
        properties.extend(
            [
                ("amount", "float", False, "Amount stated on the relationship."),
                ("currency", "string", False, "Currency for the amount."),
            ]
        )
    if relationship_type in {"HAS_PREMIUM", "PAYS_PREMIUM"}:
        properties.append(
            ("payment_frequency", "string", False, "Premium payment frequency.")
        )
    if relationship_type in {
        "HAS_PAYOUT_RATE",
        "TRIGGERS_PAYMENT",
        "CALCULATED_BY",
    }:
        properties.extend(
            [
                ("rate_value", "float", False, "Rate value."),
                ("rate_unit", "string", False, "Rate unit."),
            ]
        )
    if relationship_type in {
        "HAS_WAITING_PERIOD",
        "SUBJECT_TO_WAITING_PERIOD",
    }:
        properties.extend(
            [
                ("duration_value", "integer", False, "Duration value."),
                ("duration_unit", "string", False, "Duration unit."),
            ]
        )
    if relationship_type in {
        "HAS_EXCLUSION",
        "EXCLUDES",
        "EXCLUDES_CONDITION",
        "EXCLUDES_TREATMENT",
        "EXCLUDES_DIRECT_BILLING",
        "EXCLUDES_GUARANTEE",
    }:
        properties.append(
            ("exclusion_reason", "string", False, "Reason or rule for exclusion.")
        )
    if relationship_type in {
        "REQUIRES_DOCUMENT",
        "PROVIDES_DOCUMENT",
        "DEFINED_IN",
        "GOVERNED_BY",
    }:
        properties.append(
            ("document_role", "string", False, "Role of the linked document.")
        )
    if relationship_type in {"HAS_CATEGORY", "IS_A", "PART_OF"}:
        properties.append(
            ("classification_basis", "string", False, "Basis for classification.")
        )
    if relationship_type in {"LOCATED_AT", "HAS_GEOGRAPHIC_SCOPE"}:
        properties.append(("location_scope", "string", False, "Location scope."))
    if relationship_type in {"HAS_EFFECTIVE_DATE"}:
        properties.append(("effective_date", "date", False, "Effective date."))
    if relationship_type in {
        "SUBMITS_CLAIM",
        "FILES_CLAIM",
    }:
        properties.append(("claim_status", "string", False, "Claim status."))
    if relationship_type in {
        "PERFORMED_AT",
        "PERFORMED_BY",
        "TREATED_AT",
        "OCCURS_AT",
        "EXPERIENCES",
        "UNDERGOES",
        "DIAGNOSES",
        "PRESCRIBES",
        "USES_DEVICE",
    }:
        properties.append(("event_date", "date", False, "Related event date."))
    if relationship_type in {
        "SUPPORTS_DIRECT_BILLING",
        "PROVIDES_GUARANTEE",
    }:
        properties.append(
            (
                "authorization_required",
                "boolean",
                False,
                "Whether preapproval is needed.",
            )
        )
    return tuple(properties)


def _property_definitions_to_dicts(
    property_definitions: tuple[tuple[str, str, bool, str], ...],
) -> list[dict[str, object]]:
    return [
        {
            "name": property_name,
            "data_type": data_type,
            "required": required,
            "description": description,
        }
        for property_name, data_type, required, description in property_definitions
    ]


def _deduplicate_property_definitions(
    property_definitions: tuple[tuple[str, str, bool, str], ...],
) -> tuple[tuple[str, str, bool, str], ...]:
    deduplicated: list[tuple[str, str, bool, str]] = []
    seen_names: set[str] = set()
    for property_definition in property_definitions:
        property_name = property_definition[0]
        if property_name in seen_names:
            continue
        seen_names.add(property_name)
        deduplicated.append(property_definition)
    return tuple(deduplicated)


def _csv_bool(value: object) -> str:
    return "true" if bool(value) else "false"


def _select_final_schema_labels(
    items: dict[str, AggregatedSchemaItem],
    allowed_labels: tuple[str, ...],
    limit: int,
) -> list[str]:
    labels = [label for label in allowed_labels if label in items]
    if len(labels) <= limit:
        return labels
    return [
        label
        for label, _item in sorted(
            ((label, items[label]) for label in labels),
            key=lambda label_item: (
                -label_item[1].occurrence_count,
                -len(label_item[1].source_files),
                allowed_labels.index(label_item[0]),
            ),
        )[:limit]
    ]


def _subset_schema_summary(
    summary: SchemaDiscoverySummary,
    *,
    node_labels: list[str],
    relationship_labels: list[str],
) -> SchemaDiscoverySummary:
    kept_nodes = {label: summary.nodes[label] for label in node_labels}
    kept_relationships = {
        label: summary.relationships[label] for label in relationship_labels
    }
    per_file: dict[str, FileSchemaSummary] = {}
    for file_path, file_summary in summary.per_file.items():
        file_node_labels = sorted(
            label for label in file_summary.node_labels if label in kept_nodes
        )
        file_relationship_labels = sorted(
            label
            for label in file_summary.relationship_labels
            if label in kept_relationships
        )
        if file_node_labels or file_relationship_labels:
            per_file[file_path] = FileSchemaSummary(
                node_labels=file_node_labels,
                relationship_labels=file_relationship_labels,
            )
    return SchemaDiscoverySummary(
        nodes=kept_nodes,
        relationships=kept_relationships,
        per_file=per_file,
    )


def _merge_aggregated_schema_items(
    items: Iterable[AggregatedSchemaItem],
    canonical_label_map: dict[str, str],
    *,
    label_normalizer: Callable[[str], str],
) -> dict[str, AggregatedSchemaItem]:
    buckets: dict[str, list[AggregatedSchemaItem]] = {}
    for item in items:
        canonical_label = label_normalizer(
            canonical_label_map.get(item.label, item.label)
        )
        buckets.setdefault(canonical_label, []).append(item)

    merged_items: dict[str, AggregatedSchemaItem] = {}
    for canonical_label, grouped_items in sorted(buckets.items()):
        source_files: list[str] = []
        aliases: list[str] = []
        examples: list[str] = []
        occurrence_count = sum(item.occurrence_count for item in grouped_items)
        weighted_confidence_sum = 0.0
        for item in grouped_items:
            for source_file in item.source_files:
                _append_unique(source_files, source_file)
            for alias in item.aliases:
                _append_unique(aliases, alias)
            for example in item.examples:
                _append_unique(examples, example)
            weighted_confidence_sum += item.average_confidence * item.occurrence_count
        merged_items[canonical_label] = AggregatedSchemaItem(
            label=canonical_label,
            occurrence_count=occurrence_count,
            source_files=source_files,
            aliases=aliases,
            examples=examples[:5],
            average_confidence=round(weighted_confidence_sum / occurrence_count, 4)
            if occurrence_count
            else 0.0,
        )
    return merged_items


def _ordered_schema_items_for_batching(
    items: list[AggregatedSchemaItem],
    *,
    kind: Literal["node", "relationship"],
) -> list[AggregatedSchemaItem]:
    return sorted(
        items,
        key=lambda item: (
            _schema_item_family_key(item, kind=kind),
            -item.occurrence_count,
            slugify_vietnamese(item.label, separator="_", fallback="unknown"),
        ),
    )


def _batch_items(
    items: list[AggregatedSchemaItem],
    batch_size: int,
) -> list[list[AggregatedSchemaItem]]:
    return [
        items[index : index + batch_size] for index in range(0, len(items), batch_size)
    ]


def _schema_item_family_key(
    item: AggregatedSchemaItem,
    *,
    kind: Literal["node", "relationship"],
) -> str:
    searchable_text = _canonical_search_text(" ".join([item.label, *item.aliases]))
    if kind == "node":
        family_terms = {
            "accident": ["accident", "tai nan"],
            "benefit": ["benefit", "quyen loi", "chi tra", "muc boi thuong"],
            "claim": ["claim", "yeu cau boi thuong", "ho so"],
            "condition": ["condition", "benh", "tinh trang"],
            "contract": ["contract", "hop dong", "giay chung nhan"],
            "exclusion": ["exclusion", "loai tru", "khong chi tra"],
            "expense": ["expense", "chi phi", "vien phi"],
            "facility": ["facility", "hospital", "benh vien", "co so y te"],
            "limit": ["limit", "han muc", "gioi han", "so tien bao hiem"],
            "location": ["location", "dia diem", "quoc gia", "tinh", "thanh pho"],
            "person": ["person", "nguoi", "benh nhan", "khach hang"],
            "plan": ["plan", "program", "goi", "chuong trinh", "san pham"],
            "premium": ["premium", "phi bao hiem", "muc phi"],
            "provider": ["provider", "bac si", "nha cung cap"],
            "treatment": ["treatment", "dieu tri", "phau thuat", "thu thuat"],
            "waiting": ["waiting", "thoi gian cho"],
        }
    else:
        family_terms = {
            "applies": ["applies", "ap dung"],
            "benefit": ["benefit", "quyen loi"],
            "coverage": ["cover", "bao hiem", "chi tra"],
            "exclusion": ["exclude", "loai tru", "khong bao lanh"],
            "issue": ["issue", "phat hanh", "cap"],
            "limit": ["limit", "han muc", "gioi han"],
            "location": ["located", "toa lac", "nam tai", "thuoc"],
            "payment": ["pay", "pays", "tra tien", "boi thuong"],
            "purchase": ["purchase", "mua", "giao ket", "ky ket"],
            "service": ["service", "dich vu", "cung cap"],
            "taxonomy": ["is a", "loai hinh", "part of", "thuoc"],
            "treatment": ["treat", "dieu tri", "thuc hien"],
            "waiting": ["waiting", "thoi gian cho"],
        }
    for family, terms in family_terms.items():
        if any(term in searchable_text for term in terms):
            return family
    return searchable_text[:24]


def _canonical_search_text(value: str) -> str:
    ascii_value = transliterate_vietnamese(_split_camel_case(value)).lower()
    return re.sub(r"[^a-z0-9]+", " ", ascii_value).strip()


def _normalize_node_schema_label(label: str) -> str:
    stripped_label = label.strip()
    if re.fullmatch(r"[A-Z][A-Za-z0-9]*", stripped_label):
        return stripped_label
    words = re.findall(
        r"[A-Za-z0-9]+",
        transliterate_vietnamese(_split_camel_case(stripped_label)),
    )
    if not words:
        return "UnknownNode"
    return "".join(word[:1].upper() + word[1:].lower() for word in words)


def _normalize_relationship_schema_label(label: str) -> str:
    stripped_label = label.strip()
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", stripped_label):
        return stripped_label
    ascii_label = transliterate_vietnamese(_split_camel_case(stripped_label))
    normalized_label = re.sub(r"[^A-Za-z0-9]+", "_", ascii_label.upper()).strip("_")
    return normalized_label or "UNKNOWN_RELATIONSHIP"


def _split_camel_case(value: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)


def _split_markdown_sections(text: str) -> list[str]:
    matches = list(re.finditer(r"^(#{1,6})\s+.+?\s*$", text, flags=re.MULTILINE))
    if not matches:
        return [text.strip()] if text.strip() else []
    sections: list[str] = []
    if matches[0].start() > 0:
        preface = text[: matches[0].start()].strip()
        if preface:
            sections.append(preface)
    for index, match in enumerate(matches):
        next_start = (
            matches[index + 1].start() if index + 1 < len(matches) else len(text)
        )
        section = text[match.start() : next_start].strip()
        if section:
            sections.append(section)
    return sections


def _chunk_result_to_dict(result: SchemaChunkDiscoveryResult) -> dict[str, Any]:
    return asdict(result)


def _chunk_result_from_dict(payload: dict[str, Any]) -> SchemaChunkDiscoveryResult:
    return SchemaChunkDiscoveryResult(
        chunk_id=str(payload["chunk_id"]),
        file_path=str(payload["file_path"]),
        content_hash=str(payload["content_hash"]),
        provider_slot_id=str(payload["provider_slot_id"]),
        nodes=[
            SchemaNodeProposal(
                label=str(node["label"]),
                vietnamese_aliases=[str(item) for item in node["vietnamese_aliases"]],
                description=str(node["description"]),
                evidence_text=str(node["evidence_text"]),
                confidence=float(node["confidence"]),
            )
            for node in payload.get("nodes", [])
            if isinstance(node, dict)
        ],
        relationships=[
            SchemaRelationshipProposal(
                source_label=str(relationship["source_label"]),
                relationship_label=str(relationship["relationship_label"]),
                target_label=str(relationship["target_label"]),
                vietnamese_aliases=[
                    str(item) for item in relationship["vietnamese_aliases"]
                ],
                description=str(relationship["description"]),
                evidence_text=str(relationship["evidence_text"]),
                confidence=float(relationship["confidence"]),
            )
            for relationship in payload.get("relationships", [])
            if isinstance(relationship, dict)
        ],
        usage=dict(payload.get("usage", {})),
    )


def _aggregate_nodes(
    label: str,
    proposals: list[SchemaNodeProposal],
    source_files: list[str],
) -> AggregatedSchemaItem:
    aliases: list[str] = []
    examples: list[str] = []
    for proposal in proposals:
        for alias in proposal.vietnamese_aliases:
            _append_unique(aliases, alias)
        _append_unique(examples, proposal.evidence_text)
    return AggregatedSchemaItem(
        label=label,
        occurrence_count=len(proposals),
        source_files=source_files,
        aliases=aliases,
        examples=examples[:5],
        average_confidence=_average([proposal.confidence for proposal in proposals]),
    )


def _aggregate_relationships(
    label: str,
    proposals: list[SchemaRelationshipProposal],
    source_files: list[str],
) -> AggregatedSchemaItem:
    aliases: list[str] = []
    examples: list[str] = []
    for proposal in proposals:
        for alias in proposal.vietnamese_aliases:
            _append_unique(aliases, alias)
        _append_unique(examples, proposal.evidence_text)
    return AggregatedSchemaItem(
        label=label,
        occurrence_count=len(proposals),
        source_files=source_files,
        aliases=aliases,
        examples=examples[:5],
        average_confidence=_average([proposal.confidence for proposal in proposals]),
    )


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _error_message(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return repr(exc)


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _stable_slug(value: str) -> str:
    return slugify_vietnamese(value, separator="_", fallback="unknown")
