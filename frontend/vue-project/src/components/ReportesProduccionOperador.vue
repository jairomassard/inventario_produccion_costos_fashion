<template>
  <div class="reportes-produccion">
    <h1>Reportes de Producción</h1>

    <div>
      <button @click="volverAlMenu" class="btn btn-secondary">Volver al Menú Principal</button>
      <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
    </div>

    <!-- Filtros -->
    <section>
      <h2>Consultar Órdenes</h2>
      <label for="numero-orden">Número de Orden:</label>
      <input
        type="text"
        id="numero-orden"
        v-model="filtroNumeroOrden"
        placeholder="Número de Orden"
      />
      <br />
      <label for="estado">Estado:</label>
      <select v-model="filtroEstado" id="estado">
        <option value="">Todos</option>
        <option value="Pendiente">Pendiente</option>
        <option value="Lista para Producción">Lista para Producción</option>
        <option value="En Producción">En Producción</option>
        <option value="En Producción-Parcial">En Producción-Parcial</option>
        <option value="Finalizada">Finalizada</option>
      </select>
      <br />
      <label for="fecha-inicio">Fecha Inicio:</label>
      <input type="date" id="fecha-inicio" v-model="filtroFechaInicio" />
      <label for="fecha-fin">Fecha Fin:</label>
      <input type="date" id="fecha-fin" v-model="filtroFechaFin" />
      <br />
      <p class="info-message">
        Nota: Para incluir órdenes del día actual, seleccione un día adicional para Fecha Fin.
      </p>
      <button @click="consultarOrdenes">Consultar</button>
      <button @click="imprimirListadoPdf">Imprimir Listado <i class="fas fa-file-pdf pdf-icon"></i></button>
    </section>

    <!-- Tabla de órdenes -->
    <section v-if="tablaOrdenesVisible">
      <h2 v-if="ordenes.length > 0">Órdenes de Producción</h2>
      <table v-if="ordenes.length > 0">
        <thead>
          <tr>
            <th>ID</th>
            <th>Número de Orden</th>
            <th>Producto</th>
            <th>Cantidad a Producir</th>
            <th>Estado</th>
            <th>Fecha Estado</th>
            <th>Acciones</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="orden in ordenes" :key="orden.id">
            <td>{{ orden.id }}</td>
            <td>{{ orden.numero_orden }}</td>
            <td>{{ orden.producto_compuesto_nombre }}</td>
            <td>{{ orden.cantidad_paquetes }}</td>
            <td>{{ orden.estado }}</td>
            <td>{{ obtenerFechaEstado(orden) }}</td>
            <td>
              <button @click="cargarDetalleOrden(orden.id)">Detalle</button>
              <button @click="descargarPdfOperador(orden.id)">Imprimir <i class="fas fa-file-pdf pdf-icon"></i></button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="ordenes.length === 0 && filtroEstado !== '' && filtroNumeroOrden === ''">No se encontraron órdenes de producción.</p>
    </section>

    

    <!-- Detalle de la orden -->
    <section v-if="mostrarDetalle" class="detalle-orden">
      <h2>Detalle de la Orden</h2>
      <div class="acciones-orden">
        <button @click="descargarPdfOperador(detalleOrden.id)">Imprimir Detalle <i class="fas fa-file-pdf pdf-icon"></i></button>
      </div>

      <div class="info-general">
        <p><strong>Número de Orden:</strong> {{ detalleOrden.numero_orden }}</p>
        <p><strong>Producto:</strong> {{ detalleOrden.producto_compuesto_nombre }}</p>
        <p><strong>Cantidad de Paquetes:</strong> {{ detalleOrden.cantidad_paquetes }}</p>
        <p><strong>Bodega de Producción:</strong> {{ detalleOrden?.bodega_produccion_nombre || 'No especificada' }}</p>
        <p><strong>Estado:</strong> {{ detalleOrden?.estado || '-' }}</p>
      </div>

      <!-- Tabla de fechas -->
      <table class="tabla-fechas">
        <thead>
          <tr>
            <th colspan="4">-- Fechas de Producción --</th>
          </tr>
          <tr>
            <th>Creación</th>
            <th>Lista para Producción</th>
            <th>Inicio Producción</th>
            <th>Finalización</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{{ formatFecha(detalleOrden.fecha_creacion) }}</td>
            <td>{{ formatFecha(detalleOrden.fecha_lista_para_produccion) }}</td>
            <td>{{ formatFecha(detalleOrden.fecha_inicio) }}</td>
            <td>{{ formatFecha(detalleOrden.fecha_finalizacion) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- Tabla de responsables -->
      <table class="tabla-responsables">
          <tbody>
            <tr>
              <td class="label">Creado por</td>
              <td class="value">{{ detalleOrden?.creado_por || 'N/A' }}</td>
              <td class="label">Producido por</td>
              <td class="value">{{ detalleOrden?.producido_por || 'N/A' }}</td>
            </tr>
          </tbody>
      </table>

      <!-- Tabla de componentes (sin costos) -->
      <table class="tabla-componentes">
        <thead>
          <tr>
            <th style="width: 60%">Componente</th>
            <th style="width: 15%">Cant. x Paquete</th>
            <th style="width: 15%">Cant. Total</th>
            <th style="width: 10%">Peso Total</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="componente in componentes" :key="componente.nombre">
            <td>{{ componente.nombre }}</td>
            <td>{{ Number(componente.cant_x_paquete).toFixed(2) }}</td>
            <td>{{ Number(componente.cantidad_total).toFixed(2) }}</td>
            <td>{{ Number(componente.peso_total).toFixed(2) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- Tabla de Historial de Entregas -->
      <h3>Historial de Entregas</h3>
      <table class="tabla-historial" v-if="historialEntregas.length > 0">
        <thead>
          <tr>
            <th>Cantidad Entregada</th>
            <th>Fecha y Hora</th>
            <th>Comentario</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entrega in historialEntregas" :key="entrega.id">
            <td>{{ entrega.cantidad }}</td>
            <td>{{ formatFecha(entrega.fecha_hora) }}</td>
            <td>{{ entrega.comentario || 'N/A' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else>No hay entregas registradas para esta orden.</p>

      <div v-if="detalleOrden.comentario_cierre_forzado">
        <h3>Cierre Forzado:</h3>
        <p>{{ detalleOrden.comentario_cierre_forzado }}</p>
      </div>
      <div v-else-if="detalleOrden.estado === 'Finalizada'">
        <h3>Orden Finalizada sin Novedad</h3>
      </div>
    </section>
  </div>
</template>
  
<script>
import apiClient from "../services/axios";

export default {
  data() {
    return {
      filtroNumeroOrden: "",
      filtroEstado: "",
      filtroFechaInicio: "",
      filtroFechaFin: "",
      ordenes: [],
      detalleOrden: null,
      componentes: [],
      historialEntregas: [],
      mostrarDetalle: false,
      tablaOrdenesVisible: true, // Añadir esta línea
    };
  },
  methods: {
    formatFecha(fecha) {
      if (!fecha) return "-";
      const fechaObj = new Date(fecha);
      return fechaObj.toLocaleString("es-CO", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    },
    limpiarPagina() {
      this.filtroNumeroOrden = "";
      this.filtroEstado = "";
      this.filtroFechaInicio = "";
      this.filtroFechaFin = "";
      this.ordenes = [];
      this.detalleOrden = null;
      this.componentes = [];
      this.historialEntregas = [];
      this.mostrarDetalle = false;
      this.tablaOrdenesVisible = true; // Añadir esta línea
    },
    obtenerFechaEstado(orden) {
      switch (orden.estado) {
        case "Pendiente":
          return this.formatFecha(orden.fecha_creacion);
        case "Lista para Producción":
          return this.formatFecha(orden.fecha_lista_para_produccion);
        case "En Producción":
        case "En Producción-Parcial":
          return this.formatFecha(orden.fecha_inicio);
        case "Finalizada":
          return this.formatFecha(orden.fecha_finalizacion);
        default:
          return "-";
      }
    },
    async consultarOrdenes() {
      try {
        const params = {};
        if (this.filtroNumeroOrden) {
          params.numero_orden = this.filtroNumeroOrden;
        } else {
          if (this.filtroEstado) params.estado = this.filtroEstado;
          if (this.filtroFechaInicio && this.filtroFechaFin) {
            params.fecha_inicio = this.filtroFechaInicio;
            params.fecha_fin = this.filtroFechaFin;
          }
        }
        const response = await apiClient.get("/api/ordenes-produccion/filtrar", { params });
        this.ordenes = response.data.sort((a, b) => b.id - a.id);
        this.mostrarDetalle = false;
        this.detalleOrden = {};
        this.tablaOrdenesVisible = true; // Añadir esta línea
      } catch (error) {
        console.error("Error al consultar órdenes de producción:", error);
        alert("No se pudieron consultar las órdenes de producción.");
      }
    },
    async imprimirListadoPdf() {
      try {
        const params = {
          estado: this.filtroEstado || null,
          fecha_inicio: this.filtroFechaInicio || null,
          fecha_fin: this.filtroFechaFin || null,
        };
        const response = await apiClient.post("/api/ordenes-produccion/listado-operador-pdf", params, {
          responseType: "blob",
        });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", "Listado_Ordenes_Produccion.pdf");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch (error) {
        console.error("Error al imprimir el listado en PDF:", error);
        alert("No se pudo generar el PDF del listado.");
      }
    },
    async cargarDetalleOrden(ordenId) {
      try {
        const detalleResponse = await apiClient.get(`/api/ordenes-produccion/${ordenId}`);
        this.detalleOrden = detalleResponse.data.orden || {};
        this.detalleOrden.bodega_produccion_nombre = detalleResponse.data.orden.bodega_produccion_nombre || "No especificada";
        
        // Mapear componentes sin costos
        if (detalleResponse.data.materiales) {
          this.componentes = detalleResponse.data.materiales.map((componente) => ({
            nombre: componente.producto_base_nombre,
            cant_x_paquete: componente.cant_x_paquete,
            cantidad_total: componente.cantidad_total,
            peso_total: componente.peso_total,
          }));
        } else {
          this.componentes = [];
        }

        const historialResponse = await apiClient.get(`/api/ordenes-produccion/${ordenId}/historial-entregas`);
        this.historialEntregas = historialResponse.data.historial || [];
        this.mostrarDetalle = true;
        this.tablaOrdenesVisible = false; // Añadir esta línea
      } catch (error) {
        console.error("Error al cargar detalle de la orden:", error);
        alert("No se pudo cargar el detalle de la orden.");
        this.mostrarDetalle = false;
      }
    },
    async descargarPdfOperador(ordenId) {
      try {
        if (!ordenId) {
          alert("El ID de la orden no está disponible.");
          return;
        }
        const response = await apiClient.get(`/api/ordenes-produccion/${ordenId}/pdf-operador`, {
          responseType: "blob",
        });
        const url = window.URL.createObjectURL(new Blob([response.data]));
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", `Orden_${ordenId}_Operador.pdf`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch (error) {
        console.error("Error al descargar el PDF para operador:", error);
        alert("No se pudo descargar el PDF de la orden.");
      }
    },
    volverAlMenu() {
      const tipoUsuario = localStorage.getItem("tipo_usuario");
      if (tipoUsuario === "admin") {
        this.$router.push('/menu');
      } else if (tipoUsuario === "gerente") {
        this.$router.push('/menu-gerente');
      } else if (tipoUsuario === "operador") {
        this.$router.push('/menu-operador');
      } else {
        alert("Rol no reconocido. Contacta al administrador.");
      }
    },
  },
};
</script>
  
<style scoped>
/* Contenedor principal */
.reportes-produccion {
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

.btn-secondary {
  background-color: #6c757d;
}

.btn-secondary:hover {
  background-color: #5a6268;
}

.btn-warning {
  background-color: #ffc107;
  color: #333;
}

.btn-warning:hover {
  background-color: #e0a800;
}

/* Formularios */
label {
  font-weight: bold;
  display: block;
  margin-bottom: 5px;
  color: #555;
}

input, select {
  width: 100%;
  padding: 10px;
  margin-bottom: 15px;
  border: 1px solid #ccc;
  border-radius: 4px;
  font-size: 14px;
}

.info-message {
  color: #666;
  font-style: italic;
  margin-bottom: 10px;
}

/* Tablas generales */
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

/* Detalle de la orden */
.detalle-orden {
  background-color: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.acciones-orden {
  margin-bottom: 15px;
}

.info-general p {
  margin: 5px 0;
  font-size: 14px;
  color: #333;
}

.info-general p strong {
  color: #0056b3;
}

/* Tabla de fechas */
.tabla-fechas {
  width: 100%;
  margin: 15px 0;
  border-collapse: collapse;
  background-color: #f8f9fa;
  border-radius: 4px;
  overflow: hidden;
}

.tabla-fechas th, .tabla-fechas td {
  padding: 10px;
  border: 1px solid #e9ecef;
  text-align: center;
  width: 25%;
  height: 40px;
}

.tabla-fechas th {
  background-color: #e9ecef;
  color: #555;
  font-weight: bold;
}

.tabla-fechas td {
  color: #333;
  font-size: 12px;
}


  /* Tabla de responsables */
  .tabla-responsables {
    width: 100%;
    margin: 15px 0;
    border-collapse: collapse;
    background-color: #f8f9fa;
    border-radius: 4px;
    overflow: hidden;
  }
  
  .tabla-responsables td {
    padding: 10px;
    border: 1px solid #e9ecef;
    text-align: center;
  }
  
  .tabla-responsables .label {
    background-color: #e9ecef;
    font-weight: bold;
    color: #555;
  }
  
  .tabla-responsables .value {
    color: #333;
  }

/* Tabla de componentes */
.tabla-componentes {
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
  font-size: 14px;
  background-color: #fff;
  border-radius: 4px;
  overflow: hidden;
}

/* Tabla de historial */
.tabla-historial {
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
  font-size: 14px;
  background-color: #fff;
  border-radius: 4px;
  overflow: hidden;
}

/* Historial de entregas */
p {
  margin: 5px 0;
  color: #555;
  font-size: 14px;
}

/* --- Responsividad --- */
@media (max-width: 768px) {
  .reportes-produccion {
    margin: 10px auto;
    padding: 10px;
  }

  input, select, button {
    width: 100%;
    margin-bottom: 10px;
    font-size: 16px;
  }

  table {
    display: block;
    overflow-x: auto;
    white-space: nowrap;
  }

  th, td {
    font-size: 12px;
    padding: 8px;
  }

  h1 {
    font-size: 20px;
  }

  h2, h3 {
    font-size: 18px;
  }

  .tabla-fechas td {
    font-size: 10px;
  }
}
</style>
  