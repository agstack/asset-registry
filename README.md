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