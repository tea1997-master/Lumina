/**
 * アプリケーション初期化 (app.js)
 * Windows 11 設定 app スタイルのテーマ切り替え対応
 */

import { THEMES, getSavedTheme, saveTheme, applyTheme, initTheme } from "./common/utils/theme.js";

function renderApp() {
  const root = document.getElementById("app");
  if (!root) return;

  const currentTheme = getSavedTheme();

  root.innerHTML = `
    <div class="app-container">
      <nav class="app-sidebar">
        <h2 class="sidebar-title">Lumina</h2>
        <a class="nav-item active" href="#settings">
          <span>⚙️</span>
          <span>設定</span>
        </a>
      </nav>

      <main class="app-main">
        <header class="page-header">
          <h1 class="page-title">設定</h1>
          <p class="page-subtitle">外観と個人用設定の管理</p>
        </header>

        <section class="settings-group">
          <h2 class="group-title">外観</h2>

          <div class="settings-card">
            <div class="card-info">
              <span class="card-title">モードの選択</span>
              <span class="card-description">アプリの色（ライト・ダーク・システム設定連動）を選択します</span>
            </div>

            <div class="card-action">
              <select id="theme-selector" class="fluent-select" aria-label="テーマ選択">
                <option value="${THEMES.SYSTEM}" ${currentTheme === THEMES.SYSTEM ? "selected" : ""}>システム設定に合わせる</option>
                <option value="${THEMES.LIGHT}" ${currentTheme === THEMES.LIGHT ? "selected" : ""}>ライト</option>
                <option value="${THEMES.DARK}" ${currentTheme === THEMES.DARK ? "selected" : ""}>ダーク</option>
              </select>
            </div>
          </div>
        </section>
      </main>
    </div>
  `;

  const selector = document.getElementById("theme-selector");
  if (selector) {
    selector.addEventListener("change", (e) => {
      const selected = e.target.value;
      saveTheme(selected);
      applyTheme(selected);
    });
  }
}

window.addEventListener("DOMContentLoaded", () => {
  initTheme();
  renderApp();
});
