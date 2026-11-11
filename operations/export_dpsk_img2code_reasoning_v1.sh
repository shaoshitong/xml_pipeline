#!/bin/bash
# DSH's JSON stdout caps long thinking events. Export persisted assistant
# reasoning and scoped turn metadata only, not system prompts or tool payloads.
set -euo pipefail
case_dir=$1
session_root=$2
requested_rounds=${3:-3}
session_id=$(sed -n '1p' "$case_dir/round1.events.jsonl" | jq -er 'select(.type=="session") | .sessionId')
if [[ ! "$session_id" =~ ^session-[a-f0-9-]+$ ]]; then
  echo 'Unexpected DSH session identifier' >&2
  exit 1
fi
session_file=$(find "$session_root" -type f -path "*/$session_id/session.v4.jsonl.zstd" -print -quit)
test -n "$session_file"
zstdcat "$session_file" | jq -cs --arg sid "$session_id" --argjson limit "$requested_rounds" '
  def turns($name): [.[] | select(.type==$name) | .data.turn | select(.<= $limit)];
  def reasoning: .[] | select(.type=="assistant/message" and .data.turn<= $limit) | . as $record
    | .data.message.content | to_entries[] | select(.value.type=="reasoning")
    | {turn:$record.data.turn,step:$record.data.step,seq:$record.seq,part:.key,text:.value.text};
  {session_id:$sid, expected_turns:$limit,
   request_models:([.[]|select(.type=="request/context")|{model:.data.model,provider:.data.provider}]|unique),
   turns_started:turns("turn/start"),turns_ended:turns("turn/end"),reasoning:[reasoning]}
  | if .turns_started==[range(1;$limit+1)] and .turns_ended==.turns_started and
       ([.reasoning[].turn]|unique)==.turns_started then . else error("missing_or_incomplete_DSH_turn") end
'
