import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
import plotly.graph_objects as go

import pymongo
from datetime import datetime, time, date,  timedelta

# Import for navbar
from streamlit_option_menu import option_menu
from functions import *


############ THIS DASHBOARD IS THE OLD VERSION. IT IS STILL HERE BECASUE THE FUNCTIONALITIES TO SHOW THE PRICES WITHOUT AGGREGATING IT BY MONTHS SHOULD BE KEPT, AND ALSO SHOWING MoM INFLATION   ################
st.set_page_config(page_title="Chainflation - Dashboard",layout="wide")
st.title("Chainflation Data Sources")

@st.cache_resource
def get_mongo_client():
    mongo_client = pymongo.MongoClient(st.secrets["DB_SECRET"])
    return mongo_client

@st.cache_data 
def loadData():
    mongo_client = get_mongo_client() 
    # get product prices
    prod_prices  = getProductPrices(mongo_client)

    # Get inflation per product
    prod_infl = getProductInflation(prod_prices, 30) 

    # # Get inflation per category 
    category_infl = getCategoriesInflation(prod_infl)


    # # Get total inflation
    total = getTotalInflation(category_infl)

    return prod_prices, prod_infl, category_infl, total

def plot_priceTime(prod_params):

    
    fig = px.line(prod_prices[(prod_prices['fuente'] == prod_params)], x="fecha", y="precio", color= "producto")
    fig.update_layout(
        title=f"Precios {prod_params}",
        xaxis_title="Fecha",
        yaxis_title="Precio",
    )
    return fig

def plot_prod_comTime(prod_params):

    fig = px.line(prod_prices[(prod_prices['producto'] == prod_params)], x="fecha", y="precio", color='fuente')
    fig.update_layout(
        title=f"Precio por supermercado",
        xaxis_title="Fecha",
        yaxis_title="Precio",
    )
    return fig

def filter_df_by_date(df, time_period):
    # Get current date and time
    now = datetime.now()

    if time_period == "Semana":
        # Get date for a week ago
        date_last_week = now - timedelta(days=7)
        # Filter values for the last week
        filtered_df = df[df["fecha"] >= date_last_week]
        
    elif time_period == "Mes":
        # Get date for a month ago
        date_last_month = now - timedelta(days=30)
        # Filter values for the last month
        filtered_df = df[df["fecha"] >= date_last_month]
    
    elif time_period == "Trimestre":
        # Get date for a year ago
        date_last_year = now - timedelta(days=90)
        # Filter values for the last year
        filtered_df = df[df["fecha"] >= date_last_year]
        
    elif time_period == "Año":
        # Get date for a year ago
        date_last_year = now - timedelta(days=365)
        # Filter values for the last year
        filtered_df = df[df["fecha"] >= date_last_year]
        
    else:
        raise ValueError("Invalid time_period argument. Possible values: 'last_week', 'last_month', 'last_year'.")
        
    return filtered_df


with st.sidebar:
    selected = option_menu(
        "",
        ["Inflación", 'Sectores'],
        icons=["","bi-joystick"],
        menu_icon="",
        default_index=0,
    )

# Load data into the dataframe.
prods_prices, prods_infl, categories_infl, total = loadData()

if selected == "Sectores":

    # SECCION DE PRECIOS SEGUN SECTOR Y SOURCES
    # PARAMETROS
    st.subheader(f"Histórico de precios por sector:")
    col1, col2, col3, = st.columns(3)
    with col1:
        param_cesta = st.selectbox(
            "Selecciona el sector", ['alimentacion', 'energia', 'vivienda']
        )

    prod_prices = prods_prices[param_cesta]
    prod_infl = prods_infl[param_cesta]
    category_infl = categories_infl[param_cesta]

    sources_names = prod_prices['fuente'].unique()
    product_names = prod_prices['producto'].unique()
    

    with col2:
        param_prod = st.selectbox(
            "Selecciona la fuente", 
            sources_names
        )
    
    with col3:
        periodo = st.selectbox(
            "Selecciona el periodo", 
            ["Año", "Trimestre"]
        )
    
    
    prod_prices = filter_df_by_date(prod_prices, periodo)
    
    fig = plot_priceTime(param_prod)
    st.plotly_chart(fig, use_container_width=True)

    if param_cesta == "alimentacion":
        st.subheader(
            f"Compara precios entre supermercados:"
        )
        param_prod = st.selectbox(
            "Selecciona el producto a comparar", 
            product_names
        )
        fig = plot_prod_comTime(param_prod)
        st.plotly_chart(fig, use_container_width=True)



if selected == "Inflación":
    # PARAMETROS

    st.subheader(f"Histórico de inflación")

    fig = go.Figure()

    for category in total['category'].unique():
        category_data = total[total['category'] == category]
        fig.add_trace(go.Scatter(x=category_data['fecha'], y=category_data['inflation'], 
                                mode='lines+markers', name=category))

    fig.update_layout(
        title=f"Inflación por productos",
        xaxis_title="Fecha",
        yaxis_title="Precio",
    )
    st.plotly_chart(fig, use_container_width=True)