import { useState } from 'react';
import { Image } from 'expo-image';
import { StyleSheet } from 'react-native';

import { Field, Header, Panel, PrimaryButton, Screen, StatusPill } from '@/components/valcomp-ui';
import { ThemedText } from '@/components/themed-text';
import { Spacing } from '@/constants/theme';
import { apiBaseUrl, apiRequest } from '@/lib/api';

type LinkStartResponse = {
  link_code: string;
  expires_at: string;
};

export default function LinkScreen() {
  const [backendUrl, setBackendUrl] = useState(apiBaseUrl);
  const [link, setLink] = useState<LinkStartResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function startLink() {
    setLoading(true);
    setError('');
    try {
      setLink(await apiRequest<LinkStartResponse>('/riot/link/start', { method: 'POST', body: {} }));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel gerar o codigo.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen>
      <Header
        eyebrow="Vinculo Riot"
        title="Um codigo curto, uma vez no Windows."
        body="O companion detecta a sessao Riot local automaticamente, envia para o backend e depois o app mobile passa a consultar tudo remoto."
      />

      <Panel>
        <Image source={require('@/assets/valcomp/hero-agent.png')} style={styles.hero} contentFit="cover" />
        <Field
          label="Backend"
          value={backendUrl}
          onChangeText={setBackendUrl}
          autoCapitalize="none"
          helper="Esta URL vem de EXPO_PUBLIC_API_BASE_URL. O campo fica aqui para conferir rapidamente durante dev."
        />
        <PrimaryButton onPress={startLink} disabled={loading}>
          {loading ? 'Gerando codigo...' : 'Gerar codigo de vinculo'}
        </PrimaryButton>
      </Panel>

      {link ? (
        <Panel style={styles.codePanel}>
          <StatusPill label="CODIGO ATIVO" tone="success" />
          <ThemedText style={styles.code}>{link.link_code}</ThemedText>
          <ThemedText themeColor="textSecondary">
            No PC logado na Riot, abra o Valcomp Companion, confira o backend e cole esse codigo.
          </ThemedText>
          <ThemedText type="code" themeColor="textSecondary">
            expira em {new Date(link.expires_at).toLocaleTimeString()}
          </ThemedText>
        </Panel>
      ) : null}

      {error ? (
        <Panel>
          <StatusPill label="ERRO" tone="warning" />
          <ThemedText themeColor="textSecondary">{error}</ThemedText>
        </Panel>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: {
    width: '100%',
    height: 220,
    borderRadius: 28,
  },
  codePanel: {
    gap: Spacing.two,
  },
  code: {
    fontSize: 52,
    lineHeight: 58,
    letterSpacing: 8,
    fontWeight: '800',
  },
});
