import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt

import pymongo
import sys
from datetime import datetime, time, timedelta
import time as t
from statistics import mean
import os

pd.set_option("display.max_columns", None)

DATABASE = "chainflation"


def getAlimentacionJson():
    myclient = pymongo.MongoClient(os.environ['chainflation_mongo'])
    mydb = myclient[DATABASE]

    alim_collect = mydb["alimentacion"]
    cursor  = alim_collect.find({},{"_id":0}).sort("fecha", 1)
    records = list(cursor)
    
    return records

def getViviendaJson():
    myclient = pymongo.MongoClient(os.environ['chainflation_mongo'])
    mydb = myclient[DATABASE]

    alim_collect = mydb["vivienda"]
    cursor  = alim_collect.find({},{"_id":0}).sort("fecha", 1)
    records = list(cursor)
    
    return records

def getEnergiaJson():
    myclient = pymongo.MongoClient(os.environ['chainflation_mongo'])
    mydb = myclient[DATABASE]
    
    alim_collect = mydb["energia"]
    cursor  = alim_collect.find({},{"_id":0}).sort("fecha", 1)
    records = list(cursor)
    
    return records




def calcInflationProds(sector_df, ago):
    sector_df.fecha = sector_df.fecha.apply(lambda x: datetime(x.year, x.month, x.day)) # Keep only Year,Month,Day

    total_days = len(sector_df.fecha.unique())
    
    record_date = sector_df.fecha.max() #last day recorded
    ref_date =(record_date- timedelta(days=ago)) # Day to compare with
    inflations_products = pd.DataFrame()
    while total_days > 0:
        
        start_prices = sector_df[sector_df['fecha'] == record_date].sort_values(by=['producto'])
        end_prices = sector_df[sector_df['fecha'] == ref_date].sort_values(by=['producto'])

        if len(start_prices) == 0:
            record_date =(record_date - timedelta(days=1))
            continue
        elif len(end_prices) == 0:
            ref_date =(ref_date - timedelta(days=1))
            total_days -= 1
            continue
        start_prices['inflation'] = ((start_prices.loc[:,'precio'].values - end_prices.loc[:,'precio'].values )/end_prices.loc[:,'precio'].values)*100
        inflations_products = pd.concat([inflations_products, start_prices], ignore_index=True)
        
        # print(f'Stored inflation for: {record_date}')
        # print(f'Reference date : {ref_date}')
        # print(f"Prices of record: { start_prices.loc[:,'precio'].values }")
        # print(f"Prices of reference: { end_prices.loc[:,'precio'].values } \n")
        
        record_date = (record_date - timedelta(days=1))
        ref_date =(record_date - timedelta(days=ago))
        total_days -= 1

    return inflations_products



def calcCategoriesInflation(inflations_product, sector):
    categ_inflations = []
    for date in inflations_product.fecha.unique():
        daily_inflations = inflations_product[inflations_product['fecha'] == date]['inflation'].values

        pesos = {
            'alimentacion': [   0.1428, # Aceite
                0.1428, # arroz
                0.1428, # leche
                0.1428, # pollo
                0.1428, # fruta
                0.1428, # cerveza
                0.1428 # azucar
            ],
            'energia': [   
                0.1, # Sin Plomo 95
                0.1, # Sin Plomo 98
                0.1, # Gasóleo A
                0.1, # Gasóleo A+
                0.1, # Gasóleo B
                0.1, # Gasóleo C
                0.1, # Biodiésel
                0.1, # Autogas/GLP
                0.1, # GNC
                0.1 # Luz
            ],
            'vivienda': [
                0.5, # Venta
                0.5 # Alquiler
            ],
        }
        inflationCategory_pct = []
        for num1, num2 in zip(daily_inflations, pesos[sector]):
            inflationCategory_pct.append(num1 * num2)
        inflationCategory= sum(inflationCategory_pct)

        categ_inflations.append({'fecha':date, 'inflation':inflationCategory , 'category': sector})
    
    categ_inflations = pd.DataFrame.from_records(categ_inflations)

    return categ_inflations


def calcTotalInflation(inflations_categ):
    total_inflations = []
    for date in inflations_categ.fecha.unique():
        daily_inflations = inflations_categ[inflations_categ['fecha'] == date]['inflation'].values

        pesos = [
            0.33, # Alimentacion
            0.33, # Energia
            0.33  # Vivienda
        ]
        inflationCategory_pct = []
        for num1, num2 in zip(daily_inflations, pesos):
            inflationCategory_pct.append(num1 * num2)
        inflationCategory= sum(inflationCategory_pct)
        total_inflations.append({'fecha':date, 'inflation':inflationCategory , 'category': 'total'})
    
    total_inflations = pd.DataFrame.from_records(total_inflations)

    return total_inflations

def getProductPrices():
    prod_prices = {}

    prod_prices['energia'] = pd.json_normalize(getEnergiaJson())
    prod_prices['vivienda'] = pd.json_normalize(getViviendaJson())
    prod_prices['alimentacion'] = pd.json_normalize(getAlimentacionJson())

    prod_prices['energia'].rename(columns = {'combustible':'producto'}, inplace = True)
    prod_prices['vivienda'].rename(columns = {'tipo':'producto'}, inplace = True)

    return prod_prices

def getProductInflation(sector_df, ago):
    prod_infl = {}

    prod_infl['energia'] = calcInflationProds(sector_df['energia'], ago)
    prod_infl['vivienda'] = calcInflationProds(sector_df['vivienda'], ago)
    prod_infl['alimentacion'] = calcInflationProds(sector_df['alimentacion'], ago)

    return prod_infl

def getCategoriesInflation(sector_df):
    category_infl = {}

    category_infl['energia'] = calcCategoriesInflation(sector_df['energia'], 'energia')
    category_infl['vivienda'] = calcCategoriesInflation(sector_df['vivienda'], 'vivienda')
    category_infl['alimentacion'] = calcCategoriesInflation(sector_df['alimentacion'], 'alimentacion')

    return category_infl

def getTotalInflation(categs_df):
    categories_month_infl = pd.concat([categs_df['energia'], categs_df['vivienda'], categs_df['alimentacion']])
    categories_month_infl = pd.concat([categories_month_infl, calcTotalInflation(categories_month_infl)])
    return categories_month_infl


# # get product prices
# prod_prices  = getProductPrices()

# # Get inflation per product

# prod_infl = getProductInflation(prod_prices, 30) 

# # Get inflation per category 
# category_infl = getCategoriesInflation(prod_infl)


# # Get total inflation
# total = getTotalInflation(category_infl)