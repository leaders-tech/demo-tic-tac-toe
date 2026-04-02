"""Create the games and game_moves tables.

Edit this file only if this migration has not been used yet.
Create a new migration file instead when you need another schema change.
"""

from yoyo import step


steps = [
    step(
        """
        CREATE TABLE games (
            id INTEGER PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('waiting', 'active', 'finished')),
            x_user_id INTEGER NOT NULL,
            o_user_id INTEGER,
            starter_symbol TEXT NOT NULL CHECK (starter_symbol IN ('X', 'O')),
            turn_symbol TEXT CHECK (turn_symbol IN ('X', 'O')),
            winner_symbol TEXT CHECK (winner_symbol IN ('X', 'O')),
            finish_reason TEXT CHECK (finish_reason IN ('line', 'no_moves', 'forfeit')),
            forfeit_user_id INTEGER,
            disconnect_deadline_at TEXT,
            rematch_x_ready INTEGER NOT NULL DEFAULT 0 CHECK (rematch_x_ready IN (0, 1)),
            rematch_o_ready INTEGER NOT NULL DEFAULT 0 CHECK (rematch_o_ready IN (0, 1)),
            rematch_of_game_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (x_user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (o_user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (forfeit_user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (rematch_of_game_id) REFERENCES games (id) ON DELETE SET NULL
        ) STRICT
        """,
        "DROP TABLE games",
    ),
    step(
        """
        CREATE TABLE game_moves (
            id INTEGER PRIMARY KEY,
            game_id INTEGER NOT NULL,
            turn_number INTEGER NOT NULL,
            symbol TEXT NOT NULL CHECK (symbol IN ('X', 'O')),
            user_id INTEGER NOT NULL,
            size TEXT NOT NULL CHECK (size IN ('small', 'medium', 'large')),
            row_index INTEGER NOT NULL CHECK (row_index BETWEEN 0 AND 2),
            col_index INTEGER NOT NULL CHECK (col_index BETWEEN 0 AND 2),
            created_at TEXT NOT NULL,
            FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        ) STRICT
        """,
        "DROP TABLE game_moves",
    ),
]
