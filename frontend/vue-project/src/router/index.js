import { createRouter, createWebHistory } from "vue-router";
import LoginComponent from "@/components/LoginComponent.vue";
import MenuComponent from "@/components/MenuComponent.vue";
import MenuGerente from "@/components/MenuGerente.vue";
import ProductosView from "../components/ProductosView.vue";
import BodegasView from "../components/BodegasView.vue";
import CargarCantidades from "../components/CargarCantidades.vue";
import TrasladarCantidades from "../components/TrasladarCantidades.vue";
import CargarVentas from "../components/CargarVentas.vue";
import KardexView from "../components/Kardex.vue";
import ConsultaInventario from "../components/ConsultaInventario.vue";
import ModuloMateriales from "../components/ModuloMateriales.vue";
import AdminUsuariosComponent from "../components/AdminUsuariosComponent.vue";
import ProduccionAdmin from "../components/ProduccionAdmin.vue";
import ProduccionOperador from "../components/ProduccionOperador.vue";
import ReportesProduccion from "../components/ReportesProduccion.vue";
import ReportesProduccionOperador from "../components/ReportesProduccionOperador.vue";
import MenuOperador from "../components/MenuOperador.vue";
import ConsultaInventarioOperador from "../components/ConsultaInventarioOperador.vue";
import AjusteInventario from "../components/AjusteInventario.vue";
import GestionProductosMateriales from "../components/GestionProductosMateriales.vue";
import CargarNotasCredito from "../components/CargarNotasCredito.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Página principal y menús
    { path: "/", component: LoginComponent },
    { path: "/login", component: LoginComponent }, // Ruta explícita para login
    { path: "/menu", component: MenuComponent },
    { path: "/menu-gerente", component: MenuGerente },
    { path: "/menu-operador", component: MenuOperador },
    
    // Rutas específicas
    { path: "/productos", name: "productos", component: ProductosView, meta: { requiresAuth: true } },
    { path: "/bodegas", name: "bodegas", component: BodegasView, meta: { requiresAuth: true } },
    { path: "/cargar-cantidades", name: "cargarCantidades", component: CargarCantidades, meta: { requiresAuth: true } },
    { path: "/trasladar-cantidades", name: "trasladarCantidades", component: TrasladarCantidades, meta: { requiresAuth: true } },
    { path: "/cargar-ventas", name: "cargarVentas", component: CargarVentas, meta: { requiresAuth: true } },
    { path: "/kardex", name: "kardex", component: KardexView, meta: { requiresAuth: true } },
    { path: "/consulta-inventario", name: "ConsultaInventario", component: ConsultaInventario, meta: { requiresAuth: true } },
    { path: "/consulta-inventarioOperador", name: "ConsultaInventarioOperador", component: ConsultaInventarioOperador, meta: { requiresAuth: true } },
    { path: "/modulo-materiales", name: "ModuloMateriales", component: ModuloMateriales, meta: { requiresAuth: true } },
    { path: "/admin-usuarios", name: "AdminUsuariosComponent", component: AdminUsuariosComponent, meta: { requiresAuth: true } },
    { path: "/produccion-admin", name: "ProduccionAdmin", component: ProduccionAdmin, meta: { requiresAuth: true } },
    { path: "/produccion-operador", name: "ProduccionOperador", component: ProduccionOperador, meta: { requiresAuth: true } },
    { path: "/reportes-produccion", name: "ReportesProduccion", component: ReportesProduccion, meta: { requiresAuth: true } },
    { path: "/reportes-produccion-operador", name: "ReportesProduccionOperador", component: ReportesProduccionOperador, meta: { requiresAuth: true } },
    { path: "/ajuste-inventario", name: "AjusteInventario", component: AjusteInventario, meta: { requiresAuth: true } },
    { path: "/gestion-productos-materiales", name: "GestionProductosMateriales", component: GestionProductosMateriales, meta: { requiresAuth: true } },
    { path: "/cargar-notas-credito", name: "CargarNotasCredito", component: CargarNotasCredito, meta: { requiresAuth: true } },
    
  ],
});

// Agregar el guard de navegación
router.beforeEach((to, from, next) => {
  const tipoUsuario = localStorage.getItem("tipo_usuario");

  if (to.path === "/" || to.path === "/login")  {
    // Redirigir al menú correspondiente según el tipo de usuario
    if (tipoUsuario === "admin") {
      return next({ path: "/menu" });
    } else if (tipoUsuario === "operador") {
      return next({ path: "/menu-operador" });
    } else if (tipoUsuario === "gerente") {
      return next({ path: "/menu-gerente" });
    }
  }

  if (to.meta.requiresAuth && !tipoUsuario) {
    // Redirigir al login si no está autenticado
    return next({ path: "/" });
  }

  next();
});

export default router;




