import type { App } from "vue";
import { ElButton } from "element-plus/es/components/button/index";
import {
  ElCheckbox,
  ElCheckboxButton,
  ElCheckboxGroup,
} from "element-plus/es/components/checkbox/index";
import { ElDialog } from "element-plus/es/components/dialog/index";
import { ElDrawer } from "element-plus/es/components/drawer/index";
import {
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
} from "element-plus/es/components/dropdown/index";
import { ElEmpty } from "element-plus/es/components/empty/index";
import { ElInput } from "element-plus/es/components/input/index";
import { ElInputNumber } from "element-plus/es/components/input-number/index";
import { ElOption, ElSelect } from "element-plus/es/components/select/index";
import { ElPagination } from "element-plus/es/components/pagination/index";
import { ElPopover } from "element-plus/es/components/popover/index";
import { ElTable, ElTableColumn } from "element-plus/es/components/table/index";
import { ElLoading } from "element-plus/es/components/loading/index";
import { ElConfigProvider } from "element-plus/es/components/config-provider/index";

export function registerUI(app: App) {
  for (const component of [
    ElButton,
    ElCheckbox,
    ElCheckboxButton,
    ElCheckboxGroup,
    ElDialog,
    ElDrawer,
    ElDropdown,
    ElDropdownItem,
    ElDropdownMenu,
    ElEmpty,
    ElInput,
    ElInputNumber,
    ElOption,
    ElPagination,
    ElPopover,
    ElSelect,
    ElTable,
    ElTableColumn,
    ElConfigProvider,
  ])
    app.component(component.name!, component);
  app.directive("loading", ElLoading.directive);
}
