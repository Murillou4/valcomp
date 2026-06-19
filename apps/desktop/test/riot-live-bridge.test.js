const test = require("node:test");
const assert = require("node:assert/strict");

const { opaqueId, observedChange } = require("../src/live/riot-live-bridge");

test("opaque IDs are deterministic and never expose the Riot identifier", () => {
  const raw = "real-riot-player-identifier";
  const first = opaqueId(raw);
  assert.equal(first, opaqueId(raw));
  assert.equal(first.length, 20);
  assert.equal(first.includes(raw), false);
});

test("queue command is only observed after the live phase changes", () => {
  const command = { command: "party.join_queue", payload: {} };
  assert.equal(
    observedChange(command, { phase: "lobby", state: {} }, { phase: "lobby", state: {} }),
    false,
  );
  assert.equal(
    observedChange(command, { phase: "lobby", state: {} }, { phase: "queue", state: {} }),
    true,
  );
});

test("agent lock requires the selected agent and locked state", () => {
  const command = {
    command: "pregame.lock_agent",
    payload: { agent_id: "agent-public-id" },
  };
  assert.equal(
    observedChange(command, { phase: "pregame", state: {} }, {
      phase: "pregame",
      state: {
        agents: [
          {
            is_self: true,
            locked: true,
            agent: { id: "agent-public-id" },
          },
        ],
      },
    }),
    true,
  );
});
