import {sqliteTable,text,integer,primaryKey} from 'drizzle-orm/sqlite-core';
export const sessionVersions=sqliteTable('session_versions',{session:text('session').notNull(),revision:integer('revision').notNull(),payload:text('payload').notNull(),createdAt:text('created_at').notNull()},t=>[primaryKey({columns:[t.session,t.revision]})]);
