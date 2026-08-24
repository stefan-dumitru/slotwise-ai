CREATE DATABASE IF NOT EXISTS slotwise
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE slotwise;

-- ==========================================
-- Users
-- ==========================================
CREATE TABLE users (
    id             INT AUTO_INCREMENT PRIMARY KEY,
    full_name      VARCHAR(150) NOT NULL,
    email          VARCHAR(150) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    phone          VARCHAR(30),
    role           ENUM('customer', 'business_owner', 'admin') NOT NULL DEFAULT 'customer',
    created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ==========================================
-- Categories
-- ==========================================
CREATE TABLE categories (
    id    INT AUTO_INCREMENT PRIMARY KEY,
    name  VARCHAR(100) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- ==========================================
-- Businesses
-- ==========================================
CREATE TABLE businesses (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    owner_id     INT NOT NULL,
    category_id  INT,
    name         VARCHAR(150) NOT NULL,
    description  TEXT,
    address      VARCHAR(255),
    phone        VARCHAR(30),
    email        VARCHAR(150),
    status       ENUM('pending', 'active', 'suspended') NOT NULL DEFAULT 'active',
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_business_owner FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_business_category FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL,
    INDEX idx_business_owner (owner_id),
    INDEX idx_business_category (category_id)
) ENGINE=InnoDB;

-- ==========================================
-- Staff (always at least one per business, incl. solo owners)
-- ==========================================
CREATE TABLE staff (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    business_id  INT NOT NULL,
    user_id      INT,
    full_name    VARCHAR(150) NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_staff_business FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    CONSTRAINT fk_staff_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_staff_business (business_id)
) ENGINE=InnoDB;

-- ==========================================
-- Services
-- ==========================================
CREATE TABLE services (
    id                 INT AUTO_INCREMENT PRIMARY KEY,
    business_id        INT NOT NULL,
    name               VARCHAR(150) NOT NULL,
    description        TEXT,
    duration_minutes   SMALLINT UNSIGNED NOT NULL,
    price              DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    created_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_service_business FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    INDEX idx_service_business (business_id)
) ENGINE=InnoDB;

-- ==========================================
-- Staff <-> Services (which staff can perform which service)
-- ==========================================
CREATE TABLE staff_services (
    staff_id    INT NOT NULL,
    service_id  INT NOT NULL,
    PRIMARY KEY (staff_id, service_id),
    CONSTRAINT fk_ss_staff FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
    CONSTRAINT fk_ss_service FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ==========================================
-- Recurring weekly working hours per staff member
-- ==========================================
CREATE TABLE working_hours (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    staff_id      INT NOT NULL,
    day_of_week   TINYINT UNSIGNED NOT NULL,  -- 0 = Sunday ... 6 = Saturday
    start_time    TIME NOT NULL,
    end_time      TIME NOT NULL,
    CONSTRAINT fk_wh_staff FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
    CONSTRAINT chk_wh_day CHECK (day_of_week BETWEEN 0 AND 6),
    CONSTRAINT chk_wh_time CHECK (end_time > start_time),
    INDEX idx_wh_staff_day (staff_id, day_of_week)
) ENGINE=InnoDB;

-- ==========================================
-- One-off exceptions (day off, holiday, custom hours)
-- ==========================================
CREATE TABLE availability_exceptions (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    staff_id        INT NOT NULL,
    exception_date  DATE NOT NULL,
    is_closed       BOOLEAN NOT NULL DEFAULT TRUE,
    start_time      TIME,
    end_time        TIME,
    reason          VARCHAR(255),
    CONSTRAINT fk_ae_staff FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
    UNIQUE KEY uq_ae_staff_date (staff_id, exception_date)
) ENGINE=InnoDB;

-- ==========================================
-- Appointments
-- ==========================================
CREATE TABLE appointments (
    id                    INT AUTO_INCREMENT PRIMARY KEY,
    customer_id           INT NOT NULL,
    business_id           INT NOT NULL,
    service_id            INT NOT NULL,
    staff_id              INT NOT NULL,
    start_time            DATETIME NOT NULL,
    end_time              DATETIME NOT NULL,
    status                ENUM('pending', 'confirmed', 'cancelled', 'completed', 'no_show') NOT NULL DEFAULT 'confirmed',
    cancellation_reason   VARCHAR(255),
    created_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_appt_customer FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_appt_business FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    CONSTRAINT fk_appt_service FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
    CONSTRAINT fk_appt_staff FOREIGN KEY (staff_id) REFERENCES staff(id) ON DELETE CASCADE,
    CONSTRAINT chk_appt_time CHECK (end_time > start_time),
    INDEX idx_appt_staff_time (staff_id, start_time),
    INDEX idx_appt_customer (customer_id),
    INDEX idx_appt_business (business_id)
) ENGINE=InnoDB;

-- ==========================================
-- Reviews (one per appointment)
-- ==========================================
CREATE TABLE reviews (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    appointment_id  INT NOT NULL UNIQUE,
    customer_id     INT NOT NULL,
    business_id     INT NOT NULL,
    rating          TINYINT UNSIGNED NOT NULL,
    comment         TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_review_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
    CONSTRAINT fk_review_customer FOREIGN KEY (customer_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_review_business FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    CONSTRAINT chk_review_rating CHECK (rating BETWEEN 1 AND 5),
    INDEX idx_review_business (business_id)
) ENGINE=InnoDB;

-- ==========================================
-- Notifications
-- ==========================================
CREATE TABLE notifications (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    appointment_id  INT,
    type            ENUM('booking_confirmation', 'reminder', 'cancellation', 'reschedule', 'general') NOT NULL,
    message         VARCHAR(255) NOT NULL,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notif_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_notif_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE,
    INDEX idx_notif_user (user_id)
) ENGINE=InnoDB;
