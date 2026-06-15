import { type ReactNode } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  type TextInputProps,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

export function Screen({ children }: { children: ReactNode }) {
  const theme = useTheme();
  return (
    <ScrollView style={[styles.scroll, { backgroundColor: theme.background }]}>
      <SafeAreaView style={styles.safeArea}>
        <ThemedView style={styles.content}>{children}</ThemedView>
      </SafeAreaView>
    </ScrollView>
  );
}

export function Header({
  eyebrow,
  title,
  body,
}: {
  eyebrow: string;
  title: string;
  body: string;
}) {
  return (
    <ThemedView style={styles.header}>
      <ThemedText type="code" themeColor="accent" style={styles.eyebrow}>
        {eyebrow}
      </ThemedText>
      <ThemedText type="title" style={styles.title}>
        {title}
      </ThemedText>
      <ThemedText themeColor="textSecondary" style={styles.body}>
        {body}
      </ThemedText>
    </ThemedView>
  );
}

export function Panel({
  children,
  style,
}: {
  children: ReactNode;
  style?: ViewStyle | ViewStyle[];
}) {
  const theme = useTheme();
  return (
    <ThemedView
      type="backgroundElement"
      style={[styles.panel, { borderColor: theme.border }, style]}>
      {children}
    </ThemedView>
  );
}

export function PrimaryButton({
  children,
  onPress,
  disabled,
}: {
  children: ReactNode;
  onPress: () => void;
  disabled?: boolean;
}) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: disabled ? theme.backgroundSelected : theme.text },
        pressed && !disabled ? styles.pressed : null,
      ]}>
      <ThemedText
        type="smallBold"
        style={{ color: disabled ? theme.textSecondary : theme.background }}>
        {children}
      </ThemedText>
    </Pressable>
  );
}

export function Field({
  label,
  helper,
  ...props
}: TextInputProps & {
  label: string;
  helper?: string;
}) {
  const theme = useTheme();
  return (
    <ThemedView style={styles.field}>
      <ThemedText type="smallBold">{label}</ThemedText>
      <TextInput
        placeholderTextColor={theme.textSecondary}
        style={[
          styles.input,
          {
            color: theme.text,
            borderColor: theme.border,
            backgroundColor: theme.background,
          },
        ]}
        {...props}
      />
      {helper ? (
        <ThemedText type="small" themeColor="textSecondary">
          {helper}
        </ThemedText>
      ) : null}
    </ThemedView>
  );
}

export function StatusPill({
  label,
  tone = 'neutral',
}: {
  label: string;
  tone?: 'neutral' | 'success' | 'warning';
}) {
  const theme = useTheme();
  const color =
    tone === 'success' ? theme.success : tone === 'warning' ? theme.warning : theme.textSecondary;
  return (
    <ThemedView style={[styles.pill, { borderColor: color }]}>
      <ThemedText type="code" style={{ color }}>
        {label}
      </ThemedText>
    </ThemedView>
  );
}

export function SkeletonLine({ width = '100%' }: { width?: ViewStyle['width'] }) {
  const theme = useTheme();
  return <ThemedView style={[styles.skeleton, { width, backgroundColor: theme.backgroundSelected }]} />;
}

const styles = StyleSheet.create({
  scroll: {
    flex: 1,
  },
  safeArea: {
    flex: 1,
    alignItems: 'center',
    paddingHorizontal: Spacing.three,
    paddingBottom: BottomTabInset + Spacing.four,
  },
  content: {
    width: '100%',
    maxWidth: MaxContentWidth,
    gap: Spacing.four,
    paddingTop: Spacing.four,
  },
  header: {
    gap: Spacing.two,
    paddingTop: Spacing.two,
  },
  eyebrow: {
    textTransform: 'uppercase',
    letterSpacing: 1.2,
  },
  title: {
    fontSize: 42,
    lineHeight: 44,
    letterSpacing: -1.4,
  },
  body: {
    maxWidth: 520,
  },
  panel: {
    borderWidth: 1,
    borderRadius: 30,
    padding: Spacing.four,
    gap: Spacing.three,
  },
  button: {
    minHeight: 52,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.four,
  },
  pressed: {
    transform: [{ translateY: 1 }, { scale: 0.99 }],
  },
  field: {
    gap: Spacing.two,
  },
  input: {
    minHeight: 52,
    borderRadius: 18,
    borderWidth: 1,
    paddingHorizontal: Spacing.three,
    fontSize: 16,
    fontWeight: '600',
  },
  pill: {
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.one,
  },
  skeleton: {
    height: 18,
    borderRadius: 999,
  },
});

