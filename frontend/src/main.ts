import { createApp } from "vue";
import { createPinia } from "pinia";
import { registerUI } from "./components/ui";
import "element-plus/dist/index.css";
import "./assets/main.css";
import App from "./App.vue";
import router from "./router";
import { useAuth } from "./stores/auth";
const app = createApp(App);
app.use(createPinia()).use(router);
registerUI(app);
window.addEventListener("sunpath:unauthorized", () => {
  useAuth().clear();
  void router.replace("/login");
});
app.mount("#app");
