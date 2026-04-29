from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import bcrypt

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery

app = FastAPI(
    title="Uncle Joe's Coffee API",
    description="Backend API for Uncle Joe's Coffee locations and menu data",
    version="1.0.0",
)

# Google Cloud / BigQuery settings
GCP_PROJECT = "uncle-joes-coffee"
DATASET = "uncle_joes"

LOCATIONS_TABLE = f"{GCP_PROJECT}.{DATASET}.locations"
MENU_TABLE = f"{GCP_PROJECT}.{DATASET}.menu_items"
MEMBERS_TABLE = f"{GCP_PROJECT}.{DATASET}.members"
ORDERS_TABLE = f"{GCP_PROJECT}.{DATASET}.orders"
ORDER_ITEMS_TABLE = f"{GCP_PROJECT}.{DATASET}.order_items"

# BigQuery client
client = bigquery.Client(project=GCP_PROJECT)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def rows_to_dicts(rows) -> List[Dict[str, Any]]:
    """Convert BigQuery rows into normal Python dictionaries."""
    return [dict(row.items()) for row in rows]


@app.get("/")
def root():
    return {"message": "Uncle Joe's Coffee API is running"}


# ---------------------------------------------------------------------------
# LOCATIONS
# ---------------------------------------------------------------------------

@app.get("/locations")
def get_locations(
    state: Optional[str] = Query(default=None, description="Filter by state abbreviation"),
    city: Optional[str] = Query(default=None, description="Filter by city name"),
    limit: int = Query(default=100, ge=1, le=500, description="Number of records to return"),
):
    """
    Return all locations.
    Optional filtering by state and city.
    """
    query = f"""
        SELECT *
        FROM `{LOCATIONS_TABLE}`
        WHERE 1=1
    """

    query_params = []

    if state:
        query += " AND LOWER(state) = LOWER(@state)"
        query_params.append(bigquery.ScalarQueryParameter("state", "STRING", state))

    if city:
        query += " AND LOWER(city) = LOWER(@city)"
        query_params.append(bigquery.ScalarQueryParameter("city", "STRING", city))

    query += " ORDER BY state, city LIMIT @limit"
    query_params.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))

    job_config = bigquery.QueryJobConfig(query_parameters=query_params)

    try:
        results = client.query(query, job_config=job_config).result()
        return rows_to_dicts(results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching locations: {str(e)}")


@app.get("/locations/{location_id}")
def get_location_by_id(location_id: str):
    """
    Return a single location by ID.
    """
    query = f"""
        SELECT *
        FROM `{LOCATIONS_TABLE}`
        WHERE id = @location_id
        LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("location_id", "STRING", location_id)
        ]
    )

    try:
        results = list(client.query(query, job_config=job_config).result())

        if not results:
            raise HTTPException(status_code=404, detail="Location not found")

        return dict(results[0].items())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching location: {str(e)}")


# ---------------------------------------------------------------------------
# MENU
# ---------------------------------------------------------------------------

@app.get("/menu")
def get_menu(
    category: Optional[str] = Query(default=None, description="Filter by category"),
    size: Optional[str] = Query(default=None, description="Filter by size"),
    limit: int = Query(default=100, ge=1, le=500, description="Number of records to return"),
):
    """
    Return all menu items.
    Optional filtering by category and size.
    """
    query = f"""
        SELECT *
        FROM `{MENU_TABLE}`
        WHERE 1=1
    """

    query_params = []

    if category:
        query += " AND LOWER(category) = LOWER(@category)"
        query_params.append(bigquery.ScalarQueryParameter("category", "STRING", category))

    if size:
        query += " AND LOWER(size) = LOWER(@size)"
        query_params.append(bigquery.ScalarQueryParameter("size", "STRING", size))

    query += " ORDER BY category, name LIMIT @limit"
    query_params.append(bigquery.ScalarQueryParameter("limit", "INT64", limit))

    job_config = bigquery.QueryJobConfig(query_parameters=query_params)

    try:
        results = client.query(query, job_config=job_config).result()
        return rows_to_dicts(results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching menu items: {str(e)}")


@app.get("/menu/{item_id}")
def get_menu_item_by_id(item_id: str):
    """
    Return a single menu item by ID.
    """
    query = f"""
        SELECT *
        FROM `{MENU_TABLE}`
        WHERE id = @item_id
        LIMIT 1
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("item_id", "STRING", item_id)
        ]
    )

    try:
        results = list(client.query(query, job_config=job_config).result())

        if not results:
            raise HTTPException(status_code=404, detail="Menu item not found")

        return dict(results[0].items())
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching menu item: {str(e)}")


# ---------------------------------------------------------------------------
# LOGIN
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/login")
def login(req: LoginRequest):
    """Authenticate a Coffee Club member by email and password."""
    query = f"""
        SELECT id, first_name, last_name, email, phone, home_store, password_hash
        FROM `{MEMBERS_TABLE}`
        WHERE LOWER(email) = LOWER(@email)
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("email", "STRING", req.email)
        ]
    )
    try:
        results = list(client.query(query, job_config=job_config).result())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    if not results:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    member = dict(results[0].items())
    stored_hash = member["password_hash"]

    if not bcrypt.checkpw(req.password.encode("utf-8"), stored_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    member.pop("password_hash")
    return {"success": True, "member": member}


# ---------------------------------------------------------------------------
# ORDERS
# ---------------------------------------------------------------------------

@app.get("/members/{member_id}/orders")
def get_member_orders(member_id: str):
    """Return all orders for a member, including line items and store info."""
    query = f"""
        SELECT
            o.order_id,
            o.order_date,
            o.order_total,
            l.city,
            l.state,
            ARRAY_AGG(STRUCT(
                oi.item_name,
                oi.quantity,
                oi.price
            )) AS items
        FROM `{ORDERS_TABLE}` o
        LEFT JOIN `{ORDER_ITEMS_TABLE}` oi ON o.order_id = oi.order_id
        LEFT JOIN `{GCP_PROJECT}.{DATASET}.locations` l ON o.store_id = l.id
        WHERE o.member_id = @member_id
        GROUP BY o.order_id, o.order_date, o.order_total, l.city, l.state
        ORDER BY o.order_date DESC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("member_id", "STRING", member_id)
        ]
    )
    try:
        results = list(client.query(query, job_config=job_config).result())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    orders = []
    for row in results:
        order = dict(row.items())
        order["order_date"] = str(order["order_date"])
        order["order_total"] = float(order["order_total"])
        items = order.get("items", [])
        order["items"] = [dict(item) for item in items] if items else []
        orders.append(order)
    return orders


# ---------------------------------------------------------------------------
# POINTS
# ---------------------------------------------------------------------------

@app.get("/members/{member_id}/points")
def get_member_points(member_id: str):
    """Return the total Coffee Club points balance for a member."""
    query = f"""
        SELECT SUM(CAST(FLOOR(order_total) AS INT64)) AS total_points
        FROM `{ORDERS_TABLE}`
        WHERE member_id = @member_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("member_id", "STRING", member_id)
        ]
    )
    try:
        results = list(client.query(query, job_config=job_config).result())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    total = results[0]["total_points"] if results and results[0]["total_points"] else 0
    return {"member_id": member_id, "total_points": int(total)}