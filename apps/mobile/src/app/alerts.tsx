import { Image } from 'expo-image';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet } from 'react-native';

import {
  AnimatedBlock,
  EmptyState,
  Field,
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
import { registerPushDevice } from '@/lib/push';

type SkinAsset = {
  uuid: string;
  displayName?: string;
  displayIcon?: string;
  fullRender?: string;
  contentTierUuid?: string;
};

type WatchItem = {
  item_id: string;
  item_name?: string;
  display_icon?: string;
  tier?: string;
  notify_enabled: boolean;
};

type SkinListResponse = {
  items: SkinAsset[];
};

type WatchlistResponse = {
  items: WatchItem[];
};

export default function AlertsScreen() {
  const [query, setQuery] = useState('');
  const [skins, setSkins] = useState<SkinAsset[]>([]);
  const [watchlist, setWatchlist] = useState<WatchItem[]>([]);
  const [loadingSkins, setLoadingSkins] = useState(false);
  const [loadingWatchlist, setLoadingWatchlist] = useState(false);
  const [busyItem, setBusyItem] = useState('');
  const [pushLoading, setPushLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    loadWatchlist();
  }, []);

  const watchIds = useMemo(
    () => new Set(watchlist.map((item) => item.item_id.toLowerCase())),
    [watchlist],
  );

  const filteredSkins = useMemo(() => {
    const cleanQuery = query.trim().toLowerCase();
    const list = cleanQuery
      ? skins.filter((skin) => (skin.displayName || '').toLowerCase().includes(cleanQuery))
      : skins;
    return list.slice(0, 18);
  }, [query, skins]);

  async function loadSkins() {
    setLoadingSkins(true);
    setError('');
    try {
      const response = await apiRequest<SkinListResponse>('/valorant/items/skins');
      setSkins(response.items.filter((skin) => skin.displayName));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel carregar as skins.');
    } finally {
      setLoadingSkins(false);
    }
  }

  async function loadWatchlist() {
    setLoadingWatchlist(true);
    setError('');
    try {
      const response = await apiRequest<WatchlistResponse>('/valorant/skins/watchlist');
      setWatchlist(response.items);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel carregar seus alertas.');
    } finally {
      setLoadingWatchlist(false);
    }
  }

  async function addSkin(skin: SkinAsset) {
    setBusyItem(skin.uuid);
    setError('');
    setNotice('');
    try {
      const response = await apiRequest<{ item: WatchItem }>('/valorant/skins/watchlist', {
        method: 'POST',
        body: { item_id: skin.uuid, notify_enabled: true },
      });
      setWatchlist((current) => [
        response.item,
        ...current.filter((item) => item.item_id.toLowerCase() !== skin.uuid.toLowerCase()),
      ]);
      setNotice(`${response.item.item_name || skin.displayName || 'Skin'} adicionada aos alertas.`);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel adicionar o alerta.');
    } finally {
      setBusyItem('');
    }
  }

  async function removeSkin(itemId: string) {
    setBusyItem(itemId);
    setError('');
    setNotice('');
    try {
      await apiRequest(`/valorant/skins/watchlist/${itemId}`, { method: 'DELETE' });
      setWatchlist((current) =>
        current.filter((item) => item.item_id.toLowerCase() !== itemId.toLowerCase()),
      );
      setNotice('Alerta removido.');
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel remover o alerta.');
    } finally {
      setBusyItem('');
    }
  }

  async function enablePush() {
    setPushLoading(true);
    setError('');
    setNotice('');
    try {
      await registerPushDevice();
      setNotice('Notificacoes ativadas neste aparelho.');
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Nao foi possivel ativar notificacoes.');
    } finally {
      setPushLoading(false);
    }
  }

  return (
    <Screen>
      <AnimatedBlock>
        <Header
          eyebrow="Alertas"
          title="Quando a skin entrar, o app te avisa."
          body="Monte sua lista de desejo e ative notificacoes. O backend compara sua loja diaria com os itens monitorados."
        />
      </AnimatedBlock>

      <AnimatedBlock delay={70}>
        <Panel style={styles.summaryPanel}>
          <ThemedView style={styles.rowBetween}>
            <StatusPill label={`${watchlist.length} ALERTAS`} tone={watchlist.length ? 'success' : 'neutral'} />
            <ThemedText type="code" themeColor="textSecondary">
              loja diaria
            </ThemedText>
          </ThemedView>
          <ThemedText type="subtitle" style={styles.summaryTitle}>
            Lista de desejo monitorada todos os dias.
          </ThemedText>
          <ThemedView style={styles.actions}>
            <PrimaryButton onPress={enablePush} disabled={pushLoading}>
              {pushLoading ? 'Ativando...' : 'Ativar notificacoes'}
            </PrimaryButton>
            <PrimaryButton variant="secondary" onPress={loadWatchlist} disabled={loadingWatchlist}>
              {loadingWatchlist ? 'Atualizando...' : 'Atualizar lista'}
            </PrimaryButton>
          </ThemedView>
        </Panel>
      </AnimatedBlock>

      {watchlist.length ? (
        <AnimatedBlock delay={120}>
          <Panel>
            <ThemedText type="smallBold">Skins monitoradas</ThemedText>
            {watchlist.map((item) => (
              <WatchRow
                key={item.item_id}
                item={item}
                busy={busyItem === item.item_id}
                onRemove={() => removeSkin(item.item_id)}
              />
            ))}
          </Panel>
        </AnimatedBlock>
      ) : (
        <EmptyState
          title="Nenhum alerta ainda"
          body="Carregue o catalogo, escolha uma skin e o Valcomp avisa quando ela aparecer na sua loja."
          action={<PrimaryButton onPress={loadSkins}>Carregar catalogo</PrimaryButton>}
        />
      )}

      <AnimatedBlock delay={150}>
        <Panel>
          <Field
            label="Buscar skin"
            value={query}
            onChangeText={setQuery}
            placeholder="Vandal, Phantom, Sheriff..."
          />
          <PrimaryButton onPress={loadSkins} disabled={loadingSkins}>
            {loadingSkins ? 'Carregando catalogo...' : skins.length ? 'Recarregar skins' : 'Carregar skins'}
          </PrimaryButton>
        </Panel>
      </AnimatedBlock>

      {loadingSkins ? (
        <Panel>
          <SkeletonLine width="44%" />
          <SkeletonLine />
          <SkeletonLine width="68%" />
        </Panel>
      ) : null}

      {filteredSkins.length ? (
        <ThemedView style={styles.grid}>
          {filteredSkins.map((skin, index) => {
            const watching = watchIds.has(skin.uuid.toLowerCase());
            return (
              <AnimatedBlock key={skin.uuid} delay={index * 30}>
                <SkinCard
                  skin={skin}
                  watching={watching}
                  busy={busyItem === skin.uuid}
                  onAdd={() => addSkin(skin)}
                />
              </AnimatedBlock>
            );
          })}
        </ThemedView>
      ) : null}

      {notice ? <Notice title="OK" body={notice} tone="success" /> : null}
      {error ? <Notice title="ATENCAO" body={error} tone="warning" /> : null}
    </Screen>
  );
}

