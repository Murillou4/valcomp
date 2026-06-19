const EventEmitter = require("events");
const fs = require("fs");
const https = require("https");
const path = require("path");
const { createHash } = require("crypto");
const WebSocket = require("ws");

const CLIENT_PLATFORM =
  "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0KCSJwbGF0Zm9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxhdGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9";
const REGION_TO_SHARD = { na: "na", latam: "na", br: "na", eu: "eu", ap: "ap", kr: "kr" };

class RiotLiveBridge extends EventEmitter {
  constructor({ log }) {
    super();
    this.log = log;
    this.context = null;
    this.contextDetectedAt = 0;
    this.localSocket = null;
    this.revision = 0;
    this.lastPregameId = "";
    this.lastInGameId = "";
    this.postgameUntil = 0;
    this.memberIds = new Map();
    this.assets = { maps: new Map(), agents: new Map(), ranks: new Map(), fetchedAt: 0 };
    this.playerNames = new Map();
    this.capabilities = defaultCapabilities();
    this.matchAcceptPath = "";
    this.lastChatAt = 0;
    this.lastCredentialFingerprint = "";
  }

  async poll() {
    try {
      const context = await this.ensureContext();
      const [partyPlayer, pregamePlayer, currentPlayer] = await Promise.all([
        this.remote("GET", `/parties/v1/players/${context.puuid}`, null, true),
        this.remote("GET", `/pregame/v1/players/${context.puuid}`, null, true),
        this.remote("GET", `/core-game/v1/players/${context.puuid}`, null, true),
      ]);
      const partyId = String(partyPlayer?.CurrentPartyID || "");
      const pregameId = String(pregamePlayer?.MatchID || "");
      const currentGameId = String(currentPlayer?.MatchID || "");
      const [party, pregame, currentGame, channels] = await Promise.all([
        partyId ? this.remote("GET", `/parties/v1/parties/${partyId}`, null, true) : null,
        pregameId ? this.remote("GET", `/pregame/v1/matches/${pregameId}`, null, true) : null,
        currentGameId ? this.remote("GET", `/core-game/v1/matches/${currentGameId}`, null, true) : null,
        this.chatChannels(),
      ]);
      if (party) await this.ensurePlayerNames(party.Members || []);
      await this.ensureAssets();
      let phase = "client";
      let state = this.baseState(context, channels);
      if (currentGameId && currentGame) {
        this.lastInGameId = currentGameId;
        this.postgameUntil = 0;
        phase = "in_game";
        state = { ...state, ...this.normalizeCurrentGame(currentGame, party) };
      } else if (pregameId && pregame) {
        phase = pregameId !== this.lastPregameId ? "match_found" : "pregame";
        this.lastPregameId = pregameId;
        state = { ...state, ...this.normalizePregame(pregame, party) };
      } else if (party) {
        const normalizedParty = this.normalizeParty(party);
        phase = normalizedParty.queue.searching ? "queue" : "lobby";
        state = { ...state, ...normalizedParty };
        if (this.lastInGameId) {
          this.postgameUntil = Date.now() + 20000;
          state = {
            ...state,
            previous_match_id: opaqueId(this.lastInGameId),
            result: null,
            rr_change: null,
          };
          this.lastInGameId = "";
          phase = "postgame";
        } else if (Date.now() < this.postgameUntil) {
          phase = "postgame";
        }
      }
      return { revision: ++this.revision, phase, state };
    } catch (error) {
      this.invalidateContext(error);
      return {
        revision: ++this.revision,
        phase: "offline",
        state: {
          reason: "riot_client_unavailable",
          message: friendlyError(error),
          capabilities: defaultCapabilities(),
        },
      };
    }
  }

  setRevisionFloor(value) {
    const floor = Number(value);
    if (Number.isSafeInteger(floor) && floor > this.revision) this.revision = floor;
  }

  async credentialSnapshot() {
    const context = await this.ensureContext();
    return {
      access_token: context.accessToken,
      entitlement_token: context.entitlement,
      puuid: context.puuid,
      region: context.region,
      shard: context.shard,
      client_version: context.clientVersion,
    };
  }

