# AgStack Asset Registry 2.0 — Community Proposal
*Draft for Review & Comment*  
*Version: February 2025*

## 1. Executive Summary

AgStack proposes evolving the Asset Registry from today’s centralized MVP (v1.0) into a **federated, DNS-inspired global system** (v2.0) centered on:

- A **single globally-governed Hub**, replicated across regions  
- A network of **authorized, containerized regional Nodes**  
- A **secure WKT permissioning & masking system** managed by the Hub  
- **Strict governance**, versioning, and release controls  
- **Support for Points, LineStrings, Polygons**, and hashed **ListIDs**  
- A modernized **User Registry** with OECD-grade identity verification  

Asset Registry 2.0 preserves the core principle of GeoIDs:

> **GeoIDs have no authorship, ownership, or metadata attached.  
> They are deterministic hashes mapping to geospatial boundaries.**

The registry only maps **GeoID → Authoritative Node**, while Nodes store geometry and enforce permissions using Hub-managed rules.

This document is intended to gather broad community feedback before entering the RFC phase.

---

## 2. Background: Asset Registry v1.0

Today’s registry:

- Generates unique 64-character GeoIDs from normalized WKT  
- Stores polygon boundaries (future: expanded geometry types)  
- Uses deterministic hashing (no ownership attached)  
- Provides basic API functions for registration & lookup  
- Is centralized (single-instance), limiting scale and sovereignty  

To serve global users and national programs, v2.0 must introduce:

- Federation  
- Governance  
- Permissioned access  
- Secure WKT masking  
- ListIDs  
- Expanded geometry types  
- Identity evolution  

---

## 3. Architecture: Global Hub + Regional Nodes

### 3.1 Global Hub (Root Authority)

The **Global Hub** is the single canonical source of:

```
GeoID → AuthoritativeNodeURL
```

**The Hub:**

- Does **not** store geometry  
- Does **not** store metadata  
- Does **not** store authorship  
- Stores **delegation only**  

**New in v2.0:**

- **Permissions & masking policies**  
- **WKT resolution authorization system**  
- **Versioned policy sets & registry software releases**  
- **OECD-grade identity verification via evolved User Registry**  
- **Signed delegation & permission records**  
- **Daily QoS monitoring from nodes**  

Hub is replicated globally (N ≥ 1 initially; expands over time).

---

### 3.2 Regional Nodes (Authoritative GeoID Registries)

Nodes are delegated a **geospatial region** and can register boundaries only within that region.

Nodes:

- Store full WKT boundaries  
- Support **Point**, **LineString**, and **Polygon**  
- Use the same deterministic hashing rules for all geometries  
- Enforce permissioning using Hub-managed policies  
- Run immutable AgStack containers (auto-updated)  
- Report uptime, QoS, version, region data to the Hub  
- Serve WKT over a secure channel only after Hub authorization  

Nodes can be operated by:

- Governments  
- Accredited AgStack members  
- Managed hosting providers (AWS, Azure, etc.)

---

## 4. WKT Permissioning & Masking (New in v2.0)

### 4.1 WKT Resolution Pipeline (Hub → Node → Client)

All WKT resolution follows this pipeline:

```
Client → Hub → Permission Check → Node → WKT / Masked WKT → Client
```

### 4.2 Masking Behavior

**Masked WKT is always:**

```
The S2 cell at ~10km resolution that contains the centroid of the GeoID boundary.
```

---

## 5. Support for More Geometry Types

Asset Registry 2.0 adds support for:

- **POINT**  
- **LINESTRING**  
- **POLYGON**  

Hashing rules remain **identical for all types**:

```
GeoID = HASH( normalize(WKT) )
```

---

## 6. ListIDs (Lists of GeoIDs)

Asset Registry 2.0 introduces **ListIDs**, which are:

> **Hashed lists of GeoIDs (order-insensitive, unique set).**

Properties:
- Atomic (no hierarchical lists)  
- Deterministic (same set → same ListID)  
- Stored at Node-level  
- Delegations stored at Hub-level like GeoIDs  

---

## 7. Large Region Support (>1000 Acres)

Large regions will support:

- **One primary GeoID** representing the full region (Polygon)  
- **Automatic subdivision into child GeoIDs (optional)**  
- **Parent S2 token association** for indexing and masking  

---

## 8. Roadmap

### Phase 1 (0–6 months)
- Extend normalization to Points & LineStrings  
- Define ListID hashing  
- Design masking system (S2 parent-cell masking)  
- User Registry modernization  
- Draft permission/identity RFC

### Phase 2 (6–12 months)
- Implement Hub-managed permissions  
- Implement WKT resolution tokens  
- Node software with permission enforcement  
- ListID v1 implementation  
- Node region-bound enforcement

### Phase 3 (12–24 months)
- Full rollout to pilot Nodes  
- Multi-region Hub replication  
- WKT masking optimized  
- GeoID+ListID caching and CDN acceleration  
- Real-world security audits

### Phase 4 (24–36 months)
- Governance board established  
- LTS releases  
- Managed hosting partnerships  
- Accreditation expansion  
- Identity provider integrations  

---

## 9. Community Feedback Questions

### 1. Do you support adding WKT masking and permissioning?  
### 2. Should the Hub control authentication + permissioning globally?  
### 3. Should unauthorized users receive a 10km S2 parent-cell mask?  
### 4. Do you support adding support for Points and LineStrings?  
### 5. Do you support deterministic ListIDs?  
### 6. Should ListIDs be atomic (non-hierarchical)?  
### 7. Concerns about permission/WKT security model?  

---

## 10. Next Steps

- Publish this proposal  
- Collect feedback  
- Incorporate community input into the RFC  
- Begin Hub v0.2 + Node v1.0  
- Publish reference APIs  

