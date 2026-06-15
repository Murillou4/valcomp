import { Image } from 'expo-image';
import { usePathname } from 'expo-router';
import { type ReactNode, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  type TextInputProps,
  View,
  type ImageSourcePropType,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import Animated, { FadeInUp } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';

type ScreenProps = {
  children: ReactNode;
  scroll?: boolean;
  backgroundImage?: ImageSourcePropType;
  backgroundImageOpacity?: number;
  contentStyle?: StyleProp<ViewStyle>;
  safeAreaStyle?: StyleProp<ViewStyle>;
};

export function Screen({
  children,
  scroll = true,
  backgroundImage,
  backgroundImageOpacity = 0.14,
  contentStyle,
  safeAreaStyle,
}: ScreenProps) {
  const theme = useTheme();
  const pathname = usePathname();
  const content = (
    <SafeAreaView style={[styles.safeArea, safeAreaStyle]}>
      <Animated.View
        key={pathname}
        entering={FadeInUp.duration(420).springify().damping(22)}
        style={[styles.content, contentStyle]}>
        {children}
      </Animated.View>
    </SafeAreaView>
  );

  return (
    <View style={[styles.screen, { backgroundColor: theme.background }]}>
      <AmbientLayer />
      {backgroundImage ? (
        <Image
          source={backgroundImage}
          contentFit="cover"
          style={[styles.backgroundImage, { opacity: backgroundImageOpacity }]}
        />
      ) : null}
      {scroll ? (
        <ScrollView
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}>
          {content}
        </ScrollView>
      ) : (
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.noScroll}>
          {content}
        </KeyboardAvoidingView>
      )}
    </View>
  );
}

export function Header({
  eyebrow,
  title,
  body,
  compact = false,
}: {
  eyebrow: string;
  title: string;
  body: string;
  compact?: boolean;
}) {
  return (
    <ThemedView style={[styles.header, compact ? styles.headerCompact : null]}>
      <ThemedText type="code" themeColor="accent" style={styles.eyebrow}>
        {eyebrow}
      </ThemedText>
      <ThemedText type="title" style={[styles.title, compact ? styles.titleCompact : null]}>
        {title}
      </ThemedText>
      <ThemedText themeColor="textSecondary" style={styles.body}>
        {body}
      </ThemedText>
    </ThemedView>
  );
}

export function AnimatedBlock({
  children,
  delay = 0,
  style,
}: {
  children: ReactNode;
  delay?: number;
  style?: StyleProp<ViewStyle>;
}) {
  return (
    <Animated.View
      entering={FadeInUp.delay(delay).duration(420).springify().damping(20)}
      style={style}>
      {children}
    </Animated.View>
  );
}

export function Panel({
  children,
  style,
  tone = 'default',
}: {
  children: ReactNode;
  style?: StyleProp<ViewStyle>;
  tone?: 'default' | 'soft' | 'accent';
}) {
  const theme = useTheme();
  return (
    <ThemedView
      type={tone === 'accent' ? 'accentSoft' : tone === 'soft' ? 'backgroundSelected' : 'backgroundElement'}
      style={[styles.panel, { borderColor: theme.border }, style]}>
      {children}
    </ThemedView>
  );
}

export function PrimaryButton({
  children,
  onPress,
  disabled,
  variant = 'primary',
}: {
  children: ReactNode;
  onPress: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
}) {
  const theme = useTheme();
  const primary = variant === 'primary';
  const danger = variant === 'danger';
  const backgroundColor = disabled
    ? theme.backgroundSelected
    : primary
      ? theme.text
      : danger
        ? theme.accentSoft
        : variant === 'ghost'
          ? 'transparent'
          : theme.backgroundSelected;
  const color = disabled
    ? theme.textSecondary
    : primary
      ? theme.background
      : danger
        ? theme.accent
        : theme.text;

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor, borderColor: primary ? backgroundColor : theme.border },
        pressed && !disabled ? styles.pressed : null,
      ]}>
      <ThemedText type="smallBold" style={{ color }}>
        {children}
      </ThemedText>
    </Pressable>
  );
}

export function Field({
  label,
  helper,
  rightAccessory,
  inputStyle,
  ...props
}: TextInputProps & {
  label: string;
  helper?: string;
  rightAccessory?: ReactNode;
  inputStyle?: StyleProp<ViewStyle>;
}) {
  const theme = useTheme();
  return (
    <ThemedView style={styles.field}>
      <ThemedText type="smallBold">{label}</ThemedText>
      <ThemedView
        style={[
          styles.inputShell,
          {
            borderColor: theme.border,
            backgroundColor: theme.background,
          },
          inputStyle,
        ]}>
        <TextInput
          placeholderTextColor={theme.textSecondary}
          style={[
            styles.input,
            {
              color: theme.text,
            },
          ]}
          {...props}
        />
        {rightAccessory ? <View style={styles.inputAccessory}>{rightAccessory}</View> : null}
      </ThemedView>
      {helper ? (
        <ThemedText type="small" themeColor="textSecondary">
          {helper}
        </ThemedText>
      ) : null}
    </ThemedView>
  );
}

