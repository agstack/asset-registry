# AgStack Asset Registry 2.0 — Executive Summary

This document provides a **short, high-level overview** of the Asset Registry 2.0 proposal.  
It is intended to serve as the **README** for the GitHub repository, with the full proposal linked separately.

---

## 🚀 What Is Asset Registry 2.0?

Asset Registry 2.0 is AgStack’s next-generation, **DNS-inspired**, globally governed system for managing **GeoIDs** — deterministic hashes mapping to agricultural field boundaries.

It replaces the centralized v1.0 model with a **federated, scalable, secure architecture** built around:

### **1. A Global Hub (Root Authority)**
- Stores only **GeoID → Authoritative Node** mappings  
- Does *not* store geometry, metadata, or authorship  
- Manages:
  - Permissions  
  - Version control  
  - Governance  
  - Node accreditation  
- Replicated globally for performance and resilience  

### **2. Regional Nodes (Authoritative Registries)**
- Store the full geometry (WKT) for GeoIDs in their delegated regions  
- Run secure, immutable AgStack containers with auto-updates  
- Enforce permissioning rules defined by the Hub  
- Support **Point**, **LineString**, and **Polygon** geometries  
- Respond to WKT resolution requests using Hub-issued authorization tokens  

---

## 🔐 Secure WKT Permissioning & Masking

WKT boundaries are now **permissioned assets**:

1. Client requests WKT through the Hub  
2. Hub checks permission + identity  
3. Hub issues a time-bound signed token  
4. Node returns:
   - Exact WKT (if authorized)  
   - Masked 10 km S2 parent cell (if not authorized)  
   - 403 forbidden (if explicitly denied)  

This protects sensitive boundary data while maintaining global resolvability.

---

## 🧩 New Features in v2.0

### **1. Support for Multiple Geometry Types**
- Points  
- LineStrings  
- Polygons  
- Same deterministic hashing rules for all  

### **2. ListIDs**
Hashed, deterministic, order-insensitive lists of GeoIDs.  
Used for:
- Access control  
- Supply-chain traceability  
- Bulk operations  
- Regional programs  

### **3. Large Region Support**
Regions > 1000 acres may leverage:
- Parent S2 tokens  
- Optional subdivision  
- Hierarchical lookup patterns  

### **4. Modernized Identity**
The User Registry evolves to support:
- OECD-grade identity verification  
- Multi-provider authentication (OIDC, SAML, national ID systems)  
- Role-based access control  
- Auditable access logs  

---

## 🏛 Governance Model

Asset Registry 2.0 adopts a hybrid of:

### **ICANN-style global governance**
- Single global root  
- Delegated regional authorities  
- Accreditation, compliance, and dispute processes  

### **Linux kernel–style release management**
- No forks for Nodes  
- Signed, secure, over-the-wire updates  
- LTS and rapid patch cycles  

Nodes must meet:
- Geospatial region boundaries  
- Identity verification  
- Operational uptime requirements  
- Security / telemetry reporting  

---

## 📅 Roadmap Overview

### **0–6 Months**
- Identity upgrades  
- Normalization for new geometry types  
- Masking model  
- ListID hashing  
- Draft RFC process  

### **6–12 Months**
- Hub-managed permissions  
- Node enforcement logic  
- WKT token model  
- Node accreditation for pilots  

### **12–24 Months**
- Multi-region Hub mirrors  
- CDN-style caching  
- Performance hardening  
- Expanded Node accreditation  

### **24–36 Months**
- Governance board seated  
- LTS releases  
- Managed hosting partnerships  
- Broader country onboarding  

---

## 📣 Community Participation

We invite all AgStack contributors, governments, implementers, researchers, and partners to review the full proposal and provide feedback.

👉 **Full Proposal:** `asset-registry-2.0-proposal.md`  
👉 **Feedback Form:** *[Insert Google Form link here]*  
👉 **GitHub Issues:** Use this repo for discussion

Your input will shape the official **Asset Registry 2.0 RFC** and governance charter.

---

## 🌍 Vision

Asset Registry 2.0 enables a **globally unified, sovereign, secure, and open** agricultural geospatial infrastructure — a foundational building block for the next generation of digital agriculture applications, services, and AI.

