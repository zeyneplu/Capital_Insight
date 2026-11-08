from fastapi import APIRouter
from ..dependencies import CustomerDep
from ..schemas import CustomerOut
router = APIRouter(prefix="/v1/customers", tags=["Customers"])


@router.get("/me", response_model=CustomerOut, summary="Get the consenting fictional customer")
def me(customer: CustomerDep):
    return customer
