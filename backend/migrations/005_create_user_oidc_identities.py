"""Create the user_oidc_identities table.

Edit this file only if this migration has not been used yet.
Create a new migration file instead when you need another schema change.
"""

from yoyo import step


steps = [
    step(
        """
        CREATE TABLE user_oidc_identities (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            issuer TEXT NOT NULL,
            subject TEXT NOT NULL,
            email TEXT,
            email_verified INTEGER NOT NULL CHECK (email_verified IN (0, 1)),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_login_at TEXT NOT NULL,
            UNIQUE (issuer, subject)
        ) STRICT
        """,
        "DROP TABLE user_oidc_identities",
    )
]
