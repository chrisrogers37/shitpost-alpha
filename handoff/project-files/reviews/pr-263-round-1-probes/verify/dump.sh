#!/bin/bash
# Usage: dump.sh <url-file> [with_built_at] -- md5 of signal_moves and random_baselines contents
URL="$(cat "$1")"
COLS="t.*"
psql -X -At "$URL" <<SQL
select 'signal_moves', count(*), md5(string_agg(row_to_json(t)::text, '|' order by instrument_id, entry, signal_key)) from (select * from engine.signal_moves) t;
select 'signal_moves_no_built_at', count(*), md5(string_agg((row_to_json(t)::jsonb - 'built_at')::text, '|' order by instrument_id, entry, signal_key)) from engine.signal_moves t;
select 'random_baselines', count(*), md5(string_agg(row_to_json(t)::text, '|' order by data_to, instrument_id, entry, "window", weekday, hour)) from engine.random_baselines t;
select 'instruments', string_agg(id || ':' || slug, ',' order by id) from engine.instruments;
SQL
