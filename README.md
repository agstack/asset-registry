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


## 🗺️ Region List & QR Mapping Service
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

# 🌾 FieldList & QR Mapping Service

This system allows users to register accounts, create "FieldLists" from registered GeoIDs, manage access via ACL (Access Control Lists), and view field data.

The system distinguishes between **Masked Views** (public/protected) and **Actual Field Views** (requires OTP/Approval).

---

## 🔐 User Authentication & Management

Endpoints for user signup, OTP verification, and login.

### 1. User Signup
Register a new user to the system.

**Endpoint:** `POST /signup`

****Body (JSON):****
```json
{
    "firstName": "test",
    "lastName": "test",
    "companyName": "TP",
    "email": "test@gmail.com",
    "phone_number": "+919876543210",
    "password": "Password@123",
    "confirm_password": "Password@123"
}
```

**Response:**

```json
{
    "message": "OTP sent to +919876543210. Please verify to complete registration.",
    "public_key": "bf201011-c9b3-42c9-89e7-ee4b538ca125",
    "status": "otp_sent"
}
```
---

### 2. Verify Signup OTP
Verify the phone number to complete account creation.

**Endpoint:** `POST /verify-otp`

**Body (JSON):**

```json
{
    "public_key": "bf201011-c9b3-42c9-89e7-ee4b538ca125",
    "otp": "890251"
}
```

**Response:**

```json
{
    "email": "test@gmail.com",
    "phone_num": "+919876543210",
    "message": "User created successfully"
}
```
---

###  3. Login
Login to receive an access_token and user_registry_id.

**Endpoint:** `POST /login_fieldlistid`

**Body (JSON):**

```json
{
    "email": "test@gmail.com",
    "password": "Password@123"
}
```

**Response:**

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
    "message": "Login successful",
    "user_registry_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13"
}
```
---

### 4. Lookup User
Find a user_id using an email address or phone number.

**Endpoint:** `POST /lookup-user`

**Body (JSON):**

```json
{
    "contact": "test@gmail.com"
}
```

**Response:**

```json
{
    "email": "test@gmail.com",
    "phone_num": "+919876543210",
    "user_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13"
}
```
---

## 🗺️ FieldList Management
Create and manage groups of GeoIDs (FieldLists).

### 5. Create FieldList (Ingest)
Create a new FieldList ID from a list of GeoIDs.

**Endpoint:** `POST /ingest`

**Body (JSON):**


```json
{
    "geoids": [
        "5e2b7ee994b1ff30ce47754379968eecd380a59a0322e5fadeb2c90a69163133"
    ],
    "user_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13",
    "fieldlistid_name": "test_field_jp"
}
```

**Response:**

```json
{
    "fieldListId": "f810ac2f-51659e5d...",
    "maskListId": "cde5ce8de7e6...",
    "maskList": [...],
    "fieldListName": "test_field_jp"
}
```
---

### 6. Get All FieldList IDs
Retrieve a list of all FieldList IDs available in the system.

**Endpoint:** `GET /field-list-ids`

**Response:**

```json
[
    "08fa1695-e5739d2a...",
    "0ace0b45-aff2ad42..."
]
```
---

### 7. Get User's FieldLists
Get all FieldLists associated with a specific user.

**Endpoint:** `GET /all-field-users`

**Response:**

```json
[
    {
        "email": "test@gmail.com",
        "fieldlist_name": "Name_857c93",
        "fieldlistid": "b2451616-8fa08ab0...",
        "phone_num": "8054840910",
        "user_registry_id": "3c5fc37f-abd3-465c..."
    }
]
```
---

## 👁️ Data Visualization & Masking
View masked data (polygons) and verify identity to view actual field data.

### 8. Get Masked Data
View the masked representation (S2 Cells) of a FieldList.

**Endpoint:** `GET /getWKT/mask/{field_list_id}`

**Response:**

```json
{
    "cells": [
        {
            "geometry": { "type": "Polygon", "coordinates": [...] },
            "s2_cell_id": "89c25f"
        }
    ],
    "view": "mask"
}
```
---

### 9. Request OTP for Field Access
Request an OTP to view the actual field data.

**Endpoint:** `POST /request-otp-fieldlistid`

**Body (JSON):**
```json
{
    "user_registry_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13",
    "field_list_id": "b2451616-8fa08ab0-a979868f-6c47ca6c-5f02a3ed-c3f9de69-a91ed478-bde6c14c"
}
```
**Response:**

```json
{
    "message": "OTP sent to registred number: ******910",
    "status": "success"
}
```
---

### 10. Verify Field Access OTP
Verify the OTP to authorize viewing of field data.

**Endpoint:** `POST /verify-otp-fieldlistid`

**Body (JSON):**

```json
{
    "user_registry_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13",
    "field_list_id": "b2451616-8fa08ab0-a979868f-6c47ca6c-5f02a3ed-c3f9de69-a91ed478-bde6c14c",
    "otp": "998173"
}
```

**Response:**

```json
{
    "field_list_id": "b2451616-8fa08ab0-a979868f-6c47ca6c-5f02a3ed-c3f9de69-a91ed478-bde6c14c", "message": "OTP verified",
    "status": "success",
    "user_registry_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13"
}
```
---

### 11. Get Actual Field Data (WKT)
Once authorized/verified, retrieve the actual field geometry.

**Endpoint:** `POST /getWKT/field/{field_list_id}`

**Body (JSON):**

```json
{
    "user_registry_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13"
}
```

**Response:**

```json
{
    "fields": [
        {
            "fieldId": "0b5cde4783",
            "geoid": "7296a4a0...",
            "wkt": "POLYGON ((-73.8486 40.7193, ...))"
        }
    ],
    "view": "field"
}
```
---

## 🔒 Access Control (ACL)
Manage permissions for who can view FieldLists.

### 12. Request Access
User requests access to a specific FieldList.

**Endpoint:** `POST /request_access`

**Body (JSON):**

```json
{
    "user_registry_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13",
    "field_list_id": "b55680e4-4a2780b9-8004444e-bd3ebbd6-d317212f-498f15a9-b7d43133-e91cae16"
}
```

**Response:**

```json
  {
      "message": "Access approved",
      "status": "success"
  }
