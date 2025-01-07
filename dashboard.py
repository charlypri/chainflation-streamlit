import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from functions import *
import folium
from streamlit_folium import st_folium
import plotly.express as px
import requests
from streamlit_option_menu import option_menu
import plotly.graph_objects as go
from datetime import date

load_dotenv()

# Configuración básica de Streamlit
st.set_page_config(page_title="Chainflation - Dashboard", page_icon="📊", layout="wide")


@st.cache_resource(hash_funcs={"pymongo.mongo_client.MongoClient": id})
def load_data():
    """
    Carga los datos de precios de productos y categorías de inflación desde MongoDB.

    Returns:
        prod_prices (dict): Diccionario que contiene los precios de los productos (alimentación, vivienda, energía).
        category_infl (DataFrame): DataFrame que contiene la inflación por categorías.
    """
    prod_prices = getProductPrices()
    category_infl = getCategoriesInflation()
    return prod_prices, category_infl


def display_sidebar_menu():
    """
    Muestra el menú lateral de la aplicación.

    Returns:
        menu (str): Opción seleccionada del menú.
    """
    with st.sidebar:
        menu = option_menu(
            "Explora los Datos",
            ["General", "Precios de Alimentos", "Precios de Vivienda"],
            icons=["", "gear", "bi-joystick"],
            menu_icon="",
            default_index=0,
        )
    return menu


def filter_vivienda_data(vivienda_df, producto_tipo, fecha_inicio, fecha_fin):
    """
    Filtra los datos de precios de vivienda por tipo de producto (venta o alquiler) y fechas.

    Args:
        vivienda_df (DataFrame): DataFrame con los datos de precios de vivienda.
        producto_tipo (str): Tipo de producto, puede ser 'Venta' o 'Alquiler'.
        fecha_inicio (datetime): Fecha de inicio del rango.
        fecha_fin (datetime): Fecha de fin del rango.

    Returns:
        DataFrame: Datos filtrados por tipo de producto y fechas.
    """
    return vivienda_df[
        (vivienda_df["producto"] == producto_tipo)
        & (vivienda_df["fecha"] >= pd.to_datetime(fecha_inicio))
        & (vivienda_df["fecha"] <= pd.to_datetime(fecha_fin))
    ]


def filter_alimentacion_data(alimentacion_df, supermercado, fecha_inicio, fecha_fin):
    """
    Filtra los datos de precios de alimentación por supermercado y fechas.

    Args:
        alimentacion_df (DataFrame): DataFrame con los datos de precios de alimentación.
        supermercado (str): Supermercado seleccionado.
        fecha_inicio (datetime): Fecha de inicio del rango.
        fecha_fin (datetime): Fecha de fin del rango.

    Returns:
        DataFrame: Datos filtrados por supermercado y fechas.
    """
    return alimentacion_df[
        (alimentacion_df["fuente"] == supermercado)
        & (alimentacion_df["fecha"] >= pd.to_datetime(fecha_inicio))
        & (alimentacion_df["fecha"] <= pd.to_datetime(fecha_fin))
    ]


def plot_inflation_trend(category_infl, date_range):
    """
    Crea una gráfica de la tendencia de inflación por categorías en función del rango de fechas seleccionado.

    Args:
        category_infl (DataFrame): DataFrame con los datos de inflación por categorías.
        date_range (str): Periodo de tiempo seleccionado por el usuario.

    Returns:
        fig (go.Figure): Figura de Plotly con la gráfica de la tendencia de inflación.
    """
    fig = go.Figure()
    time_periods = {
        "3 month": date.today() - timedelta(days=91),
        "6 Months": date.today() - timedelta(days=180),
        "1 year": date.today() - timedelta(days=365),
        "5 years": date.today() - timedelta(days=720),
    }

    for category in category_infl["category"].unique():
        category_data = category_infl[
            category_infl["category"] == category
        ].sort_values("fecha")

        category_data = category_data[
            category_data["fecha"].dt.date > time_periods[date_range]
        ]

        fig.add_trace(
            go.Scatter(
                x=category_data["fecha"],
                y=category_data["inflation"],
                mode="lines+markers",
                name=category.capitalize(),
                marker=dict(
                    size=15,
                    line=dict(
                        width=0,  # Set to 0 to remove the border
                        color="rgba(0,0,0,0)"  # Transparent border color
                    )
                ),
                line=dict(width=4),
                hoverlabel=dict(
                    font=dict(
                        size=20  # Set the desired font size
                    )
                ),
                hovertemplate="%{x}<br>Inflation: %{y:.1f}%<extra></extra>"


            )
        )

    fig.update_layout(
        xaxis_title="Fecha",
        yaxis_title="Inflación (%)",
        height=600,
        title=dict(
            text="Inflación YoY de Chainflation",
            font=dict(
                size=30,
            )
        ),
        legend=dict(
            font=dict(
                size=25,
            )
        ),
        xaxis=dict(
            title="Fecha",
            titlefont=dict(size=30),
            tickfont=dict(size=25),
        ),
        yaxis=dict(
            title="Inflación (%)",
            titlefont=dict(size=30),
            tickfont=dict(size=25),
        ),
        font=dict(
            size=24,
        )
    )
    return fig


