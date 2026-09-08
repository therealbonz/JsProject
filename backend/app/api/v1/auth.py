import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.tenant import User, Organization, OrganizationMembership, AIConfiguration
from app.models.crm import Product
from app.schemas.auth import UserRegister, UserLogin, Token, UserResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

def slugify(text: str) -> str:
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    return re.sub(r'[-\s]+', '-', slug).strip('-')

@router.post("/register", response_model=Token)
async def register_user(payload: UserRegister, db: AsyncSession = Depends(get_db)):
    # Check if email exists
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists"
        )

    # 1. Create Organization
    slug = slugify(payload.organization_name)
    org = Organization(name=payload.organization_name, slug=slug, status="active")
    db.add(org)
    await db.flush()

    # 2. Create User
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        is_active=True,
        is_superuser=False
    )
    db.add(user)
    await db.flush()

    # 3. Create Membership as Admin
    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role="admin"
    )
    db.add(membership)

    # 4. Create Default AI Configuration for this tenant
    ai_config = AIConfiguration(
        organization_id=org.id,
        company_name=org.name,
        company_description="Commercial office, janitorial, and facilities supply distributor.",
        autonomy_level="semi_autonomous",
        max_discount_pct=10.0,
        tone_of_voice="professional, consultative, and value-driven",
        prohibited_phrases=["guaranteed profit", "free forever", "unlimited free returns"],
        sales_guidelines="Focus on recurring supply cost reduction, wholesale volume discounts, and guaranteed next-day delivery.",
        hitl_required_for_closing=True
    )
    db.add(ai_config)

    # 5. Seed Initial Sample Products for the Organization
    sample_products = [
        Product(
            organization_id=org.id,
            name="EcoClean Commercial Disinfectant (4x1 Gal)",
            sku="CLN-EC-001",
            category="Janitorial",
            description="Hospital-grade EPA registered disinfectant for commercial facilities.",
            unit_price=48.50,
            min_allowed_price=42.00,
            currency="USD",
            is_active=True
        ),
        Product(
            organization_id=org.id,
            name="Premium 2-Ply Bath Tissue (96 Rolls)",
            sku="JAN-PP-096",
            category="Janitorial",
            description="High-capacity commercial bath tissue rolls for corporate restrooms.",
            unit_price=64.00,
            min_allowed_price=55.00,
            currency="USD",
            is_active=True
        ),
        Product(
            organization_id=org.id,
            name="Heavy Duty Multi-Purpose Copy Paper (10 Ream Case)",
            sku="OFF-PAP-5000",
            category="Office Supplies",
            description="92 Brightness 20lb white paper case for high-speed laser printers.",
            unit_price=52.00,
            min_allowed_price=46.00,
            currency="USD",
            is_active=True
        )
    ]
    for p in sample_products:
        db.add(p)

    await db.commit()

    token = create_access_token({"sub": user.id, "org_id": org.id, "role": "admin"})
    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=org.id,
        role="admin"
    )

@router.post("/login", response_model=Token)
async def login_user(payload: UserLogin, db: AsyncSession = Depends(get_db)):
    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Get user's primary membership
    mem_stmt = select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
    mem_res = await db.execute(mem_stmt)
    membership = mem_res.scalar_one_or_none()

    org_id = membership.organization_id if membership else ""
    role = membership.role if membership else "viewer"

    token = create_access_token({"sub": user.id, "org_id": org_id, "role": role})
    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=org_id,
        role=role
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
