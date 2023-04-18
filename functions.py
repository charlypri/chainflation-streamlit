import pandas as pd
import plotly.express as px
import matplotlib.pyplot as plt

import pymongo
from datetime import datetime, time, timedelta
from statistics import mean
import os

pd.set_option("display.max_columns", None)

DATABASE = "chainflation"
year_date = datetime.now() - timedelta(days=365)

def getAlimentacionJson(secret):
    myclient = pymongo.MongoClient(secret)
    mydb = myclient[DATABASE]

    alim_collect = mydb["alimentacion"]
    cursor  = alim_collect.find({"fecha": {"$gte": year_date}},{"_id":0, 'fecha': 1, 'producto': 1, 'precio_referencia': 1, 'tienda': 1}).sort("fecha", 1)
    records = list(cursor)
    
    return records

def getViviendaJson(secret):
    myclient = pymongo.MongoClient(secret)
    mydb = myclient[DATABASE]

    alim_collect = mydb["vivienda"]
    cursor  = alim_collect.find({"fecha": {"$gte": year_date}},{"_id":0, 'fecha': 1, 'tipo': 1, 'provincia':1, 'precio': 1, 'fuente': 1}).sort("fecha", 1)
    records = list(cursor)
    
    return records

def getEnergiaJson(secret):
    myclient = pymongo.MongoClient(secret)
    mydb = myclient[DATABASE]
    
    alim_collect = mydb["energia"]
    cursor  = alim_collect.find({"fecha": {"$gte": year_date}},{"_id":0, 'fecha': 1, 'combustible': 1,  'precio': 1, 'fuente': 1}).sort("fecha", 1)
    records = list(cursor)
    
    return records

def calcInflationFuentes(sector_df, ago):
    sector_df.fecha = sector_df.fecha.apply(lambda x: datetime(x.year, x.month, x.day)) # Keep only Year,Month,Day

    total_days = len(sector_df.fecha.unique())
    
    record_date = sector_df.fecha.max() #last day recorded
    ref_date =(record_date - timedelta(days=ago)) # Day to compare with
    inflations_products = pd.DataFrame()
    while total_days > 0:
        
        end_prices = sector_df[sector_df['fecha'] == record_date].groupby(["producto","fuente", "fecha"]).mean(numeric_only=True).sort_values(by=['producto']).reset_index()
        start_prices = sector_df[sector_df['fecha'] == ref_date].groupby(["producto","fuente", "fecha"]).mean(numeric_only=True).sort_values(by=['producto']).reset_index()

        if len(end_prices) == 0:
            record_date =(record_date - timedelta(days=1))
            continue
        elif len(start_prices) == 0:
            ref_date =(ref_date - timedelta(days=1))
            total_days -= 1
            continue
        prices = pd.merge(start_prices, end_prices, on=['producto', "fuente"], how='inner', suffixes=('_ref', ''))
        prices["inflation"] = ((prices["precio"] - prices["precio_ref"]) / prices["precio_ref"]) *100
        inflations_products = pd.concat([inflations_products, prices], ignore_index=True)
        
        record_date = (record_date - timedelta(days=1))
        ref_date =(record_date - timedelta(days=ago))
        total_days -= 1

    inflations_products.drop(["precio_ref","fecha_ref"], axis=1, inplace=True)
    return inflations_products


def calcInflationProds(sector_df, ago):
    sector_df.fecha = sector_df.fecha.apply(lambda x: datetime(x.year, x.month, x.day)).copy() # Keep only Year,Month,Day
    
    record_date = sector_df.fecha.max() #last day recorded
    ref_date =(record_date - timedelta(days=ago)) # Day to compare with
    inflations_products = pd.DataFrame()
    while (ref_date >= sector_df.fecha.min()):

        record_prices = sector_df[sector_df['fecha'] == record_date].groupby(["producto", "fecha"]).mean(numeric_only=True).sort_values(by=['producto']).reset_index()
        ref_prices = sector_df[sector_df['fecha'] == ref_date].groupby(["producto", "fecha"]).mean(numeric_only=True).sort_values(by=['producto']).reset_index()

        if len(record_prices) == 0:
            record_date =(record_date - timedelta(days=1))
            ref_date =(record_date - timedelta(days=ago))
            continue
        elif len(ref_prices) == 0:
            ref_date =(ref_date - timedelta(days=1)) 
            continue

        prices = pd.merge(ref_prices, record_prices, on='producto', how='inner', suffixes=('_ref', ''))
        prices["inflation"] = ((prices["precio"] - prices["precio_ref"]) / prices["precio_ref"]) *100
        inflations_products = pd.concat([inflations_products, prices], ignore_index=True)
        
        record_date = (record_date - timedelta(days=1))
        ref_date =(record_date - timedelta(days=ago))

    return inflations_products



