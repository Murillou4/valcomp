import { useState } from 'react';
import { Pressable, StyleSheet, useWindowDimensions } from 'react-native';

import {
  AnimatedBlock,
  Field,
  Header,
  Notice,
  Panel,
  PrimaryButton,
  Screen,
  StatusPill,
} from '@/components/valcomp-ui';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { apiBaseUrl, apiRequest } from '@/lib/api';

type LinkStartResponse = {
  link_code: string;
  expires_at: string;
};

export default function LinkScreen() {
  const { height } = useWindowDimensions();
  const tiny = height < 680;
  const compact = height < 760;
  const [link, setLink] = useState<LinkStartResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
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
    <Screen
      scroll={tiny}
      backgroundImage={require('@/assets/valcomp/hero-agent.png')}
      backgroundImageOpacity={0.18}
      contentStyle={[styles.content, compact ? styles.contentCompact : null]}>
      <AnimatedBlock>
        <Header
          compact={compact}
          eyebrow="Vinculo Riot"
          title="Conecte sua Riot pelo PC uma unica vez."
          body="Gere o codigo no celular, abra o companion no Windows e confirme. Depois disso o app consulta a loja diaria remoto."
        />
      </AnimatedBlock>

      <AnimatedBlock delay={80}>
        <Panel style={[styles.codePanel, compact ? styles.codePanelCompact : null]}>
          <ThemedView style={styles.rowBetween}>
            <StatusPill label={link ? 'CODIGO ATIVO' : 'PRONTO'} tone={link ? 'success' : 'neutral'} />
            {link ? (
              <ThemedText type="code" themeColor="textSecondary">
                expira {new Date(link.expires_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </ThemedText>
            ) : null}
          </ThemedView>

          <ThemedView style={styles.codeBox}>
            <ThemedText style={[styles.code, compact ? styles.codeCompact : null]}>
              {link?.link_code || '------'}
            </ThemedText>
          </ThemedView>

          <ThemedText themeColor="textSecondary" style={styles.instructions}>
            No Windows: abra o Valcomp Companion, clique em detectar Riot e digite este codigo.
          </ThemedText>

          <PrimaryButton onPress={startLink} disabled={loading}>
            {loading ? 'Gerando codigo...' : link ? 'Gerar novo codigo' : 'Gerar codigo de vinculo'}
          </PrimaryButton>
        </Panel>
      </AnimatedBlock>

      <AnimatedBlock delay={150}>
        <Panel tone="soft" style={styles.stepsPanel}>
          <Step number="1" text="Abra Riot Client ou VALORANT no PC onde voce joga." />
          <Step number="2" text="Abra o companion Windows e deixe ele detectar sua sessao." />
          <Step number="3" text="Digite o codigo acima. Nenhum token aparece na tela." />
        </Panel>
      </AnimatedBlock>

      <Pressable
        onPress={() => setAdvancedOpen((current) => !current)}
        style={({ pressed }) => [styles.advancedToggle, pressed ? styles.pressed : null]}>
        <ThemedText type="smallBold" themeColor="textSecondary">
          {advancedOpen ? 'Ocultar opcoes avancadas' : 'Mostrar opcoes avancadas'}
        </ThemedText>
      </Pressable>

      {advancedOpen ? (
        <AnimatedBlock>
          <Panel>
            <Field
              label="URL do servidor"
              value={apiBaseUrl}
              editable={false}
              helper="Campo visivel so para debug. O app usa esta URL compilada no build."
            />
          </Panel>
        </AnimatedBlock>
      ) : null}

      {error ? <Notice title="ATENCAO" body={error} tone="warning" /> : null}
    </Screen>
  );
}

function Step({ number, text }: { number: string; text: string }) {
  return (
    <ThemedView style={styles.step}>
      <ThemedView type="accentSoft" style={styles.stepNumber}>
        <ThemedText type="code" themeColor="accent">
          {number}
        </ThemedText>
      </ThemedView>
      <ThemedText type="smallBold" style={styles.stepText}>
        {text}
      </ThemedText>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  content: {
    flex: 1,
    justifyContent: 'center',
    paddingTop: Spacing.three,
  },
  contentCompact: {
    gap: Spacing.two,
    paddingTop: Spacing.two,
  },
  codePanel: {
    gap: Spacing.three,
  },
  codePanelCompact: {
    gap: Spacing.two,
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.two,
    backgroundColor: 'transparent',
  },
  codeBox: {
    minHeight: 104,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'rgba(16,16,19,0.56)',
  },
  code: {
    fontSize: 56,
    lineHeight: 62,
    letterSpacing: 9,
    fontWeight: '800',
  },
  codeCompact: {
    fontSize: 46,
    lineHeight: 50,
  },
  instructions: {
    maxWidth: 520,
  },
  stepsPanel: {
    gap: Spacing.two,
  },
  step: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    backgroundColor: 'transparent',
  },
  stepNumber: {
    width: 28,
    height: 28,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepText: {
    flex: 1,
  },
  advancedToggle: {
    alignSelf: 'flex-start',
    paddingVertical: Spacing.one,
  },
  pressed: {
    opacity: 0.72,
    transform: [{ translateY: 1 }],
  },
});
