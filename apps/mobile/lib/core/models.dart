class Profile {
  const Profile({
    required this.userId,
    required this.displayName,
    required this.avatarUrl,
  });

  final String userId;
  final String displayName;
  final String avatarUrl;

  factory Profile.fromJson(Map<String, dynamic> json) => Profile(
    userId: _string(json['user_id']),
    displayName: _string(json['display_name']),
    avatarUrl: _string(json['avatar_url']),
  );
}

class RiotAccount {
  const RiotAccount({
    required this.gameName,
    required this.tagLine,
    required this.region,
    required this.shard,
    this.linkedAt,
  });

  final String gameName;
  final String tagLine;
  final String region;
  final String shard;
  final DateTime? linkedAt;

  String get riotId => tagLine.isEmpty ? gameName : '$gameName#$tagLine';

  factory RiotAccount.fromJson(Map<String, dynamic> json) => RiotAccount(
    gameName: _string(json['game_name']),
    tagLine: _string(json['tag_line']),
    region: _string(json['region']),
    shard: _string(json['shard']),
    linkedAt: DateTime.tryParse(_string(json['linked_at'])),
  );
}

class MeData {
  const MeData({required this.profile, this.riotAccount});

  final Profile profile;
  final RiotAccount? riotAccount;

  factory MeData.fromJson(Map<String, dynamic> json) => MeData(
    profile: Profile.fromJson(_map(json['profile'])),
    riotAccount: json['riot_account'] is Map
        ? RiotAccount.fromJson(_map(json['riot_account']))
        : null,
  );
}

class StoreItem {
  const StoreItem({
    required this.itemId,
    required this.name,
    required this.displayIcon,
    required this.fullRender,
    required this.tier,
    required this.source,
    this.price,
    this.originalPrice,
    this.discountPercent,
    this.isSeen,
    this.bonusOfferId = '',
  });

  final String itemId;
  final String name;
  final String displayIcon;
  final String fullRender;
  final String tier;
  final String source;
  final int? price;
  final int? originalPrice;
  final int? discountPercent;
  final bool? isSeen;
  final String bonusOfferId;

  String get image => fullRender.isNotEmpty ? fullRender : displayIcon;

  factory StoreItem.fromJson(Map<String, dynamic> json) => StoreItem(
    itemId: _string(json['item_id']),
    name: _string(json['name']),
    displayIcon: _string(json['display_icon']),
    fullRender: _string(json['full_render']),
    tier: _string(json['tier']),
    source: _string(json['source']),
    price: _nullableInt(json['price']),
    originalPrice: _nullableInt(json['original_price']),
    discountPercent: _nullableInt(json['discount_percent']),
    isSeen: json['is_seen'] is bool ? json['is_seen'] as bool : null,
    bonusOfferId: _string(json['bonus_offer_id']),
  );
}

class DailyStore {
  const DailyStore({
    required this.items,
    required this.nightMarket,
    this.expiresAt,
    this.secondsRemaining,
    this.nightMarketExpiresAt,
    this.nightMarketSecondsRemaining,
    this.nightMarketActive = false,
  });

  final List<StoreItem> items;
  final List<StoreItem> nightMarket;
  final DateTime? expiresAt;
  final int? secondsRemaining;
  final DateTime? nightMarketExpiresAt;
  final int? nightMarketSecondsRemaining;
  final bool nightMarketActive;

  factory DailyStore.fromJson(Map<String, dynamic> json) => DailyStore(
    items: _list(
      json['items'],
    ).map((e) => StoreItem.fromJson(_map(e))).toList(),
    nightMarket: _list(
      json['night_market'],
    ).map((e) => StoreItem.fromJson(_map(e))).toList(),
    expiresAt: DateTime.tryParse(_string(json['expires_at'])),
    secondsRemaining: _nullableInt(json['seconds_remaining']),
    nightMarketExpiresAt: DateTime.tryParse(
      _string(json['night_market_expires_at']),
    ),
    nightMarketSecondsRemaining: _nullableInt(
      json['night_market_seconds_remaining'],
    ),
    nightMarketActive: json['night_market_active'] == true,
  );
}

class NightMarket {
  const NightMarket({
    required this.active,
    required this.items,
    this.expiresAt,
    this.secondsRemaining,
  });

  final bool active;
  final List<StoreItem> items;
  final DateTime? expiresAt;
  final int? secondsRemaining;