def calcCategoriesInflation(inflations_product, sector):
    categ_inflations = []
    for date in inflations_product.fecha.unique():
        daily_inflations = inflations_product[inflations_product['fecha'] == date]['inflation'].values

        pesos = {
            'alimentacion': [   0.05882, # Aceite
                0.05882, # mantequilla
                0.05882, # arroz
                0.05882, # maiz
                0.05882, # garbanzos
                0.05882, # alubias
                0.05882, # patata
                0.05882, # azucar
                0.05882, # pescado
                0.05882, # huevos
                0.05882, # pollo
                0.05882, # leche
                0.05882, # agua
                0.05882, # cafe
                0.05882, # cerveza
                0.05882, # platano
                0.05882, # manzana
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
            0.36, # Alimentacion
            0.23, # Energia
            0.31  # Vivienda
        ]
        inflationCategory_pct = []
        for num1, num2 in zip(daily_inflations, pesos):
            inflationCategory_pct.append(num1 * num2)
        inflationCategory= sum(inflationCategory_pct)
        total_inflations.append({'fecha':date, 'inflation':inflationCategory , 'category': 'total'})
    
    total_inflations = pd.DataFrame.from_records(total_inflations)

    return total_inflations

def getProductPrices(secret):
    prod_prices = {}

    prod_prices['energia'] = pd.json_normalize(getEnergiaJson(secret))
    prices_vivienda = pd.json_normalize(getViviendaJson(secret))
    prod_prices['vivienda'] = prices_vivienda.loc[~((prices_vivienda['fuente'] == 'idealista') & (prices_vivienda['provincia'] == 'Madrid'))].copy()
    prod_prices['alimentacion'] = pd.json_normalize(getAlimentacionJson(secret))
    prod_prices['alimentacion']["precio"] = prod_prices['alimentacion']["precio_referencia"] 

    prod_prices['energia'].rename(columns = {'combustible':'producto'}, inplace = True)
    prod_prices['vivienda'].rename(columns = {'tipo':'producto'}, inplace = True)
    prod_prices['alimentacion'].rename(columns = {'tienda':'fuente'}, inplace = True)

    return prod_prices

def getSourcesInflation(sector_df, ago):
    fuente_infl = {}

    fuente_infl['energia'] = calcInflationFuentes(sector_df['energia'], ago)
    fuente_infl['vivienda'] = calcInflationFuentes(sector_df['vivienda'], ago)
    fuente_infl['alimentacion'] = calcInflationFuentes(sector_df['alimentacion'], ago)

    return fuente_infl

def getProductInflation(sector_df, ago):
    prod_infl = {}

    # Normalizar precios de la luz a medias semanales
    sector_df['energia'] = normalize_luz(sector_df['energia'])
    sector_df['vivienda'] = preprocess_vivienda(sector_df['vivienda'])

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
    categories_month_infl.sort_values(by="fecha", inplace=True)
    return categories_month_infl


def normalize_luz(energy_prices):
    # Function that calculates the updates de electricity price with the mean pf the last 7 days
    luz_df = energy_prices[energy_prices['producto'] == 'Luz']
    rolling_mean = luz_df['precio'].rolling(window=7, min_periods=1).mean()

    # Update the 'precio' column in the original dataframe with the rolling mean values
    energy_prices.loc[energy_prices['producto'] == 'Luz', 'precio'] = rolling_mean

    return energy_prices

def preprocess_vivienda(vivienda_prices):
    vivienda_prices = vivienda_prices[vivienda_prices["provincia"] == 'España']
    return vivienda_prices

# # get product prices
# prod_prices  = getProductPrices()

# # Get inflation per product

# prod_infl = getProductInflation(prod_prices, 30) 

# # Get inflation per category 
# category_infl = getCategoriesInflation(prod_infl)


# # Get total inflation
# total = getTotalInflation(category_infl)