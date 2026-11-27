"""Protected professional dashboard endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.dependencies import require_verified_doctor
from app.models.user import User


router = APIRouter()


class DoctorDashboardResponse(BaseModel):
    display_name: str | None
    role: str
    account_status: str
    is_verified: bool
    dashboard_access: bool


@router.get(
    "/dashboard",
    response_model=DoctorDashboardResponse,
    summary="Get Professional Dashboard",
)
async def get_doctor_dashboard(
    doctor: User = Depends(require_verified_doctor()),
) -> DoctorDashboardResponse:

    return DoctorDashboardResponse(
        display_name=doctor.display_name,
        role=doctor.role,
        account_status=doctor.account_status,
        is_verified=doctor.is_verified,
        dashboard_access=True,
    )