  factory NightMarket.fromJson(Map<String, dynamic> json) => NightMarket(
    active: json['active'] == true,
    items: _list(
      json['items'],
    ).map((item) => StoreItem.fromJson(_map(item))).toList(),
    expiresAt: DateTime.tryParse(_string(json['expires_at'])),
    secondsRemaining: _nullableInt(json['seconds_remaining']),
  );

  factory NightMarket.fromDaily(DailyStore store) => NightMarket(
    active: store.nightMarketActive,
    items: store.nightMarket,
    expiresAt: store.nightMarketExpiresAt,
    secondsRemaining: store.nightMarketSecondsRemaining,
  );
}

class ItemStatus {
  const ItemStatus({
    required this.itemId,
    required this.owned,
    required this.inDailyStore,
    required this.inNightMarket,
    required this.source,
    this.price,
    this.expiresAt,
  });

  final String itemId;
  final bool owned;
  final bool inDailyStore;
  final bool inNightMarket;
  final int? price;
  final DateTime? expiresAt;
  final String source;

  factory ItemStatus.fromJson(Map<String, dynamic> json) => ItemStatus(
    itemId: _string(json['item_id']),
    owned: json['owned'] == true,
    inDailyStore: json['in_daily_store'] == true,
    inNightMarket: json['in_night_market'] == true,
    price: _nullableInt(json['price']),
    expiresAt: DateTime.tryParse(_string(json['expires_at'])),
    source: _string(json['source']),
  );
}

class CompetitiveSummary {
  const CompetitiveSummary({
    required this.tier,
    required this.tierName,
    required this.tierIcon,
    required this.rankedRating,
    required this.rrEarned,
    required this.wins,
    required this.games,
    this.lastMatchAt,
  });

  final int tier;
  final String tierName;
  final String tierIcon;
  final int rankedRating;
  final int rrEarned;
  final int wins;
  final int games;
  final DateTime? lastMatchAt;

  factory CompetitiveSummary.fromJson(Map<String, dynamic> json) =>
      CompetitiveSummary(
        tier: _int(json['tier']),
        tierName: _string(json['tier_name']),
        tierIcon: _string(json['tier_icon']),
        rankedRating: _int(json['ranked_rating']),
        rrEarned: _int(json['rr_earned']),
        wins: _int(json['wins']),
        games: _int(json['games']),
        lastMatchAt: DateTime.tryParse(_string(json['last_match_at'])),
      );
}

class RecentMatch {
  const RecentMatch({
    required this.matchId,
    required this.queueId,
    this.startedAt,
  });

  final String matchId;
  final String queueId;
  final DateTime? startedAt;

  factory RecentMatch.fromJson(Map<String, dynamic> json) => RecentMatch(
    matchId: _string(json['match_id']),
    queueId: _string(json['queue_id']),
    startedAt: DateTime.tryParse(_string(json['started_at'])),
  );
}

class PlayerSummary {
  const PlayerSummary({
    required this.available,
    required this.competitive,
    required this.recentMatches,
    required this.totalMatches,
  });

  final bool available;
  final CompetitiveSummary competitive;
  final List<RecentMatch> recentMatches;
  final int totalMatches;

  factory PlayerSummary.fromJson(Map<String, dynamic> json) => PlayerSummary(
    available: json['available'] == true,
    competitive: CompetitiveSummary.fromJson(_map(json['competitive'])),
    recentMatches: _list(
      json['recent_matches'],
    ).map((e) => RecentMatch.fromJson(_map(e))).toList(),
    totalMatches: _int(json['total_matches']),
  );
}

class MatchDetails {
  const MatchDetails({
    required this.match,
    required this.teams,
    required this.players,
    required this.rounds,
    this.self,
  });

  final MatchInfo match;
  final List<MatchTeam> teams;
  final List<MatchPlayer> players;
  final List<MatchRound> rounds;
  final MatchPlayer? self;

  factory MatchDetails.fromJson(Map<String, dynamic> json) => MatchDetails(
    match: MatchInfo.fromJson(_map(json['match'])),
    teams: _list(
      json['teams'],
    ).map((item) => MatchTeam.fromJson(_map(item))).toList(),
    players: _list(
      json['players'],
    ).map((item) => MatchPlayer.fromJson(_map(item))).toList(),
    rounds: _list(
      json['rounds'],
    ).map((item) => MatchRound.fromJson(_map(item))).toList(),
    self: json['self'] is Map ? MatchPlayer.fromJson(_map(json['self'])) : null,
  );
}

