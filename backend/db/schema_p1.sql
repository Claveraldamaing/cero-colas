-- Esquema P1 PostgreSQL. Referencia generada desde los modelos SQLAlchemy.

-- Aplicar con: python -m app.db.migrate (versiona la inicialización).

-- Sin DNI, fecha de nacimiento ni tokens hospitalarios persistentes.



CREATE TABLE p1_auth_attempts (
	id VARCHAR(36) NOT NULL, 
	scope VARCHAR(32) NOT NULL, 
	subject_hash VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_p1_auth_attempt_window ON p1_auth_attempts (scope, subject_hash, created_at);


CREATE TABLE p1_challenges (
	id VARCHAR(64) NOT NULL, 
	answer_hash VARCHAR(64) NOT NULL, 
	client_hash VARCHAR(64) NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	consumed_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_p1_challenges_expires_at ON p1_challenges (expires_at);


CREATE TABLE p1_schema_migrations (
	version VARCHAR(40) NOT NULL, 
	applied_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	PRIMARY KEY (version)
)

;


CREATE TABLE p1_users (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	password_hash VARCHAR(256) NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	active BOOLEAN NOT NULL, 
	preferences JSON NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE UNIQUE INDEX ix_p1_users_email ON p1_users (email);


CREATE TABLE p1_recovery_tokens (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	used_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES p1_users (id) ON DELETE CASCADE
)

;

CREATE UNIQUE INDEX ix_p1_recovery_tokens_token_hash ON p1_recovery_tokens (token_hash);

CREATE INDEX ix_p1_recovery_tokens_user_id ON p1_recovery_tokens (user_id);


CREATE TABLE p1_sessions (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	csrf_hash VARCHAR(64) NOT NULL, 
	created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	revoked_at TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES p1_users (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_p1_sessions_expires_at ON p1_sessions (expires_at);

CREATE INDEX ix_p1_sessions_user_id ON p1_sessions (user_id);

CREATE UNIQUE INDEX ix_p1_sessions_token_hash ON p1_sessions (token_hash);


CREATE TABLE p1_usage_events (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	session_id VARCHAR(36) NOT NULL, 
	event_type VARCHAR(40) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_p1_usage_session_type UNIQUE (session_id, event_type), 
	FOREIGN KEY(user_id) REFERENCES p1_users (id) ON DELETE CASCADE, 
	FOREIGN KEY(session_id) REFERENCES p1_sessions (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_p1_usage_events_user_id ON p1_usage_events (user_id);


CREATE TABLE p1_surveys (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	usage_event_id VARCHAR(36) NOT NULL, 
	ease_score INTEGER NOT NULL, 
	satisfaction_score INTEGER NOT NULL, 
	comment TEXT, 
	scale_min INTEGER NOT NULL, 
	scale_max INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_p1_survey_scale CHECK (scale_min < scale_max), 
	CONSTRAINT ck_p1_survey_ease CHECK (ease_score >= scale_min AND ease_score <= scale_max), 
	CONSTRAINT ck_p1_survey_satisfaction CHECK (satisfaction_score >= scale_min AND satisfaction_score <= scale_max), 
	FOREIGN KEY(user_id) REFERENCES p1_users (id) ON DELETE CASCADE, 
	UNIQUE (usage_event_id), 
	FOREIGN KEY(usage_event_id) REFERENCES p1_usage_events (id) ON DELETE CASCADE
)

;

CREATE INDEX ix_p1_surveys_user_id ON p1_surveys (user_id);