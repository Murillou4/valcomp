import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/app_controller.dart';
import '../core/riot_mobile_auth.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

class RiotMobileLoginScreen extends StatefulWidget {
  const RiotMobileLoginScreen({super.key});

  @override
  State<RiotMobileLoginScreen> createState() => _RiotMobileLoginScreenState();
}

class _RiotMobileLoginScreenState extends State<RiotMobileLoginScreen> {
  InAppWebViewController? _webViewController;
  double _progress = 0;
  bool _submitting = false;
  bool _completed = false;
  String _error = '';
  String _details = '';

  static final WebUri _loginUri = WebUri.uri(
    Uri.https('auth.riotgames.com', '/authorize', {
      'redirect_uri': 'http://localhost/redirect',
      'client_id': 'riot-client',
      'response_type': 'token id_token',
      'nonce': '1',
      'scope': 'openid link ban lol_region account',
    }),
  );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(18, 14, 18, 10),
              child: Row(
                children: [
                  IconButton(
                    onPressed: _submitting
                        ? null
                        : () => Navigator.pop(context),
                    icon: const Icon(Icons.close_rounded),
                    style: IconButton.styleFrom(
                      backgroundColor: ValcompColors.surface,
                      fixedSize: const Size(46, 46),
                    ),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Login Riot',
                          style: TextStyle(
                            fontSize: 23,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        Text(
                          'Opção avançada pelo celular',
                          style: TextStyle(color: ValcompColors.muted),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Recarregar',
                    onPressed: _submitting
                        ? null
                        : () => _webViewController?.loadUrl(
                            urlRequest: URLRequest(url: _loginUri),
                          ),
                    icon: const Icon(Icons.refresh_rounded),
                  ),
                ],
              ),
            ),
            if (_progress < 1 || _submitting)
              LinearProgressIndicator(
                minHeight: 3,
                value: _submitting ? null : _progress.clamp(0, 1),
                color: ValcompColors.red,
                backgroundColor: ValcompColors.border,
              ),
            if (_error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
                child: ErrorNotice(message: _error, details: _details),
              ),
            Expanded(
              child: Stack(
                children: [
                  InAppWebView(
                    initialUrlRequest: URLRequest(url: _loginUri),
                    initialSettings: InAppWebViewSettings(
                      javaScriptEnabled: true,
                      domStorageEnabled: true,
                      thirdPartyCookiesEnabled: true,
                      sharedCookiesEnabled: true,
                      useShouldOverrideUrlLoading: true,
                      supportMultipleWindows: false,
                    ),
                    onWebViewCreated: (controller) {
                      _webViewController = controller;
                    },
                    shouldOverrideUrlLoading: (controller, action) async {
                      final url = action.request.url;
                      if (await _inspectUrl(url)) {
                        return NavigationActionPolicy.CANCEL;
                      }
                      return NavigationActionPolicy.ALLOW;
                    },
                    onLoadStart: (controller, url) {
                      unawaited(_inspectUrl(url));
                    },
                    onUpdateVisitedHistory: (controller, url, _) {
                      unawaited(_inspectUrl(url));
                    },
                    onProgressChanged: (_, progress) {
                      if (!mounted) return;
                      setState(() => _progress = progress / 100);
                    },
                    onReceivedError: (_, request, error) {
                      if (request.isForMainFrame != true || !mounted) return;
                      setState(() {
                        _error = 'O login Riot não carregou corretamente.';
                        _details =
                            '${error.type}: ${error.description}\n${request.url}';
                      });
                    },
                  ),
                  if (_submitting)
                    const ColoredBox(
                      color: Color(0xAA090E15),
                      child: Center(
                        child: CircularProgressIndicator(
                          color: ValcompColors.red,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Future<bool> _inspectUrl(WebUri? url) async {
    if (_completed || _submitting || url == null) return false;
    final tokens = _tokensFromUrl(url);
    if (tokens == null) return false;
    await _complete(tokens);
    return true;
  }

  Future<void> _complete(_RiotWebTokens tokens) async {
    final state = context.read<AppController>();
    setState(() {
      _submitting = true;
      _error = '';
      _details = '';
    });
    try {
      final riotSession = await fetchRiotMobileSession(
        accessToken: tokens.accessToken,
        idToken: tokens.idToken,
      );
      final cookies = await _riotCookies();
      final ssid = cookies['ssid'] ?? '';
      if (ssid.isEmpty) {
        throw const ApiException(
          'A Riot autenticou, mas o cookie de renovação não ficou disponível. Feche esta tela e tente de novo.',
          code: 'riot_ssid_missing',
        );
      }
      final riotId = await state.completeMobileRiotLogin(
        accessToken: tokens.accessToken,
        idToken: tokens.idToken,
        entitlementToken: riotSession.entitlementToken,
        puuid: riotSession.puuid,
        region: riotSession.region,
        shard: riotSession.shard,
        gameName: riotSession.gameName,
        tagLine: riotSession.tagLine,
        ssid: ssid,
        cookies: cookies,
      );
      _completed = true;
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Conta Riot vinculada: $riotId')));
    } on ApiException catch (exception) {
      if (!mounted) return;
      setState(() {
        _error = exception.userMessage;
        _details = exception.fullDetails;
      });
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _error = 'Não foi possível concluir o login Riot.';
        _details = error.toString();
      });
    } finally {
      if (mounted && !_completed) {
        setState(() => _submitting = false);
      }
    }
  }

  Future<Map<String, String>> _riotCookies() async {
    final manager = CookieManager.instance();
    final result = <String, String>{};
    for (final url in const [
      'https://auth.riotgames.com',
      'https://authenticate.riotgames.com',
      'https://riotgames.com',
      'https://playvalorant.com',
    ]) {
      final cookies = await manager.getCookies(url: WebUri(url));
      for (final cookie in cookies) {
        if (cookie.name.isNotEmpty && cookie.value.isNotEmpty) {
          result[cookie.name] = cookie.value;
        }
      }
    }
    return result;
  }
}

Map<String, String>? riotTokenParametersFromUrlForTest(String url) {
  final tokens = _tokensFromUri(Uri.tryParse(url));
  if (tokens == null) return null;
  return {'access_token': tokens.accessToken, 'id_token': tokens.idToken};
}

String riotShardForRegionForTest(String region) => riotShardForRegion(region);

String riotLoginUrlForTest() =>
    _RiotMobileLoginScreenState._loginUri.toString();

_RiotWebTokens? _tokensFromUrl(WebUri url) {
  return _tokensFromUri(Uri.tryParse(url.toString()));
}

_RiotWebTokens? _tokensFromUri(Uri? uri) {
  if (uri == null) return null;
  final values = <String, String>{};
  for (final source in [uri.fragment, uri.query]) {
    if (source.isEmpty) continue;
    try {
      values.addAll(Uri.splitQueryString(source));
    } on FormatException {
      continue;
    }
  }
  final accessToken = values['access_token'] ?? '';
  if (accessToken.isEmpty) return null;
  return _RiotWebTokens(
    accessToken: accessToken,
    idToken: values['id_token'] ?? '',
  );
}

class _RiotWebTokens {
  const _RiotWebTokens({required this.accessToken, required this.idToken});

  final String accessToken;
  final String idToken;
}
