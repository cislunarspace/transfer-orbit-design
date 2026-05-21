# PRD: GUI 脚本选择时自动切换回 Script Info 标签页

## Problem Statement

当前 GUI 右侧有两个标签页："Script Info" 和 "Files"。当用户正在 Files 标签页浏览文件时，如果点击左侧脚本列表中的任意脚本名称，右侧参数面板会更新为对应脚本的内容，但标签页仍停留在 Files，用户必须手动点击 "Script Info" 标签才能查看脚本的参数配置。这增加了操作步骤，不符合直觉。

用户期望：点击左侧脚本名称时，自动将右侧标签页切换回 Script Info，直接展示脚本的参数配置界面。

## Solution

修改主窗口的脚本选中回调逻辑：

1. 保存右侧 `QTabWidget` 的实例引用，使回调方法能够操作标签页。
2. 在脚本选中回调末尾，遍历标签页查找 "Script Info" / "脚本信息" 标签，将当前标签页切换至该标签。
3. 查找逻辑同时匹配中英文标题，以兼容未来可能的双语界面。

## User Stories

1. As a GUI user, when I am on the Files tab browsing output files, I want clicking any script name in the left sidebar to automatically switch the right panel back to the Script Info tab, so that I can immediately see that script's parameter configuration without manually clicking the Script Info tab.
2. As a GUI user, when I am on the Files tab and click a different script name, I want the Script Info tab to show the newly selected script's parameters, so that the entire workflow feels seamless and intuitive.
3. As a GUI user already on the Script Info tab, I want clicking a script name to keep me on the Script Info tab (no visual flicker or unnecessary re-switch), so that the interface remains stable.
4. As a developer, I want the tab-switching logic to locate the target tab by its title text rather than by hard-coded index, so that adding or reordering tabs in the future does not break this behavior.

## Implementation Decisions

- The right-hand `QTabWidget` will be saved as an instance attribute (`self._right_tabs`) during construction so that the script-selection callback can reference it.
- On script selection (`_on_script_selected`), after rebuilding the parameter panel, iterate over all tabs and match against the set `{"Script Info", "脚本信息"}`. Set the matched tab as current.
- If no matching tab is found (defensive), the operation is silently skipped — the existing behavior of updating the parameter panel is preserved.
- No new modules are introduced; the change is confined to the main window class.

## Testing Decisions

- This is a small UI interaction change. Manual verification is sufficient:
  1. Open the GUI, select a script — Script Info tab shows parameters.
  2. Click the Files tab to switch to file browser.
  3. Click a different script in the left sidebar — verify the right panel automatically switches back to Script Info and displays the new script's parameters.
  4. Click another script while already on Script Info — verify no visual disruption.
- Automated unit tests are not required because the behavior is purely presentational and tightly coupled to the Qt widget lifecycle.

## Out of Scope

- Changing the tab order or adding new tabs.
- Internationalization framework — only the lookup set is bilingual-ready, not the full UI.
- Animated tab transitions.
- Keyboard shortcut-based tab switching.

## Further Notes

- The Script Info tab is created at index 0 and the Files tab at index 1 in the current layout, but the implementation must not rely on this ordering.
- The `Files` tab's internal state (selected directory, expanded nodes) should remain intact across tab switches; this is the default Qt behavior and requires no extra handling.
