<template>
  <div>
    <h1>Gestión de Productos</h1>

    <div>
      <!-- Contenido de la página -->
      <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú Principal</button>
      <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
    </div>

    <h2>Creación y Edición de Productos</h2>
    <!-- Formulario para Crear/Editar Producto -->
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
        <button v-if="!modoEdicion" type="submit">Crear Producto</button>
        <div v-else>
          <button type="submit">Guardar Producto</button>
          <button type="button" @click="cancelarEdicion">Cancelar</button>
        </div>
      </div>
    </form>

    <!-- Subida de Archivo CSV -->
    <div>
      <h2>Cargar Productos desde archivo .CSV</h2>
      <input type="file" @change="cargarCsv" />
      <button @click="procesarCsv">Subir</button>
    </div>

    <!-- Botón para cargar productos -->
    <div>
      <h2>Consulta de Productos Creados</h2>
      <label for="buscarCodigo">Buscar por Código:</label>
      <input v-model="filtroCodigo" id="buscarCodigo" placeholder="Ingrese código de producto" />
      
      <button @click="consultarProductos">Consultar Productos</button>
    </div>

    <!-- Lista de Productos -->
    <div v-if="productos.length">
      <h2>Productos Cargados</h2>
      <table>
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Peso Total (g)</th>
            <th>Peso Unidad (g)</th>
            <th>Código de Barras</th>
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
            <td>
              <button @click="editarProducto(prod)">Editar</button>
              <button @click="eliminarProducto(prod.id)">Eliminar</button>
            </td>
          </tr>
        </tbody>
      </table>
      <button v-if="productos.length < totalProductos" @click="cargarMasProductos">
        Cargar más productos
      </button>
    </div>
  </div>
</template>

<script>
import apiClient from '../services/axios';

export default {
  name: 'ProductosForm',
  data() {
    return {
      producto: {
        codigo: '',
        nombre: '',
        peso_total_gr: '',
        peso_unidad_gr: '',
        codigo_barras: '',
      },
      productos: [],
      totalProductos: 0,
      offset: 0,
      limit: 20, // Límite inicial de productos por cargar
      modoEdicion: false,
      filtroCodigo: '',
    };
  },
  methods: {
    limpiarPagina() {
      this.resetearFormulario(); // Restablecer el formulario de producto
      this.productos = []; // Limpiar la lista de productos
      this.totalProductos = 0; // Reiniciar el total de productos
      this.offset = 0; // Reiniciar el offset de paginación
      this.modoEdicion = false; // Salir del modo de edición
    },
    async crearProducto() {
      try {
        await apiClient.post('/api/productos', this.producto);
        alert('Producto creado correctamente');
        this.resetearFormulario();
      } catch (error) {
        console.error('Error al crear producto:', error);
      }
    },
    async consultarProductos() {
      try {
        this.offset = 0; // Reiniciar el offset para una nueva consulta
        const params = {
          offset: this.offset,
          limit: this.limit,
          search: this.filtroCodigo || '', // Filtro por código de producto
        };
        const response = await apiClient.get('/api/productos', { params });

        if (response.data.productos.length === 0) {
            alert("Código de Producto no encontrado. Intente con otro código.");
            return;
        }

        //const response = await apiClient.get(`/api/productos?offset=${this.offset}&limit=${this.limit}`);
        console.log('DEBUG: Respuesta de productos:', response.data);
        this.productos = response.data.productos.sort((a, b) => a.nombre.localeCompare(b.nombre));
        this.totalProductos = response.data.total;
      } catch (error) {
        if (error.response && error.response.status === 404) {
            alert("Código de Producto no encontrado. Intente con otro código.");
        } else {
            console.error('Error al cargar productos:', error);
            alert("Ocurrió un error al consultar los productos.");
        }
      }
    },
    async cargarMasProductos() {
      try {
        this.offset += this.limit;
        const response = await apiClient.get(`/api/productos?offset=${this.offset}&limit=${this.limit}`);
        const nuevosProductos = response.data.productos.sort((a, b) => a.nombre.localeCompare(b.nombre));
        this.productos = [...this.productos, ...nuevosProductos];
      } catch (error) {
        console.error('Error al cargar más productos:', error);
      }
    },
    cargarCsv(event) {
      this.archivoCsv = event.target.files[0];
    },
    async procesarCsv() {
      const formData = new FormData();
      formData.append('file', this.archivoCsv);
      try {
        await apiClient.post('/api/productos/csv', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        });
        alert('Productos cargados correctamente');
        this.consultarProductos();
      } catch (error) {
        console.error('Error al cargar archivo CSV:', error);
      }
    },
    async eliminarProducto(id) {
      try {
        await apiClient.delete(`/api/productos/${id}`);
        alert('Producto eliminado correctamente');
        this.consultarProductos();
      } catch (error) {
        console.error('Error al eliminar producto:', error);
      }
    },
    editarProducto(producto) {
      this.modoEdicion = true;
      this.producto = { ...producto }; // Copia los datos del producto al formulario
    },
    async actualizarProducto() {
      try {
        await apiClient.put(`/api/productos/${this.producto.id}`, this.producto);
        alert('Producto actualizado correctamente');
        this.cancelarEdicion();
      } catch (error) {
        console.error('Error al actualizar producto:', error);
      }
    },
    cancelarEdicion() {
      this.modoEdicion = false;
      this.resetearFormulario();
    },
    resetearFormulario() {
      this.producto = {
        codigo: '',
        nombre: '',
        peso_total_gr: '',
        peso_unidad_gr: '',
        codigo_barras: '',
      };
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