  async execute(command) {
    const started = Date.now();
    try {
      const context = await this.ensureContext();
      const stateBefore = await this.poll();
      const payload = command.payload || {};
      let response;
      switch (command.command) {
        case "party.change_queue":
          response = await this.partyRequest("POST", "queue", { queueID: payload.queue_id });
          break;
        case "party.join_queue":
          response = await this.partyRequest("POST", "matchmaking/join");
          break;
        case "party.leave_queue":
          response = await this.partyRequest("POST", "matchmaking/leave");
          break;
        case "party.set_ready":
          response = await this.partyRequest(
            "POST",
            `members/${context.puuid}/setReady`,
            { ready: payload.ready },
          );
          break;
        case "party.invite":
          response = await this.partyRequest(
            "POST",
            `invites/name/${encodeURIComponent(payload.game_name)}/tag/${encodeURIComponent(payload.tag_line)}`,
          );
          break;
        case "party.remove_member": {
          const rawPuuid = this.memberIds.get(payload.puuid);
          if (!rawPuuid) throw commandError("Membro não encontrado no party atual.", "member_unavailable");
          response = await this.remote("DELETE", `/parties/v1/players/${rawPuuid}`);
          break;
        }
        case "party.set_accessibility":
          response = await this.partyRequest("POST", "accessibility", {
            accessibility: payload.accessibility,
          });
          break;
        case "party.generate_code":
          response = await this.partyRequest("POST", "invitecode");
          break;
        case "pregame.select_agent":
          response = await this.pregameRequest("POST", `select/${payload.agent_id}`);
          break;
        case "pregame.lock_agent":
          response = await this.pregameRequest("POST", `lock/${payload.agent_id}`);
          break;
        case "chat.send":
          if (Date.now() - this.lastChatAt < 1000) {
            throw commandError("Aguarde um instante antes de enviar outra mensagem.", "rate_limited");
          }
          this.lastChatAt = Date.now();
          response = await this.local("POST", "/chat/v6/messages", {
            cid: payload.cid,
            message: payload.message,
            type: payload.chat_type,
          });
          break;
        case "current_game.leave": {
          if (payload.confirmed !== true) throw commandError("Confirmação ausente.", "confirmation_required");
          const player = await this.remote("GET", `/core-game/v1/players/${context.puuid}`);
          const matchId = String(player?.MatchID || "");
          if (!matchId) throw commandError("Nenhuma partida ativa foi encontrada.", "match_unavailable");
          response = await this.remote(
            "POST",
            `/core-game/v1/players/${context.puuid}/disassociate/${matchId}`,
          );
          break;
        }
        case "match.accept":
          if (!this.matchAcceptPath) {
            throw commandError(
              "O cliente instalado não confirmou uma operação de aceite segura.",
              "capability_unavailable",
            );
          }
          response = await this.local("POST", this.matchAcceptPath);
          break;
        default:
          throw commandError("Comando não permitido pelo Companion.", "command_not_allowed");
      }
      await delay(650);
      const stateAfter = await this.poll();
      return {
        status: "succeeded",
        result: {
          api_accepted: true,
          observed: observedChange(command, stateBefore, stateAfter),
          phase: stateAfter.phase,
          elapsed_ms: Date.now() - started,
          response: safeCommandResponse(command.command, response),
        },
      };
    } catch (error) {
      return {
        status: error.code === "command_not_allowed" || error.code === "capability_unavailable" ? "rejected" : "failed",
        result: {
          code: error.code || "riot_request_failed",
          message: friendlyError(error),
          elapsed_ms: Date.now() - started,
        },
      };
    }
  }

  async partyRequest(method, suffix, body = null) {
    const context = await this.ensureContext();
    const player = await this.remote("GET", `/parties/v1/players/${context.puuid}`);
    const partyId = String(player?.CurrentPartyID || "");
    if (!partyId) throw commandError("Nenhum party ativo foi encontrado.", "party_unavailable");
    return this.remote(method, `/parties/v1/parties/${partyId}/${suffix}`, body);
  }

