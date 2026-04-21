from typing import Optional, List, Dict, Any

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

# BigQuery client
client = bigquery.Client(project=GCP_PROJECT)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can restrict this later to your frontend URL
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