def display_metrics(category_infl, metric_type):
    """
    Muestra las métricas de inflación máximas o mínimas por categoría.

    Args:
        category_infl (DataFrame): DataFrame con los datos de inflación por categorías.
        metric_type (str): Tipo de métrica a mostrar, puede ser 'max' o 'min'.
    """
    categories = category_infl["category"].unique()
    sorted_categories = sorted(categories, key=lambda x: (x != "total", x))

    for category in sorted_categories:
        category_data = category_infl[category_infl["category"] == category]

        if metric_type == "max":
            metric_row = category_data.loc[category_data["inflation"].idxmax()]
        else:
            metric_row = category_data.loc[category_data["inflation"].idxmin()]

        month = metric_row["fecha"].strftime("%B %Y")
        value = metric_row["inflation"]
        with st.container(border=True):
            st.metric(
                label=f"{category.capitalize()}",
                value=month,
                delta=f"{value:.2f}%",
                delta_color="inverse"
            )


def obtener_provincia_mas_cara_y_mas_barata(df_vivienda_filtrado):
    """
    Retorna la provincia más cara y más barata según el precio.
    """
    provincia_mas_cara = df_vivienda_filtrado.loc[
        df_vivienda_filtrado["precio"].idxmax()
    ]
    provincia_mas_barata = df_vivienda_filtrado.loc[
        df_vivienda_filtrado["precio"].idxmin()
    ]
    return provincia_mas_cara, provincia_mas_barata


def obtener_provincia_mayor_aumento_y_bajada(df_vivienda_filtrado):
    """
    Retorna la provincia que más ha aumentado y más ha disminuido en valor.
    """
    df_vivienda_filtrado = (
        df_vivienda_filtrado.sort_values(
            "fecha"
        )  # Asegurar que los datos están ordenados por fecha
        .groupby("provincia")
        .agg(
            precio_inicio=("precio", "first"),
            precio_fin=("precio", "last"),
        )
        .reset_index()
        .copy()
    )
    df_vivienda_filtrado["variacion"] = (
        df_vivienda_filtrado["precio_fin"] - df_vivienda_filtrado["precio_inicio"]
    )

    provincia_mayor_aumento = df_vivienda_filtrado.loc[
        df_vivienda_filtrado["variacion"].idxmax()
    ]
    provincia_mayor_bajada = df_vivienda_filtrado.loc[
        df_vivienda_filtrado["variacion"].idxmin()
    ]
    return provincia_mayor_aumento, provincia_mayor_bajada


def obtener_provincias_con_mas_variacion(df_vivienda_filtrado):
    """
    Retorna las 5 provincias con mayor y menor variación entre el primer y último día de los datos disponibles.
    """
    # Agrupar por provincia y calcular el precio del primer y último día
    variacion_provincias = (
        df_vivienda_filtrado.sort_values(
            "fecha"
        )  # Asegurar que los datos están ordenados por fecha
        .groupby("provincia")
        .agg(
            precio_inicio=("precio", "first"),
            precio_fin=("precio", "last"),
        )
        .copy()
    )

    # Calcular la variación porcentual entre el primer y último día
    variacion_provincias["variacion"] = (
        variacion_provincias["precio_fin"] - variacion_provincias["precio_inicio"]
    ) / variacion_provincias["precio_inicio"]

    # Seleccionar las 5 provincias con mayor aumento y mayor bajada
    top_aumento_provincias = variacion_provincias.nlargest(5, "variacion")
    top_bajada_provincias = variacion_provincias.nsmallest(5, "variacion")

    # Concatenar para un gráfico comparativo
    top_variacion_provincias = pd.concat(
        [top_aumento_provincias, top_bajada_provincias]
    ).reset_index()

    return top_variacion_provincias.sort_values("variacion")