  async pregameRequest(method, suffix) {
    const context = await this.ensureContext();
    const player = await this.remote("GET", `/pregame/v1/players/${context.puuid}`);
    const matchId = String(player?.MatchID || "");
    if (!matchId) throw commandError("A seleção de agente não está ativa.", "pregame_unavailable");
    return this.remote(method, `/pregame/v1/matches/${matchId}/${suffix}`);
  }

  async ensureContext() {
    if (this.context && Date.now() - this.contextDetectedAt < 45000) return this.context;
    const lockfile = readLockfile();
    const entitlements = await localRequest(lockfile, "GET", "/entitlements/v1/token");
    const [regionLocale, sessions] = await Promise.all([
      optionalLocalRequest(lockfile, "/riotclient/region-locale"),
      optionalLocalRequest(lockfile, "/product-session/v1/external-sessions"),
    ]);
    const session = parseSessions(sessions);
    const log = parseShooterLog();
    const region = String(session.region || log.region || regionLocale.region || "").toLowerCase();
    const shard = String(session.shard || log.shard || REGION_TO_SHARD[region] || "").toLowerCase();
    const context = {
      lockfile,
      accessToken: String(entitlements.accessToken || ""),
      entitlement: String(entitlements.token || ""),
      puuid: String(entitlements.subject || ""),
      region,
      shard,
      clientVersion: String(log.clientVersion || session.clientVersion || ""),
    };
    if (!context.accessToken || !context.entitlement || !context.puuid || !region || !shard) {
      throw new Error("A sessão local do VALORANT ainda não está pronta.");
    }
    this.context = context;
    this.contextDetectedAt = Date.now();
    const credentialFingerprint = createHash("sha256")
      .update(`${context.puuid}:${context.accessToken}`)
      .digest("hex");
    if (credentialFingerprint !== this.lastCredentialFingerprint) {
      this.lastCredentialFingerprint = credentialFingerprint;
      queueMicrotask(() => this.emit("credentials-changed"));
    }
    await this.discoverCapabilities();
    this.connectLocalEvents();
    return context;
  }

  invalidateContext(error) {
    const message = String(error?.message || error || "");
    if (/401|403|ECONN|fetch|lockfile|sessão/i.test(message)) {
      this.context = null;
      this.contextDetectedAt = 0;
    }
  }

