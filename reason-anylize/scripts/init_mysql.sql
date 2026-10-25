-- ============================================================
-- 经营归因分析系统 · MySQL 初始化脚本
-- 10 张系统表(需求文档第 7 节)+ 9 张演示业务表(第 12 节)
-- 字符集 utf8mb4 / InnoDB;与 backend/app/models.py 保持一致(scripts/check_schema.py 可校验)
-- 用法: mysql -u root -p < init_mysql.sql (需先 CREATE DATABASE reason_analyze;)
-- ============================================================

USE reason_analyze;

-- ---------------- 系统表 ----------------

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    external_user_id VARCHAR(128) NOT NULL UNIQUE,
    username VARCHAR(64) NOT NULL UNIQUE,
    display_name VARCHAR(128) NOT NULL DEFAULT '',
    role VARCHAR(32) NOT NULL DEFAULT 'analyst',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    title VARCHAR(256) NOT NULL DEFAULT '新会话',
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    last_message_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX ix_conversations_user (user_id),
    INDEX ix_conversations_status (status),
    CONSTRAINT fk_conversations_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    role VARCHAR(32) NOT NULL,
    message_type VARCHAR(32) NOT NULL DEFAULT 'text',
    content TEXT NOT NULL,
    tool_name VARCHAR(64) NULL,
    tool_status VARCHAR(32) NULL,
    seq_no INT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_messages_conv_seq (conversation_id, seq_no),
    CONSTRAINT fk_messages_conv FOREIGN KEY (conversation_id) REFERENCES conversations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS attachments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    message_id INT NULL,
    file_name VARCHAR(256) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    file_type VARCHAR(64) NOT NULL DEFAULT '',
    file_size INT NOT NULL DEFAULT 0,
    parse_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_attachments_conv (conversation_id),
    CONSTRAINT fk_attachments_conv FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    CONSTRAINT fk_attachments_msg FOREIGN KEY (message_id) REFERENCES messages(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS analysis_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    user_id INT NOT NULL,
    input_text TEXT NOT NULL,
    task_status VARCHAR(32) NOT NULL DEFAULT 'queued',
    current_step VARCHAR(128) NOT NULL DEFAULT 'pending',
    started_at DATETIME NULL,
    finished_at DATETIME NULL,
    error_message TEXT NULL,
    INDEX ix_tasks_conv (conversation_id),
    CONSTRAINT fk_tasks_conv FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    CONSTRAINT fk_tasks_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS analysis_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    conversation_id INT NOT NULL,
    problem_definition TEXT NOT NULL,
    key_metrics_json TEXT NOT NULL,
    evidence_list_json TEXT NOT NULL,
    conclusion_text TEXT NOT NULL,
    missing_data_text TEXT NOT NULL,
    next_action_text TEXT NOT NULL,
    result_markdown TEXT NOT NULL,
    result_file_path VARCHAR(512) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_results_task (task_id),
    INDEX ix_results_conv (conversation_id),
    CONSTRAINT fk_results_task FOREIGN KEY (task_id) REFERENCES analysis_tasks(id),
    CONSTRAINT fk_results_conv FOREIGN KEY (conversation_id) REFERENCES conversations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS context_summaries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    start_seq_no INT NOT NULL,
    end_seq_no INT NOT NULL,
    summary_text TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_summaries_conv (conversation_id),
    CONSTRAINT fk_summaries_conv FOREIGN KEY (conversation_id) REFERENCES conversations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS websocket_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    conversation_id INT NULL,
    token VARCHAR(128) NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,
    consumed_at DATETIME NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_ws_tokens_token (token),
    CONSTRAINT fk_ws_tokens_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_ws_tokens_conv FOREIGN KEY (conversation_id) REFERENCES conversations(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS system_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(128) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    config_group VARCHAR(64) NOT NULL DEFAULT 'misc',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS task_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NULL,
    log_level VARCHAR(16) NOT NULL DEFAULT 'info',
    log_type VARCHAR(32) NOT NULL DEFAULT 'task',
    log_content TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX ix_task_logs_task (task_id),
    CONSTRAINT fk_task_logs_task FOREIGN KEY (task_id) REFERENCES analysis_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------- 演示业务表: 场景一 商品目录优化 ----------------

CREATE TABLE IF NOT EXISTS scn1_categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    category_id INT NOT NULL UNIQUE,
    category_name VARCHAR(128) NOT NULL,
    parent_id INT NULL,
    level INT NOT NULL,
    sort_order INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scn1_products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL UNIQUE,
    sku_code VARCHAR(64) NOT NULL,
    product_name VARCHAR(256) NOT NULL,
    category_id INT NOT NULL,
    price DOUBLE NOT NULL,
    cost_price DOUBLE NOT NULL,
    brand VARCHAR(64) NOT NULL DEFAULT '',
    shelf_status VARCHAR(32) NOT NULL DEFAULT 'on',
    on_shelf_date DATE NULL,
    INDEX ix_scn1_products_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scn1_search_exposures (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stat_date DATE NOT NULL,
    product_id INT NOT NULL,
    search_keyword VARCHAR(128) NOT NULL DEFAULT '',
    exposure_cnt INT NOT NULL DEFAULT 0,
    exposure_uv INT NOT NULL DEFAULT 0,
    INDEX ix_scn1_expo_date_product (stat_date, product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scn1_clicks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stat_date DATE NOT NULL,
    product_id INT NOT NULL,
    search_keyword VARCHAR(128) NOT NULL DEFAULT '',
    click_cnt INT NOT NULL DEFAULT 0,
    click_uv INT NOT NULL DEFAULT 0,
    INDEX ix_scn1_click_date_product (stat_date, product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scn1_conversions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    stat_date DATE NOT NULL,
    product_id INT NOT NULL,
    order_cnt INT NOT NULL DEFAULT 0,
    order_uv INT NOT NULL DEFAULT 0,
    gmv DOUBLE NOT NULL DEFAULT 0,
    refund_cnt INT NOT NULL DEFAULT 0,
    INDEX ix_scn1_conv_date_product (stat_date, product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ---------------- 演示业务表: 场景二 客户行为分析 ----------------

CREATE TABLE IF NOT EXISTS scn2_customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL UNIQUE,
    city VARCHAR(64) NOT NULL DEFAULT '',
    age_band VARCHAR(32) NOT NULL DEFAULT '',
    gender VARCHAR(16) NOT NULL DEFAULT '',
    member_level VARCHAR(16) NOT NULL DEFAULT 'L1',
    register_date DATE NULL,
    channel VARCHAR(32) NOT NULL DEFAULT ''
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scn2_visit_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    event_time DATETIME NOT NULL,
    page_type VARCHAR(64) NOT NULL DEFAULT '',
    channel VARCHAR(32) NOT NULL DEFAULT '',
    device_type VARCHAR(32) NOT NULL DEFAULT '',
    session_id VARCHAR(64) NOT NULL DEFAULT '',
    INDEX ix_scn2_visit_time (event_time),
    INDEX ix_scn2_visit_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scn2_cart_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    event_time DATETIME NOT NULL,
    product_id INT NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    unit_price DOUBLE NOT NULL DEFAULT 0,
    INDEX ix_scn2_cart_time (event_time),
    INDEX ix_scn2_cart_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS scn2_order_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(64) NOT NULL UNIQUE,
    customer_id INT NOT NULL,
    order_time DATETIME NOT NULL,
    order_amount DOUBLE NOT NULL DEFAULT 0,
    order_status VARCHAR(32) NOT NULL DEFAULT 'paid',
    channel VARCHAR(32) NOT NULL DEFAULT '',
    INDEX ix_scn2_order_time (order_time),
    INDEX ix_scn2_order_customer (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