export function PasswordField(props: Omit<TextInputProps, 'secureTextEntry'> & { label: string; helper?: string }) {
  const [visible, setVisible] = useState(false);
  return (
    <Field
      {...props}
      secureTextEntry={!visible}
      rightAccessory={
        <Pressable
          accessibilityLabel={visible ? 'Ocultar senha' : 'Mostrar senha'}
          onPress={() => setVisible((current) => !current)}
          hitSlop={10}
          style={({ pressed }) => [styles.eyeButton, pressed ? styles.pressed : null]}>
          <EyeGlyph crossed={!visible} />
        </Pressable>
      }
    />
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

export function Notice({
  title,
  body,
  tone = 'neutral',
}: {
  title: string;
  body?: string;
  tone?: 'neutral' | 'success' | 'warning';
}) {
  return (
    <Panel tone={tone === 'warning' ? 'accent' : 'soft'} style={styles.notice}>
      <StatusPill label={title} tone={tone === 'success' ? 'success' : tone === 'warning' ? 'warning' : 'neutral'} />
      {body ? <ThemedText themeColor="textSecondary">{body}</ThemedText> : null}
    </Panel>
  );
}

export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <Panel style={styles.emptyState}>
      <ThemedText type="subtitle" style={styles.emptyTitle}>
        {title}
      </ThemedText>
      <ThemedText themeColor="textSecondary" style={styles.emptyBody}>
        {body}
      </ThemedText>
      {action}
    </Panel>
  );
}

export function SkeletonLine({ width = '100%' }: { width?: ViewStyle['width'] }) {
  const theme = useTheme();
  return <ThemedView style={[styles.skeleton, { width, backgroundColor: theme.backgroundSelected }]} />;
}

function EyeGlyph({ crossed }: { crossed: boolean }) {
  const theme = useTheme();
  return (
    <View style={[styles.eye, { borderColor: theme.textSecondary }]}>
      <View style={[styles.eyeDot, { backgroundColor: theme.textSecondary }]} />
      {crossed ? <View style={[styles.eyeSlash, { backgroundColor: theme.textSecondary }]} /> : null}
    </View>
  );
}

function AmbientLayer() {
  const theme = useTheme();
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      <View style={[styles.ambientOne, { backgroundColor: theme.accent }]} />
      <View style={[styles.ambientTwo, { backgroundColor: theme.backgroundSelected }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    overflow: 'hidden',
  },
  backgroundImage: {
    ...StyleSheet.absoluteFill,
  },
  scroll: {
    flex: 1,
  },
  scrollContent: {
    flexGrow: 1,
  },
  noScroll: {
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
    gap: Spacing.three,
    paddingTop: Spacing.four,
  },
  header: {
    gap: Spacing.two,
    paddingTop: Spacing.two,
    backgroundColor: 'transparent',
  },
  headerCompact: {
    gap: Spacing.one,
  },
  eyebrow: {
    textTransform: 'uppercase',
    letterSpacing: 1.4,
  },
  title: {
    fontSize: 36,
    lineHeight: 38,
    letterSpacing: -1.1,
  },
  titleCompact: {
    fontSize: 30,
    lineHeight: 32,
  },
  body: {
    maxWidth: 520,
  },
  panel: {
    borderWidth: 1,
    borderRadius: 22,
    padding: Spacing.three,
    gap: Spacing.three,
  },
  button: {
    minHeight: 50,
    borderRadius: 14,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.four,
  },
  pressed: {
    transform: [{ translateY: 1 }, { scale: 0.985 }],
    opacity: 0.9,
  },
  field: {
    gap: Spacing.two,
    backgroundColor: 'transparent',
  },
  inputShell: {
    minHeight: 50,
    borderRadius: 16,
    borderWidth: 1,
    flexDirection: 'row',
    alignItems: 'center',
  },
  input: {
    flex: 1,
    paddingHorizontal: Spacing.three,
    paddingVertical: Platform.select({ ios: 14, default: 10 }),
    fontSize: 16,
    fontWeight: '600',
  },
  inputAccessory: {
    paddingRight: Spacing.three,
  },
  eyeButton: {
    width: 34,
    height: 34,
    alignItems: 'center',
    justifyContent: 'center',
  },
  eye: {
    width: 24,
    height: 14,
    borderWidth: 1.6,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  eyeDot: {
    width: 5,
    height: 5,
    borderRadius: 5,
  },
  eyeSlash: {
    position: 'absolute',
    width: 27,
    height: 1.6,
    transform: [{ rotateZ: '-35deg' }],
  },
  pill: {
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: Spacing.twoHalf,
    paddingVertical: Spacing.one,
    backgroundColor: 'transparent',
  },
  notice: {
    gap: Spacing.two,
  },
  emptyState: {
    minHeight: 142,
    justifyContent: 'center',
  },
  emptyTitle: {
    fontSize: 26,
    lineHeight: 30,
  },
  emptyBody: {
    maxWidth: 520,
  },
  skeleton: {
    height: 18,
    borderRadius: 999,
  },
  ambientOne: {
    position: 'absolute',
    width: 260,
    height: 260,
    borderRadius: 260,
    right: -120,
    top: 10,
    opacity: 0.08,
  },
  ambientTwo: {
    position: 'absolute',
    width: 220,
    height: 220,
    borderRadius: 220,
    left: -110,
    bottom: 110,
    opacity: 0.28,
  },
});
