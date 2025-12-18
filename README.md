# 🌍 Asset Registration Service API

This repository outlines the API calls necessary for registering geo-spatial assets (typically field boundaries defined by a **WKT polygon**) and obtaining a unique, 256-bit alphanumeric ID (**GeoID**). It also includes endpoints for user authentication and token management.

---

## 🔒 Authentication

All registration endpoints require a valid **Access Token** obtained through the login process.

### 1. Login

Authenticates the user and returns a pair of JWTs: an `access_token` (short-lived) and a `refresh_token` (long-lived).

* **Endpoint:** `POST https://user-registry.agstack.org/login`
* **Headers:**
    * `Content-Type: application/json`
    * `X-FROM-ASSET-REGISTRY: True`
* **Body (JSON):**

    ```json
    {
      "email": "testuser@example.com",
      "password": "TestPassword123"
    }
    ```

* **Example Response:**

    ```json
    {
      "access_token": "YOUR_NEWLY_GENERATED_ACCESS_TOKEN",
      "refresh_token": "YOUR_LONG_LIVED_REFRESH_TOKEN"
    }
    ```

---

## 📝 Registering a Field Boundary (Asset)

The primary endpoint for registering a geo-spatial asset. This API handles new registrations, S2 indexing requests, and checks for existing boundaries.

### 2. Register New Field Boundary (GeoID Only)

Registers the asset using its **WKT** representation and returns only the GeoID.

* **Endpoint:** `POST https://api-ar.agstack.org/register-field-boundary`
* **Headers:**
    * `Authorization: Bearer <access_token>`
    * `X-FROM-ASSET-REGISTRY: True`
    * `Content-Type: application/json`
* **Body (JSON):**
    * `wkt`: **W**ell-**K**nown **T**ext representation of the geometry.**Required**
    * `threshold`: Matching sensitivity percentage (e.g., 95).**Optional**

    ```json
    {
      "wkt": "POLYGON((76.88855767250062 30.311450431756946,76.88841819763184 30.310732833916543,76.88945889472961 30.31070505582999,76.8894535303116 30.311399505631794,76.88855767250062 30.311450431756946))",
      "threshold": 95
    }
    ```

* **Example Response (Success):**

    ```json
    {
      "Geo Id": "0d8b4afb3b3332f75cf5b1889b0564a9e7a80f4bad239a9a593e1665210c3079",
      "message": "Field Boundary registered successfully."
    }
    ```

### 3. Register Field Boundary with S2 Indices(Optional)

Registers the asset and also returns the **S2 Cell Tokens** that cover the geometry at specified levels.

* **Body (JSON) - Additional Fields:**
    * `return_s2_indices`: Set to `true`.**Required**
    * `s2_index`: A comma-separated string of desired S2 levels (e.g., "8,13").**Optional**

    ```json
    {
      "wkt": "POLYGON((76.89016699790955 30.310293011861138, ...))",
      "threshold": 95,
      "return_s2_indices": true,
      "s2_index": "8,13"
    }
    ```

* **Example Response:**

    ```json
    {
      "Geo Id": "56d35a1abc15ff5f96d6b75bf93d3db5d2891a03a990231e7ab9cc5b37ffe9d3",
      "S2 Cell Tokens": {
        "13": ["390fb43c"],
        "8": ["390fb"]
      },
      "message": "Field Boundary registered successfully."
    }
    ```

### 4. Handling Already Registered Boundaries

If you attempt to register a geometry that already exists in the system (based on the overlap `threshold`), the API will return the existing GeoID(s) instead of creating a new one.

* **Example `curl` Command:**

    ```bash
    curl -X POST https://api-ar.agstack.org/register-field-boundary\
      -H "Authorization: Bearer <access_token>" \
      -H "X-Refresh-Token: <refresh_token>" \
      -H "X-FROM-ASSET-REGISTRY: True" \
      -H "Content-Type: application/json" \
      -d '{
            "wkt": "POLYGON((-73.84912140391035 40.72077437574217, -73.84931242628205 40.72047776197556, -73.84896765419661 40.72036653147276, -73.84879759769481 40.720662262956154, -73.84912140391035 40.72077437574217))", 
            "threshold": 95
          }'
    ```

* **Example Response (Duplicate):**

    ```json
    {
      "matched geo ids": [
        "60cfd23622803f6cbdf666f19d61dc56f37f3cbb9625f66edebd83d04bb89ede"
      ],
      "message": "field already registered previously"
    }
    ```

---

## 🔑 Token Refresh

If a registration attempt fails due to an expired token, use the refresh flow.

### 5. Refresh Access Token

