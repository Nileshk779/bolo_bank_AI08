from fastapi import APIRouter, HTTPException

from services.data_service import (
    get_customer,
    get_customer_transactions,
    get_customers,
    get_demo_queue,
    get_demo_sessions,
)

router = APIRouter(prefix="/api/demo", tags=["demo-data"])


@router.get("/customers")
def customers():
    return get_customers()


@router.get("/customers/{customer_id}")
def customer_details(customer_id: str):
    customer = get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


@router.get("/customers/{customer_id}/transactions")
def customer_transactions(customer_id: str):
    if not get_customer(customer_id):
        raise HTTPException(status_code=404, detail="Customer not found")
    return get_customer_transactions(customer_id)


@router.get("/queue")
def demo_queue():
    return get_demo_queue()


@router.get("/sessions")
def demo_sessions():
    return get_demo_sessions()
