import { Image } from 'expo-image';
import { useState } from 'react';
import { Pressable, StyleSheet, useWindowDimensions } from 'react-native';

import {
  AnimatedBlock,
  Field,
  Notice,
  Panel,
  PasswordField,
  PrimaryButton,
  Screen,
  StatusPill,
} from '@/components/valcomp-ui';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { useAuth } from '@/lib/session';

type Mode = 'login' | 'signup';

export function AuthScreen() {
  const { signIn, signUp } = useAuth();
  const { height } = useWindowDimensions();
  const compact = height < 760;
  const tiny = height < 660;
  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  async function submit() {
    const cleanEmail = email.trim().toLowerCase();
    if (!cleanEmail || password.length < 6) {
      setError('Use um email valido e uma senha com pelo menos 6 caracteres.');
      return;
    }
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const response =
        mode === 'login'
          ? await signIn(cleanEmail, password)
          : await signUp(cleanEmail, password, displayName.trim());
      if (!response.session) {
        setNotice(response.message || 'Conta criada. Entre com seu email e senha.');
      }
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel autenticar.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen
      scroll={tiny}
      safeAreaStyle={styles.safeArea}
      contentStyle={[styles.content, compact ? styles.contentCompact : null]}>
      <AnimatedBlock style={[styles.brand, compact ? styles.brandCompact : null]}>
        <Image source={require('@/assets/valcomp/logo.png')} style={styles.logo} contentFit="contain" />
        <StatusPill label={mode === 'login' ? 'ENTRAR' : 'CRIAR CONTA'} tone="success" />
      </AnimatedBlock>

      <AnimatedBlock delay={70} style={styles.copy}>
        <ThemedText type="title" style={[styles.title, compact ? styles.titleCompact : null]}>
          {mode === 'login' ? 'Sua loja diaria, sem abrir o PC.' : 'Crie sua conta Valcomp.'}
        </ThemedText>
        <ThemedText themeColor="textSecondary" style={styles.subtitle}>
          {mode === 'login'
            ? 'Entre para ver loja, alertas e vinculo Riot em um app simples.'
            : 'Cadastro direto pelo Valcomp. Nada de email de confirmacao ou OAuth por enquanto.'}
        </ThemedText>
      </AnimatedBlock>

      <AnimatedBlock delay={120}>
        <Panel style={[styles.formCard, compact ? styles.formCardCompact : null]}>
          {mode === 'signup' ? (
            <Field
              label="Nome no app"
              value={displayName}
              onChangeText={setDisplayName}
              autoCapitalize="words"
              placeholder="Seu nome aqui"
            />
          ) : null}
          <Field
            label="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            placeholder="voce@email.com"
          />
          <PasswordField
            label="Senha"
            value={password}
            onChangeText={setPassword}
            placeholder="minimo 6 caracteres"
          />
          <PrimaryButton onPress={submit} disabled={loading}>
            {loading ? 'Conectando...' : mode === 'login' ? 'Entrar' : 'Criar conta'}
          </PrimaryButton>

          <Pressable
            onPress={() => {
              setMode(mode === 'login' ? 'signup' : 'login');
              setError('');
              setNotice('');
            }}
            style={({ pressed }) => [styles.modeButton, pressed ? styles.pressed : null]}>
            <ThemedText type="smallBold" themeColor="accent">
              {mode === 'login' ? 'Ainda nao tenho conta' : 'Ja tenho conta'}
            </ThemedText>
          </Pressable>
        </Panel>
      </AnimatedBlock>

      {notice ? <Notice title="OK" body={notice} tone="success" /> : null}
      {error ? <Notice title="ATENCAO" body={error} tone="warning" /> : null}

      {!compact ? (
        <ThemedView style={styles.featureStrip}>
          <ThemedText type="code" themeColor="textSecondary">
            loja diaria
          </ThemedText>
          <ThemedText type="code" themeColor="textSecondary">
            alertas de skin
          </ThemedText>
          <ThemedText type="code" themeColor="textSecondary">
            companion Windows
          </ThemedText>
        </ThemedView>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    justifyContent: 'center',
    paddingBottom: Spacing.three,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    gap: Spacing.three,
    paddingTop: Spacing.two,
    paddingBottom: Spacing.three,
  },
  contentCompact: {
    gap: Spacing.two,
  },
  brand: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  brandCompact: {
    marginBottom: -Spacing.one,
  },
  logo: {
    width: 116,
    height: 52,
  },
  copy: {
    gap: Spacing.two,
  },
  title: {
    fontSize: 38,
    lineHeight: 39,
    letterSpacing: -1.2,
    maxWidth: 480,
  },
  titleCompact: {
    fontSize: 31,
    lineHeight: 32,
  },
  subtitle: {
    maxWidth: 520,
  },
  formCard: {
    padding: Spacing.four,
    gap: Spacing.three,
  },
  formCardCompact: {
    padding: Spacing.three,
    gap: Spacing.twoHalf,
  },
  modeButton: {
    alignItems: 'center',
    paddingVertical: Spacing.one,
  },
  pressed: {
    transform: [{ translateY: 1 }, { scale: 0.99 }],
    opacity: 0.82,
  },
  featureStrip: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.two,
    backgroundColor: 'transparent',
  },
});
