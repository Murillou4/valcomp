import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../core/models.dart';
import '../core/theme.dart';

const tierColors = <String, Color>{
  '12683d76-48d7-84a3-4e09-6985794f0445': Color(0xFF5A9FE2),
  '0cebb8be-46d7-c12a-d306-e9907bfc5a25': Color(0xFF009587),
  '60bca009-4182-7998-dee7-b8a2558dc369': Color(0xFFD1548D),
  'e046854e-406c-37f4-6607-19a9ba8426fc': Color(0xFFF5955B),
  '411e4a55-4e59-7757-41f0-86a53f101bb5': Color(0xFFFAD663),
};

const tierIcons = <String, String>{
  '12683d76-48d7-84a3-4e09-6985794f0445':
      'https://media.valorant-api.com/contenttiers/12683d76-48d7-84a3-4e09-6985794f0445/displayicon.png',
  '0cebb8be-46d7-c12a-d306-e9907bfc5a25':
      'https://media.valorant-api.com/contenttiers/0cebb8be-46d7-c12a-d306-e9907bfc5a25/displayicon.png',
  '60bca009-4182-7998-dee7-b8a2558dc369':
      'https://media.valorant-api.com/contenttiers/60bca009-4182-7998-dee7-b8a2558dc369/displayicon.png',
  'e046854e-406c-37f4-6607-19a9ba8426fc':
      'https://media.valorant-api.com/contenttiers/e046854e-406c-37f4-6607-19a9ba8426fc/displayicon.png',
  '411e4a55-4e59-7757-41f0-86a53f101bb5':
      'https://media.valorant-api.com/contenttiers/411e4a55-4e59-7757-41f0-86a53f101bb5/displayicon.png',
};

class StoreItemCard extends StatelessWidget {
  const StoreItemCard({super.key, required this.item, this.onTap});

  final StoreItem item;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final color = tierColors[item.tier] ?? const Color(0xFF44505D);
    final tierIcon = tierIcons[item.tier];
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(24),
        child: Ink(
          height: 132,
          decoration: BoxDecoration(
            color: ValcompColors.surface,
            borderRadius: BorderRadius.circular(24),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(24),
            child: Stack(
              fit: StackFit.expand,
              children: [
                if (tierIcon != null)
                  Positioned(
                    left: -16,
                    bottom: -35,
                    child: Opacity(
                      opacity: 0.17,
                      child: CachedNetworkImage(
                        imageUrl: tierIcon,
                        width: 145,
                        height: 145,
                        fit: BoxFit.contain,
                      ),
                    ),
                  ),
                DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.bottomCenter,
                      end: Alignment.topCenter,
                      colors: [
                        color.withValues(alpha: 0.94),
                        color.withValues(alpha: 0.18),
                        Colors.transparent,
                      ],
                      stops: const [0, 0.52, 0.88],
                    ),
                  ),
                ),
                if (item.image.isNotEmpty)
                  Positioned(
                    left: 78,
                    right: 32,
                    top: 17,
                    height: 72,
                    child: CachedNetworkImage(
                      imageUrl: item.image,
                      fit: BoxFit.contain,
                      placeholder: (_, __) => const SizedBox.shrink(),
                      errorWidget: (_, __, ___) => const SizedBox.shrink(),
                    ),
                  ),
                Positioned(
                  left: 22,
                  right: 128,
                  bottom: 16,
                  child: Text(
                    item.name.toUpperCase(),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 15,
                      height: 1.05,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 0.1,
                    ),
                  ),
                ),
                if (item.price != null)
                  Positioned(
                    top: 16,
                    right: 20,
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: Colors.black.withValues(alpha: 0.34),
                        borderRadius: BorderRadius.circular(14),
                      ),
                      child: Row(
                        children: [
                          Image.asset(
                            'assets/images/vp-symbol.png',
                            width: 16,
                            height: 16,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            '${item.price}',
                            style: const TextStyle(
                              fontWeight: FontWeight.w800,
                              color: Colors.white,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