  async remote(method, apiPath, body = null, allowMissing = false) {
    const context = this.context || (await this.ensureContext());
    const response = await fetch(
      `https://glz-${context.region}-1.${context.shard}.a.pvp.net${apiPath}`,
      {
        method,
        headers: {
          Authorization: `Bearer ${context.accessToken}`,
          "X-Riot-Entitlements-JWT": context.entitlement,
          "X-Riot-ClientPlatform": CLIENT_PLATFORM,
          ...(context.clientVersion ? { "X-Riot-ClientVersion": context.clientVersion } : {}),
          Accept: "application/json",
          ...(body ? { "Content-Type": "application/json" } : {}),
          "User-Agent": "",
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: AbortSignal.timeout(7000),
      },
    );
    if (allowMissing && [400, 404].includes(response.status)) return null;
    if (!response.ok) {
      const error = commandError(`A Riot respondeu HTTP ${response.status}.`, "riot_http_error");
      error.status = response.status;
      throw error;
    }
    const text = await response.text();
    return text ? JSON.parse(text) : {};
  }

  async pd(method, apiPath, body = null) {
    const context = this.context || (await this.ensureContext());
    const response = await fetch(`https://pd.${context.shard}.a.pvp.net${apiPath}`, {
      method,
      headers: {
        Authorization: `Bearer ${context.accessToken}`,
        "X-Riot-Entitlements-JWT": context.entitlement,
        "X-Riot-ClientPlatform": CLIENT_PLATFORM,
        ...(context.clientVersion ? { "X-Riot-ClientVersion": context.clientVersion } : {}),
        Accept: "application/json",
        "Content-Type": "application/json",
        "User-Agent": "",
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(7000),
    });
    if (!response.ok) {
      throw commandError(`A Riot respondeu HTTP ${response.status}.`, "riot_http_error");
    }
    const text = await response.text();
    return text ? JSON.parse(text) : {};
  }

  async local(method, apiPath, body = null, allowMissing = false) {
    const context = this.context || (await this.ensureContext());
    try {
      return await localRequest(context.lockfile, method, apiPath, body);
    } catch (error) {
      if (allowMissing && error.status === 404) return null;
      throw error;
    }
  }

  async discoverCapabilities() {
    try {
      const swagger = await this.local("GET", "/swagger/v3/openapi.json");
      const paths = swagger?.paths && typeof swagger.paths === "object" ? swagger.paths : {};
      const has = (method, fragment) =>
        Object.entries(paths).some(([route, operations]) =>
          route.toLowerCase().includes(fragment) && Boolean(operations?.[method.toLowerCase()]),
        );
      const matchAcceptPath = Object.entries(paths).find(([route, operations]) => {
        const normalized = route.toLowerCase();
        return normalized.includes("match") && normalized.includes("accept") && Boolean(operations?.post);
      });
      this.matchAcceptPath =
        matchAcceptPath && !matchAcceptPath[0].includes("{") ? matchAcceptPath[0] : "";
      this.capabilities = {
        party: true,
        agent: true,
        chat: has("post", "/chat/v6/messages"),
        leave: true,
        match_accept: Boolean(this.matchAcceptPath),
        swagger_detected: true,
      };
    } catch (error) {
      this.capabilities = defaultCapabilities();
      this.log("warning", "local_swagger_unavailable", { error: String(error) });
    }
  }

  connectLocalEvents() {
    if (!this.context || this.localSocket) return;
    const { lockfile } = this.context;
    const authorization = Buffer.from(`riot:${lockfile.password}`).toString("base64");
    const socket = new WebSocket(`wss://127.0.0.1:${lockfile.port}`, {
      rejectUnauthorized: false,
      headers: { Authorization: `Basic ${authorization}` },
    });
    this.localSocket = socket;
    socket.on("open", () => socket.send(JSON.stringify([5, "OnJsonApiEvent"])));
    socket.on("message", () => this.emit("changed"));
    socket.on("close", () => {
      if (this.localSocket === socket) this.localSocket = null;
      setTimeout(() => this.context && this.connectLocalEvents(), 10000);
    });
    socket.on("error", (error) => {
      this.log("warning", "local_event_socket_error", { error: String(error) });
      if (/ECONNREFUSED|ECONNRESET|socket hang up/i.test(String(error))) {
        this.context = null;
        this.contextDetectedAt = 0;
      }
    });
  }

  async chatChannels() {
    const channels = [];
    for (const [kind, endpoint] of [
      ["party", "/chat/v6/conversations/ares-parties"],
      ["pregame", "/chat/v6/conversations/ares-pregame"],
      ["team", "/chat/v6/conversations/ares-coregame"],
    ]) {
      const response = await this.local("GET", endpoint, null, true).catch(() => null);
      const conversations = Array.isArray(response) ? response : response?.conversations || response?.Conversations || [];
      for (const item of conversations) {
        const cid = String(item.cid || item.Cid || item.id || "");
        if (cid) channels.push({ id: cid, kind, name: channelName(kind) });
      }
    }
    return channels;
  }

  baseState(context, channels) {
    return {
      experimental: true,
      approved_by_riot: false,
      region: context.region.toUpperCase(),
      shard: context.shard.toUpperCase(),
      account_id: opaqueId(context.puuid),
      capabilities: this.capabilities,
      chat_channels: channels,
    };
  }

  normalizeParty(party) {
    this.memberIds.clear();
    const members = (party.Members || []).map((member) => {
      const rawId = String(member.Subject || "");
      const id = opaqueId(rawId);
      if (rawId) this.memberIds.set(id, rawId);
      return {
        id,
        ...this.playerNames.get(rawId),
        is_owner: rawId === String(party.Owner || ""),
        is_ready: Boolean(member.IsReady),
        competitive_tier: numberOrNull(member.CompetitiveTier),
        rank: rankInfo(this.assets.ranks, member.CompetitiveTier),
        account_level: numberOrNull(member.PlayerIdentity?.AccountLevel),
      };
    });
    const matchmaking = party.MatchmakingData || {};
    const queueId = String(matchmaking.QueueID || party.QueueID || "");
    const state = String(party.State || matchmaking.QueueState || "").toUpperCase();
    const enteredAt = parseRiotDate(matchmaking.QueueEntryTime || matchmaking.QueueEntryUnixMilliseconds);
    return {
      party: {
        id: opaqueId(String(party.ID || "")),
        accessibility: String(party.Accessibility || ""),
        members,
      },
      queue: {
        id: queueId,
        searching: state.includes("MATCHMAKING") || state.includes("QUEUE"),
        entered_at: enteredAt,
        elapsed_seconds: enteredAt ? Math.max(0, Math.floor((Date.now() - Date.parse(enteredAt)) / 1000)) : null,
      },
    };
  }

  normalizePregame(match, party) {
    const allies = Array.isArray(match.AllyTeam?.Players) ? match.AllyTeam.Players : [];
    return {
      ...(party ? this.normalizeParty(party) : {}),
      pregame_id: opaqueId(String(match.ID || "")),
      map: this.mapInfo(String(match.MapID || "")),
      mode: { id: String(match.Mode || match.QueueID || ""), name: String(match.Mode || match.QueueID || "") },
      timer: {
        phase_time_remaining_ms: numberOrNull(match.PhaseTimeRemainingNS)
          ? Math.floor(Number(match.PhaseTimeRemainingNS) / 1_000_000)
          : null,
      },
      agents: allies.map((player) => ({
        player_id: opaqueId(String(player.Subject || "")),
        agent: this.agentInfo(String(player.CharacterID || "")),
        selected: Boolean(player.CharacterID),
        locked: String(player.CharacterSelectionState || "").toLowerCase().includes("locked"),
        is_self: String(player.Subject || "") === this.context.puuid,
      })),
      available_agents: [...this.assets.agents.values()].map((agent) => ({
        id: String(agent.uuid || ""),
        name: String(agent.displayName || ""),
        icon: String(agent.displayIconSmall || agent.displayIcon || ""),
      })),
    };
  }

  normalizeCurrentGame(match, party) {
    const players = Array.isArray(match.Players) ? match.Players : [];
    const self = players.find((player) => String(player.Subject || "") === this.context.puuid);
    const teamId = String(self?.TeamID || "");
    const teammates = players.filter((player) => !teamId || String(player.TeamID || "") === teamId);
    return {
      ...(party ? this.normalizeParty(party) : {}),
      match: {
        id: opaqueId(String(match.MatchID || match.ID || "")),
        map: this.mapInfo(String(match.MapID || "")),
        mode: { id: String(match.ModeID || ""), name: String(match.ModeID || "") },
        server: String(match.GamePodID || ""),
        state: String(match.State || "IN_GAME"),
        team: teammates.map((player) => ({
          player_id: opaqueId(String(player.Subject || "")),
          agent: this.agentInfo(String(player.CharacterID || "")),
          is_self: String(player.Subject || "") === this.context.puuid,
        })),
        score: null,
        round: null,
      },
    };
  }

  mapInfo(id) {
    const item = this.assets.maps.get(id.toLowerCase());
    return { id, name: item?.displayName || "", icon: item?.splash || item?.displayIcon || "" };
  }

  agentInfo(id) {
    const item = this.assets.agents.get(id.toLowerCase());
    return { id, name: item?.displayName || "", icon: item?.displayIconSmall || item?.displayIcon || "" };
  }

  async ensureAssets() {
    if (Date.now() - this.assets.fetchedAt < 30 * 60 * 1000) return;
    try {
      const [maps, agents, tiers] = await Promise.all([
        fetch("https://valorant-api.com/v1/maps?language=pt-BR", { signal: AbortSignal.timeout(6000) }).then((r) => r.json()),
        fetch("https://valorant-api.com/v1/agents?language=pt-BR&isPlayableCharacter=true", { signal: AbortSignal.timeout(6000) }).then((r) => r.json()),
        fetch("https://valorant-api.com/v1/competitivetiers?language=pt-BR", { signal: AbortSignal.timeout(6000) }).then((r) => r.json()),
      ]);
      this.assets.maps = new Map(
        (maps.data || []).flatMap((item) => [item.uuid, item.mapUrl].filter(Boolean).map((key) => [String(key).toLowerCase(), item])),
      );
      this.assets.agents = new Map((agents.data || []).map((item) => [String(item.uuid).toLowerCase(), item]));
      this.assets.ranks = new Map(
        (((tiers.data || []).at(-1) || {}).tiers || []).map((item) => [Number(item.tier), item]),
      );
      this.assets.fetchedAt = Date.now();
    } catch (error) {
      this.log("warning", "live_assets_unavailable", { error: String(error) });
    }
  }

  async ensurePlayerNames(members) {
    const ids = members.map((member) => String(member.Subject || "")).filter(Boolean);
    const missing = ids.filter((id) => !this.playerNames.has(id));
    if (!missing.length) return;
    try {
      const response = await this.pd("PUT", "/name-service/v2/players", missing);
      for (const player of Array.isArray(response) ? response : []) {
        const id = String(player.Subject || "");
        if (id) {
          this.playerNames.set(id, {
            game_name: String(player.GameName || ""),
            tag_line: String(player.TagLine || ""),
          });
        }
      }
    } catch (error) {
      this.log("warning", "party_names_unavailable", { error: String(error) });
    }
  }

  close() {
    if (this.localSocket) this.localSocket.close();
    this.localSocket = null;
    this.context = null;
  }
}

function readLockfile() {
  const lockfilePath = path.join(process.env.LOCALAPPDATA || "", "Riot Games", "Riot Client", "Config", "lockfile");
  if (!fs.existsSync(lockfilePath)) throw new Error("Abra o Riot Client e o VALORANT.");
  const [name, pid, port, password, protocol] = fs.readFileSync(lockfilePath, "utf8").trim().split(":", 5);
  if (!password || !port) throw new Error("O lockfile do Riot Client está inválido.");
  return { name, pid: Number(pid), port: Number(port), password, protocol };
}

function localRequest(lockfile, method, apiPath, body = null) {
  return new Promise((resolve, reject) => {
    const authorization = Buffer.from(`riot:${lockfile.password}`).toString("base64");
    const encoded = body ? Buffer.from(JSON.stringify(body)) : null;
    const request = https.request(
      {
        hostname: "127.0.0.1",
        port: lockfile.port,
        path: apiPath,
        method,
        rejectUnauthorized: false,
        timeout: 6000,
        headers: {
          Authorization: `Basic ${authorization}`,
          Accept: "application/json",
          "User-Agent": "",
          ...(encoded ? { "Content-Type": "application/json", "Content-Length": encoded.length } : {}),
        },
      },
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          if ((response.statusCode || 500) >= 400) {
            const error = new Error(`A API local respondeu HTTP ${response.statusCode}.`);
            error.status = response.statusCode;
            reject(error);
            return;
          }
          try {
            resolve(text ? JSON.parse(text) : {});
          } catch {
            reject(new Error("A API local devolveu uma resposta inválida."));
          }
        });
      },
    );
    request.on("timeout", () => request.destroy(new Error("A Riot demorou para responder.")));
    request.on("error", reject);
    if (encoded) request.write(encoded);
    request.end();
  });
}