function WatchRow({
  item,
  busy,
  onRemove,
}: {
  item: WatchItem;
  busy: boolean;
  onRemove: () => void;
}) {
  return (
    <ThemedView style={styles.watchRow}>
      {item.display_icon ? (
        <Image source={{ uri: item.display_icon }} style={styles.watchImage} contentFit="contain" />
      ) : (
        <ThemedView type="accentSoft" style={styles.watchFallback} />
      )}
      <ThemedView style={styles.watchCopy}>
        <ThemedText type="smallBold">{item.item_name || item.item_id.slice(0, 8)}</ThemedText>
        <ThemedText type="code" themeColor="textSecondary">
          {item.tier || 'skin'}
        </ThemedText>
      </ThemedView>
      <Pressable
        disabled={busy}
        onPress={onRemove}
        style={({ pressed }) => [styles.smallButton, pressed ? styles.pressed : null]}>
        <ThemedText type="smallBold" themeColor="accent">
          {busy ? '...' : 'Remover'}
        </ThemedText>
      </Pressable>
    </ThemedView>
  );
}

function SkinCard({
  skin,
  watching,
  busy,
  onAdd,
}: {
  skin: SkinAsset;
  watching: boolean;
  busy: boolean;
  onAdd: () => void;
}) {
  const image = skin.fullRender || skin.displayIcon;
  return (
    <Panel style={styles.skinPanel}>
      <ThemedView style={styles.skinTop}>
        <ThemedView style={styles.skinCopy}>
          <ThemedText type="code" themeColor="textSecondary">
            {skin.contentTierUuid ? skin.contentTierUuid.slice(0, 8) : 'skin'}
          </ThemedText>
          <ThemedText type="subtitle" style={styles.skinName}>
            {skin.displayName}
          </ThemedText>
        </ThemedView>
        {image ? <Image source={{ uri: image }} style={styles.skinImage} contentFit="contain" /> : null}
      </ThemedView>
      <PrimaryButton onPress={onAdd} disabled={watching || busy}>
        {watching ? 'Alerta ativo' : busy ? 'Adicionando...' : 'Adicionar alerta'}
      </PrimaryButton>
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
  summaryTitle: {
    fontSize: 28,
    lineHeight: 31,
  },
  actions: {
    gap: Spacing.two,
    backgroundColor: 'transparent',
  },
  watchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    paddingVertical: Spacing.two,
    backgroundColor: 'transparent',
  },
  watchImage: {
    width: 54,
    height: 38,
  },
  watchFallback: {
    width: 54,
    height: 38,
    borderRadius: 12,
  },
  watchCopy: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  smallButton: {
    paddingHorizontal: Spacing.two,
    paddingVertical: Spacing.two,
  },
  grid: {
    gap: Spacing.three,
  },
  skinPanel: {
    minHeight: 160,
    justifyContent: 'space-between',
  },
  skinTop: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.three,
    backgroundColor: 'transparent',
  },
  skinCopy: {
    flex: 1,
    backgroundColor: 'transparent',
  },
  skinImage: {
    width: 116,
    height: 72,
  },
  skinName: {
    fontSize: 25,
    lineHeight: 29,
  },
  pressed: {
    opacity: 0.72,
    transform: [{ translateY: 1 }],
  },
});
