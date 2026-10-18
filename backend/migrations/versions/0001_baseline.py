"""Baseline: the production schema before v3.

Production and restored copies are stamped at this revision. Empty databases
are created from it, so it reproduces the hand-made schema exactly, including
its mixed timestamp types and the upper-case task status enum.

Revision ID: 0001
Revises:
Create Date: 2026-10-18
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

BASELINE_SQL = """
CREATE TYPE taskstatus AS ENUM (
    'PENDING',
    'IN_PROGRESS',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
);

CREATE TABLE conversations (
    id integer NOT NULL,
    video_id text NOT NULL,
    user_id integer,
    guest_session_id text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);

CREATE SEQUENCE conversations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE conversations_id_seq OWNED BY conversations.id;

CREATE TABLE credit_purchases (
    id integer NOT NULL,
    user_id integer NOT NULL,
    provider text DEFAULT 'dodo'::text NOT NULL,
    provider_session_id text NOT NULL,
    provider_payment_id text,
    product_id text,
    credits_amount integer NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE credit_purchases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE credit_purchases_id_seq OWNED BY credit_purchases.id;

CREATE TABLE credits_ledger (
    id integer NOT NULL,
    user_id integer NOT NULL,
    delta integer NOT NULL,
    reason text NOT NULL,
    ref_type text NOT NULL,
    ref_id text NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL
);

CREATE SEQUENCE credits_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE credits_ledger_id_seq OWNED BY credits_ledger.id;

CREATE TABLE messages (
    id integer NOT NULL,
    conversation_id integer NOT NULL,
    role text NOT NULL,
    content text NOT NULL,
    metadata json,
    created_at timestamp with time zone
);

CREATE SEQUENCE messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE messages_id_seq OWNED BY messages.id;

CREATE TABLE notes (
    id integer NOT NULL,
    video_id text NOT NULL,
    "timestamp" text NOT NULL,
    text text,
    generated_by_ai boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    user_id integer NOT NULL
);

CREATE SEQUENCE notes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE notes_id_seq OWNED BY notes.id;

CREATE TABLE tasks (
    id integer NOT NULL,
    task_type text NOT NULL,
    status taskstatus NOT NULL,
    task_details json,
    worker_details json,
    retry_count integer,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);

CREATE SEQUENCE tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE tasks_id_seq OWNED BY tasks.id;

CREATE TABLE users (
    id integer NOT NULL,
    password_hash text,
    long_term_token text,
    profile_data json,
    created_at timestamp with time zone,
    google_id text,
    email text NOT NULL,
    name text NOT NULL,
    profile_image_url text,
    credits_balance integer DEFAULT 0 NOT NULL
);

CREATE SEQUENCE users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE users_id_seq OWNED BY users.id;

CREATE TABLE videos (
    id integer NOT NULL,
    video_id text NOT NULL,
    title text,
    transcript_available boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone,
    video_metadata jsonb,
    summary text,
    miscellaneous_data json DEFAULT '{}'::json NOT NULL
);

CREATE SEQUENCE videos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

ALTER SEQUENCE videos_id_seq OWNED BY videos.id;

ALTER TABLE ONLY conversations ALTER COLUMN id SET DEFAULT nextval('conversations_id_seq'::regclass);

ALTER TABLE ONLY credit_purchases ALTER COLUMN id SET DEFAULT nextval('credit_purchases_id_seq'::regclass);

ALTER TABLE ONLY credits_ledger ALTER COLUMN id SET DEFAULT nextval('credits_ledger_id_seq'::regclass);

ALTER TABLE ONLY messages ALTER COLUMN id SET DEFAULT nextval('messages_id_seq'::regclass);

ALTER TABLE ONLY notes ALTER COLUMN id SET DEFAULT nextval('notes_id_seq'::regclass);

ALTER TABLE ONLY tasks ALTER COLUMN id SET DEFAULT nextval('tasks_id_seq'::regclass);

ALTER TABLE ONLY users ALTER COLUMN id SET DEFAULT nextval('users_id_seq'::regclass);

ALTER TABLE ONLY videos ALTER COLUMN id SET DEFAULT nextval('videos_id_seq'::regclass);

ALTER TABLE ONLY conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);

ALTER TABLE ONLY credit_purchases
    ADD CONSTRAINT credit_purchases_pkey PRIMARY KEY (id);

ALTER TABLE ONLY credits_ledger
    ADD CONSTRAINT credits_ledger_pkey PRIMARY KEY (id);

ALTER TABLE ONLY messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);

ALTER TABLE ONLY notes
    ADD CONSTRAINT notes_pkey PRIMARY KEY (id);

ALTER TABLE ONLY tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);

ALTER TABLE ONLY users
    ADD CONSTRAINT users_email_key UNIQUE (email);

ALTER TABLE ONLY users
    ADD CONSTRAINT users_google_id_key UNIQUE (google_id);

ALTER TABLE ONLY users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);

ALTER TABLE ONLY videos
    ADD CONSTRAINT videos_pkey PRIMARY KEY (id);

ALTER TABLE ONLY videos
    ADD CONSTRAINT videos_video_id_key UNIQUE (video_id);

CREATE UNIQUE INDEX uq_credits_ledger_ref ON credits_ledger USING btree (user_id, reason, ref_type, ref_id);

ALTER TABLE ONLY conversations
    ADD CONSTRAINT conversations_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id);

ALTER TABLE ONLY messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES conversations(id);

ALTER TABLE ONLY notes
    ADD CONSTRAINT notes_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id);

ALTER TABLE ONLY notes
    ADD CONSTRAINT notes_video_id_fkey FOREIGN KEY (video_id) REFERENCES videos(video_id);
"""


def upgrade() -> None:
    op.execute(BASELINE_SQL)


def downgrade() -> None:
    op.execute(
        "DROP TABLE messages, conversations, notes, credits_ledger, "
        "credit_purchases, tasks, videos, users CASCADE"
    )
    op.execute("DROP TYPE taskstatus")
