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
  });

  final String gameName;
  final String tagLine;
  final String region;
  final String shard;

  String get riotId => tagLine.isEmpty ? gameName : '$gameName#$tagLine';

  factory RiotAccount.fromJson(Map<String, dynamic> json) => RiotAccount(
    gameName: _string(json['game_name']),
    tagLine: _string(json['tag_line']),
    region: _string(json['region']),
    shard: _string(json['shard']),
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
  });

  final String itemId;
  final String name;
  final String displayIcon;
  final String fullRender;
  final String tier;
  final String source;
  final int? price;

  String get image => fullRender.isNotEmpty ? fullRender : displayIcon;

  factory StoreItem.fromJson(Map<String, dynamic> json) => StoreItem(
    itemId: _string(json['item_id']),
    name: _string(json['name']),
    displayIcon: _string(json['display_icon']),
    fullRender: _string(json['full_render']),
    tier: _string(json['tier']),
    source: _string(json['source']),
    price: _nullableInt(json['price']),
  );
}

class DailyStore {
  const DailyStore({
    required this.items,
    required this.nightMarket,
    this.expiresAt,
    this.secondsRemaining,
  });

  final List<StoreItem> items;
  final List<StoreItem> nightMarket;
  final DateTime? expiresAt;
  final int? secondsRemaining;

  factory DailyStore.fromJson(Map<String, dynamic> json) => DailyStore(
    items: _list(
      json['items'],
    ).map((e) => StoreItem.fromJson(_map(e))).toList(),
    nightMarket: _list(
      json['night_market'],
    ).map((e) => StoreItem.fromJson(_map(e))).toList(),
    expiresAt: DateTime.tryParse(_string(json['expires_at'])),
    secondsRemaining: _nullableInt(json['seconds_remaining']),
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