async function optionalLocalRequest(lockfile, apiPath, request = localRequest) {
  try {
    return await request(lockfile, "GET", apiPath);
  } catch (error) {
    if (error?.status === 404) return {};
    throw error;
  }
}

function parseSessions(data) {
  const session = Object.values(data || {}).find((value) => value?.productId === "valorant");
  const result = {};
  for (const argument of session?.launchConfiguration?.arguments || []) {
    if (typeof argument !== "string" || !argument.includes("=")) continue;
    const [key, ...rest] = argument.split("=");
    const normalized = key.replace(/^-+/, "").toLowerCase();
    if (normalized === "ares-deployment") result.region = rest.join("=");
    if (["ares-shard", "ares-platform"].includes(normalized)) result.shard = rest.join("=");
  }
  if (session?.version) result.clientVersion = session.version;
  return result;
}

function parseShooterLog() {
  const file = path.join(process.env.LOCALAPPDATA || "", "VALORANT", "Saved", "Logs", "ShooterGame.log");
  if (!fs.existsSync(file)) return {};
  try {
    const stats = fs.statSync(file);
    const size = Math.min(stats.size, 12 * 1024 * 1024);
    const descriptor = fs.openSync(file, "r");
    const buffer = Buffer.alloc(size);
    fs.readSync(descriptor, buffer, 0, size, stats.size - size);
    fs.closeSync(descriptor);
    const text = buffer.toString("utf8");
    const regions = [...text.matchAll(/https:\/\/glz-(.+?)-1\.(.+?)\.a\.pvp\.net/gi)];
    const versions = [...text.matchAll(/CI server version: ([^\r\n]+)/g)];
    return {
      ...(regions.length ? { region: regions.at(-1)[1], shard: regions.at(-1)[2] } : {}),
      ...(versions.length ? { clientVersion: versions.at(-1)[1].trim().replace(/^(release-\d+\.\d+-)/, "$1shipping-") } : {}),
    };
  } catch {
    return {};
  }
}