class MatchInfo {
  const MatchInfo({
    required this.matchId,
    required this.mapName,
    required this.mapSplash,
    required this.queueId,
    required this.completionState,
    required this.durationSeconds,
    required this.winningTeam,
    this.startedAt,
  });

  final String matchId;
  final String mapName;
  final String mapSplash;
  final String queueId;
  final String completionState;
  final int durationSeconds;
  final String winningTeam;
  final DateTime? startedAt;

  factory MatchInfo.fromJson(Map<String, dynamic> json) => MatchInfo(
    matchId: _string(json['match_id']),
    mapName: _string(json['map_name']),
    mapSplash: _string(json['map_splash']),
    queueId: _string(json['queue_id']),
    completionState: _string(json['completion_state']),
    durationSeconds: _int(json['duration_seconds']),
    winningTeam: _string(json['winning_team']),
    startedAt: DateTime.tryParse(_string(json['started_at'])),
  );
}

class MatchTeam {
  const MatchTeam({
    required this.teamId,
    required this.won,
    required this.roundsWon,
    required this.roundsPlayed,
  });

  final String teamId;
  final bool won;
  final int roundsWon;
  final int roundsPlayed;

  factory MatchTeam.fromJson(Map<String, dynamic> json) => MatchTeam(
    teamId: _string(json['team_id']),
    won: json['won'] == true,
    roundsWon: _int(json['rounds_won']),
    roundsPlayed: _int(json['rounds_played']),
  );
}

class MatchPlayer {
  const MatchPlayer({
    required this.subject,
    required this.gameName,
    required this.tagLine,
    required this.teamId,
    required this.agentName,
    required this.agentIcon,
    required this.tierName,
    required this.tierIcon,
    required this.accountLevel,
    required this.isSelf,
    required this.stats,
  });

  final String subject;
  final String gameName;
  final String tagLine;
  final String teamId;
  final String agentName;
  final String agentIcon;
  final String tierName;
  final String tierIcon;
  final int accountLevel;
  final bool isSelf;
  final MatchPlayerStats stats;

  String get riotId => tagLine.isEmpty ? gameName : '$gameName#$tagLine';

  factory MatchPlayer.fromJson(Map<String, dynamic> json) => MatchPlayer(
    subject: _string(json['subject']),
    gameName: _string(json['game_name']),
    tagLine: _string(json['tag_line']),
    teamId: _string(json['team_id']),
    agentName: _string(json['agent_name']),
    agentIcon: _string(json['agent_icon']),
    tierName: _string(json['competitive_tier_name']),
    tierIcon: _string(json['competitive_tier_icon']),
    accountLevel: _int(json['account_level']),
    isSelf: json['is_self'] == true,
    stats: MatchPlayerStats.fromJson(_map(json['stats'])),
  );
}

class MatchPlayerStats {
  const MatchPlayerStats({
    required this.score,
    required this.roundsPlayed,
    required this.kills,
    required this.deaths,
    required this.assists,
    required this.acs,
    required this.kd,
    required this.damage,
    required this.averageDamagePerRound,
    required this.headshotPercent,
  });

  final int score;
  final int roundsPlayed;
  final int kills;
  final int deaths;
  final int assists;
  final double acs;
  final double kd;
  final int damage;
  final double averageDamagePerRound;
  final double headshotPercent;

  factory MatchPlayerStats.fromJson(Map<String, dynamic> json) =>
      MatchPlayerStats(
        score: _int(json['score']),
        roundsPlayed: _int(json['rounds_played']),
        kills: _int(json['kills']),
        deaths: _int(json['deaths']),
        assists: _int(json['assists']),
        acs: _double(json['acs']),
        kd: _double(json['kd']),
        damage: _int(json['damage']),
        averageDamagePerRound: _double(json['average_damage_per_round']),
        headshotPercent: _double(json['headshot_percent']),
      );
}

class MatchRound {
  const MatchRound({
    required this.round,
    required this.winningTeam,
    required this.result,
    required this.ceremony,
    required this.plantSite,
  });

  final int round;
  final String winningTeam;
  final String result;
  final String ceremony;
  final String plantSite;

