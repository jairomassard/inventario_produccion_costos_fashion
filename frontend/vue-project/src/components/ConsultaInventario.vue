<template>
  <div class="consulta-inventario">
    <h1>Consulta de Inventario de Productos</h1>

    <div>
      <button @click="volverAlMenu" class="btn">Volver al Menú Principal</button>
      <button @click="limpiarPagina" class="btn btn-warning">Limpiar Página</button>
    </div>

    <!-- Filtros de búsqueda -->
    <div>
      <div>
        <label for="nombreFiltro">Buscar por nombre:</label>
        <input 
          type="text" 
          id="nombreFiltro"
          v-model="nombreDigitado"
          placeholder="Ingrese nombre del producto"
          class="form-control"
          @input="sincronizarPorNombre"
        />
      </div>
      <div>
        <label for="codigoFiltro">Buscar por código:</label>
        <input 
          v-model="codigoDigitado" 
          id="codigoFiltro" 
          placeholder="Ingrese código de producto" 
          class="form-control"
          @input="sincronizarCodigoConSelector"
        />
      </div>
      <div>
        <label for="productoSelector">Seleccione un producto:</label>
        <select v-model="filtroProducto" id="productoSelector" @change="sincronizarSelectorConCodigo">
          <option value="">Todos</option>
          <option v-for="producto in productosDisponibles" :key="producto.codigo" :value="producto.codigo">
            {{ producto.codigo }} - {{ producto.nombre }}
          </option>
        </select>
      </div>
      <!-- Filtro por estado movido arriba -->
      <div>
        <label for="filtroEstado">Filtrar por Estado:</label>
        <select v-model="filtroEstado" id="filtroEstado" @change="consultar">
          <option value="">Todos</option>
          <option value="verde">Verde (OK)</option>
          <option value="amarillo">Amarillo (Advertencia)</option>
          <option value="rojo">Rojo (Crítico)</option>
        </select>
      </div>
      <div>
        <button @click="consultar">Consultar Inventario</button>
      </div>
    </div>

    <!-- Filtros adicionales para consulta general -->
    <div v-if="mostrarInventario && filtroProducto === '' && codigoDigitado === '' && nombreDigitado === ''">
      <label for="filtroBodega">Filtrar por bodega:</label>
      <select v-model="filtroBodega" id="filtroBodega" @change="filtrarPorBodega">
        <option value="">Todas</option>
        <option v-for="bodega in bodegas" :key="bodega" :value="bodega">{{ bodega }}</option>
      </select>
    </div>
    <div v-if="mostrarInventario && filtroProducto === '' && codigoDigitado === '' && nombreDigitado === ''">
      <label for="umbralAlerta">Umbral de Alerta (%):</label>
      <input v-model.number="umbralAlerta" id="umbralAlerta" type="number" min="0" max="100" step="1" />
    </div>

    <!-- Tabla Resumen de Costos (solo para consulta general) -->
    <div v-if="mostrarInventario && filtroProducto === '' && codigoDigitado === '' && nombreDigitado === ''">
      <h2>Resumen de Costos por Almacén</h2>
      <table class="resumen-costos">
        <thead>
          <tr>
            <th>Almacén</th>
            <th>Costo Total</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="bodega in bodegasMostradas" :key="bodega">
            <td>{{ bodega }}</td>
            <td>${{ formatCosto(calcularCostoTotalBodega(bodega)) }}</td>
          </tr>
          <tr class="total-row">
            <td><strong>TOTAL</strong></td>
            <td><strong>${{ formatCosto(calcularCostoTotalInventario()) }}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Tabla de Inventario -->
    <div v-if="mostrarInventario">
      <h2>Inventario de Productos</h2>
      <button v-if="productosFiltrados.length" @click="exportarAExcel" class="btn">Exportar a Excel</button>
      <table>
        <thead>
          <tr>
            <th>Código</th>
            <th>Nombre</th>
            <th>Stock Mínimo</th> <!-- Nueva columna -->
            <th>Total</th>
            <th>Estado</th>
            <template v-for="bodega in bodegasMostradas" :key="bodega">
              <th>{{ bodega }}</th>
              <th>Costo Total {{ bodega }}</th>
            </template>
          </tr>
        </thead>
        <tbody>
          <tr v-for="producto in productosFiltrados" :key="producto.codigo">
            <td>{{ producto.codigo }}</td>
            <td>{{ producto.nombre }}</td>
            <td>{{ producto.stock_minimo !== null ? producto.stock_minimo : '-' }}</td> <!-- Mostrar stock_minimo -->
            <td>{{ producto.cantidad_total }}</td>
            <td>
              <span v-if="producto.stock_minimo !== null && producto.stock_minimo !== undefined">
                <span v-if="Number(producto.cantidad_total) > Number(producto.stock_minimo) * (1 + Number(umbralAlerta) / 100)" class="estado verde">✔</span>
                <span v-else-if="Number(producto.cantidad_total) > Number(producto.stock_minimo)" class="estado amarillo">⚠</span>
                <span v-else class="estado rojo">✖</span>
              </span>
              <span v-else>-</span>
            </td>
            <template v-for="bodega in bodegasMostradas" :key="bodega">
              <td>{{ producto.cantidades_por_bodega[bodega] || 0 }}</td>
              <td>${{ formatCosto(producto.costos_por_bodega[bodega] || 0) }}</td>
            </template>
          </tr>
        </tbody>
      </table>
      <div v-if="filtroProducto === '' && codigoDigitado === '' && nombreDigitado === ''" class="paginacion">
        <button :disabled="paginaActual === 1" @click="cambiarPagina(paginaActual - 1)">Anterior</button>
        <span>Página {{ paginaActual }}</span>
        <button :disabled="productosFiltrados.length < limite" @click="cambiarPagina(paginaActual + 1)">Siguiente</button>
      </div>
    </div>
  </div>
