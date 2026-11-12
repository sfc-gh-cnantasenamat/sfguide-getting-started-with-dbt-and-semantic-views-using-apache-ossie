author: Aniruth Narayanan, Chanin Nantasenamat
id: getting-started-with-dbt-and-semantic-views-using-apache-ossie
categories: snowflake-site:taxonomy/solution-center/certification/quickstart, snowflake-site:taxonomy/product/ai, snowflake-site:taxonomy/product/analytics, snowflake-site:taxonomy/product/data-engineering
language: en
summary: Build a dbt star schema on TPC-H data, export dbt semantic layer metrics as an Apache Ossie document, and publish them as a Snowflake Semantic View.
environments: web
status: Published
feedback link: https://github.com/Snowflake-Labs/sfquickstarts/issues

# Getting Started with dbt and Semantic Views using Apache Ossie

## Overview

### The Problem

When a data engineering team defines metrics like `total_revenue`, `revenue_per_item`, and `products_sold` in the dbt semantic layer, those definitions often stay locked inside dbt tooling. If an analyst queries Snowflake directly from SQL or a BI tool, or if an AI agent needs governed metrics in a Snowflake Semantic View, someone usually has to rewrite those joins, measures, and ratios by hand in a second YAML format. Maintaining the same metric in two places invites drift: one small change to a discount formula or entity join in dbt leaves the warehouse semantic view out of sync.

### The Solution

