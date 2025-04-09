<template>
  <div class="produccion-admin">
    <h1>Gestión de Productos y Materiales</h1>
    
    <div>
      <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú</button>
      <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
    </div>

    <!-- Formulario para Crear/Editar Producto -->
    <section>
      <h2>Crear o Editar Producto</h2>
      <form @submit.prevent="modoEdicion ? actualizarProducto() : crearProducto()">
          <div>
              <label for="codigo">Código del Producto:</label>
              <input v-model="producto.codigo" id="codigo" required :disabled="modoEdicion" />
          </div>
          <div>
              <label for="nombre">Nombre del Producto:</label>
              <input v-model="producto.nombre" id="nombre" required />
          </div>
          <div>
              <label for="peso_total">Peso Total en Gramos:</label>
              <input v-model.number="producto.peso_total_gr" id="peso_total" type="number" required />
          </div>
          <div>
              <label for="peso_unidad">Peso por Unidad en Gramos:</label>
              <input v-model.number="producto.peso_unidad_gr" id="peso_unidad" type="number" required />
          </div>
          <div>
              <label for="codigo_barras">Código de Barras:</label>
              <input v-model="producto.codigo_barras" id="codigo_barras" />
          </div>
          <div>
              <label>Tipo de Producto:</label>
              <select v-model="producto.es_producto_compuesto">
                  <option :value="false">A Granel</option>
                  <option :value="true">Compuesto</option>
              </select>
          </div>
          <div>
              <button v-if="!modoEdicion" type="submit">Crear Producto</button>
              <div v-else>
                <button type="submit">Guardar Producto</button>
                <button type="button" @click="cancelarEdicion">Cancelar</button>
              </div>
          </div>
      </form>
    </section>

    <!-- Formulario para Definir Materiales de un Producto Compuesto -->
    <section v-if="producto.es_producto_compuesto && producto.id">
      <h3>Materiales del Producto</h3>
      <div v-for="(material, index) in materiales" :key="index" class="material-item">
        <select v-model="material.producto_base">
          <option v-for="prod in productosDisponibles" :key="prod.id" :value="prod.id">
            {{ prod.codigo }} - {{ prod.nombre }}
          </option>
        </select>
        <input v-model.number="material.cantidad" type="number" min="1" required />
        <button @click.prevent="eliminarMaterial(index)">Eliminar</button>
      </div>
      <button @click.prevent="agregarMaterial">Agregar Material</button>
      <button @click.prevent="guardarMateriales">Guardar Materiales</button>
    </section>

    <!-- Consulta de Productos -->
    <section>
      <h2>Consulta de Productos</h2>
      <input v-model="filtroCodigo" placeholder="Código del producto" />
      <button @click="consultarProductos">Consultar</button>
      
      <table v-if="productos.length">
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Peso Total (g)</th>
            <th>Peso Unidad (g)</th>
            <th>Código de Barras</th>
            <th>Prod. Compuesto</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="prod in productos" :key="prod.id">
            <td>{{ prod.codigo }}</td>
            <td>{{ prod.nombre }}</td>
            <td>{{ prod.peso_total_gr }}</td>
            <td>{{ prod.peso_unidad_gr }}</td>
            <td>{{ prod.codigo_barras }}</td>
            <td>{{ prod.es_producto_compuesto }}</td>
            <td>
              <button @click="editarProducto(prod)">Editar</button>
              <button @click="eliminarProducto(prod.id)">Eliminar</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>
  
  <script>
  import apiClient from "../services/axios";
  
  export default {
    name: "ModuloMateriales",
    data() {
      return {
        agregarProductosVisible: false,
        nuevosMateriales: [],
        nuevoProducto: {
          codigo: "",
          nombre: "",
          codigo_barras: "",
        },
        materiales: [],
        pesoTotalCalculado: 0,
        productosDisponibles: [],
        productosCompuestos: [],
        productoSeleccionado: null,
        codigoProducto: "",
        materialesProductoCompuesto: [],
      };
    },
    methods: {
      async cargarProductos() {
        try {
          const response = await apiClient.get("/api/productos/completos");
          this.productosDisponibles = response.data.filter((producto) => !producto.es_producto_compuesto).sort((a, b) => a.nombre.localeCompare(b.nombre));
          this.productosCompuestos = response.data.filter((producto) => producto.es_producto_compuesto).sort((a, b) => a.nombre.localeCompare(b.nombre));
        } catch (error) {
          console.error("Error al cargar productos:", error);
        }
      },
      limpiarPagina() {
        // Resetear los datos iniciales
        this.nuevoProducto = {
          codigo: "",
          nombre: "",
          codigo_barras: "",
        };
        this.materiales = [];
        this.pesoTotalCalculado = 0;
        this.productosDisponibles = [];
        this.productosCompuestos = [];
        this.productoSeleccionado = null;
        this.codigoProducto = "";
        this.materialesProductoCompuesto = [];
        this.agregarProductosVisible = false;
        this.nuevosMateriales = [];

        // Recargar los productos disponibles
        this.cargarProductos();
      },
      async crearProducto() {
        const response = await apiClient.post('/api/productos', this.producto);
        this.producto.id = response.data.id;
        alert('Producto creado correctamente');
        this.consultarProductos();
      },
      async guardarMateriales() {
        await apiClient.post('/api/materiales-producto', {
          producto_compuesto_id: this.producto.id,
          materiales: this.materiales
        });
        alert('Materiales guardados correctamente');
      },
      async consultarProductos() {
        const response = await apiClient.get('/api/productos', { params: { search: this.filtroCodigo } });
        this.productos = response.data;
      },
      async eliminarProducto(id) {
        await apiClient.delete(`/api/productos/${id}`);
        alert('Producto eliminado');
        this.consultarProductos();
      },
      editarProducto(producto) {
        this.modoEdicion = true;
        this.producto = { ...producto };
        if (producto.es_producto_compuesto) this.cargarMateriales(producto.id);
      },
      async actualizarProducto() {
        await apiClient.put(`/api/productos/${this.producto.id}`, this.producto);
        alert('Producto actualizado');
        this.consultarProductos();
      },
      async cargarMateriales(id) {
        const response = await apiClient.get(`/api/materiales-producto/${id}`);
        this.materiales = response.data;
      },
      agregarMaterial() {
        this.materiales.push({ producto_base: null, cantidad: 1 });
      },
      eliminarMaterial(index) {
        this.materiales.splice(index, 1);
      },
      volverAlMenu() {
        const tipoUsuario = localStorage.getItem("tipo_usuario"); // Obtener el tipo de usuario del almacenamiento local

        if (tipoUsuario === "admin") {
          this.$router.push('/menu'); // Redirigir al menú del administrador
        } else if (tipoUsuario === "gerente") {
          this.$router.push('/menu-gerente'); // Redirigir al menú del gerente
        } else {
          alert("Rol no reconocido. Contacta al administrador."); // Manejo de error en caso de un rol desconocido
        }
      },
    },
    mounted() {
      this.cargarProductos();
    },
  };
  </script>
  
  <style scoped>
  /* Contenedor principal */
  .produccion-admin {
    margin: 20px auto;
    max-width: 1200px;
    font-family: Arial, sans-serif;
    padding: 10px;
  }
  
  /* Títulos */
  h1 {
    text-align: center;
    color: #333;
    margin-bottom: 20px;
  }
  
  h2, h3 {
    color: #0056b3;
    margin-bottom: 15px;
  }
  
  /* Botones */
  button {
    padding: 0.6rem 1.2rem;
    border: none;
    background-color: #007bff;
    color: #fff;
    cursor: pointer;
    border-radius: 4px;
    font-size: 14px;
    margin-right: 10px;
  }
  
  button:hover {
    background-color: #0056b3;
    box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.2);
  }

  button.btn-warning {
    background-color: #ffc107; /* Amarillo para advertencias */
    color: #333; /* Texto oscuro */
  }
  
  button.btn-warning:hover {
    background-color: #e0a800; /* Amarillo más oscuro */
  }
  
  /* Formularios */
  form label {
    font-weight: bold;
    display: block;
    margin-bottom: 5px;
    color: #555;
  }
  
  form input, form select {
    width: 100%;
    padding: 10px;
    margin-bottom: 15px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 14px;
  }
  
  /* Tablas */
  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
    font-size: 14px;
  }
  
  th, td {
    border: 1px solid #ddd;
    padding: 10px;
    text-align: left;
  }
  
  th {
    background-color: #f8f9fa;
    color: #333;
    font-weight: bold;
  }
  
  tbody tr:nth-child(odd) {
    background-color: #f9f9f9;
  }
  
  tbody tr:hover {
    background-color: #f1f1f1;
  }
  
  /* Secciones */
  section {
    margin-bottom: 30px;
    padding: 15px;
    border: 1px solid #e9ecef;
    border-radius: 6px;
    background-color: #f8f9fa;
  }
  
  /* Historial de entregas */
  p {
    margin: 5px 0;
    color: #555;
    font-size: 14px;
  }
  
  /* --- Responsividad --- */
  @media (max-width: 768px) {
    /* Reducir márgenes en pantallas pequeñas */
    .produccion-admin {
      margin: 10px auto;
      padding: 10px;
    }
  
    /* Formularios en columna */
    form input, form select, button {
      width: 100%;
      margin-bottom: 10px;
      font-size: 16px;
    }
  
    /* Tablas desplazables horizontalmente */
    table {
      display: block;
      overflow-x: auto;
      white-space: nowrap;
    }
  
    th, td {
      font-size: 12px;
      padding: 8px;
    }
  
    /* Reducir tamaño de títulos */
    h1 {
      font-size: 20px;
    }
  
    h2, h3 {
      font-size: 18px;
    }
  }
  </style>
  
  
  