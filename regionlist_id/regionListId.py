from dbms import app, db
import json
import requests
from flask import jsonify, request, make_response
import psycopg2
import hashlib
import re
import qrcode
from io import BytesIO
from flask import send_file
import shapely.wkt as wkt
from shapely.geometry import mapping, Point

# ---------- regionlistid map/qr code Start -------------

# ------------------- DB Connection Helper -------------------
def get_connection():
    return psycopg2.connect(app.config['DATABASE_URL_FOR_REGION'])

# Function to generate regionListID
def generate_regionlistID(region_ids):
    """
    Generate a deterministic 64-character hex ID for a unique list of region_ids,
    formatted as eight 8-character chunks separated by '-'.
    
    Parameters
    ----------
    region_ids : list
        An unordered list of region_id strings.
    
    Returns
    -------
    str
        A 64-character hex string, e.g., '3b1f5a9c-2d4e6f7a-8b9c0d1e-2f3a4b5c-6d7e8f9a-0b1c2d3e-4f5a6b7c-8d9e0f1a'
    """
    sorted_ids = sorted(region_ids)
    m = hashlib.sha256()
    for rid in sorted_ids:
        m.update(b"|")
        m.update(rid.encode("utf-8"))
    full_hex = m.hexdigest()
    parts = [full_hex[i:i+8] for i in range(0, 64, 8)]
    return "-".join(parts)

# Create region_lists table
def create_region_lists_table():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS region_lists (
            regionlist_id VARCHAR(255) PRIMARY KEY,
            region_ids TEXT NOT NULL
        );
        """
        cursor.execute(create_table_query)
        conn.commit()
    except Exception as e:
        print(f"Error creating region_lists table: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


create_region_lists_table()

# Validate region_id existence
def fetch_region_exists(region_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM regions WHERE region_id = %s", (region_id,))
        return bool(cursor.fetchone())
    except Exception as e:
        print(f"Error validating region_id {region_id}: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

# Insert region_list mappings
def insert_region_list(regionlist_id, region_ids):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO region_lists (regionlist_id, region_ids)
        VALUES (%s, %s)
        ON CONFLICT (regionlist_id) DO NOTHING
        """
        # Store region_ids as JSON string
        region_ids_json = json.dumps(region_ids)
        cursor.execute(insert_query, (regionlist_id, region_ids_json))
        conn.commit()
    except Exception as e:
        print(f"Error inserting region_list: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

# API 1: Create regionListID for a list of region_ids
def create_regionlistID_for_regionIDs():
    if not request.is_json:
        return jsonify({"error": "Provide 'region_ids' list in JSON"}), 400
    
    data = request.json
    if not isinstance(data.get('region_ids'), list):
        return jsonify({"error": "Provide 'region_ids' list in JSON"}), 400
    
    region_ids = list(map(str, data['region_ids']))
    if not region_ids:
        return jsonify({"error": "No region_ids provided"}), 400

    valid_region_ids = []
    invalid_region_ids = []
    for region_id in region_ids:
        if fetch_region_exists(region_id):
            valid_region_ids.append(region_id)
        else:
            invalid_region_ids.append(region_id)

    response = {
        "stored_region_ids": valid_region_ids,
        "unregistered_region_ids": invalid_region_ids
    }

    if valid_region_ids:
        valid_region_ids = sorted(set(valid_region_ids))
        regionlist_id = generate_regionlistID(valid_region_ids)

        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT region_ids FROM region_lists
                        WHERE regionlist_id = %s
                        """,
                        (regionlist_id,)
                    )
                    result = cur.fetchone()
                    if result:
                        stored_ids = json.loads(result[0])
                        if sorted(stored_ids) == valid_region_ids:
                            response["message"] = "Combination of region_ids already exists"
                            response["regionListID"] = regionlist_id
                            return jsonify(response), 200

            insert_region_list(regionlist_id, valid_region_ids)
            response["message"] = "RegionListID created successfully"
            response["regionListID"] = regionlist_id
        except Exception as e:
            response["error"] = f"Error storing regionListID: {str(e)}"
            return jsonify(response), 500
    else:
        response["message"] = "No valid region_ids to store"

    return jsonify(response), 200


# API 2: Get region boundaries for a regionListID
def get_boundaries_for_regionlistID():
    try:
        regionlist_id = request.args.get('regionlist_id')
        conn = get_connection()
        cursor = conn.cursor()
        query = """
        SELECT r.region_id, r.region_boundary
        FROM regions r
        JOIN region_lists rl ON r.region_id = ANY (
            SELECT json_array_elements_text(region_ids::json)::text
            FROM region_lists
            WHERE regionlist_id = %s
        )
        WHERE rl.regionlist_id = %s
        ORDER BY r.region_id
        """
        cursor.execute(query, (regionlist_id, regionlist_id))
        results = cursor.fetchall()
        
        if not results:
            return jsonify({"error": f"No regions found for regionListID: {regionlist_id}"}), 404
        
        boundaries = [{"region_id": row[0], "region_boundary": row[1]} for row in results]
        return jsonify({"regionListID": regionlist_id, "boundaries": boundaries}), 200
    except Exception as e:
        return jsonify({"error": f"Error fetching boundaries: {str(e)}"}), 500
    finally:
        cursor.close()
        conn.close()

# API 3: Map endpoint for GeoJSON geometries
def map_page():
    regionlist_id = request.args.get('regionlist_id')
    if not regionlist_id:
        return jsonify({"error": "Missing regionlist_id parameter"}), 400

    # Validate regionlist_id format (8-8-8-8-8-8-8-8)
    if not re.fullmatch(r'(?:[a-fA-F0-9]{8}-){7}[a-fA-F0-9]{8}', regionlist_id):
        return jsonify({"error": "Invalid regionListID format"}), 400

    # Retrieve region_ids from database
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT region_ids FROM region_lists WHERE regionlist_id = %s", (regionlist_id,))
                row = cur.fetchone()
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    if not row:
        return jsonify({"error": "regionListID not found"}), 404

    region_ids = json.loads(row[0])
    geometries = []
    for region_id in region_ids:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT region_boundary FROM regions WHERE region_id = %s", (region_id,))
                    wkt_row = cur.fetchone()
            if wkt_row:
                wkt_str = wkt_row[0]
                geom = wkt.loads(wkt_str)
                geojson_dict = mapping(geom)
                # Extract only coordinates and type
                geometry = {
                    "coordinates": geojson_dict["coordinates"],
                    "type": geojson_dict["type"]
                }
                geometries.append(geometry)
        except Exception:
            continue

    if not geometries:
        return jsonify({"error": "No valid polygons found for the provided region_ids"}), 404

    return jsonify(geometries)

# generate QR code

MAP_HTML_BASE_URL = app.config['MAP_HTML_BASE_URL']

def generate_qrcode():
    regionlist_id = request.args.get('regionlist_id')
    format_type = request.args.get('format')
    if not regionlist_id or format_type != 'qr':
        return jsonify({"error": "Missing regionlist_id or format=qr parameter"}), 400

    # Validate regionlist_id format
    if not re.fullmatch(r'(?:[a-fA-F0-9]{8}-){7}[a-fA-F0-9]{8}', regionlist_id):
        return jsonify({"error": "Invalid regionListID format"}), 400

    # Check if regionlist_id exists
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM region_lists WHERE regionlist_id = %s", (regionlist_id,))
                if not cur.fetchone():
                    return jsonify({"error": "regionListID not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    # Generate QR code for map.html URL
    url = f"{MAP_HTML_BASE_URL}?regionlist_id={regionlist_id}"
    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype='image/png')