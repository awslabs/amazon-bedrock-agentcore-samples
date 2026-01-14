-- Sample Health Lakehouse Data Data
-- This file contains realistic sample data for testing row-level access control

-- Sample data for claims table
-- Format: claim_id, user_id, patient_name, patient_dob, claim_date, claim_amount, claim_type, claim_status, provider_name, provider_npi, diagnosis_code, procedure_code, submitted_date, processed_date, approved_amount, denial_reason, notes, created_by, last_modified_by, last_modified_date

-- Claims for user001@example.com (Patient: John Doe)
INSERT INTO lakehouse_db.claims VALUES
('CLM-2024-001', 'user001@example.com', 'John Doe', DATE '1985-03-15', DATE '2024-01-10', 1250.00, 'medical', 'approved', 'City Medical Center', '1234567890', 'J06.9', '99213', TIMESTAMP '2024-01-11 09:30:00', TIMESTAMP '2024-01-15 14:20:00', 1000.00, NULL, 'Annual physical examination and lab work', 'user001@example.com', 'adjuster001@example.com', TIMESTAMP '2024-01-15 14:20:00'),
('CLM-2024-002', 'user001@example.com', 'John Doe', DATE '1985-03-15', DATE '2024-02-05', 85.50, 'prescription', 'approved', 'CVS Pharmacy', '9876543210', 'E11.9', '90670', TIMESTAMP '2024-02-05 16:45:00', TIMESTAMP '2024-02-06 10:15:00', 85.50, NULL, 'Diabetes medication - monthly refill', 'user001@example.com', 'adjuster001@example.com', TIMESTAMP '2024-02-06 10:15:00'),
('CLM-2024-003', 'user001@example.com', 'John Doe', DATE '1985-03-15', DATE '2024-02-20', 3500.00, 'hospital', 'in_review', 'General Hospital', '1122334455', 'M54.5', '22612', TIMESTAMP '2024-02-21 08:00:00', NULL, NULL, NULL, 'Emergency room visit for back pain, including X-rays', 'user001@example.com', 'user001@example.com', TIMESTAMP '2024-02-21 08:00:00'),
('CLM-2024-004', 'user001@example.com', 'John Doe', DATE '1985-03-15', DATE '2024-03-10', 450.00, 'medical', 'pending', 'Downtown Dental Clinic', '2233445566', 'K02.9', 'D0150', TIMESTAMP '2024-03-11 11:20:00', NULL, NULL, NULL, 'Dental examination and cleaning', 'user001@example.com', 'user001@example.com', TIMESTAMP '2024-03-11 11:20:00');

-- Claims for user002@example.com (Patient: Jane Smith)
INSERT INTO lakehouse_db.claims VALUES
('CLM-2024-005', 'user002@example.com', 'Jane Smith', DATE '1990-07-22', DATE '2024-01-15', 850.00, 'medical', 'approved', 'Women''s Health Center', '5544332211', 'Z00.00', '99395', TIMESTAMP '2024-01-16 10:00:00', TIMESTAMP '2024-01-18 15:30:00', 680.00, NULL, 'Annual gynecological exam and preventive care', 'user002@example.com', 'adjuster001@example.com', TIMESTAMP '2024-01-18 15:30:00'),
('CLM-2024-006', 'user002@example.com', 'Jane Smith', DATE '1990-07-22', DATE '2024-02-10', 125.00, 'prescription', 'approved', 'Walgreens Pharmacy', '6655443322', 'H10.9', '90680', TIMESTAMP '2024-02-10 13:15:00', TIMESTAMP '2024-02-11 09:00:00', 125.00, NULL, 'Antibiotic prescription for eye infection', 'user002@example.com', 'adjuster001@example.com', TIMESTAMP '2024-02-11 09:00:00'),
('CLM-2024-007', 'user002@example.com', 'Jane Smith', DATE '1990-07-22', DATE '2024-02-25', 12500.00, 'hospital', 'approved', 'St. Mary''s Hospital', '7766554433', 'O80', '59400', TIMESTAMP '2024-02-26 07:30:00', TIMESTAMP '2024-03-05 16:00:00', 10000.00, NULL, 'Childbirth and postpartum care', 'user002@example.com', 'adjuster002@example.com', TIMESTAMP '2024-03-05 16:00:00'),
('CLM-2024-008', 'user002@example.com', 'Jane Smith', DATE '1990-07-22', DATE '2024-03-15', 200.00, 'medical', 'denied', 'Cosmetic Surgery Center', '8877665544', 'Z41.1', '15780', TIMESTAMP '2024-03-16 14:00:00', TIMESTAMP '2024-03-20 11:00:00', 0.00, 'Cosmetic procedures not covered by policy', 'Facial cosmetic procedure', 'user002@example.com', 'adjuster002@example.com', TIMESTAMP '2024-03-20 11:00:00'),
('CLM-2024-009', 'user002@example.com', 'Jane Smith', DATE '1990-07-22', DATE '2024-03-25', 75.00, 'prescription', 'pending', 'Target Pharmacy', '9988776655', 'Z79.890', '90715', TIMESTAMP '2024-03-26 09:45:00', NULL, NULL, NULL, 'Vitamin supplements and prenatal care', 'user002@example.com', 'user002@example.com', TIMESTAMP '2024-03-26 09:45:00');

-- Claims for adjuster001@example.com (Staff member - testing cross-access)
INSERT INTO lakehouse_db.claims VALUES
('CLM-2024-010', 'adjuster001@example.com', 'Michael Johnson', DATE '1978-11-30', DATE '2024-01-20', 500.00, 'medical', 'approved', 'Quick Care Clinic', '1231231234', 'J20.9', '99214', TIMESTAMP '2024-01-21 08:00:00', TIMESTAMP '2024-01-22 10:00:00', 500.00, NULL, 'Urgent care visit for bronchitis', 'adjuster001@example.com', 'adjuster002@example.com', TIMESTAMP '2024-01-22 10:00:00'),
('CLM-2024-011', 'adjuster001@example.com', 'Michael Johnson', DATE '1978-11-30', DATE '2024-03-01', 2800.00, 'hospital', 'pending', 'Regional Medical Center', '4564564567', 'S52.501A', '25605', TIMESTAMP '2024-03-02 15:30:00', NULL, NULL, NULL, 'Fracture treatment - left wrist, includes casting', 'adjuster001@example.com', 'adjuster001@example.com', TIMESTAMP '2024-03-02 15:30:00');

-- Sample data for users table
INSERT INTO lakehouse_db.users VALUES
('user001@example.com', 'John Doe', 'patient', 'Individual', TIMESTAMP '2023-01-15 00:00:00'),
('user002@example.com', 'Jane Smith', 'patient', 'Individual', TIMESTAMP '2023-02-20 00:00:00'),
('adjuster001@example.com', 'Michael Johnson', 'adjuster', 'Claims Department', TIMESTAMP '2022-06-01 00:00:00'),
('adjuster002@example.com', 'Sarah Williams', 'adjuster', 'Claims Department', TIMESTAMP '2022-08-15 00:00:00'),
('admin@example.com', 'Admin User', 'admin', 'IT Department', TIMESTAMP '2022-01-01 00:00:00');

-- Note: The actual data insertion for Athena requires CSV files in S3
-- This SQL is for reference and documentation purposes
-- The setup_athena.py script will create proper CSV files and upload them to S3
