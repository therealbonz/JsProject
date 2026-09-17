import csv
import io
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant import Organization
from app.models.crm import Company, Contact, Lead, ProspectCampaign
from app.schemas.prospects import (
    ProspectParsedRow,
    ProspectImportPreview,
    ProspectImportResponse
)

logger = logging.getLogger(__name__)

class ProspectImportService:
    # Standard field mapping dictionaries
    HEADER_SYNONYMS = {
        "first_name": ["first_name", "firstname", "first", "fname", "given_name"],
        "last_name": ["last_name", "lastname", "last", "lname", "surname", "family_name"],
        "full_name": ["name", "full_name", "fullname", "homeowner", "homeowner_name", "contact_name", "customer", "client"],
        "phone": ["phone", "phone_number", "cell", "cell_phone", "mobile", "tel", "telephone", "phone#", "contact_phone"],
        "email": ["email", "e-mail", "email_address", "contact_email", "mail"],
        "company_name": ["company", "company_name", "business", "business_name", "organization", "account_name", "household"],
        "address": ["address", "street", "street_address", "address_1", "address1", "service_address"],
        "city": ["city", "town", "municipality"],
        "state": ["state", "province", "region"],
        "zip_code": ["zip", "zip_code", "postal_code", "zipcode", "postcode"],
        "trade_service": ["trade", "service", "service_type", "vertical", "job_type", "trade_service", "service_needed"],
        "notes": ["notes", "note", "comment", "comments", "description", "details", "special_instructions", "remarks"]
    }

    @classmethod
    def clean_phone_number(cls, phone_raw: Optional[str]) -> Tuple[Optional[str], bool]:
        """
        Normalizes a raw phone number into standard E.164 format (+1XXXXXXXXXX).
        Returns (clean_phone, is_valid).
        """
        if not phone_raw:
            return None, False

        digits = re.sub(r"\D", "", str(phone_raw))
        if len(digits) == 10:
            return f"+1{digits}", True
        elif len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}", True
        elif len(digits) > 10 and str(phone_raw).strip().startswith("+"):
            return f"+{digits}", True
        elif len(digits) >= 10:
            return f"+{digits}", True

        return None, False

    @classmethod
    def decode_csv_bytes(cls, file_bytes: bytes) -> str:
        """
        Decodes raw bytes into text supporting UTF-8 with BOM, standard UTF-8, or Latin-1.
        """
        for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                return file_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        return file_bytes.decode("utf-8", errors="replace")

    @classmethod
    def detect_headers(cls, headers: List[str]) -> Dict[str, str]:
        """
        Maps raw CSV column headers to canonical prospect fields using robust fuzzy matching.
        Returns mapping dict: {raw_header: canonical_field}
        """
        mapping: Dict[str, str] = {}
        assigned_canonical = set()

        for raw in headers:
            norm = re.sub(r"[^a-zA-Z0-9_]", "_", raw.strip().lower()).strip("_")
            norm_clean = norm.replace("_", "")

            # 1. Check first name vs last name vs full name
            if ("first" in norm or "fname" in norm or "given" in norm) and "name" in norm:
                if "first_name" not in assigned_canonical:
                    mapping[raw] = "first_name"
                    assigned_canonical.add("first_name")
                    continue
            elif ("last" in norm or "lname" in norm or "surname" in norm or "family" in norm):
                if "last_name" not in assigned_canonical:
                    mapping[raw] = "last_name"
                    assigned_canonical.add("last_name")
                    continue
            elif any(k in norm for k in ["homeowner", "customer", "client", "full_name", "fullname"]) or norm == "name":
                if "full_name" not in assigned_canonical and "first_name" not in assigned_canonical:
                    mapping[raw] = "full_name"
                    assigned_canonical.add("full_name")
                    continue

            # 2. Phone
            if any(k in norm for k in ["phone", "cell", "mobile", "telephone", "tel"]):
                if "phone" not in assigned_canonical:
                    mapping[raw] = "phone"
                    assigned_canonical.add("phone")
                    continue

            # 3. Email
            if "email" in norm_clean or "mail" in norm:
                if "email" not in assigned_canonical:
                    mapping[raw] = "email"
                    assigned_canonical.add("email")
                    continue

            # 4. Company / Business
            if any(k in norm for k in ["company", "business", "organization", "account_name", "household"]):
                if "company_name" not in assigned_canonical:
                    mapping[raw] = "company_name"
                    assigned_canonical.add("company_name")
                    continue

            # 5. Address
            if any(k in norm for k in ["street", "address", "addr"]):
                if "address" not in assigned_canonical:
                    mapping[raw] = "address"
                    assigned_canonical.add("address")
                    continue

            # 6. City
            if any(k in norm for k in ["city", "town", "municipality"]):
                if "city" not in assigned_canonical:
                    mapping[raw] = "city"
                    assigned_canonical.add("city")
                    continue

            # 7. State
            if norm in ["state", "province", "region"] or "state" in norm:
                if "state" not in assigned_canonical:
                    mapping[raw] = "state"
                    assigned_canonical.add("state")
                    continue

            # 8. Zip
            if any(k in norm for k in ["zip", "postal", "postcode"]):
                if "zip_code" not in assigned_canonical:
                    mapping[raw] = "zip_code"
                    assigned_canonical.add("zip_code")
                    continue

            # 9. Trade / Service
            if any(k in norm for k in ["trade", "service", "vertical", "job_type", "needed"]):
                if "trade_service" not in assigned_canonical:
                    mapping[raw] = "trade_service"
                    assigned_canonical.add("trade_service")
                    continue

            # 10. Notes / Instructions
            if any(k in norm for k in ["note", "comment", "instruction", "detail", "remark", "description"]):
                mapping[raw] = "notes"
                continue

            # Default
            mapping[raw] = "custom"

        return mapping

    @classmethod
    def parse_csv_rows(
        cls,
        csv_text: str,
        default_trade: str = "general"
    ) -> Tuple[Dict[str, str], List[ProspectParsedRow]]:
        """
        Parses CSV text into a list of ProspectParsedRow records with mapped columns.
        """
        # Determine delimiter
        sample = csv_text[:2048]
        delimiter = ","
        if ";" in sample and sample.count(";") > sample.count(","):
            delimiter = ";"
        elif "\t" in sample and sample.count("\t") > sample.count(","):
            delimiter = "\t"

        reader = csv.reader(io.StringIO(csv_text), delimiter=delimiter)
        try:
            raw_headers = next(reader, None)
        except Exception:
            raw_headers = None

        if not raw_headers:
            return {}, []

        raw_headers = [h.strip() for h in raw_headers if h is not None]
        column_mapping = cls.detect_headers(raw_headers)

        rows: List[ProspectParsedRow] = []
        for idx, row in enumerate(reader, start=1):
            if not row or all(not str(c).strip() for c in row):
                continue  # Skip completely empty rows

            row_data: Dict[str, Any] = {}
            custom_fields: Dict[str, Any] = {}

            for h_idx, col_value in enumerate(row):
                if h_idx < len(raw_headers):
                    header = raw_headers[h_idx]
                    canonical = column_mapping.get(header, "custom")
                    val = str(col_value).strip() if col_value is not None else ""
                    if canonical == "custom":
                        if val:
                            custom_fields[header] = val
                    else:
                        row_data[canonical] = val

            # Split full_name if first_name and last_name aren't distinct
            first_name = row_data.get("first_name")
            last_name = row_data.get("last_name")
            if not first_name and row_data.get("full_name"):
                parts = row_data["full_name"].split(maxsplit=1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""

            phone_raw = row_data.get("phone")
            clean_phone, phone_valid = cls.clean_phone_number(phone_raw)

            # Determine validation
            is_valid = True
            val_error = None
            if not clean_phone:
                is_valid = False
                val_error = "Missing or invalid 10-digit phone number"
            elif not first_name and not row_data.get("company_name"):
                is_valid = False
                val_error = "Missing contact or homeowner name"

            trade = row_data.get("trade_service") or default_trade

            parsed = ProspectParsedRow(
                row_index=idx,
                first_name=first_name,
                last_name=last_name or "",
                phone=phone_raw,
                clean_phone=clean_phone,
                email=row_data.get("email"),
                company_name=row_data.get("company_name"),
                address=row_data.get("address"),
                city=row_data.get("city"),
                state=row_data.get("state"),
                zip_code=row_data.get("zip_code"),
                trade_service=trade,
                notes=row_data.get("notes"),
                custom_fields=custom_fields,
                is_valid=is_valid,
                validation_error=val_error
            )
            rows.append(parsed)

        return column_mapping, rows

    @classmethod
    async def get_existing_phone_numbers(
        cls,
        organization_id: str,
        db: AsyncSession
    ) -> set:
        """
        Retrieves set of normalized phone numbers already stored in contacts for this tenant org.
        """
        stmt = select(Contact.phone).where(
            Contact.organization_id == organization_id,
            Contact.phone.isnot(None)
        )
        res = await db.execute(stmt)
        existing = set()
        for (phone,) in res.all():
            if phone:
                clean, valid = cls.clean_phone_number(phone)
                if valid and clean:
                    existing.add(clean)
        return existing

    @classmethod
    async def preview_import(
        cls,
        file_bytes: bytes,
        default_trade: str = "general",
        organization_id: Optional[str] = None,
        db: Optional[AsyncSession] = None,
        sample_limit: int = 5
    ) -> ProspectImportPreview:
        """
        Performs a dry-run parsing preview: maps columns, validates sample rows, and checks duplicates.
        """
        csv_text = cls.decode_csv_bytes(file_bytes)
        mapping, rows = cls.parse_csv_rows(csv_text, default_trade=default_trade)

        existing_phones = set()
        if organization_id and db:
            existing_phones = await cls.get_existing_phone_numbers(organization_id, db)

        seen_in_file = set()
        valid_cnt = 0
        invalid_cnt = 0
        dup_cnt = 0

        for r in rows:
            if not r.is_valid:
                invalid_cnt += 1
                continue

            # Check duplication
            if r.clean_phone in seen_in_file or r.clean_phone in existing_phones:
                r.is_duplicate = True
                dup_cnt += 1
            else:
                seen_in_file.add(r.clean_phone)
                valid_cnt += 1

        return ProspectImportPreview(
            total_rows_detected=len(rows),
            detected_columns=mapping,
            sample_rows=rows[:sample_limit],
            valid_count=valid_cnt,
            invalid_count=invalid_cnt,
            duplicate_count=dup_cnt
        )

    @classmethod
    async def execute_import(
        cls,
        file_bytes: bytes,
        campaign_name: str,
        trade_service: str,
        organization: Organization,
        db: AsyncSession,
        skip_duplicates: bool = True,
        source_filename: Optional[str] = None
    ) -> ProspectImportResponse:
        """
        Parses prospect CSV and commits records into Company, Contact, Lead, and ProspectCampaign.
        """
        csv_text = cls.decode_csv_bytes(file_bytes)
        mapping, rows = cls.parse_csv_rows(csv_text, default_trade=trade_service)

        existing_phones = await cls.get_existing_phone_numbers(organization.id, db)

        # 1. Create ProspectCampaign record
        campaign = ProspectCampaign(
            organization_id=organization.id,
            name=campaign_name.strip() or f"{trade_service.title()} Outreach Campaign - {datetime.now(timezone.utc).strftime('%b %d')}",
            trade_service=trade_service,
            source_filename=source_filename or "uploaded_prospects.csv",
            status="ready",
            total_rows=len(rows),
            column_mappings=mapping
        )
        db.add(campaign)
        await db.flush()

        seen_in_file = set()
        leads_created = 0
        duplicates_skipped = 0
        errors_count = 0

        for r in rows:
            if not r.is_valid:
                errors_count += 1
                continue

            is_dup = (r.clean_phone in seen_in_file) or (r.clean_phone in existing_phones)
            if is_dup:
                duplicates_skipped += 1
                if skip_duplicates:
                    continue

            seen_in_file.add(r.clean_phone)

            # 2. Company record (Household or business)
            company_name = r.company_name or f"{r.first_name} {r.last_name} Household".strip()
            if not company_name:
                company_name = "Homeowner Residence"

            research_data = {
                "source": "csv_prospect_upload",
                "campaign_id": campaign.id,
                "campaign_name": campaign.name,
                "trade_service": r.trade_service or trade_service,
                "address": r.address,
                "city": r.city,
                "state": r.state,
                "zip_code": r.zip_code,
                "custom_attributes": r.custom_fields
            }

            company = Company(
                organization_id=organization.id,
                name=company_name,
                phone=r.clean_phone,
                address=r.address,
                industry="Residential Services" if "homeowner" in company_name.lower() or "household" in company_name.lower() else "Commercial Services",
                notes=f"Imported from campaign: {campaign.name}",
                research_data=research_data
            )
            db.add(company)
            await db.flush()

            # 3. Contact record
            contact = Contact(
                organization_id=organization.id,
                company_id=company.id,
                first_name=r.first_name or "Homeowner",
                last_name=r.last_name or "",
                phone=r.clean_phone,
                email=r.email,
                job_title="Homeowner" if "household" in company_name.lower() else "Owner / Purchasing",
                decision_maker_role="homeowner",
                is_primary=True
            )
            db.add(contact)
            await db.flush()

            # 4. Lead record
            lead = Lead(
                organization_id=organization.id,
                company_id=company.id,
                contact_id=contact.id,
                campaign_id=campaign.id,
                lead_score=60,
                pipeline_stage="ready_contact",
                status="active",
                notes=r.notes or f"Imported prospect for {r.trade_service or trade_service}",
                research_summary=f"Prospect list import: {r.address or ''} {r.city or ''} {r.zip_code or ''}".strip()
            )
            db.add(lead)
            leads_created += 1

        # Update campaign metrics
        campaign.valid_count = leads_created
        campaign.duplicate_count = duplicates_skipped
        campaign.error_count = errors_count

        campaign_id = campaign.id
        campaign_name = campaign.name

        await db.commit()

        logger.info(
            f"[PROSPECT IMPORT] Campaign '{campaign_name}' ({campaign_id}): "
            f"{leads_created} leads created, {duplicates_skipped} duplicates skipped, {errors_count} errors."
        )

        return ProspectImportResponse(
            success=True,
            campaign_id=campaign_id,
            campaign_name=campaign_name,
            trade_service=trade_service,
            total_processed=len(rows),
            leads_created=leads_created,
            duplicates_skipped=duplicates_skipped,
            errors_count=errors_count,
            status="ready",
            message=f"Successfully imported {leads_created} prospects into campaign '{campaign_name}'."
        )

    @classmethod
    def generate_sample_csv(cls) -> str:
        """
        Generates an RFC 4180 compliant sample CSV template with example residential and commercial prospects.
        """
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\r\n")

        headers = [
            "First Name",
            "Last Name",
            "Phone Number",
            "Email",
            "Street Address",
            "City",
            "State",
            "Zip Code",
            "Service Needed",
            "Notes / Property Details"
        ]
        writer.writerow(headers)

        sample_rows = [
            [
                "Michael",
                "Chang",
                "+1-303-555-0144",
                "mchang@example.com",
                "1428 Elm St",
                "Denver",
                "CO",
                "80202",
                "Carpet Cleaning",
                "3 bedrooms and hallway, pet odor in living room"
            ],
            [
                "Jennifer",
                "Holloway",
                "(303) 555-0182",
                "jholloway@example.com",
                "742 Evergreen Terrace",
                "Boulder",
                "CO",
                "80301",
                "Lawn Care",
                "Half acre lot, wants weekly mowing and fall aeration"
            ],
            [
                "Robert",
                "Sterling",
                "303-555-0199",
                "rsterling@example.com",
                "9100 Mountain View Rd",
                "Lakewood",
                "CO",
                "80226",
                "Roofing",
                "Hail damage inquiry following recent storm, 2-story home"
            ],
            [
                "Elena",
                "Vargas",
                "7205550133",
                "evargas@example.com",
                "520 Cherry Creek S Dr",
                "Denver",
                "CO",
                "80209",
                "Carpet Cleaning",
                "Deep steam cleaning for move-in, 4 rooms"
            ]
        ]
        for r in sample_rows:
            writer.writerow(r)

        return output.getvalue()
