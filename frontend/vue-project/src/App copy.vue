<template>
  <div>
    <!-- Menú de navegación (solo si el usuario está autenticado) -->
    <nav v-if="usuarioAutenticado">
      <ul>
        <li><router-link to="/productos">Productos</router-link></li>
        <li><router-link to="/bodegas">Bodegas</router-link></li>
        <li><router-link to="/consulta-inventario">Consultar Inventario</router-link></li>
        <li><router-link to="/trasladar-cantidades">Trasladar Cantidades</router-link></li>
        <li><router-link to="/cargar-cantidades">Cargar Compras</router-link></li>
        <li><router-link to="/cargar-ventas">Cargar Ventas</router-link></li>
        <li><router-link to="/kardex">Kardex</router-link></li>
        <li><router-link to="/modulo-materiales">Gestión de Materiales</router-link></li>
        <li v-if="tipoUsuario === 'admin'">
          <router-link to="/admin-usuarios">Administración de Usuarios</router-link>
        </li>
        <li><button @click="cerrarSesion" class="btn btn-danger btn-sm">Cerrar Sesión</button></li>
      </ul>
    </nav>

    <!-- Vista principal -->
    <router-view @loginSuccess="actualizarEstadoAutenticacion" />
  </div>
</template>

<script>
export default {
  name: "App",
  data() {
    return {
      usuarioAutenticado: false,
      tipoUsuario: null,
    };
  },
  mounted() {
    // Comprobar estado de autenticación al cargar la aplicación
    this.actualizarEstadoAutenticacion();
  },
  methods: {
    actualizarEstadoAutenticacion() {
      const tipo = localStorage.getItem("tipo_usuario");
      this.usuarioAutenticado = !!tipo; // Verdadero si hay un tipo de usuario
      this.tipoUsuario = tipo;
    },
    cerrarSesion() {
      localStorage.clear();
      this.usuarioAutenticado = false;
      this.tipoUsuario = null;
      this.$router.push("/");
    },
  },
};
</script>

<style scoped>
nav ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  gap: 1rem;
  background-color: #f8f9fa;
  padding: 1rem;
  border-bottom: 1px solid #ddd;
}

nav ul li {
  display: inline;
}

nav ul li a {
  text-decoration: none;
  color: #007bff;
}

nav ul li a:hover {
  text-decoration: underline;
}

nav ul li a.router-link-active {
  font-weight: bold;
  color: #0056b3;
}
</style>