</template>

<script>
import apiClient from "../services/axios";
import * as XLSX from "xlsx";

export default {
  name: "ConsultaInventario",
  data() {
    return {
      filtroProducto: "",
      codigoDigitado: "",
      nombreDigitado: "",
      productosDisponibles: [],
      productos: [],
      productosFiltrados: [],
      bodegas: [],
      bodegasMostradas: [],
      filtroBodega: "",
      mostrarInventario: false,
      paginaActual: 1,
      limite: 20,
      todosLosProductos: [],
      umbralAlerta: 10, // Valor por defecto en porcentaje
      filtroEstado: ''
    };
  },
  methods: {
    limpiarPagina() {
      this.codigoDigitado = "";
      this.nombreDigitado = "";
      this.filtroProducto = "";
      this.filtroBodega = "";
      this.filtroEstado = "";
      this.productos = [];
      this.productosFiltrados = [];
      this.bodegas = [];
      this.bodegasMostradas = [];
      this.mostrarInventario = false;
      this.paginaActual = 1;
      this.todosLosProductos = [];
      this.umbralAlerta = 10; // Restaurar valor por defecto
    },
    async consultar() {
      if (this.filtroProducto || this.codigoDigitado || this.nombreDigitado) {
        await this.consultarProductoEspecifico();
      } else {
        await this.consultarTodosLosProductos();
      }
      this.filtrarPorEstado(); // Aplicar filtro por estado después de consultar
    },
    async consultarProductoEspecifico() {
      try {
        const codigo = this.filtroProducto || this.codigoDigitado;
        let url = `/api/inventario-con-costos/${codigo}`;
        if (this.nombreDigitado && !codigo) {
          url = `/api/inventario-con-costos?nombre=${encodeURIComponent(this.nombreDigitado)}&limit=999999`;
        }
        const response = await apiClient.get(url);
        const data = response.data;

        if (data.message) {
          alert(data.message);
          this.mostrarInventario = false;
          this.productos = [];
          this.bodegas = [];
          return;
        }

        const bodegasResponse = await apiClient.get("/api/bodegas");
        const todasLasBodegas = bodegasResponse.data.map((b) => b.nombre);

        this.bodegas = todasLasBodegas;
        this.bodegasMostradas = todasLasBodegas;
        if (data.producto) {
          this.productos = [{
            codigo: data.producto.codigo,
            nombre: data.producto.nombre,
            cantidad_total: data.inventario.reduce((total, item) => total + item.cantidad, 0),
            stock_minimo: data.producto.stock_minimo !== null ? Number(data.producto.stock_minimo) : null,
            cantidades_por_bodega: todasLasBodegas.reduce((acc, bodega) => {
              const item = data.inventario.find((i) => i.bodega === bodega);
              acc[bodega] = item ? item.cantidad : 0;
              return acc;
            }, {}),
            costos_por_bodega: todasLasBodegas.reduce((acc, bodega) => {
              const item = data.inventario.find((i) => i.bodega === bodega);
              acc[bodega] = item ? item.costo_total : 0;
              return acc;
            }, {})
          }];
        } else {
          this.productos = data.productos
            .sort((a, b) => a.codigo.localeCompare(b.codigo))
            .map(producto => ({
              codigo: producto.codigo,
              nombre: producto.nombre,
              cantidad_total: Number(producto.cantidad_total),
              stock_minimo: producto.stock_minimo !== null ? Number(producto.stock_minimo) : null,
              cantidades_por_bodega: producto.cantidades_por_bodega,
              costos_por_bodega: producto.costos_por_bodega
            }));
        }
        this.productosFiltrados = [...this.productos];
        this.mostrarInventario = true;
      } catch (error) {
        console.error("Error al consultar inventario específico:", error);
        alert("Ocurrió un error al consultar el inventario.");
      }
    },
    async consultarTodosLosProductos() {
      try {
        const offset = (this.paginaActual - 1) * this.limite;
        const response = await apiClient.get(`/api/inventario-con-costos?offset=${offset}&limit=${this.limite}`);
        const { productos, bodegas } = response.data;

        if (!productos || productos.length === 0) {
          alert("No se encontró información en el inventario.");
          this.mostrarInventario = false;
          return;
        }

        this.bodegas = bodegas || [];
        this.bodegasMostradas = [...this.bodegas];
        this.productos = productos
          .sort((a, b) => a.codigo.localeCompare(b.codigo))
          .map(producto => ({
            codigo: producto.codigo,
            nombre: producto.nombre,
            cantidad_total: Number(producto.cantidad_total),
            stock_minimo: producto.stock_minimo !== null ? Number(producto.stock_minimo) : null,
            cantidades_por_bodega: { ...producto.cantidades_por_bodega },
            costos_por_bodega: { ...producto.costos_por_bodega }
          }));
        this.productosFiltrados = [...this.productos];
        this.mostrarInventario = true;

        const fullResponse = await apiClient.get("/api/inventario-con-costos?limit=999999");
        this.todosLosProductos = fullResponse.data.productos
          .sort((a, b) => a.codigo.localeCompare(b.codigo))
          .map(producto => ({
            codigo: producto.codigo,
            nombre: producto.nombre,
            cantidad_total: Number(producto.cantidad_total),
            stock_minimo: producto.stock_minimo !== null ? Number(producto.stock_minimo) : null,
            cantidades_por_bodega: { ...producto.cantidades_por_bodega },
            costos_por_bodega: { ...producto.costos_por_bodega }
          }));
      } catch (error) {
        console.error("Error al consultar inventario general:", error);
        alert("Ocurrió un error al consultar el inventario general.");
      }
    },
    filtrarPorBodega() {
      if (this.filtroBodega) {
        this.bodegasMostradas = [this.filtroBodega];
        this.productosFiltrados = this.productos.map(producto => ({
          ...producto,
          cantidad_total: producto.cantidades_por_bodega[this.filtroBodega] || 0,
        }));
      } else {
        this.bodegasMostradas = [...this.bodegas];
        this.productosFiltrados = [...this.productos];
      }
    },
    filtrarPorEstado() {
      if (!this.filtroEstado) {
        this.productosFiltrados = [...this.productos];
      } else {
        this.productosFiltrados = this.todosLosProductos.filter(producto => {
          if (producto.stock_minimo === null || producto.stock_minimo === undefined) {
            return false;
          }
          const umbral = Math.ceil(Number(producto.stock_minimo) * (Number(this.umbralAlerta) / 100));
          const diff = Number(producto.cantidad_total) - Number(producto.stock_minimo);
          if (this.filtroEstado === 'verde') return diff > umbral;
          if (this.filtroEstado === 'amarillo') return diff <= umbral && diff > 0;
          if (this.filtroEstado === 'rojo') return diff <= 0;
        });
        // Aplicar paginación después de filtrar
        const start = (this.paginaActual - 1) * this.limite;
        this.productosFiltrados = this.productosFiltrados.slice(start, start + this.limite);
      }
    },
    async cargarProductosDisponibles() {
      try {
        const response = await apiClient.get("/api/productos/completos");
        this.productosDisponibles = response.data.sort((a, b) => a.codigo.localeCompare(b.codigo));
      } catch (error) {
        console.error("[ERROR] Al cargar productos disponibles:", error);
      }
    },
    cambiarPagina(nuevaPagina) {
      this.paginaActual = nuevaPagina;
      this.consultarTodosLosProductos();
    },
    sincronizarPorNombre() {
      const productoEncontrado = this.productosDisponibles.find(p => 
        p.nombre.toLowerCase().includes(this.nombreDigitado.toLowerCase())
      );
      if (productoEncontrado) {
        this.filtroProducto = productoEncontrado.codigo;
        this.codigoDigitado = productoEncontrado.codigo;
      }
    },
    sincronizarCodigoConSelector() {
      const productoEncontrado = this.productosDisponibles.find(p => p.codigo === this.codigoDigitado);
      if (productoEncontrado) {
        this.filtroProducto = productoEncontrado.codigo;
        this.nombreDigitado = productoEncontrado.nombre;
      }
    },
    sincronizarSelectorConCodigo() {
      const productoSeleccionado = this.productosDisponibles.find(p => p.codigo === this.filtroProducto);
      if (productoSeleccionado) {
        this.codigoDigitado = productoSeleccionado.codigo;
        this.nombreDigitado = productoSeleccionado.nombre;
      }
    },
    volverAlMenu() {
      const tipoUsuario = localStorage.getItem("tipo_usuario");
      if (tipoUsuario === "admin") {
        this.$router.push('/menu');
      } else if (tipoUsuario === "gerente") {
        this.$router.push('/menu-gerente');
      } else {
        alert("Rol no reconocido. Contacta al administrador.");
      }
    },
    formatCosto(costo) {
      return Number(costo).toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    },
    calcularCostoTotalBodega(bodega) {
      return this.productosFiltrados.reduce((total, producto) => {
        return total + (producto.costos_por_bodega[bodega] || 0);
      }, 0);
    },
    calcularCostoTotalInventario() {
      return this.bodegasMostradas.reduce((total, bodega) => {
        return total + this.calcularCostoTotalBodega(bodega);
      }, 0);
    },
    exportarAExcel() {
      const dataToExport = this.filtroProducto || this.codigoDigitado || this.nombreDigitado 
        ? this.productosFiltrados 
        : this.todosLosProductos;

      let worksheetData = [];

      if (!this.filtroProducto && !this.codigoDigitado && !this.nombreDigitado) {
        worksheetData = [
          ["Resumen de Costos por Almacén"],
          ["Almacén", "Costo Total"],
          ...this.bodegasMostradas.map(bodega => [
            bodega,
            this.calcularCostoTotalBodega(bodega),
          ]),
          ["TOTAL", this.calcularCostoTotalInventario()],
          [""],
        ];
      }

      const getEstado = (producto) => {
        if (producto.stock_minimo === null || producto.stock_minimo === undefined) {
          return "-";
        }
        const cantidadTotal = Number(producto.cantidad_total);
        const stockMinimo = Number(producto.stock_minimo);
        const umbral = Math.ceil(stockMinimo * (Number(this.umbralAlerta) / 100));
        if (cantidadTotal > stockMinimo + umbral) {
          return "✔";
        } else if (cantidadTotal > stockMinimo) {
          return "⚠";
        } else {
          return "✖";
        }
      };

      worksheetData.push(
        ["Inventario de Productos"],
        ["Código", "Nombre", "Stock Mínimo", "Total", "Estado", ...this.bodegasMostradas.flatMap(bodega => [bodega, `Costo Total ${bodega}`])],
        ...dataToExport.map(producto => [
          producto.codigo,
          producto.nombre,
          producto.stock_minimo !== null ? producto.stock_minimo : "-",
          producto.cantidad_total,
          getEstado(producto),
          ...this.bodegasMostradas.flatMap(bodega => [
            producto.cantidades_por_bodega[bodega] || 0,
            producto.costos_por_bodega[bodega] || 0,
          ]),
        ])
      );

      const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);
      const workbook = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(workbook, worksheet, "Inventario");
      XLSX.writeFile(workbook, `inventario_${new Date().toISOString().slice(0,10)}.xlsx`);
    },
  },
  mounted() {
    this.cargarProductosDisponibles();
  },
};
</script>


