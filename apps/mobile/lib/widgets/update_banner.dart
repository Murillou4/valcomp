import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/update_service.dart';
import '../core/theme.dart';

class UpdateBanner extends StatelessWidget {
  const UpdateBanner({super.key, required this.info});

  final UpdateInfo info;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
      decoration: BoxDecoration(
        color: ValcompColors.red.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: ValcompColors.red.withValues(alpha: 0.28)),
      ),
      child: Row(
        children: [
          const Icon(Icons.system_update_alt_rounded, color: ValcompColors.red),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              'Atualização disponível: ${info.latestLabel}',
              style: const TextStyle(
                color: ValcompColors.text,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          TextButton(
            onPressed: () => launchUrl(
              Uri.parse(info.downloadUrl),
              mode: LaunchMode.externalApplication,
            ),
            child: const Text('Baixar'),
          ),
        ],
      ),
    );
  }
}