def obtener_producto_mas_caro_y_mas_barato(df_filtrado):
    """
    Retorna el producto más caro y el más barato según el precio de referencia.
    """
    producto_mas_caro = df_filtrado.loc[df_filtrado["precio_referencia"].idxmax()]
    producto_mas_barato = df_filtrado.loc[df_filtrado["precio_referencia"].idxmin()]
    return producto_mas_caro, producto_mas_barato


def obtener_producto_mayor_aumento_y_bajada(df_filtrado):
    """
    Retorna el producto que más ha aumentado y más ha disminuido en valor.
    """
    variacion_productos = (
        df_filtrado.sort_values(
            "fecha"
        )  # Asegurar que los datos están ordenados por fecha
        .groupby("producto")
        .agg(
            precio_inicio=("precio", "first"),
            precio_fin=("precio", "last"),
        )
        .reset_index()
        .copy()
    )

    variacion_productos["diferencia"] = (
        variacion_productos["precio_fin"] - variacion_productos["precio_inicio"]
    )

    producto_mayor_aumento = variacion_productos.loc[
        variacion_productos["diferencia"].idxmax()
    ]
    producto_mayor_bajada = variacion_productos.loc[
        variacion_productos["diferencia"].idxmin()
    ]
    return producto_mayor_aumento, producto_mayor_bajada


def obtener_productos_con_mas_variacion(df_filtrado):
    """
    Retorna los 5 productos con mayor aumento y los 5 con mayor bajada
    entre el primer y último día de los datos disponibles.
    """
    # Agrupar por producto y calcular el precio inicial y final
    variacion_productos = (
        df_filtrado.sort_values(
            "fecha"
        )  # Asegurar que los datos están ordenados por fecha
        .groupby("producto")
        .agg(
            precio_inicio=("precio_referencia", "first"),
            precio_fin=("precio_referencia", "last"),
        )
    )

    # Calcular la variación porcentual entre el primer y último día
    variacion_productos["variacion"] = (
        variacion_productos["precio_fin"] - variacion_productos["precio_inicio"]
    ) / variacion_productos["precio_inicio"]

    # Seleccionar los 5 productos con mayor aumento y mayor bajada
    top_aumento = variacion_productos.nlargest(5, "variacion")
    top_bajada = variacion_productos.nsmallest(5, "variacion")

    # Concatenar para un gráfico comparativo
    top_variacion = pd.concat([top_aumento, top_bajada]).reset_index()

    return top_variacion.sort_values("variacion")


def comparar_precios_entre_supermercados(alimentacion_df):
    """
    Retorna los productos más baratos en promedio por supermercado.
    """
    precios_promedio = (
        alimentacion_df.groupby(["fuente", "producto"])["precio_referencia"]
        .mean()
        .reset_index()
    )
    productos_mas_baratos = precios_promedio.loc[
        precios_promedio.groupby("producto")["precio_referencia"].idxmin()
    ]
    return productos_mas_baratos


def display_visualizations(df_vivienda_filtrado, top_variacion_provincias):
    # Create and show map
    geojson_provincias, full_data = prepare_geojson(df_vivienda_filtrado)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🌍 Precios Medio por Provincias en Mapa Coroplético")
        show_map(geojson_provincias, full_data)

    # Bar chart for prices by province
    with col2:
        st.subheader("📊 Provincias ordenadas por precio promedio")
        show_price_bar_chart(df_vivienda_filtrado)

    # Bar chart for provinces with most price variation
    st.subheader("📊 Provincias que más han subido y bajado en precio", divider="blue")
    show_variation_bar_chart(top_variacion_provincias)


