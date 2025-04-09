import { createRouter, createWebHistory } from "vue-router";
import LoginComponent from '@/components/LoginComponent.vue';
import MenuComponent from '@/components/MenuComponent.vue';
import ProductosView from "../components/ProductosView.vue";
import BodegasView from "../components/BodegasView.vue";
import CargarCantidades from "../components/CargarCantidades.vue";
import TrasladarCantidades from "../components/TrasladarCantidades.vue";
import CargarVentas from "../components/CargarVentas.vue";
import KardexView from "../components/Kardex.vue";
import ConsultaInventario from "../components/ConsultaInventario.vue";
import ModuloMateriales from "../components/ModuloMateriales.vue";
import AdminUsuariosComponent from "../components/AdminUsuariosComponent.vue";

const routes = [
  { path: '/', component: LoginComponent },
  { path: '/menu', component: MenuComponent },
  { path: "/productos", name: "productos", component: ProductosView, meta: { requiresAuth: true } },
  { path: "/bodegas", name: "bodegas", component: BodegasView, meta: { requiresAuth: true } },
  { path: "/cargar-cantidades", name: "cargarCantidades", component: CargarCantidades, meta: { requiresAuth: true } },
  { path: "/trasladar-cantidades", name: "trasladarCantidades", component: TrasladarCantidades, meta: { requiresAuth: true } },
  { path: "/cargar-ventas", name: "cargarVentas", component: CargarVentas, meta: { requiresAuth: true } },
  { path: "/kardex", name: "kardex", component: KardexView },
  { path: "/consulta-inventario", name: "consultaInventario", component: ConsultaInventario, meta: { requiresAuth: true } },
  { path: "/modulo-materiales", name: "moduloMateriales", component: ModuloMateriales, meta: { requiresAuth: true } },
  { path: "/admin-usuarios", name: "AdminUsuariosComponent", component: AdminUsuariosComponent, meta: { requiresAuth: true } },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;



