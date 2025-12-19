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
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from twilio.rest import Client
from flask import Flask, render_template, jsonify, request, url_for, session
from datetime import date, timedelta, datetime ,timezone
import uuid
import jwt
from twilio.rest import Client
import random
import base64
from functools import wraps
import concurrent.futures
from psycopg2.extras import RealDictCursor
from s2sphere import CellId, Cell, LatLng

# ------------------- DB Connection Helper -------------------
def get_connection():
    return psycopg2.connect(app.config['DATABASE_URL_FOR_REGION'])

def get_pg_connection():
    return psycopg2.connect(app.config['TERRAPIPE_BE_DB_URL'])

def init_db():
    """Create mapping tables if not exist."""
    conn = get_connection()
    cur = conn.cursor()
    # Mask list mapping
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mask_field_mapping (
            fieldlistid TEXT PRIMARY KEY,
            masklistid TEXT NOT NULL,
            masklist JSONB NOT NULL
        );
    """)
    # Field mapping
    cur.execute("""
        CREATE TABLE IF NOT EXISTS field_mapping (
            fieldlistid TEXT,
            fieldid TEXT,
            geoid TEXT,
            wkt TEXT,
            PRIMARY KEY(fieldlistid, fieldid)
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def generate_public_key():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return pub_pem  # Keep full structure

def signup():
    if request.method != 'POST':
        return jsonify({"message": "Method not allowed"}), 405

    try:
        data = request.get_json(force=True)
        phone = data.get("phone_number")

        if not phone:
            return jsonify({"message": "Phone number is required"}), 400

        # Normalize phone number
        if not phone.startswith("+"):
            phone = "+91" + phone.lstrip("0")

        # Generate OTP and public_key
        otp = generate_otp()
        expiry = datetime.utcnow() + timedelta(minutes=5)
        public_key = str(uuid.uuid4())

        # Store OTP and public_key in DB
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_otps (public_key, phone_number, otp_code, otp_expiry)
            VALUES (%s, %s, %s, %s);
        """, (public_key, phone, otp, expiry))
        conn.commit()
        cursor.execute("""
            INSERT INTO pending_signups (public_key, signup_payload)
            VALUES (%s, %s);
        """, (public_key, json.dumps(data)))
        conn.commit()
        send_otp_sms(phone, otp)

        # Store signup payload and public_key in session
        session['pending_signup'] = data
        session['otp_phone'] = phone
        session['public_key'] = public_key

        return jsonify({
            "status": "otp_sent",
            "public_key": public_key,
            "message": f"OTP sent to {phone}. Please verify to complete registration."
        })

    except Exception as e:
        return jsonify({
            "message": "Signup initiation error",
            "error": str(e)
        }), 500

    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()


def login():
    try:
        if request.method != "POST":
            return jsonify({"message": "Method not allowed"}), 405

        data = request.get_json(force=True)
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"message": "Email and password required"}), 400

        response = requests.post( app.config['TERRAPIPE_LOGIN_URL'], json={"email": email, "password": password})

        if response.status_code == 200:
            resp_data = response.json()
            token = resp_data.get("access_token")

            if not token:
                return jsonify({"message": "Token not found in response"}), 500

            try:
                decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                user_registry_id = decoded.get("sub")
            except jwt.ExpiredSignatureError:
                return jsonify({"message": "Token expired"}), 401
            except jwt.InvalidTokenError as e:
                return jsonify({"message": "Invalid token", "error": str(e)}), 401
            except Exception as e:
                return jsonify({"message": "Unexpected error", "error": str(e)}), 500

            # Store in session
            session["access_token"] = token
            session["user_registry_id"] = user_registry_id

            print(f'user_registry_id: {session["user_registry_id"]}')
            return jsonify({
                "message": "Login successful",
                "access_token": token,
                "user_registry_id": user_registry_id
            })

        else:
            return jsonify({
                "message": "Login failed",
                "error": response.json().get("message", "Unknown error")
            }), response.status_code

    except Exception as e:
        return jsonify({"message": "Login error", "error": str(e)}), 500


TWILIO_SID = app.config['TWILIO_SID']
TWILIO_AUTH_TOKEN = app.config['TWILIO_AUTH_TOKEN']
TWILIO_PHONE = app.config['TWILIO_PHONE']


twilio_client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)

def send_otp_sms(phone_number, otp):
    message = twilio_client.messages.create(
        body=f"Your verification code is: {otp}",
        from_=TWILIO_PHONE,
        to=phone_number
    )
    return message.sid


def generate_otp():
    return str(random.randint(100000, 999999))

# @app.route('/request-otp', methods=['POST'])
# def request_otp():
#     try:
#         public_key = request.json.get('public_key')
#         if not public_key:
#             return jsonify({"status": "error", "message": "Public key is required"}), 400

#         conn = get_connection()
#         cursor = conn.cursor()
#         cursor.execute("SELECT phone_number FROM user_registrations WHERE public_key = %s;", (public_key,))
#         result = cursor.fetchone()

#         if not result:
#             return jsonify({"status": "error", "message": "User not found"}), 404

#         phone = result[0]
#         if not phone.startswith("+"):
#             phone = "+91" + phone.lstrip("0")

#         otp = generate_otp()
#         expiry = datetime.utcnow() + timedelta(minutes=5)

#         cursor.execute("""
#             INSERT INTO user_otps (public_key, phone_number, otp_code, otp_expiry)
#             VALUES (%s, %s, %s, %s);
#         """, (public_key, phone, otp, expiry))

#         conn.commit()
#         send_otp_sms(phone, otp)
#         return jsonify({"status": "success", "message": f"OTP sent to {phone}"})
#     except Exception as e:
#         print("Error in /request-otp:", str(e))
#         return jsonify({"status": "error", "message": "Internal server error", "details": str(e)}), 500
#     finally:
#         cursor.close()
#         conn.close()


def verify_otp():
    public_key = request.json.get('public_key')
    otp_input = request.json.get('otp')

    if not public_key or not otp_input:
        return jsonify({"message": "Public key and OTP are required"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    try:
        #  Lookup OTP by public_key
        cursor.execute("""
            SELECT phone_number, otp_code, otp_expiry FROM user_otps
            WHERE public_key = %s
            ORDER BY created_at DESC
            LIMIT 1;
        """, (public_key,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"message": "No OTP found"}), 404

        phone, otp_code, otp_expiry = result

        if otp_code == otp_input and datetime.utcnow() <= otp_expiry:
            cursor.execute("""
                UPDATE user_otps
                SET is_verified = TRUE
                WHERE public_key = %s AND otp_code = %s;
            """, (public_key, otp_input))
            conn.commit()

            # Retrieve pending signup data from DB or cache
            cursor.execute("""
                SELECT signup_payload FROM pending_signups
                WHERE public_key = %s;
            """, (public_key,))
            signup_row = cursor.fetchone()

            if not signup_row:
                return jsonify({"message": "Signup data not found"}), 404

            signup_data = signup_row[0]  # Assuming JSON stored as text
            print(f"signup data : {signup_data}")
            headers = {"Content-Type": "application/json"}
            response = requests.post(app.config['TERRAPIPE_SIGNUP_URL'], headers=headers, json=signup_data, timeout=10)

            try:
                api_response = response.json()
                print(f"api_response : {api_response}")
                msg = api_response.get("message", "").lower()
                print(f"response code : {response.status_code}")
                print(f"message : {msg}")

            except ValueError:
                return jsonify({
                    "message": "Terrapipe returned non-JSON response",
                    "status_code": response.status_code,
                    "raw_response": response.text
                }), response.status_code

            #if user already exists just update the number
            if response.status_code == 409 and "a user with this email already exists" in api_response.get("message", "").lower():
                email = signup_data.get("email")
                new_phone = signup_data.get("phone_number")

                if not email or not new_phone:
                    return jsonify({"message": "Missing email or phone number in signup data"}), 400

                terrapipe_conn = get_pg_connection()
                terrapipe_cur = terrapipe_conn.cursor()

                terrapipe_cur.execute("""
                    SELECT user_registry_id, phone_num, email
                    FROM users
                    WHERE email = %s
                    LIMIT 1;
                """, (email,))
                user_row = terrapipe_cur.fetchone()

                if user_row:
                    user_registry_id, old_phone, user_email = user_row
                    print(f"user_row : {user_row}")
                    print(f"old_phone : {old_phone}")
                    if not old_phone: #if phone number is not available
                        terrapipe_cur.execute("""
                            UPDATE users
                            SET phone_num = %s
                            WHERE user_registry_id = %s;
                        """, (new_phone, user_registry_id))
                        terrapipe_conn.commit()

                        terrapipe_cur.close()
                        terrapipe_conn.close()

                        return jsonify({
                            "message": "User already exists. Phone number added successfully",
                            "email": email,
                            "new_phone": new_phone
                        }), 200
                    else:
                        # Phone number already exists then skip
                        terrapipe_cur.close()
                        terrapipe_conn.close()
                        return jsonify({
                            "message": "User already exists with phone number",
                            "email": email,
                            "existing_phone": old_phone
                        }), 200

                terrapipe_cur.close()
                terrapipe_conn.close()

            return jsonify(api_response), response.status_code

        else:
            return jsonify({"message": "Invalid or expired OTP"}), 403

    except Exception as e:
        return jsonify({
            "message": "OTP verification error",
            "error": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()


#step 1
asset_registry_base = "https://api-ar.agstack.org"

def fetch_wkt(geoid):
    url = f"{asset_registry_base}/fetch-field-wkt/{geoid}"
    res = requests.get(url)
    if res.status_code != 200:
        raise Exception(f"Invalid response: {res.status_code} - {res.text}")
    polygon_wkt = res.json().get("WKT")
    if not polygon_wkt:
        raise Exception(f"No WKT found for geoid {geoid}")
    return polygon_wkt

def compute_centroid(polygon_wkt):
    geom = wkt.loads(polygon_wkt)
    centroid = geom.centroid
    return centroid.y, centroid.x

def map_to_s2(lat, lon, level=10):
    latlng = LatLng.from_degrees(lat, lon)
    cell = CellId.from_lat_lng(latlng).parent(level)
    return cell.id(), cell.to_token()

def get_s2_polygon(cellid):
    """Return GeoJSON polygon of the S2 cell."""
    cell = Cell(CellId(cellid))
    coords = []
    for i in range(4):
        v = cell.get_vertex(i)
        latlng = LatLng.from_point(v)
        coords.append([latlng.lng().degrees, latlng.lat().degrees])
    coords.append(coords[0])
    return {
        "type": "Polygon",
        "coordinates": [coords]
    }


def get_fieldlist_mapping(fieldlistid):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT masklistid, masklist FROM mask_field_mapping WHERE fieldlistid=%s", (fieldlistid,))
    row = cur.fetchone()
    masklistid, masklist = (row if row else (None, None))

    cur.execute("SELECT fieldid, geoid, wkt FROM field_mapping WHERE fieldlistid=%s ORDER BY fieldid", (fieldlistid,))
    rows = cur.fetchall()
    fields = [{"fieldId": r[0], "geoid": r[1], "wkt": r[2]} for r in rows]

    cur.close()
    conn.close()
    return masklistid, masklist, fields

def generate_fieldlistid(geoids):
    geoids_sorted = sorted(geoids)
    concat_str = "".join(geoids_sorted)
    raw_hash = hashlib.sha256(concat_str.encode()).hexdigest()
    formatted_hash = "-".join(raw_hash[i:i+8] for i in range(0, len(raw_hash), 8))
    return formatted_hash

def generate_masklistid(masklist):
    masklist_sorted = sorted(masklist)
    concat_str = "".join(masklist_sorted)
    return hashlib.sha256(concat_str.encode()).hexdigest()

def generate_fieldid(fieldlistid, geoid):
    concat = f"{fieldlistid}-{geoid}"
    return hashlib.sha256(concat.encode()).hexdigest()[:10]


def store_fieldlist_mapping(fieldlistid, masklistid, masklist, fields, user_id, fieldlistid_name):
    conn = get_connection()
    cur = conn.cursor()

    # Store mask mapping with user_id and fieldlistid_name
    cur.execute("""
        INSERT INTO mask_field_mapping (fieldlistid, masklistid, masklist, user_id, fieldlistid_name)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (fieldlistid) DO UPDATE
        SET masklistid = EXCLUDED.masklistid,
            masklist = EXCLUDED.masklist,
            user_id = EXCLUDED.user_id,
            fieldlistid_name = EXCLUDED.fieldlistid_name;
    """, (fieldlistid, masklistid, json.dumps(masklist), user_id, fieldlistid_name))

    # Store fields
    for field in fields:
        cur.execute("""
            INSERT INTO field_mapping (fieldlistid, fieldid, geoid, wkt)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (fieldlistid, fieldid) DO UPDATE
            SET geoid = EXCLUDED.geoid,
                wkt = EXCLUDED.wkt;
        """, (fieldlistid, field["fieldId"], field["geoid"], field["wkt"]))

    conn.commit()
    cur.close()
    conn.close()


def process_geoids(geoids, user_id, fieldlistid_name):
    fieldlistid = generate_fieldlistid(geoids)
    masklist = []
    fields = []

    for geoid in geoids:
        polygon_wkt = fetch_wkt(geoid)
        lat, lon = compute_centroid(polygon_wkt)
        _, token = map_to_s2(lat, lon)
        masklist.append(token)

        fieldid = generate_fieldid(fieldlistid, geoid)

        fields.append({
            "fieldId": fieldid,
            "geoid": geoid,
            "wkt": polygon_wkt
        })

    masklistid = generate_masklistid(masklist)
    store_fieldlist_mapping(fieldlistid, masklistid, masklist, fields, user_id, fieldlistid_name)
    return fieldlistid, masklistid, masklist, fields


def is_fieldlist_registered(fieldlistid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT fieldlistid FROM mask_field_mapping WHERE fieldlistid=%s", (fieldlistid,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def ingest_geoids():
    data = request.get_json()
    geoids = data.get("geoids", [])
    user_id = data.get("user_id")
    fieldlistid_name = data.get("fieldlistid_name")

    if not geoids or not user_id or not fieldlistid_name:
        return jsonify({"error": "Geoids, user_id and fieldlistid_name are required"}), 400

    #generate fieldlistid
    fieldlistid = generate_fieldlistid(geoids)

    #check if already exists
    if is_fieldlist_registered(fieldlistid):
        return jsonify({
            "message": "The same combination of geoids is already registered",
            "fieldListId": fieldlistid
        }), 200

    #normal flow
    fieldlistid, masklistid, masklist, fields = process_geoids(geoids, user_id, fieldlistid_name)
    return jsonify({
        "fieldListId": fieldlistid,
        "maskListId": masklistid,
        "maskList": masklist,
        "fieldListName": fieldlistid_name
    })


def get_user_data():
    try:
        data = request.get_json(force=True)

        conn = get_pg_connection()
        cursor = conn.cursor()

        # Get user_registry_id from request
        user_registry_id = data.get("user_registry_id", "").strip()
        if not user_registry_id:
            return jsonify({"message": "user_registry_id is required"}), 400

        print(f"Running query for user_registry_id: {user_registry_id}")

        cursor.execute("""
            SELECT user_registry_id, phone_num, email
            FROM users
            WHERE user_registry_id = %s
            LIMIT 1;
        """, (user_registry_id,))
        
        result = cursor.fetchone()
        print(f'DB result: {result}')

        if result:
            user_id, phone, email = result
            return jsonify({
                "user_id": user_id,
                "phone_num": phone,
                "email": email
            })
        else:
            return jsonify({"message": "User not found"}), 404

    except Exception as e:
        print("Lookup error:", str(e))
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()


def check_approved_user():
    try:
        data = request.get_json(force=True)

        user_registry_id = data.get("user_registry_id", "").strip()
        field_list_id = data.get("field_list_id", "").strip()

        if not user_registry_id or not field_list_id:
            return jsonify({"message": "user_registry_id and field_list_id are required"}), 400

        conn = get_connection()
        cursor = conn.cursor()

        print(f"Checking ACL for user_registry_id={user_registry_id}, field_list_id={field_list_id}")

        cursor.execute("""
            SELECT 1
            FROM user_acl
            WHERE user_id = %s AND field_list_id = %s
            LIMIT 1;
        """, (user_registry_id, field_list_id))

        result = cursor.fetchone()
        print(f"DB result: {result}")

        if result:
            return jsonify({
                "message": "user approved",
                "user_registry_id": user_registry_id,
                "field_list_id": field_list_id
            }), 200
        else:
            return jsonify({
                "message": "user not approved",
                "user_registry_id": user_registry_id,
                "field_list_id": field_list_id
            }), 403

    except Exception as e:
        print("ACL check error:", str(e))
        return jsonify({"message": "Internal server error", "error": str(e)}), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()


# ----------------- Request OTP -----------------
def request_otp_fieldlistid():
    acl_conn = None
    acl_cursor = None
    user_conn = None
    user_cursor = None
    try:
        data = request.get_json(force=True)
        user_registry_id = data.get("user_registry_id", "").strip()
        field_list_id = data.get("field_list_id", "").strip()

        if not user_registry_id or not field_list_id:
            return jsonify({"status": "error", "message": "user_registry_id and field_list_id are required"}), 400

        # ---------- STEP 1: Check ACL in terrapipe_backend ----------
        acl_conn = get_connection()   # this connects to terrapipe_backend
        acl_cursor = acl_conn.cursor()

        acl_cursor.execute("""
            SELECT 1 FROM user_acl 
            WHERE user_id = %s AND field_list_id = %s
        """, (user_registry_id, field_list_id))
        authorized = acl_cursor.fetchone()
        if not authorized:
            return jsonify({"status": "error", "message": "Unauthorized: Not approved in ACL"}), 403

        # ---------- STEP 2: Get user phone/email from terrapipe_be ----------
        user_conn = get_pg_connection()  # this connects to terrapipe_be
        user_cursor = user_conn.cursor()

        user_cursor.execute("""
            SELECT phone_num, email 
            FROM users 
            WHERE user_registry_id = %s
        """, (user_registry_id,))
        user = user_cursor.fetchone()
        if not user:
            return jsonify({"status": "error", "message": "User not found"}), 404

        phone, email = user
        if not phone:
            return jsonify({"status": "error", "message": "No phone number found for this user"}), 400

        # ---------- STEP 3: Generate OTP ----------
        phone = format_phone_number(phone)
        otp = generate_otp()
        expiry = datetime.utcnow() + timedelta(minutes=5)

        acl_cursor.execute("""
            INSERT INTO user_otps (user_registry_id, phone_number, otp_code, otp_expiry, is_verified, created_at)
            VALUES (%s, %s, %s, %s, FALSE, NOW())
        """, (user_registry_id, phone, otp, expiry))
        acl_conn.commit()

        send_otp_sms(phone, otp)

        return jsonify({
            "status": "success",
            "message": f"OTP sent to registred number: ******{phone[-3:]}",
            "user_registry_id": user_registry_id,
            "field_list_id": field_list_id
        })

    except Exception as e:
        print("Error in /request-otp-fieldlistid:", str(e))
        return jsonify({"status": "error", "message": "Internal server error", "details": str(e)}), 500
    finally:
        if acl_cursor: acl_cursor.close()
        if acl_conn: acl_conn.close()
        if user_cursor: user_cursor.close()
        if user_conn: user_conn.close()


# ----------------- Verify OTP -----------------

def format_phone_number(phone: str) -> str:
    phone = phone.strip()
    if not phone.startswith("+"):
        phone = "+91" + phone
    return phone

def verify_otp_fieldlistid():
    conn = None
    cursor = None
    try:
        data = request.get_json(force=True)
        user_registry_id = data.get("user_registry_id", "").strip()
        field_list_id = data.get("field_list_id", "").strip()
        otp_input = data.get("otp", "").strip()

        if not user_registry_id or not field_list_id or not otp_input:
            return jsonify({"status": "error", "message": "user_registry_id, field_list_id and otp are required"}), 400

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 1 FROM user_acl 
            WHERE user_id = %s AND field_list_id = %s
        """, (user_registry_id, field_list_id))
        authorized = cursor.fetchone()
        if not authorized:
            return jsonify({"status": "error", "message": "Unauthorized: Not approved in ACL"}), 403

        cursor.execute("""
            SELECT otp_code, otp_expiry 
            FROM user_otps
            WHERE user_registry_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_registry_id,))
        result = cursor.fetchone()

        if not result:
            return jsonify({"status": "error", "message": "No OTP found"}), 404

        otp_code, otp_expiry = result

        if otp_code == otp_input and datetime.utcnow() <= otp_expiry:
            cursor.execute("""
                UPDATE user_otps
                SET is_verified = TRUE
                WHERE user_registry_id = %s AND otp_code = %s
            """, (user_registry_id, otp_input))
            conn.commit()
            return jsonify({
                "status": "success",
                "message": "OTP verified",
                "user_registry_id": user_registry_id,
                "field_list_id": field_list_id
            })
        else:
            return jsonify({"status": "error", "message": "Invalid or expired OTP"}), 403

    except Exception as e:
        print("Error in /verify-otp:", str(e))
        return jsonify({"status": "error", "message": "Internal server error", "details": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()


def get_field_view(field_list_id):
    conn = None
    cursor = None
    try:
        data = request.get_json(force=True)
        user_registry_id = data.get("user_registry_id", "").strip()

        if not user_registry_id:
            return jsonify({"status": "error", "message": "user_registry_id is required"}), 400

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check if user is approved in user_acl
        cursor.execute("""
            SELECT status FROM user_acl
            WHERE user_id = %s AND field_list_id = %s
        """, (user_registry_id, field_list_id))
        acl_record = cursor.fetchone()
        print(f"ACL Check for user {user_registry_id}, field_list_id {field_list_id}: {acl_record}")
        if not acl_record or acl_record['status'] != 'Approved':
            return jsonify({"status": "error", "message": "Unauthorized: Not approved in ACL"}), 403

        # Check OTP status
        cursor.execute("""
            SELECT is_verified, otp_expiry
            FROM user_otps
            WHERE user_registry_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_registry_id,))
        otp_data = cursor.fetchone()
        print(f"OTP Check for user {user_registry_id}: {otp_data}")
        if not otp_data:
            return jsonify({"status": "error", "message": "OTP verification required"}), 403

        is_verified, otp_expiry = otp_data['is_verified'], otp_data['otp_expiry']
        
        # otp_expiry is already a datetime object, no need to parse
        if not is_verified or datetime.utcnow() > otp_expiry:
            return jsonify({"status": "error", "message": "OTP not verified or expired"}), 403

        # Fetch field data
        _, _, fields = get_fieldlist_mapping(field_list_id)
        if not fields:
            return jsonify({"status": "error", "message": "No fields found"}), 404

        print(f"Field data fetched for field_list_id {field_list_id}: {len(fields)} fields")
        return jsonify({
            "user_registry_id": user_registry_id,
            "field_list_id": field_list_id,
            "view": "field",
            "fields": fields
        })

    except Exception as e:
        print(f"Error in /getWKT/field/{field_list_id}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_mask_view(fieldlistid):
    try:
        masklistid, masklist, _ = get_fieldlist_mapping(fieldlistid)
        if not masklistid:
            return jsonify({
                "status": "error",
                "message": f"No mask found for fieldListId {fieldlistid}"
            }), 404

        cells = []
        for mask in masklist:
            try:
                cellid = CellId.from_token(mask).id()
                cells.append({
                    "s2_cell_id": mask,
                    "geometry": get_s2_polygon(cellid)
                })
            except Exception as e:
                print(f"Error generating geometry for mask {mask}: {e}")

        return jsonify({
            "status": "success",
            "fieldListId": fieldlistid,
            "view": "mask",
            "maskResolution": {"s2_level": 10, "edge_km_range": [7, 10]},
            "masklistid": masklistid,
            "cells": cells
        })

    except Exception as e:
        print(f"Error in /getWKT/mask/{fieldlistid}: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Internal server error",
            "details": str(e)
        }), 500

def decode_fieldlistid():
    try:
        data = request.get_json(force=True)
        encoded_fieldlistid = data.get("encoded_fieldlistid")

        if not encoded_fieldlistid:
            return jsonify({"message": "Encoded fieldListId required"}), 400

        try:
            decoded_bytes = base64.b64decode(encoded_fieldlistid)
            decoded_fieldlistid = decoded_bytes.decode('utf-8')
            return jsonify({
                "message": "FieldListId decoded successfully",
                "fieldlistid": decoded_fieldlistid
            }), 200
        except base64.binascii.Error:
            return jsonify({"message": "Invalid Base64 encoding"}), 400
        except UnicodeDecodeError:
            return jsonify({"message": "Failed to decode Base64 string to UTF-8"}), 400
        except Exception as e:
            return jsonify({"message": "Unexpected error during decoding", "error": str(e)}), 500

    except Exception as e:
        return jsonify({"message": "Decode error", "error": str(e)}), 500


# Updated /qrcode_fieldlistid endpoint
FIELD_MAP_HTML_BASE_URL = app.config['FIELD_MAP_HTML_BASE_URL']

def generate_fieldlistid_qrcode():
    fieldlist_id = request.args.get('fieldlist_id')
    if not fieldlist_id:
        return jsonify({"error": "Missing fieldlist_id parameter"}), 400

    # Validate fieldlist_id format (UUID with 8-8-8-8-8-8-8-8 segments, 7 dashes)
    if not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}', fieldlist_id):
        return jsonify({"error": "Invalid fieldlist_id format"}), 400

    # Check if fieldlist_id exists in the mask_field_mapping table
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM mask_field_mapping WHERE fieldlistid = %s", (fieldlist_id,))
                if not cur.fetchone():
                    return jsonify({"error": "fieldlist_id not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    # Encode fieldlist_id in Base64
    try:
        encoded_fieldlist_id = base64.b64encode(fieldlist_id.encode()).decode('utf-8')
    except Exception as e:
        return jsonify({"error": f"Failed to encode fieldlist_id: {str(e)}"}), 500

    # Generate URL with encoded fieldlist_id
    url = f"{FIELD_MAP_HTML_BASE_URL}?fieldlistid={encoded_fieldlist_id}"
    print(f"Generated URL: {url}")  # Print the URL for reference

    # Generate QR code
    try:
        img = qrcode.make(url)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return jsonify({"error": f"Failed to generate QR code: {str(e)}"}), 500


def lookup_user():
    try:
        data = request.get_json(force=True)
 
        conn = get_pg_connection()
        cursor = conn.cursor()
 
        contact = data.get("contact", "").strip()
        if "@" in contact:  # Email
            normalized = contact.lower()
        else:  # Phone number
            normalized = contact
 
        print(f'Normalized contact: "{normalized}"')
        print(f"Running query for contact: {normalized}")
 
        cursor.execute("""
            SELECT user_registry_id, email, phone_num
            FROM users
            WHERE LOWER(TRIM(email)) = %s OR TRIM(phone_num) = %s
            LIMIT 1;
        """, (normalized, normalized))
 
 
 
        result = cursor.fetchone()
        print(f'DB result: {result}')
 
        if result:
            user_id, email, phone = result
            return jsonify({
                "user_id": user_id,
                "email": email,
                "phone_num": phone
            })
        else:
            return jsonify({"message": "User not found"}), 404
 
    except Exception as e:
        print("Lookup error:", str(e))
        return jsonify({"message": "Internal server error", "error": str(e)}), 500
 
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
 
 
def get_field_list_ids():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT fieldlistid FROM mask_field_mapping ORDER BY fieldlistid;")
        results = cursor.fetchall()
        field_ids = [row[0] for row in results]
        return jsonify(field_ids)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        conn.close()
 
def add_to_acl():
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        field_list_id = data.get("field_list_id")
 
        if not user_id or not field_list_id:
            return jsonify({"message": "Missing user_id or field_list_id"}), 400
 
        conn = get_connection()
        cursor = conn.cursor()
 
        # Insert user into ACL and set status = 'Approved'
        cursor.execute("""
            INSERT INTO user_acl (user_id, field_list_id, status, created_at)
            VALUES (%s, %s, 'Approved', NOW())
            ON CONFLICT (user_id, field_list_id) DO UPDATE
            SET status = 'Approved';
        """, (user_id, field_list_id))
 
 
        conn.commit()
        return jsonify({"message": "User added to ACL and approved successfully"}), 200
 
    except Exception as e:
        print("ACL insert error:", str(e))
        return jsonify({"message": "Internal server error", "error": str(e)}), 500
 
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()


VALID_GEO_ID_REGEX = re.compile(r'^[a-f0-9]{64}$', re.IGNORECASE)


def get_geoids():
    try:
        data = request.get_json(force=True)
        access_token = data.get("access_token")
        user_registry_id = data.get("user_registry_id")

        if not access_token or not user_registry_id:
            return jsonify({"message": "access_token and user_registry_id are required"}), 400

        flask_url = "https://api.terrapipe.io/geo-id"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(flask_url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            geo_ids_raw = data.get("geo_ids", [])

            # filter valid ids
            geo_ids = [
                geo_id for geo_id, _, _ in geo_ids_raw
                if geo_id and VALID_GEO_ID_REGEX.fullmatch(geo_id)
            ]

            def fetch_field_name(geo_id):
                try:
                    url = f"https://api.terrapipe.io/fetch-field/{geo_id}"
                    resp = requests.get(url, headers=headers, timeout=10)
                    if resp.status_code == 200:
                        return {"geoid": geo_id, "field_name": resp.json().get("field_name", geo_id)}
                except Exception:
                    pass
                return {"geoid": geo_id, "field_name": geo_id}

            geoids_info = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                results = list(executor.map(fetch_field_name, geo_ids))
                geoids_info.extend(results)

            if not geoids_info:
                return jsonify({"message": "No valid Geo Ids found."}), 404

            return jsonify({
                "message": "Geo Ids fetched successfully",
                "user_registry_id": user_registry_id,
                "geoids": geoids_info
            }), 200

        else:
            return jsonify({
                "message": "Failed to fetch geo ids from Flask",
                "error": response.json().get("message", "Unknown error")
            }), response.status_code

    except Exception as e:
        return jsonify({
            "message": "Error while fetching geo ids",
            "error": str(e)
        }), 500

def get_fieldlists():
    try:
        data = request.get_json(force=True)
        user_registry_id = data.get("user_registry_id")

        if not user_registry_id:
            return jsonify({"error": "user_registry_id is required"}), 400

        conn = get_connection()
        cur = conn.cursor()

        query = """
            SELECT fieldlistid, fieldlistid_name
            FROM mask_field_mapping
            WHERE user_id = %s
        """
        cur.execute(query, (user_registry_id,))
        rows = cur.fetchall()

        cur.close()
        conn.close()

        if not rows:
            return jsonify({"message": "No fieldlists found for this user"}), 404

        fieldlists = [
            {"fieldlistid": row[0], "fieldlistid_name": row[1]}
            for row in rows
        ]
        return jsonify({"fieldlists": fieldlists}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Helper that encapsulates the user lookup used by /get_user_data
def fetch_user_data_by_registry(user_registry_id):
    """Return dict with user_registry_id, phone_num, email or None if not found."""
    if not user_registry_id:
        return None
 
    conn = None
    cursor = None
    try:
        conn = get_pg_connection()   # same connection helper your get_user_data used
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_registry_id, phone_num, email
            FROM users
            WHERE user_registry_id = %s
            LIMIT 1;
        """, (user_registry_id,))
        row = cursor.fetchone()
        if row:
            return {"user_registry_id": row[0], "phone_num": row[1], "email": row[2]}
        return None
    except Exception as e:
        app.logger.exception("fetch_user_data_by_registry error")
        return None
    finally:
        if cursor: cursor.close()
        if conn: conn.close()



# Keep /get_user_data but make it use the helper above
def get_user_data_acl():
    try:
        data = request.get_json(force=True)
        user_registry_id = data.get("user_registry_id", "").strip()
        if not user_registry_id:
            return jsonify({"message": "user_registry_id is required"}), 400
 
        user = fetch_user_data_by_registry(user_registry_id)
        if user:
            # Keep response shape similar to what you had earlier
            return jsonify({
                "user_id": user["user_registry_id"],
                "phone_num": user["phone_num"],
                "email": user["email"]
            })
        else:
            return jsonify({"message": "User not found"}), 404
 
    except Exception as e:
        app.logger.exception("Lookup error")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500
 

def get_all_field_users():
    try:
        # Connect to Node 1 (mask_field_mapping)
        conn1 = get_connection()
        cursor1 = conn1.cursor()
        cursor1.execute("SELECT fieldlistid, fieldlistid_name, user_id FROM mask_field_mapping;")
        mask_rows = cursor1.fetchall()
 
        # Connect to Node 6 (users table)
        conn2 = get_pg_connection()
        cursor2 = conn2.cursor()
        cursor2.execute("SELECT user_registry_id, email, phone_num FROM users;")
        user_rows = cursor2.fetchall()
 
        # Convert user_rows to a dictionary for fast lookup
        user_dict = {u[0]: {"email": u[1], "phone_num": u[2]} for u in user_rows}
 
        # Merge data
        data = []
        for m in mask_rows:
            fieldlistid, fieldlistid_name, user_id = m
            if user_id in user_dict:
                data.append({
                    "fieldlistid": fieldlistid,
                    "fieldlist_name": fieldlistid_name,
                    "user_registry_id": user_id,
                    "email": user_dict[user_id]["email"],
                    "phone_num": user_dict[user_id]["phone_num"]
                })
        return jsonify(data)
 
    except Exception as e:
        return jsonify({"error": str(e)}), 500
 
    finally:
        if 'cursor1' in locals() and cursor1:
            cursor1.close()
        if 'conn1' in locals() and conn1:
            conn1.close()
        if 'cursor2' in locals() and cursor2:
            cursor2.close()
        if 'conn2' in locals() and conn2:
            conn2.close()


def get_field_users(field_list_id):
    """
    Returns all users in user_acl for the given field_list_id
    along with their email, phone, and approval status.
    """
    conn_acl = None
    cursor_acl = None
    conn_users = None
    cursor_users = None
    try:
        # 1. Fetch user_ids + status from user_acl
        conn_acl = get_connection()
        cursor_acl = conn_acl.cursor()
        cursor_acl.execute("""
            SELECT user_id, status
            FROM user_acl
            WHERE field_list_id = %s
            ORDER BY created_at ASC;
        """, (field_list_id,))
        acl_rows = cursor_acl.fetchall()
        user_status_map = {r[0]: r[1] for r in acl_rows}  # user_id -> status
        user_ids = list(user_status_map.keys())
 
        if not user_ids:
            return jsonify([])  # no users in this field_list_id
 
        # 2. Fetch user details from users table
        conn_users = get_pg_connection()
        cursor_users = conn_users.cursor()
        query = """
            SELECT user_registry_id, email, phone_num
            FROM users
            WHERE user_registry_id = ANY(%s::uuid[]);
        """
        cursor_users.execute(query, (user_ids,))
        user_rows = cursor_users.fetchall()
 
        # Convert to dict for fast lookup
        user_dict = {r[0]: {"email": r[1], "phone_num": r[2]} for r in user_rows}
 
        # 3. Merge results
        result = []
        for uid in user_ids:
            if uid in user_dict:
                result.append({
                    "user_id": uid,
                    "email": user_dict[uid]["email"],
                    "phone_num": user_dict[uid]["phone_num"],
                    "status": user_status_map.get(uid, "Pending")
                })
 
        return jsonify(result)
 
    except Exception as e:
        app.logger.exception("Error fetching field users")
        return jsonify({"message": "Internal server error", "error": str(e)}), 500
 
    finally:
        if cursor_acl: cursor_acl.close()
        if conn_acl: conn_acl.close()
        if cursor_users: cursor_users.close()
        if conn_users: conn_users.close()
 

def get_users_for_field(fieldlistid):
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
 
        # get distinct user_id values for this fieldlistid
        cursor.execute("""
            SELECT DISTINCT user_id
            FROM mask_field_mapping
            WHERE fieldlistid = %s;
        """, (fieldlistid,))
        rows = cursor.fetchall()
 
        users = []
        for row in rows:
            # row[0] is the user_registry_id stored in mask_field_mapping.user_id
            user_registry_id = row[0]
            # reuse the helper — same logic as your /get_user_data
            user = fetch_user_data_by_registry(user_registry_id)
            if user:
                users.append({
                    "fieldlistid": fieldlistid,
                    "user_registry_id": user_registry_id,
                    "email": user.get("email"),
                    "phone_num": user.get("phone_num")
                })
            else:
                # include the id even if user record not found (so frontend can handle)
                users.append({
                    "fieldlistid": fieldlistid,
                    "user_registry_id": user_registry_id,
                    "email": None,
                    "phone_num": None
                })
 
        return jsonify(users)
 
    except Exception as e:
        app.logger.exception("get_users_for_field error")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def link_fieldlistid():
    fieldlist_id = request.args.get('fieldlist_id')
    if not fieldlist_id:
        return jsonify({"error": "Missing fieldlist_id parameter"}), 400

    # Validate fieldlist_id format (UUID with 8-8-8-8-8-8-8-8 segments, 7 dashes)
    if not re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}-[0-9a-f]{8}', fieldlist_id):
        return jsonify({"error": "Invalid fieldlist_id format"}), 400

    # Check if fieldlist_id exists in DB
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM mask_field_mapping WHERE fieldlistid = %s", (fieldlist_id,))
                if not cur.fetchone():
                    return jsonify({"error": "fieldlist_id not found"}), 404
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    # Encode fieldlist_id in Base64
    try:
        encoded_fieldlist_id = base64.b64encode(fieldlist_id.encode()).decode('utf-8')
    except Exception as e:
        return jsonify({"error": f"Failed to encode fieldlist_id: {str(e)}"}), 500

    # Generate link
    url = f"{FIELD_MAP_HTML_BASE_URL}?fieldlistid={encoded_fieldlist_id}"
    # print(f"Generated URL: {url}")
    return jsonify({"link": url})

def get_geoids_by_fieldlistid():
    fieldlist_id = request.args.get("fieldlist_id")
    if not fieldlist_id:
        return jsonify({"error": "Missing fieldlist_id parameter"}), 400

    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT geoid FROM field_mapping
            WHERE fieldlistid = %s
        """, (fieldlist_id,))
        rows = cur.fetchall()

        cur.close()
        conn.close()

        if not rows:
            return jsonify({"message": "No geoids found for this fieldlistid"}), 404

        geoids = [row[0] for row in rows]
        return jsonify({"fieldlistid": fieldlist_id, "geoids": geoids}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

def generate_facilityid():
    return str(uuid.uuid4()) 

def store_facility_mapping(facilityid, geoid, polygon_wkt, user_id, facility_name):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO facility_mapping (facilityid, geoid, wkt, user_id, facility_name)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (facilityid) DO UPDATE
        SET geoid = EXCLUDED.geoid,
            wkt = EXCLUDED.wkt,
            user_id = EXCLUDED.user_id,
            facility_name = EXCLUDED.facility_name;
    """, (facilityid, geoid, polygon_wkt, user_id, facility_name))

    conn.commit()
    cur.close()
    conn.close()

def process_facility(geoid, user_id, facility_name):
    polygon_wkt = fetch_wkt(geoid)
    facilityid = generate_facilityid()
    store_facility_mapping(facilityid, geoid, polygon_wkt, user_id, facility_name)
    return facilityid, geoid, polygon_wkt

def get_facility_by_geoid(geoid, user_id):
    """Check if a facility already exists for given geoid and user_id"""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT facilityid, facility_name, user_id, wkt
        FROM facility_mapping
        WHERE geoid = %s AND user_id = %s
        LIMIT 1;
    """, (geoid, user_id))

    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        return {
            "facilityId": str(row[0]),
            "facilityName": row[1],
            "user_id": row[2],
            "polygon": row[3],
            "geoid": geoid
        }
    return None


def create_facility():
    data = request.get_json()
    geoid = data.get("geoid")
    user_id = data.get("user_id")
    facility_name = data.get("facility_name")

    if not geoid or not user_id:
        return jsonify({"error": "Geoid and user_id are required"}), 400

    try:
        existing = get_facility_by_geoid(geoid, user_id)
        if existing:
            return jsonify({
                "message": "Facility already exists",
                **existing
            }), 200

        facilityid, geoid, polygon_wkt = process_facility(geoid, user_id, facility_name)
        return jsonify({
            "facilityId": str(facilityid),
            "geoid": geoid,
            "polygon": polygon_wkt,
            "facilityName": facility_name,
            "user_id": user_id
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_facility_view(facilityid):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT wkt, facility_name, user_id, geoid FROM facility_mapping WHERE facilityid = %s", (facilityid,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return jsonify({"error": "Facility not found"}), 404

    return jsonify({
        "facilityid": facilityid,
        "wkt": row[0],
        "facility_name": row[1],
        "user_id": row[2],
        "geoid": row[3]
    })

def request_access():
    conn = None
    cursor = None
    try:
        data = request.get_json(force=True)
        user_registry_id = data.get("user_registry_id", "").strip()
        field_list_id = data.get("field_list_id", "").strip()

        if not user_registry_id or not field_list_id:
            return jsonify({"status": "error", "message": "user_registry_id and field_list_id are required"}), 400

        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Check if an access request already exists
        cursor.execute("""
            SELECT status FROM user_acl
            WHERE user_id = %s AND field_list_id = %s
        """, (user_registry_id, field_list_id))
        existing_request = cursor.fetchone()

        if existing_request:
            if existing_request['status'] == 'Pending':
                return jsonify({"status": "error", "message": "Access request already pending"}), 400
            elif existing_request['status'] == 'Approved':
                return jsonify({"status": "error", "message": "Access already approved"}), 400
            else:
                return jsonify({"status": "error", "message": f"Access request status: {existing_request['status']}"}), 400

        # Insert new access request with status 'Pending'
        cursor.execute("""
            INSERT INTO user_acl (user_id, field_list_id, status, created_at)
            VALUES (%s, %s, 'Pending', %s)
            RETURNING acl_id
        """, (user_registry_id, field_list_id, datetime.utcnow()))
        acl_id = cursor.fetchone()['acl_id']
        conn.commit()

        return jsonify({
            "status": "success",
            "message": "Access request submitted successfully",
            "acl_id": acl_id
        })

    except psycopg2.IntegrityError as e:
        if "user_acl_user_id_field_list_id_key" in str(e):
            return jsonify({"status": "error", "message": "Access request already exists"}), 400
        return jsonify({"status": "error", "message": "Database error", "details": str(e)}), 500
    except Exception as e:
        print(f"Error in /request_access: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error", "details": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def pending_requests():
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT ua.acl_id, ua.field_list_id, mfm.fieldlistid_name AS field_list_name, ua.user_id, ua.status
            FROM user_acl ua
            JOIN mask_field_mapping mfm ON ua.field_list_id = mfm.fieldlistid
            WHERE ua.status = 'Pending'
            ORDER BY ua.created_at DESC
        """)
        requests = cursor.fetchall()

        enriched_requests = []
        for req in requests:
            user_data = fetch_user_data_by_registry(req['user_id'])
            enriched_req = dict(req)
            enriched_req['email'] = user_data['email'] if user_data else '-'
            enriched_req['phone_num'] = user_data['phone_num'] if user_data else '-'
            enriched_requests.append(enriched_req)

        return jsonify(enriched_requests)
    except Exception as e:
        print(f"Error in /pending_requests: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error", "details": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def approve_request():
    conn = None
    cursor = None
    try:
        data = request.get_json(force=True)
        acl_id = data.get("acl_id", "").strip()
        if not acl_id:
            return jsonify({"status": "error", "message": "acl_id is required"}), 400

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE user_acl
            SET status = 'Approved'
            WHERE acl_id = %s AND status = 'Pending'
        """, (acl_id,))
        if cursor.rowcount == 0:
            return jsonify({"status": "error", "message": "No pending request found or already processed"}), 404
        conn.commit()
        return jsonify({"status": "success", "message": "Access request approved successfully"})
    except Exception as e:
        print(f"Error in /approve_request: {str(e)}")
        return jsonify({"status": "error", "message": "Internal server error", "details": str(e)}), 500
    finally:
        if cursor: cursor.close()
        if conn: conn.close()