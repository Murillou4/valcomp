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
        borderRadius: BorderRadius.circular(8),
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
            onPressed: () => openUpdateDownload(context, info),
            child: const Text('Baixar'),
          ),
        ],
      ),
    );
  }
}

Future<void> showUpdatePrompt(BuildContext context, UpdateInfo info) {
  return showDialog<void>(
    context: context,
    useRootNavigator: true,
    builder: (dialogContext) => AlertDialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      icon: const Icon(
        Icons.system_update_alt_rounded,
        color: ValcompColors.red,
        size: 32,
      ),
      title: const Text('Nova versão disponível'),
      content: Text(
        'A versão ${info.latestLabel} do Valcomp já pode ser instalada.',
        textAlign: TextAlign.center,
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(dialogContext),
          child: const Text('Depois'),
        ),
        FilledButton.icon(
          onPressed: () {
            Navigator.pop(dialogContext);
            openUpdateDownload(context, info);
          },
          icon: const Icon(Icons.download_rounded),
          label: const Text('Baixar agora'),
        ),
      ],
    ),
  );
}

Future<void> openUpdateDownload(BuildContext context, UpdateInfo info) async {
  final opened = await launchUrl(
    Uri.parse(info.downloadUrl),
    mode: LaunchMode.externalApplication,
  );
  if (!opened && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Não foi possível abrir o download.')),
    );
  }
}
