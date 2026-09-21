CREATE TABLE `session_versions` (
	`session` text NOT NULL,
	`revision` integer NOT NULL,
	`payload` text NOT NULL,
	`created_at` text NOT NULL,
	PRIMARY KEY(`session`, `revision`)
);
