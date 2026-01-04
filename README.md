# Warehouse SQL Pipeline for Operational Analytics  
*(Python → MySQL)*

## 30-Second Quick View

This project demonstrates an end-to-end **warehouse analytics SQL pipeline**
designed to replace manual, Excel-heavy reporting workflows.

The pipeline ingests **monthly exported Excel files** from warehouse operations
(outbound shipments and customization / assembly processes), standardizes schemas,
applies row-level deduplication, and loads clean records into MySQL as a
single source of truth.

The resulting database layer supports Power BI dashboards, operational analysis,
and downstream Python modeling, while remaining **safe to re-run** and fully
**traceable to source files**.

> **Note:** No raw operational data are included in this repository.
> The focus is on pipeline design, data modeling, and ingestion logic.

## Core Skills Demonstrated:

Data Analytics · SQL Data Modeling · Analytics Engineering · Data Quality Control · ETL Pipeline Design · Power BI Integration


![Pipeline Demo](docs/demo.gif)

---

## 1. Business Context

Warehouse operations generate high-frequency, event-level data such as:

- Outbound shipment records (daily shipping activity)
- Customization / upgrade / downgrade / assembly workflows
- Customer and SKU identifiers (with varying completeness across systems)
- Inventory snapshots (optional, for advanced analytics)

In the original workflow, analysts relied on dozens of Excel files and
manual merges to produce reports. As file counts and data volume grew,
this approach became:

- time-consuming and error-prone  
- difficult to audit or reproduce  
- hard to scale for automated reporting and analytics  

This project restructures that workflow into a centralized SQL-based pipeline
that is reliable, repeatable, and analytics-ready.

---

## 2. Analytical & Engineering Objectives

- Build a **single source of truth** in MySQL for warehouse operational records
- Enable repeatable analysis for:
  - daily and weekly shipment volume
  - client and SKU activity patterns
  - operational KPIs and exception monitoring
  - Power BI dashboards and Python analytics
- Ensure the pipeline is:
  - **idempotent** (safe to run multiple times)
  - **deduplicated** (no duplicate records)
  - **traceable** (each row linked to its source file)

---

## 3. Input Data (Conceptual)

The pipeline is designed to ingest **monthly exported Excel files** generated
by warehouse operational systems, including:

- Outbound shipment records
- Customization / assembly records  
  (e.g., value-added processing, prebuilt vs outbound workflows)
- Optional extensions: inbound records, inventory snapshots, SKU master data

Due to data sensitivity and access restrictions, **no raw Excel files are
included in this repository**.

---

## 4. Pipeline Architecture

### High-Level Flow

1. **Extract**
   - Read Excel files supplied externally (monthly exports)
2. **Transform**
   - Standardize column names and data types
   - Normalize date and timestamp fields
   - Clean and map identifiers (UPC, SN, stock-out codes, client codes)
   - Attach lineage metadata (`source_file`, `source_row`, `record_type`)
3. **Load**
   - Insert records into MySQL using a deterministic primary key
   - Apply `INSERT IGNORE` / `ON DUPLICATE KEY` logic for safe re-runs

---

### Deterministic Primary Key Strategy

Operational Excel exports often lack a stable unique identifier.
This pipeline generates a deterministic primary key:

hash_id = MD5(stock_out_code + UPC + SN)


This approach:
- enforces record-level uniqueness
- prevents duplicate inserts across re-runs
- avoids reliance on auto-increment IDs
- supports auditability and reproducibility

---

## 5. Database Design (Core Tables)

### `generated_stock_out` — Outbound Fact Table

**Grain:** one row per shipped item

Typical fields:
- `hash_id` (primary key)
- `stock_out_code`
- `upc`
- `sn`
- `product_name`
- `client_code`
- `quantity`
- `event_time` / `ship_date`
- `source_file`
- `source_row`
- `created_at`

---

### Customization / Assembly Tables (Modular)

Examples:
- `value_added`
- `custom_record`

Design principles:
- separate tables for distinct business processes
- use `record_type` or `category` to distinguish subtypes
- always retain `source_file` for lineage and auditing

---

## 6. Data Quality & Guardrails

The pipeline includes practical data-quality controls:

- **Schema standardization**  
  Ensures consistency across monthly Excel exports.

- **Row-level deduplication**  
  Enforced via deterministic primary keys.

- **Data lineage tracking**
  - `source_file`: originating Excel file
  - `source_row`: original row number

- **Re-run safety**  
  The pipeline can be re-executed for any time range
  without generating duplicate records.

---

## 7. Outputs & Downstream Use

The MySQL layer produced by this pipeline is designed to support:

- Power BI dashboards for warehouse operations
- Ad hoc SQL analysis
- Python-based analytics and modeling
- Monitoring rules and exception detection