function defaultCapabilities() {
  return { party: false, agent: false, chat: false, leave: false, match_accept: false, swagger_detected: false };
}

function opaqueId(value) {
  return value ? createHash("sha256").update(value).digest("hex").slice(0, 20) : "";
}

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function rankInfo(ranks, value) {
  const item = ranks.get(Number(value));
  return item
    ? {
        tier: Number(item.tier),
        name: String(item.tierName || ""),
        icon: String(item.largeIcon || item.smallIcon || ""),
      }
    : { tier: numberOrNull(value), name: "", icon: "" };
}

function parseRiotDate(value) {
  if (!value) return null;
  const parsed = typeof value === "number" ? new Date(value) : new Date(String(value));
  return Number.isNaN(parsed.getTime()) ? null : parsed.toISOString();
}

function channelName(kind) {
  return { party: "Grupo", pregame: "Seleção", team: "Equipe" }[kind] || "Chat";
}

function observedChange(command, before, after) {
  if (command.command === "party.join_queue") return after.phase === "queue";
  if (command.command === "party.leave_queue") return after.phase !== "queue";
  if (command.command === "party.change_queue") return after.state?.queue?.id === command.payload.queue_id;
  if (command.command === "party.set_ready") {
    const selfId = after.state?.account_id;
    return after.state?.party?.members?.some((item) => item.id === selfId && item.is_ready === command.payload.ready) || false;
  }
  if (command.command === "pregame.select_agent" || command.command === "pregame.lock_agent") {
    const self = after.state?.agents?.find((item) => item.is_self);
    return Boolean(
      self && self.agent?.id === command.payload.agent_id &&
      (command.command !== "pregame.lock_agent" || self.locked),
    );
  }
  if (command.command === "current_game.leave") return after.phase !== "in_game";
  return null;
}

function safeCommandResponse(command, response) {
  if (command === "party.generate_code") {
    return { invite_code: String(response?.InviteCode || response?.inviteCode || "") };
  }
  return {};
}

function commandError(message, code) {
  const error = new Error(message);
  error.code = code;
  return error;
}

function friendlyError(error) {
  const message = String(error?.message || error || "Falha desconhecida.");
  return message.replace(/Bearer\s+\S+/gi, "Bearer [REDACTED]").slice(0, 400);
}

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

module.exports = { RiotLiveBridge, opaqueId, observedChange, optionalLocalRequest };