* **Endpoint:** `GET https://user-registry.agstack.org/refresh`
* **Cookie:** The `refresh_token` must be sent as a cookie.

    ```bash
    curl -X GET [https://user-registry.agstack.org/refresh](https://user-registry.agstack.org/refresh) \
      --cookie "refresh_token_cookie=YOUR_LONG_LIVED_REFRESH_TOKEN"
    ```

* **Example Response:**

    ```json
    {
      "access_token": "YOUR_NEWLY_GENERATED_ACCESS_TOKEN"
    }
    ```

### 6. Expired Token Error

If you see this response, proceed to **Step 5** immediately.

* **Response:**
    ```json
    {
      "message": "Invalid token: Short live token has expired"
    }
    ```


## 🗺️ Region List & QR Mapping Service (Test Links)
This service provides a way to group multiple geo-spatial regions into a single, deterministic RegionListID. It includes tools to generate QR codes for easy sharing and an endpoint to retrieve GeoJSON data for map visualization.

### Region List Management
These endpoints allow you to create and manage collections of region IDs.

### 1. Create RegionListID
Generates a deterministic 64-character hex ID (formatted in 8-character chunks) for a unique list of existing region IDs.

* **Endpoint:** `POST /create_regionlistID`

* **Content-Type:** `application/json`

* **Body (JSON):**

    * `region_ids:` An array of region ID strings. **Required**
    ```json
    {
      "region_ids": [
        "3f6855e35a8dcebe-e5aabcc95f148e80-c52a4540961c23bc-1b7158ea18949a5f",
        "a23a8c2e22667d29-3e6656b66f657657-5081805792e98208-3349896b72ef09ce"
      ]
    }
    ```

* **Example Response:**

    ```json
    {
      "message": "RegionListID created successfully",
      "regionListID": "cca1099a-1a2b3bc0-a0f56527-e80253fb-484ad822-5d12698e-170cf1a3-8149c949",
      "stored_region_ids": ["..."],
      "unregistered_region_ids": []
    }
    ```
---

### 2. Get Region Boundaries
Retrieves the raw WKT boundaries for all regions associated with a specific regionlist_id.

* **Endpoint:** `GET /get_region_boundaries/`


* **Content-Type:** `application/json`

* **Body (JSON):**

    * `regionlist_id:` The unique Regionlist ID. **Required**
    ```json
    {
      "regionlist_id": "3f6855e35a8dcebe-e5aabcc95f148e80-c52a4540961c23bc-1b7158ea18949a5f"
    }
    ```

* **Example Response:**

    ```json
    {
      "boundaries": [{"region_boundary": "POLYGON ((-88.5775 15.3148, -88.5741 15.3164, -88.5665 15.3193, -88.5597 15.3219, -88.5598 15.3193, -88.56 15.317,-88.605 15.2888, -88.6032 15.2936, -88.6029 15.2942, -88.6012 15.2973, -88.5993 15.298, -88.5842 15.3101, -88.5799 15.3134, -88.5782 15.3144, -88.5775 15.3148))", "region_id": "8df6d45f5055d10c-11049aadd1052756-826aef3498972eba-0b75e75729858170"}], "regionListID": "2d627058-c3d23a34-ee5fcc00-0c3215de-ecd68fe0-86a61a45-8cbe67db-535d5d2d"
    }
    ```
---
### Visualization & Sharing
Use these endpoints to generate scannable QR codes or fetch geometry data for web maps.

### 3. Generate QR Code
Returns a PNG image of a QR code that points to the map visualization page.

* **Endpoint:** `GET /qrcode`

* **Params:**

    * `regionlist_id:` The ID of the region list. **Required**

    * `format:` Must be qr. **Required**

* **Example Link:** `/qrcode?regionlist_id=cca1099a-1a2b3bc0-a0f56527-e80253fb-484ad822-5d12698e-170cf1a3-8149c949&format=qr`

---
### 4. Fetch Map Geometries (GeoJSON)
Returns a collection of GeoJSON geometries for a given regionlist_id. This is typically called by a frontend map (like Leaflet or Mapbox).

* **Endpoint:** `GET /map`

* **Content-Type:** `application/json`

* **Body (JSON):**

    * `regionlist_id:` The ID of the region list.**Required**
    ```json
    {
      "regionlist_id": "3f6855e35a8dcebe-e5aabcc95f148e80-c52a4540961c23bc-1b7158ea18949a5f"
    }
    ```

* **Example Response:**

    ```json
        [
          {
            "type": "Polygon",
            "coordinates": [[[76.88, 30.31], [76.89, 30.31], ...]]
          }
        ]
    ```
---

### 5. Map View (Frontend)
The visualization page can be accessed via: 
`/map.html?regionlist_id=cca1099a-1a2b3bc0-a0f56527-e80253fb-484ad822-5d12698e-170cf1a3-8149c949`

You can edit or add a custom HTML template to show the polygon on the map.