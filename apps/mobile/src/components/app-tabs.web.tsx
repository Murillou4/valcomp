import {
  Tabs,
  TabList,
  TabTrigger,
  TabSlot,
  TabTriggerSlotProps,
  TabListProps,
} from 'expo-router/ui';
import { Pressable, View, StyleSheet, useWindowDimensions } from 'react-native';

import { ThemedText } from './themed-text';
import { ThemedView } from './themed-view';

import { MaxContentWidth, Spacing } from '@/constants/theme';

export default function AppTabs() {
  return (
    <Tabs>
      <TabSlot style={styles.tabSlot} />
      <TabList asChild>
        <CustomTabList>
          <TabTrigger name="store" href="/" asChild>
            <TabButton>Loja</TabButton>
          </TabTrigger>
          <TabTrigger name="link" href="/link" asChild>
            <TabButton>Vincular</TabButton>
          </TabTrigger>
          <TabTrigger name="alerts" href="/alerts" asChild>
            <TabButton>Alertas</TabButton>
          </TabTrigger>
          <TabTrigger name="account" href="/account" asChild>
            <TabButton>Conta</TabButton>
          </TabTrigger>
        </CustomTabList>
      </TabList>
    </Tabs>
  );
}

export function TabButton({ children, isFocused, ...props }: TabTriggerSlotProps) {
  return (
    <Pressable
      {...props}
      style={({ pressed }) => [styles.tabButton, pressed ? styles.pressed : null]}>
      <ThemedView
        type={isFocused ? 'backgroundSelected' : 'backgroundElement'}
        style={styles.tabButtonView}>
        <ThemedText
          type="small"
          numberOfLines={1}
          themeColor={isFocused ? 'text' : 'textSecondary'}
          style={styles.tabLabel}>
          {children}
        </ThemedText>
      </ThemedView>
    </Pressable>
  );
}

export function CustomTabList(props: TabListProps) {
  const { width } = useWindowDimensions();
  const showBrand = width >= 560;

  return (
    <View {...props} style={styles.tabListContainer}>
      <ThemedView type="backgroundElement" style={styles.innerContainer}>
        {showBrand ? (
          <ThemedText type="smallBold" style={styles.brandText}>
            Valcomp
          </ThemedText>
        ) : null}

        {props.children}
      </ThemedView>
    </View>
  );
}

const styles = StyleSheet.create({
  tabSlot: {
    flex: 1,
    height: '100%',
  },
  tabListContainer: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    width: '100%',
    paddingHorizontal: Spacing.two,
    paddingTop: Spacing.two,
    paddingBottom: Spacing.two,
    justifyContent: 'center',
    alignItems: 'center',
    flexDirection: 'row',
    backgroundColor: 'rgba(16, 16, 19, 0.96)',
  },
  innerContainer: {
    width: '100%',
    padding: Spacing.one,
    borderRadius: Spacing.three,
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.one,
    maxWidth: MaxContentWidth,
  },
  brandText: {
    marginHorizontal: Spacing.two,
  },
  pressed: {
    opacity: 0.76,
    transform: [{ translateY: 1 }, { scale: 0.98 }],
  },
  tabButton: {
    flex: 1,
    minWidth: 0,
  },
  tabButtonView: {
    minHeight: 42,
    paddingHorizontal: Spacing.one,
    borderRadius: Spacing.two,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabLabel: {
    fontSize: 12,
    lineHeight: 16,
    textAlign: 'center',
  },
});