  factory MatchRound.fromJson(Map<String, dynamic> json) => MatchRound(
    round: _int(json['round']),
    winningTeam: _string(json['winning_team']),
    result: _string(json['result']),
    ceremony: _string(json['ceremony']),
    plantSite: _string(json['plant_site']),
  );
}

class SkinWatch {
  const SkinWatch({
    required this.itemId,
    required this.itemName,
    required this.displayIcon,
    required this.tier,
    required this.notifyEnabled,
  });

  final String itemId;
  final String itemName;
  final String displayIcon;
  final String tier;
  final bool notifyEnabled;

  factory SkinWatch.fromJson(Map<String, dynamic> json) => SkinWatch(
    itemId: _string(json['item_id']),
    itemName: _string(json['item_name']),
    displayIcon: _string(json['display_icon']),
    tier: _string(json['tier']),
    notifyEnabled: json['notify_enabled'] != false,
  );
}

class SkinCatalogItem {
  const SkinCatalogItem({
    required this.itemId,
    required this.name,
    required this.displayIcon,
    required this.tier,
    required this.weaponId,
    required this.weaponName,
    required this.weaponIcon,
    required this.category,
    required this.categoryName,
  });

  final String itemId;
  final String name;
  final String displayIcon;
  final String tier;
  final String weaponId;
  final String weaponName;
  final String weaponIcon;
  final String category;
  final String categoryName;

  factory SkinCatalogItem.fromJson(Map<String, dynamic> json) =>
      SkinCatalogItem(
        itemId: _string(json['item_id']),
        name: _string(json['name']),
        displayIcon: _string(json['display_icon']),
        tier: _string(json['tier']),
        weaponId: _string(json['weapon_id']),
        weaponName: _string(json['weapon_name']),
        weaponIcon: _string(json['weapon_icon']),
        category: _string(json['category']),
        categoryName: _string(json['category_name']),
      );
}

class CatalogFilter {
  const CatalogFilter({
    required this.id,
    required this.name,
    required this.count,
    this.icon = '',
    this.category = '',
    this.color = '',
  });

  final String id;
  final String name;
  final int count;
  final String icon;
  final String category;
  final String color;

  factory CatalogFilter.fromJson(Map<String, dynamic> json) => CatalogFilter(
    id: _string(json['id']),
    name: _string(json['name']),
    count: _int(json['count']),
    icon: _string(json['icon']),
    category: _string(json['category']),
    color: _string(json['color']),
  );
}

class SkinCatalog {
  const SkinCatalog({
    required this.total,
    required this.items,
    required this.categories,
    required this.weapons,
    required this.tiers,
  });

  final int total;
  final List<SkinCatalogItem> items;
  final List<CatalogFilter> categories;
  final List<CatalogFilter> weapons;
  final List<CatalogFilter> tiers;

  factory SkinCatalog.fromJson(Map<String, dynamic> json) {
    final filters = _map(json['filters']);
    return SkinCatalog(
      total: _int(json['total']),
      items: _list(
        json['items'],
      ).map((item) => SkinCatalogItem.fromJson(_map(item))).toList(),
      categories: _list(
        filters['categories'],
      ).map((item) => CatalogFilter.fromJson(_map(item))).toList(),
      weapons: _list(
        filters['weapons'],
      ).map((item) => CatalogFilter.fromJson(_map(item))).toList(),
      tiers: _list(
        filters['tiers'],
      ).map((item) => CatalogFilter.fromJson(_map(item))).toList(),
    );
  }
}

class NotificationDelivery {
  const NotificationDelivery({
    required this.itemName,
    required this.source,
    required this.status,
    required this.sentAt,
  });

  final String itemName;
  final String source;
  final String status;
  final DateTime? sentAt;

  factory NotificationDelivery.fromJson(Map<String, dynamic> json) =>
      NotificationDelivery(
        itemName: _string(json['item_name']),
        source: _string(json['source']),
        status: _string(json['status']),
        sentAt: DateTime.tryParse(_string(json['sent_at'])),
      );
}

Map<String, dynamic> _map(dynamic value) =>
    value is Map ? Map<String, dynamic>.from(value) : <String, dynamic>{};

List<dynamic> _list(dynamic value) => value is List ? value : const [];

String _string(dynamic value) => value?.toString() ?? '';

int _int(dynamic value) => _nullableInt(value) ?? 0;

int? _nullableInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '');
}

double _double(dynamic value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '') ?? 0;
}