def prepare_geojson(df_vivienda_filtrado):
    geojson_url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/spain-provinces.geojson"
    response = requests.get(geojson_url)
    geojson_provincias = response.json()

    # Process GeoJSON and map with province data
    precios_promedio_provincia = (
        df_vivienda_filtrado.groupby("provincia")["precio"].mean().reset_index()
    )
    full_data = merge_with_geojson(geojson_provincias, precios_promedio_provincia)

    return geojson_provincias, full_data


def merge_with_geojson(geojson_provincias, precios_promedio_provincia):
    geojson_province_names = [
        feature["properties"]["name"] for feature in geojson_provincias["features"]
    ]
    geojson_province_df = pd.DataFrame({"provincia": geojson_province_names})

    province_mapping = {
        "Zaragoza": "Zaragoza",
        "València": "València/Valencia",
        "Sevilla": "Sevilla",
        "Palma": "Illes Balears",
        "Murcia": "Murcia",
        "Málaga": "Málaga",
        "Madrid": "Madrid",
        "Córdoba": "Córdoba",
        "Bilbao": "Bizkaia/Vizcaya",
        "Barcelona": "Barcelona",
        "Alicante": "Alacant/Alicante",
    }

    # Apply mapping
    precios_promedio_provincia["provincia"] = precios_promedio_provincia[
        "provincia"
    ].map(province_mapping)

    full_data = geojson_province_df.merge(
        precios_promedio_provincia, how="left", on="provincia"
    )
    full_data["precio"] = full_data["precio"].fillna(0)

    # Unir los datos del precio con las provincias en el GeoJSON
    for feature in geojson_provincias["features"]:
        provincia_name = feature["properties"]["name"]
        matching_data = precios_promedio_provincia[
            precios_promedio_provincia["provincia"] == provincia_name
        ]
        if not matching_data.empty:
            feature["properties"]["precio"] = matching_data["precio"].values[
                0
            ]  # Añadir el precio a la propiedad

    return full_data


def show_map(geojson_provincias, full_data):
    mapa = folium.Map(
        location=[40.4168, -3.7038], zoom_start=6, tiles="cartodb positron"
    )

    choropleth = folium.Choropleth(
        geo_data=geojson_provincias,
        name="choropleth",
        data=full_data,
        columns=["provincia", "precio"],
        key_on="feature.properties.name",
        fill_color="YlGnBu",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Precio promedio (€/m2)",
    )
    choropleth.add_to(mapa)

    folium.GeoJsonTooltip(
        fields=["name", "precio"],
        aliases=["Provincia:", "Precio promedio (€/m2):"],
        localize=True,
        sticky=False,
    ).add_to(choropleth.geojson)

    st_data = st_folium(mapa, width=700)


def show_price_bar_chart(df_vivienda_filtrado):
    precios_promedio_provincia = (
        df_vivienda_filtrado.groupby("provincia")["precio"].mean().reset_index()
    )
    fig_bar_provincias = px.bar(
        precios_promedio_provincia.sort_values("precio", ascending=False),
        x="provincia",
        y="precio",
        color="precio",
        title="Provincias ordenadas por precio promedio",
        labels={"precio": "Precio promedio (€)", "provincia": "Provincia"},
        color_continuous_scale=px.colors.sequential.Blues,
    )
    fig_bar_provincias.update_layout(
        yaxis_title="Precio promedio (€)", xaxis_title="Provincia", height=650
    )
    st.plotly_chart(fig_bar_provincias, use_container_width=True)


def show_variation_bar_chart(top_variacion_provincias):
    fig_variacion_provincias = px.bar(
        top_variacion_provincias,
        x="provincia",
        y="variacion",
        color="variacion",
        labels={"variacion": "Cambio porcentual (%)", "provincia": "Provincia"},
        color_continuous_scale=["red", "green"],
    )
    fig_variacion_provincias.update_layout(
        barmode="group", yaxis_title="Cambio porcentual (%)", xaxis_title="Provincia"
    )
    st.plotly_chart(fig_variacion_provincias, use_container_width=True)


# Cargar los datos
prod_prices, category_infl = load_data()
alimentacion_df = prod_prices["alimentacion"]
vivienda_df = prod_prices["vivienda"]
energia_df = prod_prices["energia"]

alimentacion_df["producto"] = alimentacion_df["producto"].str.capitalize()
vivienda_df = vivienda_df[vivienda_df["provincia"] != "España"]
vivienda_df["producto"] = vivienda_df["producto"].str.capitalize()

