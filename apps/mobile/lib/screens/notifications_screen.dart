import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'wishlist_screen.dart';

class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    return Scaffold(
      body: SafeArea(
        child: PageFrame(
          bottomPadding: 32,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AppPageHeader(
                title: 'Alertas',
                subtitle: '${state.watches.length} skins monitoradas',
                trailing: IconButton(
                  onPressed: () => Navigator.push(
                    context,
                    valcompRoute(const WishlistScreen()),
                  ),
                  style: IconButton.styleFrom(
                    backgroundColor: ValcompColors.red,
                    foregroundColor: Colors.white,
                    fixedSize: const Size(48, 48),
                  ),
                  icon: const Icon(Icons.add_rounded),
                ),
              ),
              const SizedBox(height: 28),
              Container(
                width: double.infinity,
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: ValcompColors.surface,
                  borderRadius: BorderRadius.circular(22),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        color: ValcompColors.red.withValues(alpha: 0.13),
                        borderRadius: BorderRadius.circular(15),
                      ),
                      child: const Icon(
                        Icons.notifications_active_outlined,
                        color: ValcompColors.red,
                      ),
                    ),
                    const SizedBox(width: 14),
                    const Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Verificação automática',
                            style: TextStyle(fontWeight: FontWeight.w800),
                          ),
                          SizedBox(height: 3),
                          Text(
                            'O servidor compara sua wishlist com cada rotação consultada.',
                            style: TextStyle(
                              color: ValcompColors.muted,
                              fontSize: 12,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              const SectionHeader(title: 'Histórico'),
              const SizedBox(height: 10),
              if (state.deliveries.isEmpty)
                EmptyCard(
                  icon: Icons.notifications_none_rounded,
                  title: 'Nenhum alerta enviado',
                  body: state.watches.isEmpty
                      ? 'Adicione skins à wishlist para começar.'
                      : 'Você será avisado quando uma skin monitorada aparecer.',
                  action: 'Abrir wishlist',
                  onAction: () => Navigator.push(
                    context,
                    valcompRoute(const WishlistScreen()),
                  ),
                )
              else
                ...state.deliveries.map(
                  (delivery) => Container(
                    margin: const EdgeInsets.only(bottom: 10),
                    padding: const EdgeInsets.all(17),
                    decoration: BoxDecoration(
                      color: ValcompColors.surface,
                      borderRadius: BorderRadius.circular(19),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          delivery.status == 'sent'
                              ? Icons.check_circle_outline_rounded
                              : Icons.error_outline_rounded,
                          color: delivery.status == 'sent'
                              ? ValcompColors.green
                              : ValcompColors.amber,
                        ),
                        const SizedBox(width: 13),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                delivery.itemName,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                              Text(
                                '${delivery.source == 'night_market' ? 'Mercado Noturno' : 'Loja diária'} • ${_date(delivery.sentAt)}',
                                style: const TextStyle(
                                  color: ValcompColors.muted,
                                  fontSize: 12,
                                ),
                              ),
                            ],
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
    );
  }
}

String _date(DateTime? value) => value == null
    ? 'data indisponível'
    : DateFormat("dd/MM 'às' HH:mm", 'pt_BR').format(value.toLocal());