[Apache Ossie](https://github.com/apache/ossie) (formerly Open Semantic Interchange, or OSI) provides a vendor-neutral specification for exchanging semantic models across analytics, BI, and AI platforms. Starting in `dbt-core` 1.12, dbt writes an Apache Ossie document (`target/osi_document.json`, spec version `0.1.1`) automatically during `dbt parse` and `dbt build`, and Snowflake's built-in `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_OSSIE_YAML` stored procedure turns that document directly into a native Snowflake Semantic View with no external converter package required.

### What It Looks Like in Practice

Suppose you ask for the top five product brands in the `BUILDING` market segment by total revenue, revenue per item, and distinct products sold. In this guide, you build a star schema over the `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` dataset in dbt (`fct_order_items`, `dim_customers`, and `dim_products`), declare four metrics in `models/marts/_semantic_models.yml`, and run `dbt build` so dbt both materializes the tables in Snowflake and writes `target/osi_document.json`. You then run a single dbt macro (`publish_semantic_view`) that uploads `target/osi_document.json` to a temporary Snowflake stage and calls `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_OSSIE_YAML` to publish `ANALYTICS.DEMO.SV_ORDERS`. Querying `SV_ORDERS` with `AGG(total_revenue)` and `AGG(products_sold)` returns `Brand#52` at the top with `165,202,705.9201` in total revenue and `3,458` products sold, matching the underlying tables without duplicating a single metric definition.

```text
SNOWFLAKE_SAMPLE_DATA.TPCH_SF1
        |  dbt build
        v
<db>.<schema>: fct_order_items, dim_customers, dim_products
        |  dbt parse
        v
target/osi_document.json            (Ossie spec 0.1.1, written by dbt-core)
        |  dbt run-operation publish_semantic_view
        v
SYSTEM$CREATE_SEMANTIC_VIEW_FROM_OSSIE_YAML  -->  semantic view  -->  plain SQL
```

With the end-to-end flow in place, here is what you will learn along the way.

### What You'll Learn

- How to structure a dbt star schema (`fct_order_items`, `dim_customers`, `dim_products`) and MetricFlow daily time spine over `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1`
- How to define primary and foreign entities, time and categorical dimensions, measures, and simple and ratio metrics in the dbt semantic layer
- How `dbt-core` 1.12 automatically emits an Apache Ossie `0.1.1` document (`target/osi_document.json`) without an external converter package
- How to publish `target/osi_document.json` into Snowflake as a native Semantic View using a dbt macro and `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_OSSIE_YAML`
- How to query the published Semantic View in Snowflake SQL using `AGG()` and avoid common modeling pitfalls across dbt and Snowflake

Those learning goals map directly to the objects you will create in your environment.

### What You'll Build

By the end of this guide, you will have a working `quickstart-dbt-snowflake-ossie` dbt project and the following Snowflake objects in `ANALYTICS.DEMO`:

| Path or Object | Role in the Pipeline |
|---|---|
| `models/staging/` | Four staging views (`stg_orders`, `stg_lineitem`, `stg_customers`, `stg_products`) over five TPC-H tables (`ORDERS`, `LINEITEM`, `CUSTOMER`, `NATION`, `PART`), trimmed to orders from 1998 onward. |
| `models/marts/` | Three star-schema tables (`fct_order_items`, `dim_customers`, `dim_products`) plus the daily `metricflow_time_spine` table required by MetricFlow. |
| `models/marts/_semantic_models.yml` | Three semantic models (`order_items`, `customers`, `products`) and four metrics (`total_revenue`, `item_count`, `revenue_per_item`, `products_sold`). |
| `macros/publish_semantic_view.sql` | A dbt macro that uploads `target/osi_document.json` to a temporary stage, sets the target view name, and calls `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_OSSIE_YAML`. |
| `ANALYTICS.DEMO.SV_ORDERS` | The published Snowflake Semantic View, ready to query with standard Snowflake SQL (`AGG()`). |

Before you start building, verify that your local machine and Snowflake account meet the prerequisites below.

### What You'll Need

- Access to a [Snowflake account](https://signup.snowflake.com/?utm_source=snowflake-devrel&utm_medium=developer-guides&utm_cta=developer-guides)
- A Snowflake role that can read `SNOWFLAKE_SAMPLE_DATA`, use a warehouse, and create tables, views, stages, and semantic views in a target schema (`CREATE SEMANTIC VIEW` on the schema, `SELECT` on each source table, and `OWNERSHIP` of an existing semantic view with the same name when replacing it)
- Python 3.12 installed locally (tested with `uv`; standard `venv` also works)
- Only two Python packages: `dbt-core==1.12.6` and `dbt-snowflake==1.12.5` (MetricFlow `0.213.0` is installed automatically; no separate Ossie package or converter is needed)

Once you have those prerequisites ready, you can set up the target schema in Snowflake and scaffold the local dbt project.

## Setup

This section prepares the target database and schema in Snowflake, gives you a single copy-pastable script to create all project files at once, and configures your Python 3.12 virtual environment.

### Create Target Database and Schema

To create the target database and schema in Snowflake, open a SQL worksheet in Snowsight and run the following DDL statements:

```sql
CREATE DATABASE IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS analytics.demo;
```

**Check:** Verify that `ANALYTICS.DEMO` appears in your Snowsight object explorer.

With the Snowflake schema ready, you can now create the local project files.

### Scaffold the Project Files in One Step

Every file in `quickstart-dbt-snowflake-ossie` is shown individually in the sections that follow so you can see how each layer works. To create the entire project directory and all 14 files in one step first, open your terminal and paste the following shell block:

```bash
mkdir -p quickstart-dbt-snowflake-ossie/macros \
         quickstart-dbt-snowflake-ossie/models/staging \
         quickstart-dbt-snowflake-ossie/models/marts
cd quickstart-dbt-snowflake-ossie

cat << 'EOF' > requirements.txt
# Minimal set for dbt -> Ossie -> Snowflake semantic views (tested Oct. 16, 2026).
# dbt-core writes target/osi_document.json during parse; dbt-snowflake is the adapter
# that parse requires for a snowflake profile, and it builds the tables and runs the publish macro.
# No Apache Ossie package or converter is needed on this path.
dbt-core==1.12.6
dbt-snowflake==1.12.5
EOF

cat << 'EOF' > dbt_project.yml
name: dbt_ossie_demo
version: "1.0.0"
config-version: 2

profile: dbt_ossie_demo

model-paths: ["models"]
target-path: "target"
clean-targets: ["target", "dbt_packages"]

models:
  dbt_ossie_demo:
    staging:
      +materialized: view
    marts:
      +materialized: table
EOF

cat << 'EOF' > profiles.yml
dbt_ossie_demo:
  target: dev
  outputs:
    dev:
      type: snowflake
      account: "{{ env_var('SNOWFLAKE_ACCOUNT') }}"
      user: "{{ env_var('SNOWFLAKE_USER') }}"
      # Browser SSO by default. Set SNOWFLAKE_AUTHENTICATOR to another value
      # (for example oauth_authorization_code) if your account requires it.
      authenticator: "{{ env_var('SNOWFLAKE_AUTHENTICATOR', 'externalbrowser') }}"
      role: "{{ env_var('SNOWFLAKE_ROLE') }}"
      warehouse: "{{ env_var('SNOWFLAKE_WAREHOUSE') }}"
      database: "{{ env_var('SNOWFLAKE_DATABASE', 'ANALYTICS') }}"
      schema: "{{ env_var('SNOWFLAKE_SCHEMA', 'DEMO') }}"
      threads: 8
      client_session_keep_alive: false
EOF

cat << 'EOF' > models/staging/_sources.yml
version: 2

sources:
  - name: tpch
    database: SNOWFLAKE_SAMPLE_DATA
    schema: TPCH_SF1
    tables:
      - name: orders
      - name: lineitem
      - name: customer
      - name: part
      - name: nation
EOF

cat << 'EOF' > models/staging/stg_orders.sql
-- Order headers, trimmed to a recent slice so the demo stays small.
select
    o_orderkey      as order_key,
    o_custkey       as customer_key,
    o_orderdate     as order_date,
    o_orderstatus   as order_status,
    o_totalprice    as order_total_price
from {{ source('tpch', 'orders') }}
where o_orderdate >= date '1998-01-01'
EOF

cat << 'EOF' > models/staging/stg_lineitem.sql
-- Line items are the grain of the fact table: one row per item per order.
select
    l_orderkey      as order_key,
    l_linenumber    as line_number,
    l_partkey       as part_key,
    l_quantity      as quantity,
    l_extendedprice as extended_price,
    l_discount      as discount
from {{ source('tpch', 'lineitem') }}
EOF

cat << 'EOF' > models/staging/stg_customers.sql
select
    c.c_custkey     as customer_key,
    c.c_name        as customer_name,
    c.c_mktsegment  as market_segment,
    n.n_name        as nation
from {{ source('tpch', 'customer') }} c
left join {{ source('tpch', 'nation') }} n
    on c.c_nationkey = n.n_nationkey
EOF

cat << 'EOF' > models/staging/stg_products.sql
select
    p_partkey   as part_key,
    p_name      as product_name,
    p_brand     as brand,
    p_mfgr      as manufacturer,
    p_type      as product_type
from {{ source('tpch', 'part') }}
EOF

cat << 'EOF' > models/marts/fct_order_items.sql
-- Fact table at order-item grain. Surrogate key is order_key + line_number,
-- which MetricFlow needs as a single primary entity column.
select
    o.order_key || '-' || l.line_number             as order_item_key,
    o.order_key,
    o.customer_key,
    l.part_key,
    o.order_date,
    o.order_status,
    l.quantity,
    l.extended_price,
    l.discount,
    l.extended_price * (1 - l.discount)             as net_revenue,
    l.extended_price * l.discount                   as discount_amount
from {{ ref('stg_orders') }} o
join {{ ref('stg_lineitem') }} l
    on o.order_key = l.order_key
EOF

cat << 'EOF' > models/marts/dim_customers.sql
select
    customer_key,
    customer_name,
    market_segment,
    nation
from {{ ref('stg_customers') }}
EOF

cat << 'EOF' > models/marts/dim_products.sql
select
    part_key,
    product_name,
    brand,
    manufacturer,
    product_type
from {{ ref('stg_products') }}
EOF

cat << 'EOF' > models/marts/metricflow_time_spine.sql
-- MetricFlow requires a daily time spine to resolve time-based and
-- cumulative metrics. Generated with Snowflake's GENERATOR.
with days as (
    select
        dateadd(day, seq4(), date '1990-01-01') as date_day
    from table(generator(rowcount => 20000))
)
select date_day
from days
where date_day < date '2045-01-01'
EOF

cat << 'EOF' > models/marts/_models.yml
version: 2

models:
  - name: metricflow_time_spine
    description: Daily time spine required by the dbt semantic layer.
    time_spine:
      standard_granularity_column: date_day
    columns:
      - name: date_day
        granularity: day
EOF

cat << 'EOF' > models/marts/_semantic_models.yml
semantic_models:
  - name: order_items
    model: ref('fct_order_items')
    defaults:
      agg_time_dimension: order_date
    entities:
      - name: order_item_key
        type: primary
      - name: customer_key
        type: foreign
      - name: part_key
        type: foreign
    dimensions:
      - name: order_date
        type: time
        type_params:
          time_granularity: day
    measures:
      - name: net_revenue
        agg: sum
      - name: line_count
        agg: count
        expr: order_item_key
      - name: distinct_parts
        agg: count_distinct
        expr: part_key

  - name: customers
    model: ref('dim_customers')
    entities:
      - name: customer_key
        type: primary
    dimensions:
      - name: market_segment
        type: categorical

  - name: products
    model: ref('dim_products')
    entities:
      - name: part_key
        type: primary
    dimensions:
      - name: brand
        type: categorical

metrics:
  - name: total_revenue
    type: simple
    type_params:
      measure: net_revenue
  - name: item_count
    type: simple
    type_params:
      measure: line_count
  - name: revenue_per_item
    type: ratio
    type_params:
      numerator: total_revenue
      denominator: item_count
  - name: products_sold
    type: simple
    type_params:
      measure: distinct_parts
EOF

cat << 'EOF' > macros/publish_semantic_view.sql
{#-
  Publish dbt's Ossie document (target/osi_document.json) as a Snowflake semantic view
  named view_name. Run after `dbt parse` or `dbt build`:
    dbt run-operation publish_semantic_view --args '{view_name: sv_orders}'
-#}
{% macro publish_semantic_view(view_name, doc_path='target/osi_document.json') %}
{% if execute %}
  {%- set schema = target.database ~ '.' ~ target.schema -%}
  {%- set stage = schema ~ '.ossie_publish' -%}
  {% do run_query("create temporary stage if not exists " ~ stage ~ " file_format = (type = json)") %}
  {% do run_query("put 'file://" ~ doc_path ~ "' @" ~ stage ~ " auto_compress = false overwrite = true") %}
  {% set publish %}
    execute immediate $$
    declare
      doc varchar;
    begin
      select to_json(object_insert($1, 'semantic_model',
               array_construct(object_insert($1:semantic_model[0], 'name', '{{ view_name }}', true)), true))
        into :doc
        from @{{ stage }}/osi_document.json;
      call system$create_semantic_view_from_ossie_yaml('{{ schema }}', :doc);
      return 'published {{ schema }}.{{ view_name }}';
    end;
    $$
  {% endset %}
  {% set result = run_query(publish) %}
  {{ log(result.columns[0].values()[0], info=true) }}
{% endif %}
{% endmacro %}
EOF
```

With the files on disk, the next step is to install the Python packages and set your Snowflake connection variables.

### Configure Python and Environment Variables

The project configuration lives in `requirements.txt`, `dbt_project.yml`, and `profiles.yml`. Notice that `dbt_project.yml` materializes `staging` models as views and `marts` models as tables, while `profiles.yml` reads every Snowflake setting from environment variables.

To create the Python 3.12 virtual environment, install `dbt-core` and `dbt-snowflake`, and export your Snowflake connection settings, run the following commands inside `quickstart-dbt-snowflake-ossie`:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv -r requirements.txt
source .venv/bin/activate

export SNOWFLAKE_ACCOUNT=<org-account>
export SNOWFLAKE_USER=<user>
export SNOWFLAKE_ROLE=<role>
export SNOWFLAKE_WAREHOUSE=<warehouse>
export SNOWFLAKE_DATABASE=ANALYTICS      # default
export SNOWFLAKE_SCHEMA=DEMO             # default
# export SNOWFLAKE_AUTHENTICATOR=...     # defaults to externalbrowser
```

If you prefer standard `venv` instead of `uv`, run `python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.

**Check:** Run `dbt --version` and confirm that `dbt-core` `1.12.6` and `dbt-snowflake` `1.12.5` are active.

Now that the environment is configured, let's examine how the staging layer prepares the raw TPC-H tables.

## Build Staging Models

The staging layer in `models/staging/` points to `SNOWFLAKE_SAMPLE_DATA.TPCH_SF1` and exposes clean column names across four views.

### Define the TPC-H Source

`models/staging/_sources.yml` registers the five shared TPC-H tables (`orders`, `lineitem`, `customer`, `part`, and `nation`):

```yaml
version: 2

sources:
  - name: tpch
    database: SNOWFLAKE_SAMPLE_DATA
    schema: TPCH_SF1
    tables:
      - name: orders
      - name: lineitem
      - name: customer
      - name: part
      - name: nation
```

With the source tables declared, four SQL models clean and rename their columns.

### Review the Staging Views

`models/staging/stg_orders.sql` trims orders to `1998-01-01` onward so the demo builds quickly:

```sql
-- Order headers, trimmed to a recent slice so the demo stays small.
select
    o_orderkey      as order_key,
    o_custkey       as customer_key,
    o_orderdate     as order_date,
    o_orderstatus   as order_status,
    o_totalprice    as order_total_price
from {{ source('tpch', 'orders') }}
where o_orderdate >= date '1998-01-01'
```

`models/staging/stg_lineitem.sql` exposes one row per line item per order, which forms the grain of the fact table:

```sql
-- Line items are the grain of the fact table: one row per item per order.
select
    l_orderkey      as order_key,
    l_linenumber    as line_number,
    l_partkey       as part_key,
    l_quantity      as quantity,
    l_extendedprice as extended_price,
    l_discount      as discount
from {{ source('tpch', 'lineitem') }}
```

`models/staging/stg_customers.sql` joins `customer` with `nation` so customer attributes include both `market_segment` and `nation`:

```sql
select
    c.c_custkey     as customer_key,
    c.c_name        as customer_name,
    c.c_mktsegment  as market_segment,
    n.n_name        as nation
from {{ source('tpch', 'customer') }} c
left join {{ source('tpch', 'nation') }} n
    on c.c_nationkey = n.n_nationkey
```

`models/staging/stg_products.sql` selects the product key, name, brand, manufacturer, and product type from `part`:

```sql
select
    p_partkey   as part_key,
    p_name      as product_name,
    p_brand     as brand,
    p_mfgr      as manufacturer,
    p_type      as product_type
from {{ source('tpch', 'part') }}
```

Those four staging views feed the star schema tables in `models/marts/`.

## Build Star Schema

The marts layer turns the staging views into a fact table at the order-item grain, two dimension tables, and a daily time spine table for MetricFlow.

### Create the Fact and Dimension Tables

`models/marts/fct_order_items.sql` joins `stg_orders` and `stg_lineitem`, constructs a single-column surrogate key `order_item_key` (`o.order_key || '-' || l.line_number`) required by MetricFlow as the primary entity column, and computes `net_revenue` and `discount_amount`:

```sql
-- Fact table at order-item grain. Surrogate key is order_key + line_number,
-- which MetricFlow needs as a single primary entity column.
select
    o.order_key || '-' || l.line_number             as order_item_key,
    o.order_key,
    o.customer_key,
    l.part_key,
    o.order_date,
    o.order_status,
    l.quantity,
    l.extended_price,
    l.discount,
    l.extended_price * (1 - l.discount)             as net_revenue,
    l.extended_price * l.discount                   as discount_amount
from {{ ref('stg_orders') }} o
join {{ ref('stg_lineitem') }} l
    on o.order_key = l.order_key
```

`models/marts/dim_customers.sql` and `models/marts/dim_products.sql` materialize the customer and product dimensions as tables:

```sql
select
    customer_key,
    customer_name,
    market_segment,
    nation
from {{ ref('stg_customers') }}
```

```sql
select
    part_key,
    product_name,
    brand,
    manufacturer,
    product_type
from {{ ref('stg_products') }}
```

In addition to the fact and dimension tables, MetricFlow requires a daily time spine table to validate the semantic layer.

### Add the MetricFlow Time Spine

`models/marts/metricflow_time_spine.sql` uses Snowflake's `GENERATOR` table function to generate one row per day from `1990-01-01` through `2044-12-31`:

```sql
-- MetricFlow requires a daily time spine to resolve time-based and
-- cumulative metrics. Generated with Snowflake's GENERATOR.
with days as (
    select
        dateadd(day, seq4(), date '1990-01-01') as date_day
    from table(generator(rowcount => 20000))
)
select date_day
from days
where date_day < date '2045-01-01'
```

`models/marts/_models.yml` registers `date_day` as the daily `time_spine` column for the dbt semantic layer:

```yaml
version: 2

models:
  - name: metricflow_time_spine
    description: Daily time spine required by the dbt semantic layer.
    time_spine:
      standard_granularity_column: date_day
    columns:
      - name: date_day
        granularity: day
```

With the star schema and time spine in place, you can define the semantic models and metrics on top of them.

## Define Semantic Layer

The semantic layer definition in `models/marts/_semantic_models.yml` maps the three mart tables to semantic models and defines four metrics. Running `dbt build` then materializes the warehouse objects and writes `target/osi_document.json`.

### Review the Semantic Models and Metrics

`models/marts/_semantic_models.yml` defines three semantic models (`order_items`, `customers`, and `products`) and four metrics (`total_revenue`, `item_count`, `revenue_per_item`, and `products_sold`). Notice that each entity is named after its key column (`order_item_key`, `customer_key`, `part_key`) so that relationships and the `COUNT` measure resolve cleanly when imported into Snowflake:

```yaml
semantic_models:
  - name: order_items
    model: ref('fct_order_items')
    defaults:
      agg_time_dimension: order_date
    entities:
      - name: order_item_key
        type: primary
      - name: customer_key
        type: foreign
      - name: part_key
        type: foreign
    dimensions:
      - name: order_date
        type: time
        type_params:
          time_granularity: day
    measures:
      - name: net_revenue
        agg: sum
      - name: line_count
        agg: count
        expr: order_item_key
      - name: distinct_parts
        agg: count_distinct
        expr: part_key

  - name: customers
    model: ref('dim_customers')
    entities:
      - name: customer_key
        type: primary
    dimensions:
      - name: market_segment
        type: categorical

  - name: products
    model: ref('dim_products')
    entities:
      - name: part_key
        type: primary
    dimensions:
      - name: brand
        type: categorical

metrics:
  - name: total_revenue
    type: simple
    type_params:
      measure: net_revenue
  - name: item_count
    type: simple
    type_params:
      measure: line_count
  - name: revenue_per_item
    type: ratio
    type_params:
      numerator: total_revenue
      denominator: item_count
  - name: products_sold
    type: simple
    type_params:
      measure: distinct_parts
```

With the semantic models and metrics defined, you are ready to build the dbt project and generate the Apache Ossie document.

### Build the Models and Generate the Ossie Document

To materialize the staging views and mart tables in Snowflake and emit `target/osi_document.json`, run `dbt build` from the `quickstart-dbt-snowflake-ossie` directory:

```bash
dbt build --profiles-dir .
```

**Check:** Confirm that `dbt build` completes without errors, that `FCT_ORDER_ITEMS`, `DIM_CUSTOMERS`, `DIM_PRODUCTS`, and `METRICFLOW_TIME_SPINE` exist in `ANALYTICS.DEMO`, and that `target/osi_document.json` has been written locally.

Now that `target/osi_document.json` exists on disk, the next step publishes it as a Snowflake Semantic View.

## Publish Semantic View

Publishing the Apache Ossie document to Snowflake is handled by a dbt macro in `macros/publish_semantic_view.sql` that stages `target/osi_document.json`, sets the target semantic view name, and calls `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_OSSIE_YAML`.

### Review the Publish Macro

When dbt writes `target/osi_document.json`, it always sets `semantic_model[0].name` to `"semantic_model"`. The `publish_semantic_view` macro in `macros/publish_semantic_view.sql` uploads `target/osi_document.json` to a temporary JSON stage (`ANALYTICS.DEMO.OSSIE_PUBLISH`), uses `OBJECT_INSERT` to replace `semantic_model[0].name` with your chosen `view_name`, and passes the JSON document to `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_OSSIE_YAML`:

```sql
{#-
  Publish dbt's Ossie document (target/osi_document.json) as a Snowflake semantic view
  named view_name. Run after `dbt parse` or `dbt build`:
    dbt run-operation publish_semantic_view --args '{view_name: sv_orders}'
-#}
{% macro publish_semantic_view(view_name, doc_path='target/osi_document.json') %}
{% if execute %}
  {%- set schema = target.database ~ '.' ~ target.schema -%}
  {%- set stage = schema ~ '.ossie_publish' -%}
  {% do run_query("create temporary stage if not exists " ~ stage ~ " file_format = (type = json)") %}
  {% do run_query("put 'file://" ~ doc_path ~ "' @" ~ stage ~ " auto_compress = false overwrite = true") %}
  {% set publish %}
    execute immediate $$
    declare
      doc varchar;
    begin
      select to_json(object_insert($1, 'semantic_model',
               array_construct(object_insert($1:semantic_model[0], 'name', '{{ view_name }}', true)), true))
        into :doc
        from @{{ stage }}/osi_document.json;
      call system$create_semantic_view_from_ossie_yaml('{{ schema }}', :doc);
      return 'published {{ schema }}.{{ view_name }}';
    end;
    $$
  {% endset %}
  {% set result = run_query(publish) %}
  {{ log(result.columns[0].values()[0], info=true) }}
{% endif %}
{% endmacro %}
```

With the macro in place, you can publish the semantic view with a single `dbt run-operation` command.

### Run the Publish Operation

To publish `target/osi_document.json` as `ANALYTICS.DEMO.SV_ORDERS`, run the following command in your terminal:

```bash
dbt run-operation publish_semantic_view --profiles-dir . --args '{view_name: sv_orders}'
```

You can run this operation again any time after `dbt parse` or `dbt build` and it replaces `ANALYTICS.DEMO.SV_ORDERS` in place.

**Check:** Confirm that the command logs `published ANALYTICS.DEMO.sv_orders`.

That completes the core build and publish workflow. Next, you query the published Semantic View in Snowflake SQL and review key modeling guidelines.

## Query Semantic View

Once `ANALYTICS.DEMO.SV_ORDERS` is published, you can query its dimensions and metrics directly in Snowflake SQL using the `AGG()` function.

### Run a Semantic View Query

To query `total_revenue`, `revenue_per_item`, and `products_sold` by `brand` for customers in the `BUILDING` market segment, run the following query in a Snowsight SQL worksheet:

```sql
SELECT brand,
       AGG(total_revenue)    AS total_revenue,
       AGG(revenue_per_item) AS revenue_per_item,
       AGG(products_sold)    AS products_sold
  FROM analytics.demo.sv_orders
 WHERE market_segment = 'BUILDING'
 GROUP BY brand
 ORDER BY total_revenue DESC
 LIMIT 5;
```

**Check:** Confirm that the top row is `Brand#52` with `total_revenue` of `165,202,705.9201` and `products_sold` of `3,458`. These numbers match the same query written directly against `fct_order_items`, `dim_customers`, and `dim_products`.

When you adapt this pattern to your own dbt semantic models, keep the following guidelines in mind.

### Modeling Guidelines Worth Knowing

- **Spec version:** Snowflake's loader accepts Ossie spec `0.1.1`, which is what `dbt-core` 1.12 writes. External converters on `apache/ossie` `main` emit a newer development version that Snowflake rejects, which is why this workflow uses `dbt-core` directly.
- **View name:** dbt always names the exported model `semantic_model` and provides no setting to override it, so `publish_semantic_view` rewrites `semantic_model[0].name` before calling `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_OSSIE_YAML`. Without that rewrite, every publish lands on a view named `SEMANTIC_MODEL`.
- **Entity names:** Name each entity after its key column (`order_item_key`, `customer_key`, `part_key`). That keeps table relationships and `COUNT` metrics resolvable on the Snowflake side.
- **Filtered metrics across tables:** A dbt metric filter referencing a joined dimension such as `{{ Dimension('part_key__product_type') }}` is written into `target/osi_document.json` as the literal column `part_key__product_type`, causing the Snowflake load to fail with an invalid identifier error. Keep metric filters on the fact table, or author cross-table filtered metrics in the Snowflake Semantic View directly.
- **Windowed metrics:** dbt flattens cumulative metrics to a plain `SUM` in `target/osi_document.json`, and the Snowflake Ossie loader does not accept window specifications. Define rolling windows in the Snowflake Semantic View directly.
- **Privileges for the load:** Your role needs `CREATE SEMANTIC VIEW` on the target schema, `SELECT` on each source table, and `OWNERSHIP` of any existing semantic view with the same name to replace it.

When you finish testing the semantic view, you can remove the demo objects from your Snowflake account.

## Clean Up

To remove the semantic view and demo schema created in this guide, run the following SQL statements in Snowsight:

```sql
DROP SEMANTIC VIEW IF EXISTS analytics.demo.sv_orders;
DROP SCHEMA IF EXISTS analytics.demo;
```

With the demo resources cleaned up, let's recap what you accomplished and where to go next.

## Conclusion And Resources

Congratulations! You've successfully built a star schema in dbt over TPC-H data, generated an Apache Ossie `0.1.1` semantic document with `dbt build`, and published your dbt semantic layer metrics as a native Snowflake Semantic View using `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_OSSIE_YAML`.

### What You Learned

- How `dbt-core` 1.12 natively writes `target/osi_document.json` (Apache Ossie spec `0.1.1`) during `dbt parse` and `dbt build` without extra converter packages
- How to model primary and foreign entities, dimensions, measures, and simple and ratio metrics in `models/marts/_semantic_models.yml` so they map cleanly to Snowflake
- How to stage `target/osi_document.json`, override the semantic model name, and publish a Snowflake Semantic View in place with `SYSTEM$CREATE_SEMANTIC_VIEW_FROM_OSSIE_YAML`
- How to query a Snowflake Semantic View with `AGG()` and work within the current Ossie `0.1.1` loader guidelines

### Related Resources

- [Apache Ossie Repository](https://github.com/apache/ossie)
- [Overview of Snowflake Semantic Views](https://docs.snowflake.com/en/user-guide/views-semantic/overview)
- [dbt Semantic Layer Documentation](https://docs.getdbt.com/docs/use-dbt-semantic-layer/dbt-sl)
