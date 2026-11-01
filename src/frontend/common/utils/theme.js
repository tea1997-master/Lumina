/**
 * テーマ管理ユーティリティ (common/utils/theme.js)
 * Windows 11 の設定 app に準拠した ライト / ダーク / システム設定 連動
 */

export const THEMES = {
  LIGHT: "light",
  DARK: "dark",
  SYSTEM: "system",
};

const STORAGE_KEY = "lumina-theme";

/**
 * 保存されているテーマ設定を取得 (デフォルトは 'system')
 */
export function getSavedTheme() {
  try {
    return localStorage.getItem(STORAGE_KEY) || THEMES.SYSTEM;
  } catch {
    return THEMES.SYSTEM;
  }
}

/**
 * テーマ設定を保存
 */
export function saveTheme(theme) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // localStorage 利用不可環境のフォールバック
  }
}

/**
 * OS (システム) が現在ダークモードかどうかを判定
 */
export function isSystemDark() {
  if (typeof window === "undefined" || !window.matchMedia) {
    return false;
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/**
 * 指定されたテーマ設定を DOM に適用
 * @param {string} theme - 'light' | 'dark' | 'system'
 */
export function applyTheme(theme) {
  const root = document.documentElement;

  if (theme === THEMES.SYSTEM) {
    root.setAttribute("data-theme", THEMES.SYSTEM);
  } else if (theme === THEMES.DARK) {
    root.setAttribute("data-theme", THEMES.DARK);
  } else {
    root.setAttribute("data-theme", THEMES.LIGHT);
  }
}

/**
 * 初期テーマの適用とシステム変更リスナーの設定
 * @param {Function} [onThemeChange]
 */
export function initTheme(onThemeChange) {
  const theme = getSavedTheme();
  applyTheme(theme);

  if (typeof window !== "undefined" && window.matchMedia) {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (getSavedTheme() === THEMES.SYSTEM) {
        applyTheme(THEMES.SYSTEM);
        if (onThemeChange) onThemeChange(THEMES.SYSTEM);
      }
    };

    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener("change", handler);
    } else if (mediaQuery.addListener) {
      mediaQuery.addListener(handler);
    }
  }

  return theme;
}
