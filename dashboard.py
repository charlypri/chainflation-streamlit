import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt

import pymongo
from datetime import datetime, time

# Import for navbar
from streamlit_option_menu import option_menu
from functions import *

st.set_page_config(layout="wide")
st.title("Chainflation Data Sources")


@st.cache(hash_funcs={"pymongo.mongo_client.MongoClient": id}) 
def loadData():

    # get product prices
    prod_prices  = getProductPrices()

    # Get inflation per product

    prod_infl = getProductInflation(prod_prices, 30) 

    # Get inflation per category 
    category_infl = getCategoriesInflation(prod_infl)


    # Get total inflation
    total = getTotalInflation(category_infl)

    return prod_prices, prod_infl, category_infl, total

def plot_priceTime(prod_params):

    fig = px.line(prod_prices[prod_prices['producto'].isin(prod_params)], x="fecha", y="precio", color='producto')
    fig.update_layout(
        title=f"Precios diarios",
        xaxis_title="Fecha",
        yaxis_title="Precio",
    )
    return fig

def plot_prod_infTime(prod_params):

    fig = px.line(prod_infl[prod_infl['producto'].isin(prod_params)], x="fecha", y="inflation", color='producto')
    fig.update_layout(
        title=f"Inflación por productos",
        xaxis_title="Fecha",
        yaxis_title="Precio",
    )
    return fig


with st.sidebar:
    selected = option_menu(
        "",
        ["Inflation", 'Sectores'],
        # icons=["bi-joystick"],
        menu_icon="",
        default_index=0,
    )

# Load data into the dataframe.
data = loadData()
prods_prices, prods_infl, categories_infl, total = loadData()

if selected == "Sectores":
    # PARAMETROS

    col1, col2 = st.columns(2)
    with col1:
        param_cesta = st.selectbox(
            "Select the sector", ['alimentacion', 'energia', 'vivienda']
        )

    prod_prices = prods_prices[param_cesta]
    prod_infl = prods_infl[param_cesta]
    category_infl = categories_infl[param_cesta]

    product_names = prod_prices['producto'].unique()
    

    with col2:
        param_prod = st.multiselect(
            "Select the products", 
            product_names,
            product_names[0]
        )

    st.subheader(f"Histórico de precios del sector: {param_cesta}")

    
    fig = plot_priceTime(param_prod)
    st.plotly_chart(fig)



    st.subheader(
        f"Inflación del sector: {param_cesta}"
    )
    fig = plot_prod_infTime(param_prod)
    st.plotly_chart(fig)


    st.subheader("MAIN TABLE")
    st.dataframe(prod_infl[prod_infl['producto'].isin(param_prod)], width=1400, height=500)


if selected == "Inflation":
    # PARAMETROS

    

    st.subheader(f"Histórico de inflación")

    fig = px.line(total, x="fecha", y="inflation", color='category')
    fig.update_layout(
        title=f"Inflación por productos",
        xaxis_title="Fecha",
        yaxis_title="Precio",
    )
    st.plotly_chart(fig)
