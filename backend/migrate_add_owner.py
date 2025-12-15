"""
Migration script to add owner_id and owner_username columns to existing tables
"""
from sqlalchemy import create_engine, text
import os

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://awx:password@localhost:5432/awx"
)

print(f"Connecting to database: {DATABASE_URL}")
engine = create_engine(DATABASE_URL)

# SQL commands to add missing columns
migration_sqls = [
    # Add columns to ansible_builder_playbooks if they don't exist
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='ansible_builder_playbooks' AND column_name='owner_id'
        ) THEN
            ALTER TABLE ansible_builder_playbooks ADD COLUMN owner_id INTEGER NULL;
        END IF;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='ansible_builder_playbooks' AND column_name='owner_username'
        ) THEN
            ALTER TABLE ansible_builder_playbooks ADD COLUMN owner_username VARCHAR(255) NULL;
        END IF;
    END $$;
    """,

    # Add columns to ansible_builder_inventories if they don't exist
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='ansible_builder_inventories' AND column_name='owner_id'
        ) THEN
            ALTER TABLE ansible_builder_inventories ADD COLUMN owner_id INTEGER NULL;
        END IF;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='ansible_builder_inventories' AND column_name='owner_username'
        ) THEN
            ALTER TABLE ansible_builder_inventories ADD COLUMN owner_username VARCHAR(255) NULL;
        END IF;
    END $$;
    """
]

try:
    with engine.begin() as connection:
        for i, sql in enumerate(migration_sqls, 1):
            print(f"\nExecuting migration {i}/{len(migration_sqls)}...")
            connection.execute(text(sql))
            print(f"  ✓ Migration {i} completed successfully")

    print("\n" + "="*60)
    print("All migrations completed successfully!")
    print("="*60)

except Exception as e:
    print(f"\n✗ Migration failed: {e}")
    raise

print("\nVerifying columns...")
verify_sql = """
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('ansible_builder_playbooks', 'ansible_builder_inventories')
    AND column_name IN ('owner_id', 'owner_username')
ORDER BY table_name, column_name;
"""

try:
    with engine.connect() as connection:
        result = connection.execute(text(verify_sql))
        rows = result.fetchall()

        print("\nColumns added:")
        print("-" * 60)
        for row in rows:
            print(f"  {row[0]}.{row[1]} ({row[2]})")
        print("-" * 60)

except Exception as e:
    print(f"Verification failed: {e}")
