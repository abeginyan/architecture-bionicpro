-- CRM demo data. Emails MUST match the Keycloak users (prothetic1..3@example.com)
-- so the ClickHouse mart (keyed by user_email) returns rows for those pilots.
-- Idempotent: ON CONFLICT DO NOTHING lets the file re-run harmlessly.

INSERT INTO customers (customer_id, name, email, region) VALUES
    (1, 'Prothetic One',   'prothetic1@example.com', 'Moscow'),
    (2, 'Prothetic Two',   'prothetic2@example.com', 'Kazan'),
    (3, 'Prothetic Three', 'prothetic3@example.com', 'Novosibirsk')
ON CONFLICT (customer_id) DO NOTHING;

INSERT INTO prostheses (prosthesis_id, customer_id, model, serial_number, purchased_at) VALUES
    (101, 1, 'BionicArm X1',  'SN-101-AX1', '2025-06-01'),
    (102, 1, 'BionicHand H2', 'SN-102-BH2', '2025-07-15'),
    (201, 2, 'BionicArm X1',  'SN-201-AX1', '2025-05-10'),
    (202, 2, 'BionicLeg L3',  'SN-202-CL3', '2025-08-20'),
    (301, 3, 'BionicLeg L3',  'SN-301-CL3', '2025-04-05'),
    (302, 3, 'BionicHand H2', 'SN-302-BH2', '2025-09-01')
ON CONFLICT (prosthesis_id) DO NOTHING;
