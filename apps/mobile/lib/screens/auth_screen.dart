import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/app_controller.dart';
import '../core/theme.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _signup = false;
  bool _showPassword = false;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final state = context.read<AppController>();
    final message = _signup
        ? await state.signup(_name.text, _email.text, _password.text)
        : await state.login(_email.text, _password.text);
    if (!mounted || message == null || state.authenticated) return;
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppController>();
    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxHeight < 700;
            return SingleChildScrollView(
              physics: compact
                  ? const BouncingScrollPhysics()
                  : const NeverScrollableScrollPhysics(),
              padding: EdgeInsets.fromLTRB(26, compact ? 22 : 38, 26, 24),
              child: ConstrainedBox(
                constraints: BoxConstraints(
                  minHeight: constraints.maxHeight - (compact ? 46 : 62),
                ),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 430),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Center(
                            child: Image.asset(
                              'assets/images/logo.png',
                              width: compact ? 82 : 104,
                              height: compact ? 82 : 104,
                              fit: BoxFit.contain,
                            ),
                          ),
                          SizedBox(height: compact ? 18 : 28),
                          Text(
                            _signup ? 'Crie sua conta' : 'Bem-vindo de volta',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              fontFamily: 'Asgard',
                              fontSize: compact ? 28 : 34,
                              height: 1,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 10),
                          Text(
                            _signup
                                ? 'Sua loja e seus alertas, em um só lugar.'
                                : 'Entre para consultar sua conta VALORANT.',
                            textAlign: TextAlign.center,
                            style: const TextStyle(
                              color: ValcompColors.muted,
                              fontSize: 15,
                            ),
                          ),
                          SizedBox(height: compact ? 22 : 32),
                          if (_signup) ...[
                            TextFormField(
                              controller: _name,
                              textCapitalization: TextCapitalization.words,
                              decoration: const InputDecoration(
                                labelText: 'Nome no app',
                                hintText: 'Seu nome aqui',
                                prefixIcon: Icon(Icons.person_outline_rounded),
                              ),
                              validator: (value) =>
                                  (value?.trim().length ?? 0) < 2
                                  ? 'Digite seu nome.'
                                  : null,
                            ),
                            const SizedBox(height: 14),
                          ],
                          TextFormField(
                            controller: _email,
                            keyboardType: TextInputType.emailAddress,
                            autofillHints: const [AutofillHints.email],
                            decoration: const InputDecoration(
                              labelText: 'E-mail',
                              hintText: 'voce@email.com',
                              prefixIcon: Icon(Icons.mail_outline_rounded),
                            ),
                            validator: (value) => !(value ?? '').contains('@')
                                ? 'Digite um e-mail válido.'
                                : null,
                          ),
                          const SizedBox(height: 14),
                          TextFormField(
                            controller: _password,
                            obscureText: !_showPassword,
                            autofillHints: const [AutofillHints.password],
                            decoration: InputDecoration(
                              labelText: 'Senha',
                              hintText: 'Mínimo de 6 caracteres',
                              prefixIcon: const Icon(
                                Icons.lock_outline_rounded,
                              ),
                              suffixIcon: IconButton(
                                onPressed: () => setState(
                                  () => _showPassword = !_showPassword,
                                ),
                                icon: Icon(
                                  _showPassword
                                      ? Icons.visibility_off_outlined
                                      : Icons.visibility_outlined,
                                ),
                              ),
                            ),
                            validator: (value) => (value?.length ?? 0) < 6
                                ? 'Use pelo menos 6 caracteres.'
                                : null,
                          ),
                          const SizedBox(height: 18),
                          FilledButton(
                            onPressed: state.loading ? null : _submit,
                            child: state.loading
                                ? const SizedBox(
                                    width: 22,
                                    height: 22,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      color: Colors.white,
                                    ),
                                  )
                                : Text(_signup ? 'Criar conta' : 'Entrar'),
                          ),
                          const SizedBox(height: 10),
                          TextButton(
                            onPressed: state.loading
                                ? null
                                : () => setState(() => _signup = !_signup),
                            child: Text(
                              _signup
                                  ? 'Já tenho uma conta'
                                  : 'Criar uma conta',
                              style: const TextStyle(
                                color: ValcompColors.text,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                          if (state.error.isNotEmpty)
                            Container(
                              margin: const EdgeInsets.only(top: 8),
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: ValcompColors.red.withValues(
                                  alpha: 0.12,
                                ),
                                borderRadius: BorderRadius.circular(14),
                              ),
                              child: Text(
                                state.error,
                                textAlign: TextAlign.center,
                                style: const TextStyle(
                                  color: ValcompColors.red,
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
