import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

class LinkScreen extends StatefulWidget {
  const LinkScreen({super.key});

  @override
  State<LinkScreen> createState() => _LinkScreenState();
}

class _LinkScreenState extends State<LinkScreen> {
  bool _advanced = false;
  bool _checking = false;
  bool _successHandled = false;
  String _linkError = '';
  String _linkErrorDetails = '';
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (context.read<AppController>().linkCode.isNotEmpty) {
        _startPolling();
      }
    });
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    final busy = state.loading || _checking;
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset(
            'assets/images/hero-agent.png',
            fit: BoxFit.cover,
            alignment: Alignment.topCenter,
          ),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0xAA090E15),
                  Color(0xF2090E15),
                  ValcompColors.background,
                ],
                stops: [0, 0.48, 0.82],
              ),
            ),
          ),
          SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final compact = constraints.maxHeight < 700;
                final content = Padding(
                  padding: EdgeInsets.fromLTRB(
                    24,
                    compact ? 14 : 24,
                    24,
                    compact ? 16 : 24,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      AppPageHeader(
                        title: 'Vincular conta',
                        subtitle: 'Uma única vez no seu computador',
                        trailing: Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 11,
                            vertical: 7,
                          ),
                          decoration: BoxDecoration(
                            color: ValcompColors.green.withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(99),
                          ),
                          child: const Text(
                            'SEGURO',
                            style: TextStyle(
                              color: ValcompColors.green,
                              fontSize: 11,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ),
                      ),
                      const Spacer(),
                      Text(
                        state.relinkRequired
                            ? 'Reconecte sua sessão Riot.'
                            : 'Leve sua loja para o celular.',
                        style: TextStyle(
                          fontSize: compact ? 28 : 34,
                          height: 1.03,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        'Gere o código abaixo e digite-o no Valcomp Companion, no PC onde você joga.',
                        style: TextStyle(
                          color: Color(0xCCFFFFFF),
                          fontSize: 15,
                          height: 1.4,
                        ),
                      ),
                      SizedBox(height: compact ? 18 : 26),
                      Container(
                        width: double.infinity,
                        padding: EdgeInsets.all(compact ? 18 : 22),
                        decoration: BoxDecoration(
                          color: ValcompColors.surface.withValues(alpha: 0.96),
                          borderRadius: BorderRadius.circular(26),
                          border: Border.all(color: ValcompColors.border),
                        ),
                        child: Column(
                          children: [
                            if (busy) ...[
                              const LinearProgressIndicator(
                                minHeight: 3,
                                color: ValcompColors.red,
                                backgroundColor: ValcompColors.border,
                              ),
                              const SizedBox(height: 16),
                            ],
                            if (state.linkCode.isEmpty)
                              const Text(
                                'Seu código aparecerá aqui',
                                style: TextStyle(
                                  color: ValcompColors.muted,
                                  fontWeight: FontWeight.w700,
                                ),
                              )
                            else
                              InkWell(
                                onTap: () async {
                                  await Clipboard.setData(
                                    ClipboardData(text: state.linkCode),
                                  );
                                  if (!context.mounted) return;
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                      content: Text('Código copiado.'),
                                    ),
                                  );
                                },
                                child: Text(
                                  _spacedCode(state.linkCode),
                                  style: TextStyle(
                                    fontSize: compact ? 32 : 39,
                                    letterSpacing: 4,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                              ),
                            const SizedBox(height: 8),
                            Text(
                              state.linkCode.isEmpty
                                  ? 'Válido por 10 minutos'
                                  : 'Toque no código para copiar',
                              style: const TextStyle(
                                color: ValcompColors.muted,
                                fontSize: 12,
                              ),
                            ),
                            const SizedBox(height: 18),
                            FilledButton(
                              onPressed: busy
                                  ? null
                                  : () async {
                                      await state.generateLinkCode();
                                      if (!context.mounted) return;
                                      if (state.linkCode.isNotEmpty) {
                                        _linkError = '';
                                        _linkErrorDetails = '';
                                        _startPolling();
                                      }
                                      setState(() {});
                                    },
                              child: Text(
                                state.linkCode.isEmpty
                                    ? 'Gerar código de vínculo'
                                    : 'Gerar novo código',
                              ),
                            ),
                          ],
                        ),
                      ),
                      if (state.linkCode.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        _AutoCheckNotice(checking: _checking),
                      ],
                      if (_linkError.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        ErrorNotice(
                          message: _linkError,
                          details: _linkErrorDetails,
                        ),
                      ],
                      SizedBox(height: compact ? 14 : 20),
                      _Step(
                        number: '1',
                        text: 'Abra o Riot Client ou VALORANT no PC.',
                      ),
                      const _Step(
                        number: '2',
                        text: 'Abra o Valcomp Companion e detecte sua sessão.',
                      ),
                      const _Step(
                        number: '3',
                        text: 'Digite o código e confirme o vínculo.',
                      ),
                      const SizedBox(height: 8),
                      TextButton(
                        onPressed: () => setState(() => _advanced = !_advanced),
                        child: Text(
                          _advanced
                              ? 'Ocultar opções avançadas'
                              : 'Mostrar opções avançadas',
                        ),
                      ),
                      if (_advanced)
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(13),
                          decoration: BoxDecoration(
                            color: ValcompColors.surface,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: SelectableText(
                            state.api.baseUrl,
                            style: const TextStyle(
                              color: ValcompColors.muted,
                              fontSize: 12,
                            ),
                          ),
                        ),
                      const SizedBox(height: 4),
                      OutlinedButton(
                        onPressed: busy
                            ? null
                            : () => _verifyLinked(manual: true),
                        style: OutlinedButton.styleFrom(
                          minimumSize: const Size.fromHeight(48),
                          side: const BorderSide(color: ValcompColors.border),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                        ),
                        child: _checking
                            ? const SizedBox(
                                height: 18,
                                width: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2.3,
                                  color: ValcompColors.text,
                                ),
                              )
                            : const Text('Já vinculei, verificar agora'),
                      ),
                    ],
                  ),
                );
                return Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 480),
                    child: compact
                        ? SingleChildScrollView(
                            physics: const BouncingScrollPhysics(),
                            child: ConstrainedBox(
                              constraints: BoxConstraints(
                                minHeight: constraints.maxHeight,
                              ),
                              child: content,
                            ),
                          )
                        : content,
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) {
      _verifyLinked(manual: false);
    });
    unawaited(_verifyLinked(manual: false));
  }

  Future<void> _verifyLinked({required bool manual}) async {
    if (_checking || _successHandled) return;
    setState(() {
      _checking = true;
      if (manual) {
        _linkError = '';
        _linkErrorDetails = '';
      }
    });
    try {
      final linked = await context.read<AppController>().checkRiotLink();
      if (!mounted) return;
      if (linked) {
        _finishWithSuccess();
      } else if (manual) {
        setState(() {
          _linkError =
              'Ainda não encontrei uma sessão Riot válida. Confirme se o Companion mostrou sucesso e tente de novo.';
          _linkErrorDetails =
              'GET /me ou GET /valorant/store/daily ainda não confirmou uma sessão Riot utilizável.';
        });
      }
    } on Object catch (error) {
      if (!mounted) return;
      if (manual) {
        final state = context.read<AppController>();
        setState(() {
          _linkError = state.error.isNotEmpty
              ? state.error
              : 'Não consegui validar a sessão Riot agora. Detecte novamente no Companion e tente outro código.';
          _linkErrorDetails = state.errorDetails.isNotEmpty
              ? state.errorDetails
              : error.toString();
        });
      }
    } finally {
      if (mounted && !_successHandled) {
        setState(() => _checking = false);
      }
    }
  }

  void _finishWithSuccess() {
    if (_successHandled) return;
    _successHandled = true;
    _pollTimer?.cancel();
    final state = context.read<AppController>();
    state.selectTab(1);
    unawaited(state.refreshAll(silent: true));
    final navigator = Navigator.of(context);
    final rootContext = navigator.context;
    if (navigator.canPop()) navigator.pop();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!rootContext.mounted) return;
      showDialog<void>(
        context: rootContext,
        builder: (context) => AlertDialog(
          backgroundColor: ValcompColors.surface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(24),
            side: const BorderSide(color: ValcompColors.border),
          ),
          title: const Text('Conta Riot vinculada'),
          content: const Text(
            'Pronto. Agora o Valcomp vai buscar sua loja, Mercado Noturno e dados da conta automaticamente.',
          ),
          actions: [
            FilledButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Ir para Home'),
            ),
          ],
        ),
      );
    });
  }
}