```
---

### 13. Get Pending Requests
View all access requests waiting for approval.

**Endpoint:** `GET /pending_requests`

**Response:**

```json
[
    {
        "acl_id": "f1cb6e83-30d7-4f43-ad2c-889b65592b80",
        "email": "test@gmail.com",
        "status": "Pending",
        "field_list_name": "Test_fieldlistid_name_5"
    }
]
```
---

### 14. Approve Request
Approve a pending access request using the acl_id.

**Endpoint:** `POST /approve_request`

**Body (JSON):**

```json
{
    "acl_id": "06a45e4b-fd47-48e3-8755-2739dd37e329"
}
```

**Response:**
```json
{
    "message": "request  processed",
    "status": "success"
}
```
---

### 15. Direct Add to ACL
Immediately approve a user for a FieldList without a request.

**Endpoint:** `POST /add-to-acl`

**Body (JSON):**

```json
{
    "user_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13",
    "field_list_id": "6c5626d5-42f6dd1f-cb2bfe63-ba7f6ae0-f3633ce5-68f2168d-03269557-d5fb44d3"
}
```

**Response:**

```json
{
    "message": "User added to ACL and approved successfully"
}

```
---

## 🏭 Facility Management
### 16. Create Facility
Register a facility with a specific GeoID.

**Endpoint:** `POST /create_facility`

**Body (JSON):**

```json
{
    "geoid": "a2ef5c4b3bbcc621f65232d28aebb46923f55b7cf8b85c075c50d3475fde6eb0",
    "user_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13",
    "facility_name": "Facility one"
}
```
**Response:**

```json
{
    "facilityId": "61d1716d-a5ea-4e5d-9251-ebf4dfc45949", 
    "facilityName": "Facility one", 
    "geoid": "a2ef5c4b3bbcc621f65232d28aebb46923f55b7cf8b85c075c50d3475fde6eb0", 
    "message": "Facility Created", 
    "polygon": "POLYGON((-120.41666865348816 36.842314229195566,-120.4170870780945 36.84084598055944,-120.41578888893129 36.840661374203776,-120.41540801525117 36.841962195542074,-120.41666865348816 36.842314229195566))", 
    "user_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13"}

```
---

### 17. Get Facility Data
Retrieve WKT data for a facility.

**Endpoint:** `GET /getWKT/facility/{facility_id}`

**Response:**

```json
{
    "facility_name": "MyTestFacility",
    "wkt": "POLYGON ((-120.419 36.836, ...))"
}
```
---

## 📱 Links & QR Codes
### 18. Get FieldList Public Link
Generates a safe public link with an encoded FieldList ID.

**Endpoint:** `GET /link_fieldlistid`

**Query Params:** `?fieldlist_id={id}`

**Response:**

```json

{
    "link": "[http://147.93.45.127/fieldlistid_map.html?fieldlistid=ZjgxMGFjMmY](http://147.93.45.127/fieldlistid_map.html?fieldlistid=ZjgxMGFjMmY)..."
}
```
---

### 19. Get QR Code
Download a QR code image for the FieldList map.

**Endpoint:** `GET /qrcode_fieldlistid`

**Query Params:** `?fieldlist_id={id}`

**Response:** Binary Image Data (Save as .png)
---

## 🛠️ Utilities
### 20. Get User GeoIDs
Retrieve GeoIDs registered to the logged-in user.

**Endpoint:** `POST /get-geoids`

**Body (JSON):**

```json
{
    "access_token": "YOUR_ACCESS_TOKEN",
    "user_registry_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13"
}
```

**Response:**

```json
{
    "geoids": [{"field_name": "102", "geoid": "a4fd692c2578b270a937ce77869361e3cd22cd0b021c6ad23c995868bd11651e"}, {"field_name": "105", "geoid": "1c00a0567929a228752822d564325623c51f6cdc81357fa043306d5c41b2b13e"}, {"field_name": "477d8dffaf92d265c56dca496167d71bfc1c34f443bc9a6677009963e6e99706", "geoid": "477d8dffaf92d265c56dca496167d71bfc1c34f443bc9a6677009963e6e99706"}, {"field_name": "1049f35c801ce88be72e210eeb9410ec9d7d4682b2ed46aaaa4641e392ffd669", "geoid": "1049f35c801ce88be72e210eeb9410ec9d7d4682b2ed46aaaa4641e392ffd669"}, {"field_name": "b9605fcc15025ec4844c91fff5b150038f738794016101d82bba29bc5a5aa41e"}],
    "message": "Geo Ids fetched successfully", 
    "user_registry_id": "3c5fc37f-abd3-465c-a0c3-a3dae580ed13"}
```
---

### 21. Get GeoIDs by FieldList
Extract GeoIDs contained within a FieldList ID.

**Endpoint:** `GET /get_geoids_by_fieldlistid`

**Query Params:** `?fieldlist_id={id}`

**Response:**


```json
{
    "fieldlistid": "f810ac2f...",
    "geoids": ["5e2b7ee9..."]
}
```
---