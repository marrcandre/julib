import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import PrimeVue from "primevue/config";
import ToastService from "primevue/toastservice";
import Aura from "@primeuix/themes/aura";
import { definePreset } from "@primeuix/themes";
import App from "./App.vue";
const Books = () => import("./pages/Books.vue");
const BookDetails = () => import("./pages/BookDetails.vue");
const Loans = () => import("./pages/Loans.vue");
const Locations = () => import("./pages/Locations.vue");
const ImportBooks = () => import("./pages/ImportBooks.vue");
const About = () => import("./pages/About.vue");
const PublicCatalog = () => import("./pages/PublicCatalog.vue");
const Settings = () => import("./pages/Settings.vue");
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/inter/800.css";
import "./style.css";
import "./catalog.css";
import "./book-details.css";
import "primeicons/primeicons.css";
const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, saved) {
    if (saved) return saved;
    if (to.path === from.path) return;
    return { top: 0, left: 0 };
  },
  routes: [
    { path: "/", redirect: "/livros" },
    { path: "/livros", component: Books },
    { path: "/livros/:id", component: BookDetails },
    { path: "/emprestimos", component: Loans },
    { path: "/locais", component: Locations },
    { path: "/importar", component: ImportBooks },
    { path: "/sobre", component: About },
    { path: "/configuracoes", component: Settings },
    { path: "/colecao/:token", component: PublicCatalog },
  ],
});
const preset = definePreset(Aura, {
  semantic: {
    primary: {
      50: "#eef8f1",
      100: "#d0ebda",
      200: "#a0d5b7",
      300: "#83c6a7",
      400: "#45997a",
      500: "#226f54",
      600: "#14543e",
      700: "#074e3d",
      800: "#053227",
      900: "#09291f",
      950: "#071e17",
    },
  },
});
createApp(App)
  .use(router)
  .use(ToastService)
  .use(PrimeVue, { theme: { preset, options: { darkModeSelector: ".dark" } } })
  .mount("#app");