class _AutoCheckNotice extends StatelessWidget {
  const _AutoCheckNotice({required this.checking});

  final bool checking;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: ValcompColors.green.withValues(alpha: 0.09),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: ValcompColors.green.withValues(alpha: 0.24)),
      ),
      child: Row(
        children: [
          if (checking)
            const SizedBox(
              width: 17,
              height: 17,
              child: CircularProgressIndicator(
                strokeWidth: 2.2,
                color: ValcompColors.green,
              ),
            )
          else
            const Icon(
              Icons.sync_rounded,
              color: ValcompColors.green,
              size: 19,
            ),
          const SizedBox(width: 10),
          const Expanded(
            child: Text(
              'Assim que o Companion confirmar no PC, eu volto para a Home sozinho.',
              style: TextStyle(
                color: ValcompColors.green,
                fontSize: 12,
                fontWeight: FontWeight.w800,
                height: 1.25,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Step extends StatelessWidget {
  const _Step({required this.number, required this.text});

  final String number;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Container(
            width: 28,
            height: 28,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: ValcompColors.red.withValues(alpha: 0.13),
              shape: BoxShape.circle,
            ),
            child: Text(
              number,
              style: const TextStyle(
                color: ValcompColors.red,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
    );
  }
}

String _spacedCode(String value) {
  if (value.length <= 3) return value;
  return '${value.substring(0, 3)} ${value.substring(3)}';
}