<style scoped>
  /* Contenedor principal */
  .consulta-inventario {
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

  h2 {
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

  button:disabled {
    background-color: #cccccc;
    cursor: not-allowed;
  }

  button.btn-warning {
    background-color: #ffc107; /* Amarillo para advertencias */
    color: #333; /* Texto oscuro */
  }

  button.btn-warning:hover {
    background-color: #e0a800; /* Amarillo más oscuro */
  }

  /* Formularios y filtros */
  label {
    font-weight: bold;
    display: block;
    margin-bottom: 5px;
    color: #555;
  }

  select, input {
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
    text-align: center;
  }

  th {
    background-color: #f8f9fa;
    color: #333;
    font-weight: bold;
    white-space: normal;
  }

  tbody tr:nth-child(odd) {
    background-color: #f9f9f9;
  }

  tbody tr:hover {
    background-color: #f1f1f1;
  }

  td {
    white-space: nowrap;
  }

  /* Tabla Resumen de Costos */
  .resumen-costos {
    width: 50%;
    margin: 0 auto 30px;
  }

  .resumen-costos th, .resumen-costos td {
    padding: 12px;
  }

  .total-row {
    font-weight: bold;
    background-color: #e9ecef;
  }

  /* Estado de productos */
  .estado.verde { color: green; font-size: 18px; }
  .estado.amarillo { color: rgba(255, 145, 0, 0.904); font-size: 18px; }
  .estado.rojo { color: red; font-size: 18px; }


  /* Paginación */
  .paginacion {
    margin-top: 20px;
    text-align: center;
  }

  /* --- Responsividad --- */
  @media (max-width: 768px) {
    .consulta-inventario {
      margin: 10px auto;
      padding: 10px;
    }

    select, input, button {
      width: 100%;
      margin-bottom: 10px;
      font-size: 16px;
    }

    table {
      display: block;
      overflow-x: auto;
      white-space: nowrap;
    }

    .resumen-costos {
      width: 100%;
    }

    th, td {
      font-size: 12px;
      padding: 8px;
    }

    h1 {
      font-size: 20px;
    }

    h2 {
      font-size: 18px;
    }
  }
</style>