create role r360_metabase login password 'r360_metabase_local';
create role r360_dagster login password 'r360_dagster_local';
create role r360_publisher login password 'r360_publisher_local';

create database r360_metabase owner r360_metabase;
create database r360_dagster owner r360_dagster;
create database r360_bi owner r360_publisher;

revoke all on database r360_bi from public;
grant connect on database r360_bi to r360_metabase;

\connect r360_bi
revoke create on schema public from public;
create schema r360_bi authorization r360_publisher;
grant usage on schema r360_bi to r360_metabase;
alter default privileges for role r360_publisher grant select on tables to r360_metabase;