# Mostrar el menú lateral
menu = display_sidebar_menu()

# Mostrar análisis general
if menu == "General":
    st.title("Inflación en España - Chainflation")
    st.divider()

    col1, col2 = st.columns([1, 3])
    with col1:
        date_range = st.selectbox(
            label="Period",
            options=["3 month", "6 Months", "1 year", "5 years"],
            index=2,
        )
    with st.container(border=True):
        fig = plot_inflation_trend(category_infl, date_range)
        st.plotly_chart(fig)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Máximos registrados")
        display_metrics(category_infl, "max")
    with col2:
        st.subheader("Mínimos registrados")
        display_metrics(category_infl, "min")


if menu == "Precios de Alimentos":
    # Análisis de precios de alimentos
    st.title("📊 Análisis de Precios de Alimentos")
    st.divider()

    # Columna para los filtros principales
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        supermercados = alimentacion_df["fuente"].unique()
        supermercado_seleccionado = st.selectbox(
            "Selecciona un supermercado", supermercados
        )
    with col2:
        fecha_inicio = st.date_input("Fecha de inicio", pd.to_datetime("2024-01-01"))
    with col3:
        fecha_fin = st.date_input("Fecha de fin", pd.to_datetime("2024-12-31"))

    # Filtrar los datos por supermercado y por rango de fechas
    df_filtrado = filter_alimentacion_data(
        alimentacion_df=alimentacion_df,
        supermercado=supermercado_seleccionado,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    producto_mas_caro, producto_mas_barato = obtener_producto_mas_caro_y_mas_barato(
        df_filtrado
    )
    producto_mayor_aumento, producto_mayor_bajada = (
        obtener_producto_mayor_aumento_y_bajada(df_filtrado)
    )
    top_variacion = obtener_productos_con_mas_variacion(df_filtrado)
    productos_mas_baratos = comparar_precios_entre_supermercados(alimentacion_df)

    # Métricas con tarjetas (Cards) explicadas
    st.markdown("")
    st.markdown("")
    st.subheader(" 🏷️ Productos clave para el supermercado seleccionado", divider="blue")
    st.caption(
        "Estas métricas muestran información sobre los productos más caros, baratos y aquellos que han cambiado más de precio en el supermercado seleccionado."
    )
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        with st.container(border=True):
            st.metric(
                label="Producto más caro",
                value=f"{producto_mas_caro['producto']}",
                delta=f"{producto_mas_caro['precio_referencia']:.2f}€",
                help=f"Este es el producto más caro en {supermercado_seleccionado} durante el periodo seleccionado.",
            )

    with col2:
        with st.container(border=True):
            st.metric(
                label="Producto más barato",
                value=f"{producto_mas_barato['producto']}",
                delta=f"{producto_mas_barato['precio_referencia']:.2f}€",
                help=f"Este es el producto más barato en {supermercado_seleccionado} en el mismo periodo.",
            )

    with col3:
        with st.container(border=True):
            st.metric(
                label="Mayor aumento de precio",
                value=f"{producto_mayor_aumento['producto']}",
                delta=f"{producto_mayor_aumento['diferencia']:.2f}€",
                help="Este producto ha tenido el mayor aumento en su precio durante el periodo seleccionado.",
            )
    with col4:
        with st.container(border=True):
            st.metric(
                label="Mayor bajada de precio",
                value=f"{producto_mayor_bajada['producto']}",
                delta=f"{producto_mayor_bajada['diferencia']:.2f}€",
                help="Este producto ha tenido el mayor bajada en su precio durante el periodo seleccionado.",
            )

    # Gráfico interactivo con Plotly: evolución de precios en el tiempo
    st.markdown("")
    st.markdown("")
    st.subheader(
        "📈 Evolución de precios de productos en el supermercado", divider="blue"
    )
    fig = px.line(
        df_filtrado,
        x="fecha",
        y="precio_referencia",
        color="producto",
        title="Evolución de precios por producto",
        labels={"precio_referencia": "Precio (€)"},
    )
    st.plotly_chart(fig, use_container_width=True)

    # Gráfico de barras para los 5 productos que más han subido y bajado
    st.subheader(
        " 📊 Productos que más han subido y bajado en la última semana", divider="blue"
    )
    fig_variacion = px.bar(
        top_variacion,
        x="producto",
        y="variacion",
        color="variacion",
        title="Top 5 productos que más han subido y bajado en la última semana",
        labels={"variacion": "Cambio porcentual (%)", "producto": "Producto"},
        color_continuous_scale="agsunset",
    )
    fig_variacion.update_layout(
        barmode="group", yaxis_title="Cambio porcentual (%)", xaxis_title="Producto"
    )
    st.plotly_chart(fig_variacion, use_container_width=True)

    st.markdown("")
    # Comparación de productos más baratos entre supermercados
    st.subheader(
        " 🛒 Comparación de productos más baratos entre supermercados", divider="blue"
    )
    # Graficar comparativa de precios más baratos entre supermercados
    fig_bar = px.bar(
        productos_mas_baratos,
        x="producto",
        y="precio_referencia",
        color="fuente",
        title="Comparativa de productos más baratos entre supermercados",
        labels={"precio_referencia": "Precio (€)", "producto": "Producto"},
        barmode="group",
    )
    fig_bar.update_layout(xaxis_title="Producto", yaxis_title="Precio (€)")
    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(fig_bar, use_container_width=True)

    # Pie chart con hueco en el centro y con valores
    fig_pie = px.pie(
        productos_mas_baratos,
        values="precio_referencia",
        names="fuente",
        title="Distribución de productos más baratos por supermercado",
        hole=0.4,
    )
    fig_pie.update_traces(textinfo="percent+label")
    with col2:
        st.plotly_chart(fig_pie, use_container_width=True)

elif menu == "Precios de Vivienda":
    st.title("🏡 Análisis de Precios de Vivienda por Provincias")
    st.divider()

    # Filters
    col1, col2, col3 = st.columns([1, 2, 2])
    with col1:
        producto_tipo = st.radio(
            "Selecciona si es venta o alquiler", ["Venta", "Alquiler"]
        )
    with col2:
        fecha_inicio = st.date_input("Fecha de inicio", pd.to_datetime("2024-01-01"))
    with col3:
        fecha_fin = st.date_input("Fecha de fin", pd.to_datetime("2024-12-31"))

    df_vivienda_filtrado = vivienda_df[
        (vivienda_df["producto"] == producto_tipo)
        & (vivienda_df["fecha"] >= pd.to_datetime(fecha_inicio))
        & (vivienda_df["fecha"] <= pd.to_datetime(fecha_fin))
    ]

    # Compute metrics

    provincia_mayor_aumento, provincia_mayor_bajada = (
        obtener_provincia_mayor_aumento_y_bajada(df_vivienda_filtrado)
    )
    provincia_mas_cara, provincia_mas_barata = obtener_provincia_mas_cara_y_mas_barata(
        df_vivienda_filtrado
    )
    top_variacion_provincias = obtener_provincias_con_mas_variacion(
        df_vivienda_filtrado
    )

    # Display metrics and explanation
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        with st.container(border=True):
            st.metric(
                label="Provincia más cara",
                value=f"{provincia_mas_cara['provincia']}",
                delta=f"{provincia_mas_cara['precio']:.2f}€",
                help=f"Esta es la provincia más cara para {producto_tipo} en el periodo seleccionado.",
            )

    with col2:
        with st.container(border=True):
            st.metric(
                label="Provincia más barata",
                value=f"{provincia_mas_barata['provincia']}",
                delta=f"{provincia_mas_barata['precio']:.2f}€",
                help=f"Esta es la provincia más barata para {producto_tipo} en el mismo periodo.",
            )
    with col3:
        with st.container(border=True):
            st.metric(
                label="Mayor aumento de precio",
                value=f"{provincia_mayor_aumento['provincia']}",
                delta=f"{provincia_mayor_aumento['variacion']:.2f}€",
                help="Esta provincia ha tenido el mayor aumento de precios.",
            )

    with col4:
        with st.container(border=True):
            st.metric(
                label="Mayor bajada de precio",
                value=f"{provincia_mayor_bajada['provincia']}",
                delta=f"{provincia_mayor_bajada['variacion']:.2f}€",
                help="Esta provincia ha tenido la mayor bajada de precios.",
            )

    # Map and bar chart visualizations
    display_visualizations(df_vivienda_filtrado, top_variacion_provincias)
