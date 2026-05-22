-- DietSearch PostgreSQL Schema
-- Run: psql -U dietsearch -d dietsearch -f db/schema.sql

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(64) UNIQUE NOT NULL,
    password_hash   VARCHAR(256) NOT NULL,
    email           VARCHAR(128) UNIQUE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    last_login_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS diet_profiles (
    user_id         INT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    diet_labels     TEXT[]  DEFAULT '{}',
    allergens       TEXT[]  DEFAULT '{}',
    calorie_goal    INT,
    protein_goal_g  FLOAT,
    fat_goal_g      FLOAT,
    carb_goal_g     FLOAT,
    price_pref      SMALLINT,
    cuisine_prefs   TEXT[]  DEFAULT '{}',
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS food_log_entries (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    log_date        DATE NOT NULL,
    meal_type       VARCHAR(16) NOT NULL CHECK (meal_type IN ('breakfast','lunch','dinner','snack')),
    food_id         INT NOT NULL,
    food_name       VARCHAR(128) NOT NULL,
    quantity_g      FLOAT NOT NULL CHECK (quantity_g > 0),
    calories_kcal   FLOAT NOT NULL,
    protein_g       FLOAT,
    fat_g           FLOAT,
    carb_g          FLOAT,
    created_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_food_log_user_date ON food_log_entries (user_id, log_date);

CREATE TABLE IF NOT EXISTS saved_restaurants (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    restaurant_id   VARCHAR(64) NOT NULL,
    restaurant_name VARCHAR(256) NOT NULL,
    saved_at        TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_id, restaurant_id)
);

CREATE TABLE IF NOT EXISTS search_feedbacks (
    id              SERIAL PRIMARY KEY,
    user_id         INT REFERENCES users(id),
    query_text      TEXT NOT NULL,
    restaurant_id   VARCHAR(64) NOT NULL,
    restaurant_name VARCHAR(256),
    rank_position   SMALLINT,
    is_relevant     BOOLEAN NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);
