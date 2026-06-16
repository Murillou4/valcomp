import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'link_screen.dart';

class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key});

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  late final TextEditingController _name;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(
      text: context.read<AppController>().me?.profile.displayName ?? '',
    );
  }

  @override
  void dispose() {
    _name.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    final riot = state.me?.riotAccount;
    return Scaffold(
      body: SafeArea(
        child: PageFrame(
          bottomPadding: 32,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const AppPageHeader(
                title: 'Conta',
                subtitle: 'Perfil e conexão Riot',
              ),
              const SizedBox(height: 30),
              Center(
                child: Container(
                  width: 92,
                  height: 92,
                  decoration: BoxDecoration(
                    color: ValcompColors.surfaceRaised,
                    borderRadius: BorderRadius.circular(26),
                    border: Border.all(
                      color: ValcompColors.red.withValues(alpha: 0.45),
                      width: 2,
                    ),
                  ),
                  child: const Icon(Icons.person_outline_rounded, size: 45),
                ),
              ),
              const SizedBox(height: 26),
              TextField(
                controller: _name,
                textCapitalization: TextCapitalization.words,
                decoration: const InputDecoration(
                  labelText: 'Nome no app',
                  hintText: 'Seu nome aqui',
                ),
              ),
              const SizedBox(height: 12),
              FilledButton(
                onPressed: state.loading
                    ? null
                    : () async {
                        await state.updateProfile(_name.text);
                        if (!context.mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('Nome atualizado.')),
                        );
                      },
                child: const Text('Salvar perfil'),
              ),
              const SizedBox(height: 30),
              const SectionHeader(title: 'Conta Riot'),
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: ValcompColors.surface,
                  borderRadius: BorderRadius.circular(22),
                  border: Border.all(color: ValcompColors.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          riot == null
                              ? Icons.link_off_rounded
                              : Icons.verified_rounded,
                          color: riot == null
                              ? ValcompColors.amber
                              : ValcompColors.green,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            riot?.riotId ?? 'Nenhuma conta vinculada',
                            style: const TextStyle(
                              fontSize: 17,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ],
                    ),
                    if (riot != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        '${riot.region.toUpperCase()} • shard ${riot.shard.toUpperCase()}',
                        style: const TextStyle(color: ValcompColors.muted),
                      ),
                    ],
                    const SizedBox(height: 16),
                    OutlinedButton(
                      onPressed: () => Navigator.push(
                        context,
                        valcompRoute(const LinkScreen()),
                      ),
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(48),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        side: const BorderSide(color: ValcompColors.border),
                      ),
                      child: Text(
                        riot == null
                            ? 'Vincular conta Riot'
                            : 'Vincular novamente',
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 30),
              const SectionHeader(title: 'Diagnóstico'),
              const SizedBox(height: 10),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: ValcompColors.surface,
                  borderRadius: BorderRadius.circular(22),
                  border: Border.all(color: ValcompColors.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(
                          Icons.monitor_heart_outlined,
                          color: ValcompColors.green,
                        ),
                        SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Relatório técnico seguro',
                            style: TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Reúne os últimos eventos deste aparelho e do servidor. Tokens, cookies e identificadores privados são removidos.',
                      style: TextStyle(color: ValcompColors.muted, height: 1.4),
                    ),
                    const SizedBox(height: 16),
                    OutlinedButton.icon(
                      onPressed: () async {
                        final report = await state.exportDiagnostics();
                        await Clipboard.setData(ClipboardData(text: report));
                        if (!context.mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              'Relatório copiado. Pode enviar ele inteiro.',
                            ),
                          ),
                        );
                      },
                      style: OutlinedButton.styleFrom(
                        minimumSize: const Size.fromHeight(48),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        side: const BorderSide(color: ValcompColors.border),
                      ),
                      icon: const Icon(Icons.copy_all_rounded),
                      label: const Text('Copiar relatório completo'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 30),
              OutlinedButton.icon(
                onPressed: () async {
                  await state.logout();
                  if (context.mounted) {
                    Navigator.popUntil(context, (route) => route.isFirst);
                  }
                },
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(54),
                  foregroundColor: ValcompColors.red,
                  side: const BorderSide(color: ValcompColors.red),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(17),
                  ),
                ),
                icon: const Icon(Icons.logout_rounded),
                label: const Text('Sair da conta'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
