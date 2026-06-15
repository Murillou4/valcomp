import { Image } from 'expo-image';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet } from 'react-native';

import {
  AnimatedBlock,
  EmptyState,
  Header,
  Notice,
  Panel,
  PrimaryButton,
  Screen,
  SkeletonLine,
  StatusPill,
} from '@/components/valcomp-ui';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { Spacing } from '@/constants/theme';
import { apiRequest } from '@/lib/api';

type StoreItem = {
  item_id: string;
  name: string;
  display_icon?: string;
  image?: string;
  tier?: string;
  price?: number;
  source: string;
};

type DailyStoreResponse = {
  expires_at?: string | null;
  seconds_remaining?: number | null;
  items: StoreItem[];
  night_market: StoreItem[];
  alerts?: {
    sent_count?: number;
    matched?: unknown[];
  };
};

export default function StoreScreen() {
  const [daily, setDaily] = useState<DailyStoreResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadDailyStore();
  }, []);

  const timeRemaining = useMemo(() => {
    if (!daily?.seconds_remaining) return 'aguardando loja';
    const hours = Math.floor(daily.seconds_remaining / 3600);
    const minutes = Math.floor((daily.seconds_remaining % 3600) / 60);
    return `${hours}h ${minutes}m restantes`;
  }, [daily]);

  async function loadDailyStore() {
    setLoading(true);
    setError('');
    try {
      setDaily(await apiRequest<DailyStoreResponse>('/valorant/store/daily'));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Falha ao buscar loja diaria.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Screen>
      <AnimatedBlock>
        <Header
          eyebrow="Loja"
          title="Sua loja diaria pronta para olhar."
          body="Itens do dia, preco em VP, tempo restante e sinal de alerta quando uma skin desejada aparecer."
        />
      </AnimatedBlock>

      <AnimatedBlock delay={70}>
        <Panel style={styles.summaryPanel}>
          <ThemedView style={styles.rowBetween}>
            <StatusPill
              label={daily ? 'LOJA CARREGADA' : loading ? 'BUSCANDO' : 'AGUARDANDO'}
              tone={daily ? 'success' : 'neutral'}
            />
            <ThemedText type="code" themeColor="textSecondary">
              {timeRemaining}
            </ThemedText>
          </ThemedView>
          <ThemedView style={styles.metrics}>
            <Metric label="ofertas" value={String(daily?.items.length ?? 0)} />
            <Metric label="alertas hoje" value={String(daily?.alerts?.sent_count ?? 0)} />
            <Metric label="fonte" value={daily ? 'Riot' : 'v3/v2'} />
          </ThemedView>
          <PrimaryButton onPress={loadDailyStore} disabled={loading}>
            {loading ? 'Atualizando loja...' : 'Atualizar loja'}
          </PrimaryButton>
        </Panel>
      </AnimatedBlock>

      {loading && !daily ? <StoreSkeleton /> : null}

      {daily?.items.length ? (
        <ThemedView style={styles.grid}>
          {daily.items.map((item, index) => (
            <AnimatedBlock key={item.item_id} delay={120 + index * 35}>
              <StoreCard item={item} />
            </AnimatedBlock>
          ))}
        </ThemedView>
      ) : !loading && !error ? (
        <EmptyState
          title="Loja ainda vazia"
          body="Quando sua conta Riot estiver vinculada, a loja diaria aparece aqui automaticamente. Se pedir revinculo, abra o companion no Windows."
          action={<PrimaryButton onPress={loadDailyStore}>Buscar agora</PrimaryButton>}
        />
      ) : null}

      {error ? <Notice title="ATENCAO" body={error} tone="warning" /> : null}
    </Screen>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <ThemedView style={styles.metric}>
      <ThemedText type="code" themeColor="textSecondary">
        {label}
      </ThemedText>
      <ThemedText type="subtitle" style={styles.metricValue}>
        {value}
      </ThemedText>
    </ThemedView>
  );
}

function StoreCard({ item }: { item: StoreItem }) {
  const image = item.display_icon || item.image;
  return (
    <Pressable style={({ pressed }) => [pressed ? styles.pressed : null]}>
      <Panel style={styles.itemPanel}>
        <ThemedView style={styles.itemTop}>
          <ThemedView style={styles.itemCopy}>
            <ThemedText type="code" themeColor="textSecondary">
              {item.tier || 'skin'}
            </ThemedText>
            <ThemedText type="subtitle" style={styles.itemName}>
              {item.name || item.item_id.slice(0, 8)}
            </ThemedText>
          </ThemedView>
          {image ? <Image source={{ uri: image }} style={styles.itemImage} contentFit="contain" /> : null}
        </ThemedView>
        <ThemedView style={styles.rowBetween}>
          <ThemedText type="code" themeColor="accent">
            {item.price ? `${item.price} VP` : 'preco indisponivel'}
          </ThemedText>
          <StatusPill label={item.source.toUpperCase()} />
        </ThemedView>
      </Panel>
    </Pressable>
  );
}

function StoreSkeleton() {
  return (
    <Panel>
      <SkeletonLine width="44%" />
      <SkeletonLine />
      <SkeletonLine width="70%" />
    </Panel>
  );
}

const styles = StyleSheet.create({
  summaryPanel: {
    gap: Spacing.three,
  },
  rowBetween: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.two,
    backgroundColor: 'transparent',
  },
  metrics: {
    flexDirection: 'row',
    gap: Spacing.two,
    backgroundColor: 'transparent',
  },
  metric: {
    flex: 1,
    borderRadius: 16,
    padding: Spacing.twoHalf,
    backgroundColor: 'rgba(255,255,255,0.035)',
  },
  metricValue: {
    fontSize: 24,
    lineHeight: 28,
  },
  grid: {
    gap: Spacing.three,
  },
  itemPanel: {
    minHeight: 164,
    justifyContent: 'space-between',
  },
  itemTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    backgroundColor: 'transparent',
  },
  itemCopy: {
    flex: 1,
    gap: Spacing.one,
    backgroundColor: 'transparent',
  },
  itemImage: {
    width: 124,
    height: 82,
  },
  itemName: {
    fontSize: 27,
    lineHeight: 30,
  },
  pressed: {
    transform: [{ translateY: 1 }, { scale: 0.99 }],
    opacity: 0.88,
  },
});
