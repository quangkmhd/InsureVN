-- ============================================================
-- InsureVN — SQLite Schema
-- Thiết kế 3 tầng: Source Lineage → Plan Normalization → Domain Tables
-- ============================================================

-- ============================================================
-- TẦNG 1: Source Lineage (truy ngược về JSON gốc)
-- ============================================================

-- Công ty bảo hiểm
CREATE TABLE IF NOT EXISTS companies (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    code     VARCHAR(50)  UNIQUE NOT NULL,
    name     VARCHAR(200) NOT NULL,
    website  VARCHAR(200),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Seed data
INSERT OR IGNORE INTO companies (code, name, website) VALUES
    ('aia',              'AIA Việt Nam',           'aia.com.vn'),
    ('pacific_cross',    'Pacific Cross Việt Nam',  'pacificcross.com.vn'),
    ('bic',              'BIC - BIDV Insurance',    'bic.vn'),
    ('liberty',          'Liberty Insurance',       'libertyinsurance.com.vn'),
    ('baominh',          'Bảo Minh',                'baominh.com.vn'),
    ('pti',              'PTI Insurance',           'pti.com.vn');

-- Mỗi file PDF gốc = 1 document
CREATE TABLE IF NOT EXISTS documents (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id     INT          NOT NULL REFERENCES companies(id),
    source_path    VARCHAR(500) UNIQUE NOT NULL,
    document_name  VARCHAR(300),
    document_type  VARCHAR(50),
    language       VARCHAR(10)  DEFAULT 'vi',
    description    TEXT,
    effective_date TEXT,
    version        VARCHAR(50),
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_company ON documents(company_id);
CREATE INDEX IF NOT EXISTS idx_documents_type    ON documents(document_type);

-- Mỗi file JSON trích xuất = 1 source_table
CREATE TABLE IF NOT EXISTS source_tables (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id       INT          NOT NULL REFERENCES documents(id),
    file_path         VARCHAR(500) UNIQUE NOT NULL,
    table_type        VARCHAR(50),
    classification_reason TEXT,
    classification_confidence VARCHAR(10) DEFAULT 'rule',
    page_number       INT,
    table_index       INT,
    raw_json          TEXT         NOT NULL,
    keys              TEXT, -- JSON string array
    content_type      VARCHAR(20),
    processed         BOOLEAN DEFAULT 0,
    error_reason      TEXT,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_st_document   ON source_tables(document_id);
CREATE INDEX IF NOT EXISTS idx_st_type       ON source_tables(table_type);
CREATE INDEX IF NOT EXISTS idx_st_processed  ON source_tables(processed);


-- ============================================================
-- TẦNG 2: Plan Normalization
-- ============================================================

CREATE TABLE IF NOT EXISTS plan_types (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INT REFERENCES companies(id),
    document_id     INT REFERENCES documents(id),
    raw_name        VARCHAR(200) NOT NULL,
    normalized_code VARCHAR(50),
    plan_level      INT,
    product_line    VARCHAR(100),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, raw_name)
);

CREATE INDEX IF NOT EXISTS idx_pt_company    ON plan_types(company_id);
CREATE INDEX IF NOT EXISTS idx_pt_normalized ON plan_types(normalized_code);


-- ============================================================
-- TẦNG 3: Domain Tables
-- ============================================================

CREATE TABLE IF NOT EXISTS benefit_categories (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    code      VARCHAR(100) UNIQUE NOT NULL,
    name_vi   VARCHAR(200),
    name_en   VARCHAR(200),
    parent_id INT REFERENCES benefit_categories(id)
);

-- Seed benefit categories
INSERT OR IGNORE INTO benefit_categories (code, name_vi, name_en, parent_id) VALUES
    ('inpatient',     'Điều trị nội trú',    'Inpatient',          NULL),
    ('outpatient',    'Điều trị ngoại trú',  'Outpatient',         NULL),
    ('emergency',     'Cấp cứu',             'Emergency',          NULL),
    ('maternity',     'Thai sản',             'Maternity',          NULL),
    ('dental',        'Nha khoa',             'Dental',             NULL),
    ('cancer',        'Ung thư',              'Cancer',             NULL),
    ('mental_health', 'Sức khỏe tâm thần',   'Mental Health',      NULL),
    ('accident',      'Tai nạn cá nhân',      'Personal Accident',  NULL),
    ('life',          'Sinh mạng cá nhân',    'Personal Life',      NULL),
    ('day_treatment', 'Điều trị trong ngày',  'Day Treatment',      NULL);

CREATE TABLE IF NOT EXISTS benefit_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table_id  INT NOT NULL REFERENCES source_tables(id),
    document_id      INT NOT NULL REFERENCES documents(id),
    category_id      INT REFERENCES benefit_categories(id),
    row_index        INT,
    raw_row          TEXT,
    raw_name         VARCHAR(500) NOT NULL,
    normalized_name  VARCHAR(300),
    display_order    INT,
    applicable_to    TEXT,
    note             TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bi_document  ON benefit_items(document_id);
CREATE INDEX IF NOT EXISTS idx_bi_category  ON benefit_items(category_id);
CREATE INDEX IF NOT EXISTS idx_bi_source    ON benefit_items(source_table_id);

CREATE TABLE IF NOT EXISTS benefit_values (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    benefit_item_id INT NOT NULL REFERENCES benefit_items(id),
    plan_type_id    INT NOT NULL REFERENCES plan_types(id),
    value           TEXT,
    value_numeric   REAL,
    value_context   VARCHAR(100),
    limit_type      VARCHAR(50),
    unit            VARCHAR(100),
    is_covered      BOOLEAN,
    note            TEXT
);

CREATE INDEX IF NOT EXISTS idx_bv_item ON benefit_values(benefit_item_id);
CREATE INDEX IF NOT EXISTS idx_bv_plan ON benefit_values(plan_type_id);

CREATE TABLE IF NOT EXISTS premium_entries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table_id  INT NOT NULL REFERENCES source_tables(id),
    document_id      INT NOT NULL REFERENCES documents(id),
    plan_type_id     INT REFERENCES plan_types(id),
    row_index        INT,
    raw_row          TEXT,
    age_min          INT,
    age_max          INT,
    age_label        VARCHAR(50),
    premium_amount   REAL,
    currency         VARCHAR(10)  DEFAULT 'VND',
    period           VARCHAR(20)  DEFAULT 'annual',
    year_label       VARCHAR(20),
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pe_document ON premium_entries(document_id);
CREATE INDEX IF NOT EXISTS idx_pe_plan     ON premium_entries(plan_type_id);
CREATE INDEX IF NOT EXISTS idx_pe_age      ON premium_entries(age_min, age_max);

CREATE TABLE IF NOT EXISTS hospitals (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table_id  INT NOT NULL REFERENCES source_tables(id),
    document_id      INT NOT NULL REFERENCES documents(id),
    row_index        INT,
    raw_row          TEXT,
    name_vi          VARCHAR(300),
    name_en          VARCHAR(300),
    address          TEXT,
    city             TEXT,
    country          VARCHAR(100) DEFAULT 'VN',
    phone            VARCHAR(100),
    hospital_type    VARCHAR(100),
    gop_supported    BOOLEAN DEFAULT 0,
    gop_time         VARCHAR(100),
    working_hours    VARCHAR(200),
    external_id      VARCHAR(50),
    note             TEXT,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hosp_city     ON hospitals(city);
CREATE INDEX IF NOT EXISTS idx_hosp_document ON hospitals(document_id);
CREATE INDEX IF NOT EXISTS idx_hosp_source   ON hospitals(source_table_id);

CREATE TABLE IF NOT EXISTS glossary_terms (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table_id INT NOT NULL REFERENCES source_tables(id),
    document_id     INT NOT NULL REFERENCES documents(id),
    row_index       INT,
    raw_row         TEXT,
    term            VARCHAR(300) NOT NULL,
    definition      TEXT NOT NULL,
    language        VARCHAR(10) DEFAULT 'vi',
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gloss_term     ON glossary_terms(term);
CREATE INDEX IF NOT EXISTS idx_gloss_document ON glossary_terms(document_id);

CREATE TABLE IF NOT EXISTS waiting_periods (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table_id  INT NOT NULL REFERENCES source_tables(id),
    document_id      INT NOT NULL REFERENCES documents(id),
    row_index        INT,
    raw_row          TEXT,
    condition_group  VARCHAR(200),
    condition_detail TEXT,
    waiting_days     INT,
    waiting_text     VARCHAR(200),
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_wp_document ON waiting_periods(document_id);

CREATE TABLE IF NOT EXISTS claim_payouts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table_id INT NOT NULL REFERENCES source_tables(id),
    document_id     INT NOT NULL REFERENCES documents(id),
    row_index       INT,
    raw_row         TEXT,
    event           VARCHAR(300),
    payout_rate     REAL,
    payout_text     VARCHAR(200),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cp_document ON claim_payouts(document_id);

CREATE TABLE IF NOT EXISTS short_term_premiums (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_table_id  INT NOT NULL REFERENCES source_tables(id),
    document_id      INT NOT NULL REFERENCES documents(id),
    row_index        INT,
    raw_row          TEXT,
    duration_text    VARCHAR(200),
    duration_days    INT,
    premium_rate     REAL,
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stp_document ON short_term_premiums(document_id);

-- ============================================================
-- TẦNG 4: Synthetic Foundation (Phase 01)
-- ============================================================

CREATE TABLE IF NOT EXISTS synthetic_users (
    id             VARCHAR(50) PRIMARY KEY,
    age            INT,
    gender         VARCHAR(20),
    income         REAL,
    job            VARCHAR(100),
    city           VARCHAR(100),
    family_status  VARCHAR(100),
    health_background TEXT,
    risk_tolerance VARCHAR(50),
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS synthetic_policies (
    id              VARCHAR(50) PRIMARY KEY,
    user_id         VARCHAR(50) REFERENCES synthetic_users(id),
    company_id      INT REFERENCES companies(id),
    plan_type_id    INT REFERENCES plan_types(id),
    document_id     INT REFERENCES documents(id),
    effective_date  DATE,
    renewal_date    DATE,
    payment_status  VARCHAR(50),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS synthetic_benchmark_cases (
    case_id                 VARCHAR(50) PRIMARY KEY,
    user_id                 VARCHAR(50) REFERENCES synthetic_users(id),
    query                   TEXT NOT NULL,
    expected_intent_group   VARCHAR(50),
    expected_risk_level     VARCHAR(50),
    expected_workflow       VARCHAR(50),
    expected_evidence_types TEXT, -- JSON array
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP
);
